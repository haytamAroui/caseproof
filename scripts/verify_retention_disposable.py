"""Full migration + negative retention SQL tests, disposable PostgreSQL only."""
from __future__ import annotations

import json
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
    f6_action_guard = next(p for p in paths if 'f6_reject_null_release_action' in p.name)
    rights = next(p for p in paths if 'caseproof_data_rights_ledger_shadow' in p.name)
    rights_fence = next(p for p in paths if 'caseproof_rights_grant_revocation_fence' in p.name)
    rights_enforce = next(p for p in paths if 'caseproof_rights_enforcement_gates' in p.name)
    for path in paths:
        if path in (delayed, retention, fence, dossier, attestation, revisions, revision_indexes, fixture_ownership, f6_release, f6_action_guard, rights, rights_fence, rights_enforce):
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
    _run(f6_action_guard.read_text(), env)
    # Ledger depends on F6's final typed action constraints and retention guard.
    _run(rights.read_text(), env)
    _run(rights_fence.read_text(), env)
    _run(rights_enforce.read_text(), env)
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

    # PR 1: signed rights RPC, legacy unknown, cross-matter, concurrency and purge.
    policy = json.dumps({
        "origin": "CLIENT_UPLOAD", "classification": "CLIENT_CONFIDENTIAL",
        "authorization_reference": "synthetic-contract-1",
        "process": True, "export": True,
    }, separators=(",", ":"))
    def rights_call(request, expected, *, document=doc, source=version):
        return (f"select (public.caseproof_rights_manage('{case}','{document}',"
                f"'{source}',{expected},'{request}','{policy}'::jsonb)"
                "->>'policy_version')")

    missing = (f"select (public.caseproof_rights_current('{case}',"
               f"'{doc}','{version}')->>'policy_status')")
    if _run(actor(owner, missing), env) != 'missing':
        raise AssertionError('legacy document must not inherit any rights approval')
    _run(actor(owner, rights_call(uuid4(), 0)), env, should_pass=False)
    _run(f"""
        update caseproof.organization_members
          set actions=array_append(actions,'rights:manage')
          where org_id='{org}' and user_id='{owner}';
        update caseproof._m1_matter_grants
          set permissions=array_append(permissions,'rights:manage')
          where org_id='{org}' and case_id='{case}' and user_id='{owner}';
    """, env)
    _run(actor(guest, rights_call(uuid4(), 0)), env, should_pass=False)
    _run(actor(owner, rights_call(uuid4(), 0, document=doc, source=uuid4())),
         env, should_pass=False)
    # PR2 owner switch defaults OFF: no existing workflow regresses.
    if _run("select enabled from caseproof._rights_enforcement_control", env) != 'f':
        raise AssertionError('rights enforcement must default to disabled')
    _run("update caseproof._rights_enforcement_control set enabled=true", env)
    source_gate = (f"select caseproof._rights_require_source('{org}','{case}',"
                   f"'{doc}','{version}',")
    _run(source_gate + "'process')", env, should_pass=False)
    _run("update caseproof._rights_enforcement_control set enabled=false", env)
    first_request = uuid4()
    if _run(actor(owner, rights_call(first_request, 0)), env) != '1':
        raise AssertionError('first rights policy version absent')
    if _run(actor(owner, rights_call(first_request, 0)), env) != '1':
        raise AssertionError('identical signed replay must be idempotent')
    _run(actor(owner, rights_call(first_request, 1)), env, should_pass=False)
    # The database boundary cannot be bypassed through service-only RPCs.
    _run("update caseproof._rights_enforcement_control set enabled=true", env)
    if _run(source_gate + "'process')", env) != '1':
        raise AssertionError('explicit process permission not accepted')
    if _run(source_gate + "'export')", env) != '1':
        raise AssertionError('same-matter export permission not accepted')
    _run(source_gate + "'indexForSearch')", env, should_pass=False)
    _run(source_gate + "'unrecognized_action')", env, should_pass=False)
    _run(f"select caseproof._rights_require_source('{org}','{other}',"
         f"'{doc}','{version}','export')", env, should_pass=False)
    source_payload = json.dumps({"sources": [{
        "document_id": doc, "version_id": version, "sha256": "a" * 64,
    }]}, separators=(",", ":"))
    _run(f"insert into caseproof.dossier_snapshots("
         f"org_id,case_id,snapshot_hash,bundle_signature,serialized)"
         f" values('{org}','{case}',repeat('f',64),'synthetic-rights',"
         f"'{source_payload}')", env)
    _run(f"insert into caseproof.dossier_snapshots("
         f"org_id,case_id,snapshot_hash,bundle_signature,serialized)"
         f" values('{org}','{other}',repeat('e',64),'synthetic-rights',"
         f"'{source_payload}')", env, should_pass=False)
    _run("update caseproof._rights_enforcement_control set enabled=false", env)
    print('RIGHTS_SQL_TRANSACTIONAL_OPT_IN_DENY_ALLOW_SCOPE_PASSED', flush=True)

    _run(actor(guest, missing), env, should_pass=False)
    if _run(actor(owner, missing), env) != 'present':
        raise AssertionError('signed policy projection absent after write')
    _run("update caseproof.source_rights_policies set process=false", env,
         should_pass=False)
    _run("delete from caseproof.source_rights_policies", env,
         should_pass=False)
    # A different matter in the same organization must not be able to
    # masquerade as this source, even when the user owns both matters.
    other_doc, other_version = str(uuid4()), str(uuid4())
    _run(f"""
        insert into caseproof.documents(id,org_id,case_id,source_label)
          values('{other_doc}','{org}','{other}','foreign synthetic');
        insert into caseproof.document_versions(
          id,org_id,document_id,version_number,original_sha256_hex,byte_length,media_type
        ) values('{other_version}','{org}','{other_doc}',1,repeat('b',64),10,'application/pdf');
    """, env)
    _run(actor(owner, rights_call(uuid4(), 0, document=other_doc, source=other_version)),
         env, should_pass=False)
    _run(actor(owner,
         f"select public.caseproof_rights_current('{case}','{other_doc}','{other_version}')"),
         env, should_pass=False)

    # Two independent DB connections race to append version 2. The case row
    # lock forces one writer to observe stale expected_version=1.
    outcomes: list[str] = []
    barrier = threading.Barrier(2)
    def racing_policy_write() -> None:
        with psycopg.connect() as con:
            try:
                con.execute("set local role authenticated")
                con.execute("select set_config('request.jwt.claim.sub',%s,true)", (owner,))
                con.execute("select set_config('request.jwt.claims',%s,true)",
                            ('{"role":"authenticated"}',))
                barrier.wait(timeout=10)
                con.execute(
                    "select public.caseproof_rights_manage(%s,%s,%s,%s,%s,%s::jsonb)",
                    (case, doc, version, 1, str(uuid4()), policy),
                )
                con.commit()
                outcomes.append('accepted')
            except psycopg.errors.UniqueViolation:
                con.rollback()
                outcomes.append('stale')
    threads = [threading.Thread(target=racing_policy_write) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
    if any(thread.is_alive() for thread in threads) or sorted(outcomes)!=['accepted','stale']:
        raise AssertionError(f'concurrent rights writes not serialized: {outcomes}')
    if _run(f"select count(*) from caseproof.source_rights_policies "
            f"where case_id='{case}'", env) != '2':
        raise AssertionError('rights history must append exactly one winning version')
    if _run(f"select count(*) from caseproof.audit_events "
            f"where case_id='{case}' and action='source_rights_changed'", env) != '2':
        raise AssertionError('every policy change must have one atomic audit event')
    print('RIGHTS_SIGNED_SCOPE_REPLAY_CONCURRENCY_APPEND_ONLY_PASSED', flush=True)
    # Rights revocation is a new immutable policy version, not an update to
    # earlier approvals. The transactional SQL gate must use latest only.
    revoked_policy = json.dumps({
        "origin": "CLIENT_UPLOAD", "classification": "CLIENT_CONFIDENTIAL",
        "authorization_reference": "synthetic-contract-1",
        "process": False, "export": False,
    }, separators=(",", ":"))
    revoke_rights = (
        f"select (public.caseproof_rights_manage('{case}','{doc}','{version}',"
        f"2,'{uuid4()}','{revoked_policy}'::jsonb)->>'policy_version')"
    )
    if _run(actor(owner, revoke_rights), env) != '3':
        raise AssertionError('revoked policy did not append immutable version 3')
    _run("update caseproof._rights_enforcement_control set enabled=true", env)
    _run(source_gate + "'process')", env, should_pass=False)
    _run(source_gate + "'export')", env, should_pass=False)
    # A privileged direct table write must be fenced in the SQL transaction,
    # even when a previously allowed snapshot is still in the database.
    denial = f"""
    do $rights_trigger$
    begin
      begin
        insert into caseproof.dossier_releases(
          org_id,case_id,release_id,actor_id,brief_id,
          snapshot_hash,manifest,artifacts
        ) values(
          '{org}','{case}','{uuid4()}','{owner}','{version}',
          repeat('f',64),'{{}}'::jsonb,'{{}}'::jsonb
        );
        raise exception 'protected release inserted after rights revocation';
      exception when insufficient_privilege then
        if SQLERRM <> 'source rights denied or unknown' then
          raise;
        end if;
      end;
    end $rights_trigger$;
    """
    _run(denial, env)
    _run("update caseproof._rights_enforcement_control set enabled=false", env)
    if _run(f"select count(*) from caseproof.source_rights_policies "
            f"where case_id='{case}'", env) != '3':
        raise AssertionError('revocation must preserve all three versions')
    if _run(f"select count(*) from caseproof.audit_events "
            f"where case_id='{case}' and action='source_rights_changed'", env) != '3':
        raise AssertionError('revocation missing atomic audit event')
    print('RIGHTS_SQL_RELEASE_TRIGGER_REVOKED_LATEST_VERSION_PASSED', flush=True)

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
    # NULL must be rejected at dispatch, before manifest or snapshot validation.
    # A generic failure alone would let the old vulnerable fall-through pass.
    _run(actor(owner, f"""do $test$
    begin
      begin
        perform public.caseproof_dossier_export_release('{case}', NULL, '{uuid4()}', '{{}}'::jsonb);
        raise exception 'NULL action accepted';
      exception when insufficient_privilege then
        if SQLERRM <> 'release unavailable' then raise; end if;
      end;
    end $test$"""), env)
    print('F6_NULL_ACTION_REJECTED_AT_DISPATCH_42501_PASSED', flush=True)
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
  ),'{owner}'
);
"""
    # A browser JWT with export permissions must still be unable to write
    # signed release bytes directly via the published PostgreSQL function.
    _run(actor(owner, release_attempt), env, should_pass=False)
    trusted_release = (
        "begin; set local role service_role;"
        " set local request.jwt.claims='{\"role\":\"service_role\"}';"
        + release_attempt + " commit;"
    )
    try:
        _run(trusted_release, env)
    except AssertionError as error:
        if "release capacity reached" not in str(error):
            raise
    else:
        raise AssertionError('release capacity did not fail closed')
    print('F6_DIRECT_SIGNED_WRITE_DENIED_AND_CAPACITY_FENCED_PASSED', flush=True)
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
    if _run("select erased_audit_events from caseproof.erasure_receipts", env) != '4':
        raise AssertionError('minimal erasure audit missing')
    if _run(f"select count(*) from caseproof.source_rights_policies where case_id='{case}'", env) != '0':
        raise AssertionError('rights policy history survived authorized matter purge')
    print('RIGHTS_EXISTING_PURGE_ERASES_POLICY_AND_AUDIT_PASSED', flush=True)
    print('RETENTION_SQL_DENIAL_HOLD_STORAGE_RETRY_SCOPE_AND_RECEIPT_PASSED')


if __name__ == '__main__':
    main()
