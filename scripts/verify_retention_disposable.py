"""Full migration + negative retention SQL tests, disposable PostgreSQL only."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

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
    for path in paths:
        if path in (delayed, retention):
            continue
        _run(path.read_text(), env)
        _run(f"insert into supabase_migrations.schema_migrations values('{path.name.split('_')[0]}');", env)
    _run(delayed.read_text(), env)
    _run((ROOT / 'supabase/phase4_reviewed/caseproof_phase4_signed_reference_review.sql').read_text(), env)
    _run(retention.read_text(), env)
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

    service = "set request.jwt.claims='{\"role\":\"service_role\"}'; "
    soft = f"select public.caseproof_soft_delete_matter('{case}')"
    _run(actor(guest, soft), env, should_pass=False)
    _run(actor(owner, soft), env)
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
    if _run("select erased_audit_events from caseproof.erasure_receipts", env) != '1':
        raise AssertionError('minimal erasure audit missing')
    print('RETENTION_SQL_DENIAL_HOLD_STORAGE_RETRY_SCOPE_AND_RECEIPT_PASSED')


if __name__ == '__main__':
    main()
