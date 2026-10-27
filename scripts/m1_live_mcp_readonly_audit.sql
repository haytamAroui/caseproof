-- Read-only M1 dev integrity evidence, executed through Supabase MCP.
-- This is NOT a real signed-user authorization test.
with expected(tablename,policyname) as (
  values
    ('cases','m1_private_case_read'),
    ('documents','m1_private_document_read'),
    ('document_versions','m1_private_document_version_read'),
    ('_m1_matter_grants','m1_own_private_grant_read')
),
policy_evidence as (
  select e.tablename,
    (select count(*) from pg_policies p
      where p.schemaname='caseproof'
        and p.tablename=e.tablename
        and p.cmd in ('ALL','SELECT')) as policy_count,
    exists (
      select 1 from pg_policies p
      where p.schemaname='caseproof'
        and p.tablename=e.tablename
        and p.policyname=e.policyname
        and p.cmd='SELECT'
        and p.permissive='PERMISSIVE'
        and p.roles = array['authenticated']::name[]
        and p.qual like '%auth.uid()%'
        and p.qual like '%case:read%'
        and (e.tablename='_m1_matter_grants' or p.qual like '%_m1_matter_grants%')
        and (e.tablename in ('cases','_m1_matter_grants')
          or (p.qual like '%evidence:read%' and p.qual like '%case:read%'))
    ) as matches_expected
  from expected e
),
protected as (
  select e.tablename,
    coalesce(c.relrowsecurity,false) as rls_enabled,
    has_table_privilege('authenticated',c.oid,'SELECT') as authenticated_can_select,
    has_table_privilege('anon',c.oid,'SELECT') as anon_can_select,
    has_table_privilege('authenticated',c.oid,
      'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES') as authenticated_can_write
  from expected e
  left join pg_namespace n on n.nspname='caseproof'
  left join pg_class c on c.relnamespace=n.oid and c.relname=e.tablename
),
no_policies as (
  select count(*)=0 as audit_stays_closed from pg_policies
  where schemaname='caseproof' and tablename in ('audit_events','idempotency_records')
),
live_counts as (
  select
    (select count(*) from auth.users) as users,
    (select count(*) from caseproof.organizations) as organizations,
    (select count(*) from caseproof.cases) as matters,
    (select count(*) from caseproof._m1_matter_grants) as grants
)
select
  exists (select 1 from supabase_migrations.schema_migrations
    where version='20261027160745') as expected_private_migration_installed,
  (select bool_and(matches_expected and policy_count=1) from policy_evidence)
    as no_overlapping_read_policies_and_expected_predicates,
  (select bool_and(rls_enabled and authenticated_can_select
      and not anon_can_select and not authenticated_can_write) from protected)
    as protected_reads_rls_on_and_no_client_writes,
  (select audit_stays_closed from no_policies)
    as sensitive_server_tables_keep_no_client_policy,
  not exists (select 1 from pg_roles where rolname='caseproof_m1_reader')
    as no_permanent_reader_role_yet,
  (select jsonb_build_object(
    'auth_users',users,'organizations',organizations,'matters',matters,
    'matter_grants',grants) from live_counts) as dev_fixture_counts,
  (select jsonb_agg(jsonb_build_object('table',tablename,'rls',rls_enabled,
    'auth_read',authenticated_can_select,'auth_write',authenticated_can_write,
    'anon_read',anon_can_select) order by tablename) from protected)
    as protected_relation_details;
