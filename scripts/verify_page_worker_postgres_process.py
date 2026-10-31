"""Real PostgreSQL-backed, two-OS-process recovery of a synthetic 200-page signed worker.

Runs only against the existing isolated GitHub Actions postgres fixture. Auth is
simulated via the *actual* authenticated SQL role/RPC; it is NOT live GoTrue.
No admin DSN or bearer is shipped in the application or public host.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import psycopg
from fastapi import HTTPException

from apps.api.dossier_journey import canonical
from apps.api.signed_page_jobs import SignedPageJobs
from apps.worker.signed_page_worker import SignedPageWorker
from scripts.generate_page_worker_bundle import write_bundle
from scripts.verify_page_worker_resume import CASE, JOB, SECRET, FileDossier
from scripts.verify_s2_002_database import _env, _run

EVIDENCE = Path("/tmp/caseproof-postgres-recovery")
ACTOR = "11111111-2222-4333-8444-555555555555"
OTHER = "22222222-3333-4444-8555-666666666666"
ORG = "33333333-4444-4555-8666-777777777777"
BEARER = "synthetic-role-bound-owner"
CRASH_AFTER = 120


def _rpc(*, actor: str, case: str, request: str | None, action: str,
         data: dict[str, Any] | None = None) -> dict[str, Any]:
    _env()  # refuse shared/external databases, even in subprocesses
    with psycopg.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("set local role authenticated")
            cur.execute("select set_config('request.jwt.claim.sub', %s, true)", (actor,))
            cur.execute("select set_config('request.jwt.claims', %s, true)",
                        (json.dumps({"role": "authenticated"}),))
            if request is None:
                cur.execute("select public.caseproof_dossier(%s::uuid, %s)", (case, action))
            else:
                cur.execute("select public.caseproof_page_job(%s::uuid,%s::uuid,%s,%s::jsonb)",
                            (case, request, action, json.dumps(data or {})))
            result = cur.fetchone()
            if result is None or not isinstance(result[0], dict):
                raise AssertionError("Unexpected PostgreSQL RPC response")
            return result[0]


class PgDossier(FileDossier):
    def rpc(self, bearer: str, case: str, action: str) -> dict[str, Any]:
        assert bearer == BEARER and action == "context"
        return _rpc(actor=ACTOR, case=case, request=None, action=action)


class PgJobs(SignedPageJobs):
    """The production SQL function, under the actual authenticated role.

    Unlike a mocked lease or a SQLite job table, each call runs a committed
    PostgreSQL transaction with its own DB connection, even across processes.
    """
    def __init__(self, directory: Path, *, crash_after: int = 0):
        super().__init__(PgDossier(directory), SECRET)  # type: ignore[arg-type]
        self.crash_after = crash_after
        self.writes = 0

    def call(self, bearer: str, case: str, request: str, action: str,
             data: dict[str, Any] | None = None) -> dict[str, Any]:
        if bearer != BEARER or case != CASE or request != JOB:
            raise HTTPException(403, "synthetic actor/case mismatch")
        if action not in {"enqueue", "status", "claim", "heartbeat", "put",
                          "page", "finish", "yield", "cancel"}:
            raise HTTPException(422, "invalid action")
        try:
            value = _rpc(actor=ACTOR, case=case, request=request, action=action, data=data)
        except psycopg.Error:
            # No SQL strings, subject values, tokens or pages are logged.
            raise HTTPException(409, "PostgreSQL authorization, lease or input rejection") from None
        if action == "put":
            self.writes += 1
            if self.crash_after and self.writes >= self.crash_after:
                os._exit(137)  # committed checkpoint, hard crash, never yield
        return value


def _setup(directory: Path) -> None:
    from scripts.generate_page_worker_bundle import PAGES_PER_PDF

    rows = write_bundle(directory)
    assert len(rows) == 4 and PAGES_PER_PDF == 50
    _env()
    _run(f"""
insert into auth.users(id,instance_id) values ('{ACTOR}','{ORG}'),('{OTHER}','{ORG}');
insert into caseproof.organizations(id,display_name) values ('{ORG}','Synthetic PostgreSQL recovery');
insert into caseproof.organization_members(org_id,user_id,actions) values
 ('{ORG}','{ACTOR}',array['case:read','evidence:read','review:request']),
 ('{ORG}','{OTHER}',array['case:read','evidence:read','review:request']);
insert into caseproof.cases(id,org_id,created_by_user,effective_policy_version)
 values ('{CASE}','{ORG}','{ACTOR}','postgres-recovery');
insert into caseproof._m1_matter_grants(org_id,case_id,user_id,role,permissions)
 values ('{ORG}','{CASE}','{ACTOR}','reviewer',array['case:read','evidence:read','review:request']);
""", _env())
    for row in rows:
        version, doc, data = row["version_id"], row["document_id"], row["data"]
        digest = hashlib.sha256(data).hexdigest()
        _run(f"""
insert into caseproof.documents(id,org_id,case_id,source_label)
 values ('{doc}','{ORG}','{CASE}','Synthetic page recovery');
insert into caseproof.document_versions(id,org_id,document_id,version_number,
 original_sha256_hex,byte_length,media_type,bundle_role)
 values ('{version}','{ORG}','{doc}',1,'{digest}',{len(data)},'application/pdf','exhibit');
""", _env())


def _worker(directory: Path, *, crash: bool) -> int:
    worker = SignedPageWorker(PgJobs(directory, crash_after=CRASH_AFTER if crash else 0))
    finished = worker.run(BEARER, CASE, JOB)
    print(json.dumps({"state": finished["state"], "stored": len(finished["results"])}))
    return 0


def _expect_rejected(jobs: PgJobs, action: str, data: dict[str, Any] | None = None) -> None:
    try:
        jobs.call(BEARER, CASE, JOB, action, data)
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError("PostgreSQL accepted a fenced operation")


def _orchestrate() -> int:
    _env()
    work = Path(tempfile.mkdtemp(prefix="caseproof-postgres-worker-"))
    directory = work / "bundle"
    _setup(directory)
    jobs = PgJobs(directory)
    queued = SignedPageWorker(jobs).enqueue(BEARER, CASE, JOB)
    pages = json.loads(queued["manifest"])["pages"]
    assert len(pages) == 200
    assert sum(page["needs_ocr"] for page in pages) == 100
    before = _rpc(actor=ACTOR, case=CASE, request=JOB, action="status")
    assert before["state"] == "queued"
    env = {**os.environ, "CASEPROOF_TEST_BACKEND": "postgres"}
    first = subprocess.Popen([sys.executable, "-m", "scripts.verify_page_worker_postgres_process", "worker", str(directory), "crash"], env=env)
    assert first.wait(timeout=1500) == 137, "Worker A must hard-crash after durable checkpoints"
    mid = jobs.call(BEARER, CASE, JOB, "status")
    stored = len(mid["results"])
    assert mid["state"] == "running" and CRASH_AFTER <= stored < 200, stored
    stale = _run(f"select lease_token::text from caseproof.page_jobs where case_id='{CASE}'", _env())
    assert stale
    _expect_rejected(jobs, "claim")  # PostgreSQL refuses concurrent lease owner

    # Advance *only the isolated test DB* expiry. The real PostgreSQL RPC
    # must issue a fresh fencing token and retain already committed pages.
    _run(f"update caseproof.page_jobs set lease_until=clock_timestamp()-interval '1 second' "
         f"where case_id='{CASE}' and request_id='{JOB}'", _env())
    claim = jobs.call(BEARER, CASE, JOB, "claim")
    assert claim["lease_token"] != stale and claim["claims"] == 2
    for operation, payload in [
        ("heartbeat", {"lease_token": stale}),
        ("yield", {"lease_token": stale}),
        ("finish", {"lease_token": stale}),
        ("put", {"lease_token": stale, "page_key": pages[0]["version_id"] + ":1",
                 "serialized": "{}", "artifact_hash": "0" * 64}),
    ]:
        _expect_rejected(jobs, operation, payload)
    # Hand off the fresh test lease so the resumed real process can claim it.
    jobs.call(BEARER, CASE, JOB, "yield", {"lease_token": claim["lease_token"]})
    second = subprocess.Popen([sys.executable, "-m", __name__, "worker", str(directory), "resume"], env=env)
    assert second.wait(timeout=1500) == 0, "Worker B failed to resume the PostgreSQL job"
    final = jobs.call(BEARER, CASE, JOB, "status")
    expected = {p["version_id"] + ":" + str(p["pdf_page"]): p for p in pages}
    assert final["state"] == "succeeded" and len(final["results"]) == 200
    assert len(expected) == 200
    assert {r["page_key"] for r in final["results"]} == set(expected)
    states: dict[str, int] = {}
    for result in final["results"]:
        item = jobs.read_page(BEARER, CASE, JOB, result["page_key"], job=final)
        page = expected[result["page_key"]]
        assert all(item[k] == page[k] for k in
                   ("document_id", "version_id", "original_sha256", "pdf_page", "needs_ocr"))
        assert item["semantic_support"] == "not_assessed"
        assert (item["state"] in ("ocr_candidate", "ocr_unavailable")) == page["needs_ocr"]
        states[item["state"]] = states.get(item["state"], 0) + 1
    assert states.get("text_extracted") == 100
    assert states.get("ocr_candidate", 0) + states.get("ocr_unavailable", 0) == 100
    count, audit, claims = _run(f"""select
 (select count(*) from caseproof.page_results where case_id='{CASE}')::text || ':' ||
 (select count(*) from caseproof.page_job_events where case_id='{CASE}' and operation='put')::text || ':' ||
 (select claims from caseproof.page_jobs where case_id='{CASE}')::text""", _env()).split(":")
    assert (int(count), int(audit), int(claims)) == (200, 200, 3)
    _expect_rejected(jobs, "claim")
    # Revoking matter permission denies even completed result reads.
    _run(f"update caseproof._m1_matter_grants set active=false where case_id='{CASE}' and user_id='{ACTOR}'", _env())
    _expect_rejected(jobs, "status")
    _expect_rejected(jobs, "page", {"page_key": next(iter(expected))})
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "postgres-recovery.json").write_text(json.dumps({
        "schema": "caseproof-postgres-process-recovery-v1",
        "pages": 200, "ocr_pages": 100, "verified_receipts": 200,
        "worker_a_pid": first.pid, "worker_b_pid": second.pid,
        "worker_a_durable_results": stored, "total_unique_db_rows": int(count),
        "audit_put_rows": int(audit), "lease_claims": int(claims),
        "states": states, "stale_owner_denied": True, "revoked_owner_denied": True,
        "signed_auth": False, "database": "ephemeral_postgresql_17",
        "verified_at_utc": datetime.now(UTC).isoformat(),
    }, indent=2, sort_keys=True))
    print("POSTGRES_200_PAGE_REAL_PROCESS_CRASH_RESUME_FENCING_RECEIPTS_REVOCATION_PASSED")
    return 0


def main() -> int:
    if len(sys.argv) == 4 and sys.argv[1] == "worker":
        return _worker(Path(sys.argv[2]), crash=sys.argv[3] == "crash")
    if len(sys.argv) != 1:
        raise SystemExit("unexpected arguments")
    return _orchestrate()


if __name__ == "__main__":
    raise SystemExit(main())
