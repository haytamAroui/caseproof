"""Full migration + negative retention SQL tests, disposable PostgreSQL only."""
from __future__ import annotations

import threading
import time
from pathlib import Path
from uuid import uuid4

import psycopg

from scripts.verify_s2_002_database import SCHEMA_BOOTSTRAP, _env, _run

ROOT = Path(__file__).resolve().parents[1]


def main():
    env = _env()
    _run(SCHEMA_BOOTSTRAP + """
create role service_role nologin;
create schema extensions;
create extension pgcrypto with schema extensions;
alter table auth.users add column email_confirmed_at timestamptz;
create function auth.jwt() returns jsonb language sql stable as $$
 select coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb
$$;
create function auth.role() returns text language sql stable as $$
 select auth.jwt()->>'role'
$$;
grant usage on schema auth to anon,service_role;
grant execute on all functions in schema auth to anon,authenticated,service_role;
create schema supabase_migrations;
create table supabase_migrations.schema_migrations(version text primary key);
create schema storage;
create table storage.buckets(id text primary key,name text,public boolean,file_size_limit bigint,allowed_mime_types text[]);
create table storage.objects(bucket_id text,name text, primary key(bucket_id,name));
alter table storage.objects enable row level security;
grant usage on schema storage to authenticated;
grant select,insert on storage.objects to authenticated;
""", env)
    paths = sorted((ROOT / 'supabase/migrations').glob('*.sql'))
    delayed = next(p for p in paths if 'm05_ocr_sidecar_cleanup_fk' in p.name)
    retention = next(p for p in paths if 'matter_retention' in p.name)
    fence = next(p for p in paths if 'retention_storage_fence' in p.name)
    dossier = next(p for p in paths if 'complete_dossier_journey' in p.name)
    attestation = next(p for p in paths if 'regional_review_attestation' in p.name)
    revisions = next(p for p in paths if 'dossier_draft_revisions' in p.name)
    revision_indexes = next(p for p in paths if 'dossier_draft_revision_fk_indexes' in p.name)
    fixture_ownership = next(p for p in paths if 'f5_correction_fixture_ownership' in p.name)
    f6_release = next(p for p in paths if 'f6_reviewed_release_ledger' in p.name)
    for path in paths:
        if path in (delayed, retention, fence, dossier, attestation, revisions, revision_indexes, fixture_ownership, f6_release):
            continue
        _run(path.read_text(), env)
        _run(f"insert into supabase_migrations.schema_migrations values('{path.name.split('_')[0]}');", env)
    _run(delayed.read_text(), env)
    _run((ROOT / 'supabase/phase4_reviewed/caseproof_phase4_signed_reference_review.sql').read_text(), env)
    _run(retention.read_text(), env)
    _run(fence.read_text(), env)
    _run(dossier.read_text(), env)
    _run(attestation.read_text(), env)
    _run(revisions.read_text(), env)
    _run(revision_indexes.read_text(), env)
    _run(fixture_ownership.read_text(), env)
    # F6 depends on retention guards, reviewed snapshot RPC and draft revisions.
    _run(f6_release.read_text(), env)
    print('RETENTION_FULL_SCHEMA_INSTALLED', flush=True)
    owner, guest, org, case, other, doc, version = (str(uuid4()) for _ in range(7))
    _run(f"""
insert into auth.users(id,instance_id) values('{owner}','{org}'),('{guest}','{org}');
insert into caseproof.organizations(id,display_name) values('{org}','Synthetic');
insert into caseproof.organization_members(org_id,user_id,actions) values
 ('{org}','{owner}',array['case:read','evidence:read']),('{org}','{guest}',array['case:read','evidence:read']);
insert into caseproof.cases(id,org_id,created_by_user,effective_policy_version) values
 ('{case}','{org}','{owner}','retention-test'),('{other}','{org}','{owner}','retention-test');
insert into caseproof._m1_matter_grants(org_id,case_id,user_id,role,permissions) values
 ('{org}','{case}','{owner}','reviewer',array['case:read','evidence:read']),
 ('{org}','{other}','{owner}','reviewer',array['case:read','evidence:read']);
insert into caseproof.documents(id,org_id,case_id,source_label) values('{doc}','{org}','{case}','Synthetic');
insert into caseproof.document_versions(id,org_id,document_id,version_number,original_sha256_hex,byte_length,media_type)
 values('{version}','{org}','{doc}',1,repeat('a',64),10,'application/pdf');
insert into storage.objects values('caseproof-originals-dev','{org}/{case}/leftover');
""", env)

    def actor(user, sql):
        return f"begin; set local role authenticated; set local request.jwt.claim.sub='{user}'; set local request.jwt.claims='{{\"role\":\"authenticated\"}}'; {sql}; commit;"

    # F6 release grants are independent of ordinary report/review access.
    export_call = f"select (public.caseproof_dossier_export_release('{case}','authorize')->>'authorized')"
    status_call = (
        f"select (public.caseproof_dossier_export_release('{case}','status',"
        f"'{uuid4()}')->>'state')"
    )
    _run(actor(owner, export_call), env, should_pass=False)
    _run(actor(guest, export_call), env, should_pass=False)
    _run(f"""
update caseproof.organization_members set actions=array_append(actions,'export:request')
 where org_id='{org}' and user_id='{owner}';
update caseproof._m1_matter_grants set permissions=array_append(permissions,'export:request')
 where org_id='{org}' and case_id='{case}' and user_id='{owner}';
""", env)
    if _run(actor(owner, export_call), env) != "true":
        raise AssertionError('explicit signed export grant not recognized')
    if _run(actor(owner, status_call), env) != "absent":
        raise AssertionError('unknown release not reported as absent')
    _run(actor(guest, export_call), env, should_pass=False)
    _run(actor(owner,
               f"select public.caseproof_dossier_export_release('{other}','authorize')"),
         env, should_pass=False)
    _run(actor(owner, "select count(*) from caseproof.dossier_releases"),
         env, should_pass=False)
    _run(f"update caseproof._m1_matter_grants set active=false where org_id='{org}' and case_id='{case}' and user_id='{owner}'", env)
    _run(actor(owner, export_call), env, should_pass=False)
    _run(f"update caseproof._m1_matter_grants set active=true where org_id='{org}' and case_id='{case}' and user_id='{owner}'", env)
    release_id = str(uuid4())
    _run(f"""
insert into caseproof.dossier_releases(
 org_id,case_id,release_id,actor_id,brief_id,snapshot_hash,manifest,artifacts
) values (
 '{org}','{case}','{release_id}','{owner}','{version}',repeat('a',64),
 '{{"scope":"synthetic-retention-only"}}'::jsonb,
 '{{"json":"eA=="}}'::jsonb
);
""", env)
    if _run(f"select count(*) from caseproof.dossier_releases where release_id='{release_id}'", env) != "1":
        raise AssertionError('fixture release not persisted')
    # Fill the bounded per-matter release ledger using synthetic fixture rows.
    # A distinct signed release request must reject capacity before snapshot
    # parsing; a replay of an existing release remains a separate read action.
    _run(f"""
insert into caseproof.dossier_releases(
 org_id,case_id,release_id,actor_id,brief_id,snapshot_hash,manifest,artifacts
)
select '{org}','{case}',gen_random_uuid(),'{owner}','{version}',repeat('a',64),
 '{{"scope":"synthetic-retention-only"}}'::jsonb,
 '{{"json":"eA=="}}'::jsonb
from generate_series(1,49);
""", env)
    if _run(f"select count(*) from caseproof.dossier_releases where case_id='{case}'", env) != "50":
        raise AssertionError('release capacity fixture incomplete')
    new_release = str(uuid4())
    release_attempt = f"""
select public.caseproof_dossier_export_release(
  '{case}','release','{new_release}',
  jsonb_build_object(
    'manifest', jsonb_build_object(
      'schema','caseproof-reviewed-release-v1',
      'case_id','{case}', 'release_id','{new_release}',
      'snapshot_hash',repeat('a',64),
      'server_receipt',repeat('b',64),
      'manifest_sha256',repeat('c',64),
      'artifacts','{{}}'::jsonb
    ),
    'contents',jsonb_build_object('json','eA==','markdown','eA==','docx','eA=='),
    'human_decisions','[]'::jsonb
  )
);
"""
    try:
        _run(actor(owner, release_attempt), env)
    except AssertionError as error:
        if "release capacity reached" not in str(error):
            raise
    else:
        raise AssertionError('release capacity did not fail closed')
    print('F6_RELEASE_CAPACITY_DENIED_BEFORE_SNAPSHOT_PARSE_PASSED', flush=True)
    print('F6_SEPARATE_EXPORT_GRANT_RLS_REVOKE_AND_RELEASE_RETENTION_FIXTURE_PASSED', flush=True)
    service = "set request.jwt.claims='{\"role\":\"service_role\"}'; "
    soft = f"select public.caseproof_soft_delete_matter('{case}')"
    _run(actor(guest, soft), env, should_pass=False)
    # Two genuine DB connections: an upload already racing with uncommitted
    # deletion must wait on the case lock, then fail after deletion commits.
    with psycopg.connect() as deletion, psycopg.connect() as upload:
        deletion.execute("set local role authenticated")
        deletion.execute(f"set local request.jwt.claim.sub='{owner}'")
        deletion.execute("set local request.jwt.claims='{\"role\":\"authenticated\"}'")
        deletion.execute("select public.caseproof_soft_delete_matter(%s)", (case,))
        pid = upload.info.backend_pid
        outcome = []

        def racing_upload():
            try:
                upload.execute("insert into storage.objects values('caseproof-originals-dev',%s)",
                               (f"{org}/{case}/racing-upload",))
                upload.commit()
                outcome.append('unexpected-success')
            except psycopg.errors.InsufficientPrivilege:
                upload.rollback()
                outcome.append('denied')

        worker = threading.Thread(target=racing_upload)
        worker.start()
        with psycopg.connect(autocommit=True) as observer:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                row = observer.execute("select wait_event_type from pg_stat_activity where pid=%s", (pid,)).fetchone()
                if row and row[0] == 'Lock':
                    break
                time.sleep(0.05)
            else:
                raise AssertionError('racing upload did not wait on deletion lock')
        deletion.commit()
        worker.join(timeout=5)
        if worker.is_alive() or outcome != ['denied']:
            raise AssertionError('racing upload was not denied after deletion committed')
    print('RETENTION_REAL_CONCURRENT_STORAGE_UPLOAD_DENIED', flush=True)
    _run(actor(owner, soft), env)  # idempotent creator retry
    if _run(actor(owner, f"select count(*) from caseproof.cases where id='{case}'"), env) != '0':
        raise AssertionError('deleted case visible')
    if _run(actor(owner, f"select count(*) from caseproof.documents where id='{doc}'"), env) != '0':
        raise AssertionError('deleted original metadata visible')
    _run(f"update caseproof._m1_matter_grants set active=true where case_id='{case}'", env, should_pass=False)
    _run(f"insert into caseproof.documents(org_id,case_id,source_label) values('{org}','{case}','late write')", env, should_pass=False)
    _run(f"insert into storage.objects values('caseproof-originals-dev','{org}/{case}/late-upload')", env, should_pass=False)
    finish = f"select public.caseproof_retention('finalize','{case}')"
    _run(actor(owner, finish), env, should_pass=False)
    _run(service + finish, env, should_pass=False)  # grace not elapsed
    _run(f"update caseproof.cases set deleted_at=now()-interval '31 days',legal_hold=true where id='{case}'", env)
    _run(service + finish, env, should_pass=False)
    _run(f"update caseproof.cases set legal_hold=false where id='{case}';", env)
    _run(service + f"select public.caseproof_retention('plan','{case}')", env)
    _run(f"update caseproof.cases set legal_hold=true where id='{case}'", env, should_pass=False)
    _run(service + finish, env, should_pass=False)  # files remain
    _run(f"delete from storage.objects where name='{org}/{case}/leftover'", env)
    _run(service + finish, env)
    _run(service + finish, env)  # completed retry
    if _run(f"select count(*) from caseproof.cases where id='{other}'", env) != '1':
        raise AssertionError('other matter deleted')
    if _run(f"select count(*) from caseproof.document_versions where id='{version}'", env) != '0':
        raise AssertionError('version remains')
    if _run(f"select count(*) from caseproof.dossier_releases where release_id='{release_id}'", env) != '0':
        raise AssertionError('release bytes remain after matter purge')
    if _run("select erased_audit_events from caseproof.erasure_receipts", env) != '1':
        raise AssertionError('minimal erasure audit missing')
    print('RETENTION_SQL_DENIAL_HOLD_STORAGE_RETRY_SCOPE_AND_RECEIPT_PASSED')


if __name__ == '__main__':
    main()
