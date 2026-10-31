"""Process-level crash/resume acceptance for the signed page worker.

Synthetic data only; no live Auth or database. A SQLite job store mirrors the SQL contract
(lease fencing, idempotent put, finish only when complete) so that two genuinely separate
OS processes share state. One worker is hard-killed after 120 stored pages; a second,
fresh process must resume without reprocessing any stored page.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from apps.api.signed_page_jobs import SignedPageJobs
from apps.worker.signed_page_worker import SignedPageWorker
from scripts.generate_page_worker_bundle import write_bundle

SECRET = 'synthetic-private-worker-receipt-key-0123456789'
BEARER = 'synthetic-bearer'
CASE = '11111111-1111-4111-8111-111111111111'
JOB = '22222222-2222-4222-8222-222222222222'
LEASE_SECONDS = float(os.environ.get('CASEPROOF_PAGE_JOB_LEASE_SECONDS', '30'))
CRASH_AFTER = int(os.environ.get('CASEPROOF_TEST_CRASH_AFTER', '120'))
EVIDENCE = Path(os.environ.get('CASEPROOF_PAGE_WORKER_EVIDENCE', '/tmp/caseproof-page-worker'))


class FileDossier:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    def rpc(self, bearer: str, case: str, action: str) -> dict[str, Any]:
        return {'bundle_signature': 'a' * 64}

    def sources(self, bearer: str, case: str, inspect_pdf: bool = True) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
        import hashlib
        rows, originals = [], {}
        for item in json.loads((self.directory / 'bundle.json').read_text()):
            raw = (self.directory / f"{item['version_id']}.pdf").read_bytes()
            rows.append({'document_id': item['document_id'], 'version_id': item['version_id'], 'role': 'exhibit',
                         'media_type': 'application/pdf', 'sha256': hashlib.sha256(raw).hexdigest(),
                         'byte_length': len(raw)})
            originals[item['version_id']] = raw
        return rows, originals


class SqliteJobs(SignedPageJobs):
    """Cross-process job store with the same state rules as the SQL function."""

    def __init__(self, path: str | Path, dossier: FileDossier, *, crash_after: int = 0):
        super().__init__(dossier, SECRET)  # type: ignore[arg-type]
        self.path = str(path)
        self.crash_after = crash_after

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=60, isolation_level=None)
        con.row_factory = sqlite3.Row
        return con

    def init_schema(self) -> None:
        con = self.connect()
        con.executescript("""
            create table job(k integer primary key check(k=1), manifest text, manifest_hash text,
              state text, lease text, lease_until real, claims integer);
            create table results(page_key text primary key, serialized text, artifact_hash text);
            create table puts(page_key text, pid integer, accepted integer);
        """)
        con.close()

    def call(self, bearer: str, case: str, request: str, action: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        if action not in {'enqueue', 'status', 'claim', 'heartbeat', 'put', 'page', 'finish', 'yield', 'cancel'}:
            raise ValueError('closed page job operation required')
        data = data or {}
        con = self.connect()
        try:
            con.execute('begin immediate')
            try:
                out = self.apply(con, request, action, data)
                con.execute('commit')
            except BaseException:
                con.execute('rollback')
                raise
            stored = con.execute('select count(*) from results').fetchone()[0]
        finally:
            con.close()
        if action == 'put' and self.crash_after and stored >= self.crash_after:
            os._exit(137)  # hard crash: no cleanup, lease not released
        return out

    def apply(self, con: sqlite3.Connection, request: str, action: str, data: dict[str, Any]) -> dict[str, Any]:
        now = time.time()
        job = con.execute('select * from job').fetchone()
        if action == 'enqueue':
            if job is None:
                con.execute("insert into job values(1,?,?,'queued',null,0,0)", (data['manifest'], data['manifest_hash']))
            elif job['manifest'] != data['manifest']:
                raise HTTPException(409, 'manifest replay conflict')
        elif job is None:
            raise HTTPException(404, 'unknown job')
        job = con.execute('select * from job').fetchone()

        def lease_ok() -> bool:
            return (job['state'] == 'running' and job['lease'] is not None
                    and job['lease'] == data.get('lease_token') and now < job['lease_until'])

        total = len(json.loads(job['manifest'])['pages'])
        if action == 'claim':
            if job['state'] not in ('queued', 'running') or (job['state'] == 'running' and job['lease_until'] > now):
                raise HTTPException(409, 'not claimable')
            con.execute("update job set state='running', lease=?, lease_until=?, claims=claims+1",
                        (os.urandom(8).hex(), now + LEASE_SECONDS))
        elif action in ('heartbeat', 'put', 'yield', 'finish'):
            if action == 'put':
                accepted = lease_ok()
                con.execute('insert into puts values(?,?,?)', (data['page_key'], os.getpid(), int(accepted)))
                if not accepted:
                    raise HTTPException(409, 'lease lost')
            elif not lease_ok():
                raise HTTPException(409, 'lease lost')
            if action == 'heartbeat':
                con.execute('update job set lease_until=?', (now + LEASE_SECONDS,))
            elif action == 'put':
                old = con.execute('select * from results where page_key=?', (data['page_key'],)).fetchone()
                if old is None:
                    con.execute('insert into results values(?,?,?)',
                                (data['page_key'], data['serialized'], data['artifact_hash']))
                elif (old['serialized'], old['artifact_hash']) != (data['serialized'], data['artifact_hash']):
                    raise HTTPException(409, 'replay conflict')
            elif action == 'yield':
                con.execute("update job set state='queued', lease=null")
            else:
                if con.execute('select count(*) from results').fetchone()[0] != total:
                    raise HTTPException(409, 'incomplete')
                con.execute("update job set state='succeeded', lease=null")
        elif action == 'cancel':
            con.execute("update job set state='cancelled', lease=null")
        if action == 'page':
            row = con.execute('select * from results where page_key=?', (data['page_key'],)).fetchone()
            if row is None:
                raise HTTPException(404, 'page unavailable')
            return {'serialized': row['serialized'], 'artifact_hash': row['artifact_hash']}
        job = con.execute('select * from job').fetchone()
        results = [{'page_key': r['page_key'], 'artifact_hash': r['artifact_hash']}
                   for r in con.execute('select page_key, artifact_hash from results order by page_key')]
        return {'request_id': request, 'actor_id': 'owner', 'org_id': 'org', 'state': job['state'],
                'manifest': job['manifest'], 'manifest_hash': job['manifest_hash'],
                'lease_token': job['lease'] if action == 'claim' else None,
                'lease_until': job['lease_until'], 'claims': job['claims'], 'results': results}


def spawn(db: Path, bundle: Path, *, crash: bool) -> subprocess.Popen[bytes]:
    env = {**os.environ, 'CASEPROOF_TEST_CRASH_AFTER': str(CRASH_AFTER if crash else 0),
           'CASEPROOF_PAGE_JOB_LEASE_SECONDS': str(LEASE_SECONDS)}
    return subprocess.Popen([sys.executable, '-m', 'scripts.verify_page_worker_resume', 'worker',
                             '--db', str(db), '--dir', str(bundle)], env=env)


def worker_main(db: str, directory: str) -> int:
    jobs = SqliteJobs(db, FileDossier(directory), crash_after=CRASH_AFTER)
    result = SignedPageWorker(jobs).run(BEARER, CASE, JOB)
    print(json.dumps({'state': result['state'], 'pages_checkpointed': len(result['results'])}))
    return 0



def verify_adversarial_lease_contract(bundle: Path, directory: Path) -> dict[str, bool]:
    """Exercise stale-owner fencing and replay semantics in a separate durable store."""
    import hashlib

    from apps.api.dossier_journey import canonical

    db = directory / 'adversarial.sqlite'
    jobs = SqliteJobs(db, FileDossier(bundle))
    jobs.init_schema()
    manifest, _ = SignedPageWorker(jobs).inputs(BEARER, CASE, JOB)
    serialized = canonical(manifest)
    jobs.call(BEARER, CASE, JOB, 'enqueue', {
        'manifest': serialized, 'manifest_hash': hashlib.sha256(serialized.encode()).hexdigest()
    })
    first = jobs.call(BEARER, CASE, JOB, 'claim')
    first_token = first['lease_token']
    try:
        jobs.call(BEARER, CASE, JOB, 'claim')
    except HTTPException as error:
        assert error.status_code == 409, 'active lease takeover must fail'
    else:
        raise AssertionError('active lease takeover was permitted')

    with jobs.connect() as con:
        con.execute('update job set lease_until=?', (time.time() - 1,))
    second = jobs.call(BEARER, CASE, JOB, 'claim')
    assert second['lease_token'] != first_token and second['claims'] == 2

    for action, data in (
        ('heartbeat', {'lease_token': first_token}),
        ('put', {'lease_token': first_token, 'page_key': 'stale:1',
                 'serialized': '{}', 'artifact_hash': '0' * 64}),
        ('yield', {'lease_token': first_token}),
        ('finish', {'lease_token': first_token}),
    ):
        try:
            jobs.call(BEARER, CASE, JOB, action, data)
        except HTTPException as error:
            assert error.status_code == 409, (action, error.status_code)
        else:
            raise AssertionError(f'stale lease permitted {action}')

    try:
        jobs.call(BEARER, CASE, JOB, 'finish', {'lease_token': second['lease_token']})
    except HTTPException as error:
        assert error.status_code == 409, 'incomplete finish must fail'
    else:
        raise AssertionError('incomplete job was finished')

    assert jobs.call(BEARER, CASE, JOB, 'status')['state'] == 'running'
    assert not jobs.call(BEARER, CASE, JOB, 'status')['results']
    return {
        'active_lease_takeover_denied': True,
        'expired_lease_takeover_succeeded': True,
        'stale_heartbeat_denied': True,
        'stale_put_denied': True,
        'stale_yield_denied': True,
        'stale_finish_denied': True,
        'incomplete_finish_denied': True,
    }


def orchestrate() -> int:
    work = Path(tempfile.mkdtemp(prefix='caseproof-page-worker-'))
    bundle, db = work / 'bundle', work / 'jobs.sqlite'
    write_bundle(bundle)
    jobs = SqliteJobs(db, FileDossier(bundle))
    jobs.init_schema()
    queued = SignedPageWorker(jobs).enqueue(BEARER, CASE, JOB)
    pages = json.loads(queued['manifest'])['pages']
    assert len(pages) == 200, f'expected 200 pages, got {len(pages)}'
    assert sum(1 for p in pages if p['needs_ocr']) == 100, 'expected 100 image-only pages'

    crashed = spawn(db, bundle, crash=True)
    assert crashed.wait(timeout=1500) == 137, 'first worker must die hard mid-job'
    mid = jobs.call(BEARER, CASE, JOB, 'status')
    stored = len(mid['results'])
    assert mid['state'] == 'running' and CRASH_AFTER <= stored < 200, (mid['state'], stored)
    if mid['lease_until'] > time.time():
        try:
            jobs.call(BEARER, CASE, JOB, 'claim')
        except HTTPException as error:
            assert error.status_code == 409
        else:
            raise AssertionError('an unexpired lease must block takeover')
    time.sleep(max(0.0, mid['lease_until'] - time.time()) + 1.0)

    resumed = spawn(db, bundle, crash=False)
    assert resumed.wait(timeout=1500) == 0, 'fresh worker must finish the job'
    final = jobs.call(BEARER, CASE, JOB, 'status')
    assert final['state'] == 'succeeded' and len(final['results']) == 200
    states: dict[str, int] = {}
    expected_pages = {p['version_id'] + ':' + str(p['pdf_page']): p for p in pages}
    assert len(expected_pages) == 200, 'duplicate manifest page identity'
    assert {r['page_key'] for r in final['results']} == set(expected_pages), 'missing or unexpected page'
    for item in final['results']:
        artifact = jobs.read_page(BEARER, CASE, JOB, item['page_key'], job=final)
        expected = expected_pages[item['page_key']]
        assert all(artifact[k] == expected[k] for k in ('document_id', 'version_id', 'original_sha256', 'pdf_page', 'needs_ocr'))
        assert (artifact['state'] in ('ocr_candidate', 'ocr_unavailable')) == expected['needs_ocr'], 'OCR path mismatch'
        states[artifact['state']] = states.get(artifact['state'], 0) + 1
        assert artifact['semantic_support'] == 'not_assessed'
    con = jobs.connect()
    accepted = con.execute('select page_key, pid from puts where accepted=1').fetchall()
    attempts = con.execute('select page_key, count(distinct pid) n from puts group by page_key').fetchall()
    claims = con.execute('select claims from job').fetchone()[0]
    con.close()
    assert len(accepted) == 200 and len({r['page_key'] for r in accepted}) == 200, 'each page stored exactly once'
    assert all(r['n'] == 1 for r in attempts), 'a page was written by both the crashed and the resumed worker'
    by_pid: dict[int, int] = {}
    for r in accepted:
        by_pid[r['pid']] = by_pid.get(r['pid'], 0) + 1
    assert set(by_pid) == {crashed.pid, resumed.pid} and by_pid[crashed.pid] >= CRASH_AFTER, by_pid
    assert states.get('text_extracted') == 100, states
    assert states.get('ocr_candidate', 0) + states.get('ocr_unavailable', 0) == 100, states
    assert claims == 2, claims
    adversarial = verify_adversarial_lease_contract(bundle, work)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / 'evidence.json').write_text(json.dumps({
        'pages': 200, 'text_pages': 100, 'image_only_pages': 100, 'artifact_states': states,
        'stored_by_crashed_worker': by_pid[crashed.pid], 'stored_by_resumed_worker': by_pid[resumed.pid],
        'claims': claims, 'lease_seconds': LEASE_SECONDS, 'crash_after_pages': CRASH_AFTER,
        'every_page_written_by_one_process_only': True, 'receipts_verified': 200, 'adversarial_lease_checks': adversarial}, indent=2, sort_keys=True))
    print('PAGE_WORKER_HARD_CRASH_RESUME_200_PAGES_RECEIPTS_AND_LEASE_FENCE_PASSED')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='mode')
    worker = sub.add_parser('worker')
    worker.add_argument('--db', required=True)
    worker.add_argument('--dir', required=True)
    args = parser.parse_args()
    return worker_main(args.db, args.dir) if args.mode == 'worker' else orchestrate()


if __name__ == '__main__':
    raise SystemExit(main())
