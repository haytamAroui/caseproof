-- S2-002 TEST FIXTURE ONLY. On connected caseproof-dev, run after the
-- proposal inside one transaction and ALWAYS roll back after verification.
-- In disposable GitHub Actions PostgreSQL (caseproof_s2_ci) the harness may
-- commit its synthetic fixture before launching two independent sessions;
-- that one-job PostgreSQL service is destroyed after CI. NEVER commit this
-- test fixture to a shared Supabase project.
-- Tests simulate runtime PostgreSQL roles/auth.uid() claim context, NOT a
-- real Supabase Auth signature or authenticated HTTPS user session.

insert into auth.users (id, instance_id, aud, role, email, created_at, updated_at)
values
 ('11111111-1111-4111-8111-111111111111', '00000000-0000-0000-0000-000000000000',
  'authenticated', 'authenticated', 's2test-a@example.invalid', now(), now()),
 ('22222222-2222-4222-8222-222222222222', '00000000-0000-0000-0000-000000000000',
  'authenticated', 'authenticated', 's2test-b@example.invalid', now(), now()),
 ('33333333-3333-4333-8333-333333333333', '00000000-0000-0000-0000-000000000000',
  'authenticated', 'authenticated', 's2test-c@example.invalid', now(), now());

insert into caseproof.organizations(id, display_name) values
 ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','Test tenant A'),
 ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','Test tenant B');

insert into caseproof.organization_members(org_id,user_id,actions)
values
 ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', '11111111-1111-4111-8111-111111111111',
  array['case:read','evidence:read']::text[]),
 ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '22222222-2222-4222-8222-222222222222',
  array['case:read','evidence:read']::text[]),
 ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', '33333333-3333-4333-8333-333333333333',
  array['case:read']::text[]);

insert into caseproof.cases(id,org_id,created_by_user,effective_policy_version) values
 ('aaaaaaaa-1111-4111-8111-111111111111','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  '11111111-1111-4111-8111-111111111111','test-v1'),
 ('bbbbbbbb-2222-4222-8222-222222222222','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  '22222222-2222-4222-8222-222222222222','test-v1');

insert into caseproof.documents(id,org_id,case_id,source_label) values
 ('aaaaaaaa-3333-4333-8333-333333333333','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  'aaaaaaaa-1111-4111-8111-111111111111','doc-a'),
 ('bbbbbbbb-4444-4444-8444-444444444444','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  'bbbbbbbb-2222-4222-8222-222222222222','doc-b');

insert into caseproof.document_versions(
 id,org_id,document_id,version_number,original_sha256_hex,byte_length,media_type
) values
 ('aaaaaaaa-5555-4555-8555-555555555555','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  'aaaaaaaa-3333-4333-8333-333333333333',1,repeat('a',64),12,'text/plain'),
 ('bbbbbbbb-6666-4666-8666-666666666666','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  'bbbbbbbb-4444-4444-8444-444444444444',1,repeat('b',64),12,'text/plain');

-- Audit actors must be a member of the SAME org as the recorded case.
-- A human linked only to tenant B cannot be attributed to tenant A.
do $audit_actor_fk$
begin
 begin
   insert into caseproof.audit_events (
      org_id, case_id, actor_type, actor_user_id, action,
      event_schema_version, correlation_id, input_sha256_hex
   ) values (
      'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      'aaaaaaaa-1111-4111-8111-111111111111',
      'human', '22222222-2222-4222-8222-222222222222',
      'forged-foreign-actor', 'test-v1', gen_random_uuid(), repeat('a',64)
   );
   raise exception 'cross-tenant audit actor unexpectedly accepted';
 exception
   when foreign_key_violation then null;
 end;
 begin
   insert into caseproof.audit_events (
      org_id, case_id, actor_type, actor_user_id, action,
      event_schema_version, correlation_id, input_sha256_hex
   ) values (
      'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      'aaaaaaaa-1111-4111-8111-111111111111',
      'service', '11111111-1111-4111-8111-111111111111',
      'service-impersonating-human', 'test-v1', gen_random_uuid(), repeat('a',64)
   );
   raise exception 'service audit event with human actor unexpectedly accepted';
 exception
   when check_violation then null;
 end;
 -- A correctly scoped human actor and a service event WITHOUT a human
 -- subject are accepted by the schema (both vanish on rollback).
 insert into caseproof.audit_events (
    org_id, case_id, actor_type, actor_user_id, action,
    event_schema_version, correlation_id, input_sha256_hex
 ) values (
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    'aaaaaaaa-1111-4111-8111-111111111111',
    'human', '11111111-1111-4111-8111-111111111111',
    'valid-tenant-actor', 'test-v1', gen_random_uuid(), repeat('a',64)
 );
 insert into caseproof.audit_events (
    org_id, case_id, actor_type, actor_user_id, action,
    event_schema_version, correlation_id, input_sha256_hex
 ) values (
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    'aaaaaaaa-1111-4111-8111-111111111111',
    'service', null,
    'valid-service-actor', 'test-v1', gen_random_uuid(), repeat('a',64)
 );
end $audit_actor_fk$;

-- Confirm all seven application tables enforce RLS.
do $audit$
declare rls_count integer;
begin
 select count(*) into rls_count
 from pg_class c join pg_namespace n on n.oid=c.relnamespace
 where n.nspname='caseproof' and c.relkind='r' and c.relrowsecurity;
 if rls_count <> 7 then
   raise exception 'S2-002 expected 7 RLS-protected tables, found %',rls_count;
 end if;
 if has_schema_privilege('anon','caseproof','USAGE') then
   raise exception 'anon unexpectedly has access to private schema';
 end if;
 if has_table_privilege('authenticated','caseproof.cases','INSERT')
    or has_table_privilege('authenticated','caseproof.cases','UPDATE')
    or has_table_privilege('authenticated','caseproof.cases','DELETE')
    or has_table_privilege('authenticated','caseproof.audit_events','SELECT')
    or has_table_privilege('authenticated','caseproof.audit_events','INSERT')
    or has_table_privilege('authenticated','caseproof.idempotency_records','SELECT') then
   raise exception 'authenticated has an unauthorized write/audit permission';
 end if;
end $audit$;

-- Cross-org FK cannot be bypassed by supplying a mismatched org_id/case_id.
do $fk$
begin
 begin
   insert into caseproof.documents(id,org_id,case_id,source_label)
   values (
     'aaaaaaaa-7777-4777-8777-777777777777',
     'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
     'bbbbbbbb-2222-4222-8222-222222222222',
     'forged foreign case'
   );
   raise exception 'cross-tenant composite case foreign key unexpectedly accepted';
 exception
   when foreign_key_violation then null;
 end;
end $fk$;

-- A genuine request would carry an already-verified Supabase Auth JWT.
-- Here we TEST ONLY the database policy under a direct role/claim simulation.
set local role authenticated;
select set_config('request.jwt.claim.sub','11111111-1111-4111-8111-111111111111',true);
do $alice$
begin
 if (select count(*) from caseproof.cases) <> 1
    or (select count(*) from caseproof.documents) <> 1
    or (select count(*) from caseproof.document_versions) <> 1
    or (select count(*) from caseproof.organizations) <> 1
    or (select count(*) from caseproof.organization_members) <> 1 then
   raise exception 'tenant A saw wrong row counts';
 end if;
 if exists (select 1 from caseproof.cases where org_id='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb') then
   raise exception 'tenant A could read tenant B';
 end if;
end $alice$;

select set_config('request.jwt.claim.sub','22222222-2222-4222-8222-222222222222',true);
do $bob$
begin
 if (select count(*) from caseproof.cases) <> 1
    or (select count(*) from caseproof.documents) <> 1
    or (select count(*) from caseproof.document_versions) <> 1 then
   raise exception 'tenant B saw wrong row counts';
 end if;
 if exists(select 1 from caseproof.cases where org_id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa') then
   raise exception 'tenant B could read tenant A';
 end if;
end $bob$;

-- Case-only reader cannot read document or version metadata.
select set_config('request.jwt.claim.sub','33333333-3333-4333-8333-333333333333',true);
do $carol$
begin
 if (select count(*) from caseproof.cases) <> 1 then
    raise exception 'case reader cannot see authorized case';
 end if;
 if (select count(*) from caseproof.documents) <> 0
    or (select count(*) from caseproof.document_versions) <> 0 then
    raise exception 'case-only permission exposed evidence metadata';
 end if;
end $carol$;

-- No signed JWT/subject => no rows, even for authenticated database role.
select set_config('request.jwt.claim.sub','',true);
do $empty$
begin
 if (select count(*) from caseproof.cases) <> 0
    or (select count(*) from caseproof.organizations) <> 0 then
   raise exception 'missing auth.uid leaked tenant metadata';
 end if;
end $empty$;

reset role;

-- App access contract aligns with case RLS: even a reviewer whose
-- only capability is conclusion:request_approval must also be granted
-- case:read to see the case for an authorization preflight.
update caseproof.organization_members
set actions=array['conclusion:request_approval']::text[]
where org_id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
  and user_id='33333333-3333-4333-8333-333333333333';
set local role authenticated;
select set_config('request.jwt.claim.sub','33333333-3333-4333-8333-333333333333',true);
do $action_only$
begin
 if (select count(*) from caseproof.cases) <> 0 then
   raise exception 'action-only user saw case without case:read';
 end if;
end $action_only$;
reset role;
update caseproof.organization_members
set actions=array['case:read','conclusion:request_approval']::text[]
where org_id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
  and user_id='33333333-3333-4333-8333-333333333333';
set local role authenticated;
select set_config('request.jwt.claim.sub','33333333-3333-4333-8333-333333333333',true);
do $dual_granted$
begin
 if (select count(*) from caseproof.cases) <> 1 then
   raise exception 'case:read plus action grant did not reveal permitted case';
 end if;
end $dual_granted$;
reset role;

-- Revocation must take effect on subsequent authenticated statements.
update caseproof.organization_members
set active=false, membership_revision=membership_revision+1
where org_id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
  and user_id='11111111-1111-4111-8111-111111111111';

set local role authenticated;
select set_config('request.jwt.claim.sub','11111111-1111-4111-8111-111111111111',true);
do $revoked$
begin
 if (select count(*) from caseproof.cases) <> 0
    or (select count(*) from caseproof.documents) <> 0
    or (select count(*) from caseproof.organization_members) <> 0 then
   raise exception 'revoked membership retained access';
 end if;
end $revoked$;
reset role;

-- Successful completion marker is returned only if EVERY assertion held.
select 'S2-002_ROLLBACK_ONLY_RLS_TEST_PASSED'::text as verification;
-- EXECUTION WRAPPER MUST ROLLBACK after this statement.
