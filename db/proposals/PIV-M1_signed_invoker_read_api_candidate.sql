-- M1-B proposed signed-PostgREST surface: REVIEW CANDIDATE, NOT INSTALLED.
-- Explicitly public schema views only; caseproof private tables stay unexposed.
-- No SECURITY DEFINER, RPC grants, admin DB passwords or Storage URL access.
-- Applies only after reviewed M1 private RLS; public views require approved
-- deployment and genuine signed Auth acceptance before customer data.
begin;

do $m1_invoker_gate$
declare
    policy_rows integer;
begin
    if current_setting('server_version_num')::integer < 150000 then
        raise exception 'security_invoker requires PostgreSQL 15+'
            using errcode='55000';
    end if;
    if to_regclass('caseproof._m1_matter_grants') is null
      or to_regclass('caseproof.cases') is null
      or to_regclass('caseproof.documents') is null
      or to_regclass('caseproof.document_versions') is null then
        raise exception 'M1 private foundation unavailable'
            using errcode='55000';
    end if;
    if to_regclass('public.caseproof_private_matters') is not null
      or to_regclass('public.caseproof_private_source_versions') is not null then
        raise exception 'existing API object needs manual reconciliation'
            using errcode='55000';
    end if;

    select count(*) into policy_rows
    from pg_policies p
    where p.schemaname='caseproof'
      and p.cmd='SELECT'
      and p.roles=array['authenticated']::name[]
      and (
        (p.tablename='cases' and p.policyname='m1_private_case_read')
        or (p.tablename='documents' and p.policyname='m1_private_document_read')
        or (p.tablename='document_versions'
          and p.policyname='m1_private_document_version_read')
        or (p.tablename='_m1_matter_grants'
          and p.policyname='m1_own_private_grant_read')
      );
    if policy_rows <> 4 or exists (
       select 1 from pg_policies p
       where p.schemaname='caseproof'
         and p.tablename in ('cases','documents','document_versions','_m1_matter_grants')
         and p.cmd in ('SELECT','ALL')
         and not (
           (p.tablename='cases' and p.policyname='m1_private_case_read')
           or (p.tablename='documents' and p.policyname='m1_private_document_read')
           or (p.tablename='document_versions'
             and p.policyname='m1_private_document_version_read')
           or (p.tablename='_m1_matter_grants'
             and p.policyname='m1_own_private_grant_read')
         )
    ) then
      raise exception 'unreviewed overlapping private RLS'
        using errcode='42501';
    end if;
    if exists (
      select 1 from pg_class c join pg_namespace n on n.oid=c.relnamespace
      where n.nspname='caseproof'
        and c.relname in ('cases','documents','document_versions','_m1_matter_grants')
        and (not c.relrowsecurity
         or not has_table_privilege('authenticated',c.oid,'SELECT')
         or has_table_privilege('anon',c.oid,'SELECT')
         or has_table_privilege('authenticated',c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES'))
    ) then
      raise exception 'M1 RLS or relation privileges not private'
        using errcode='42501';
    end if;
end;
$m1_invoker_gate$;

-- SECURITY INVOKER makes PostgREST's verified JWT database role and auth.uid()
-- effective for the *underlying* RLS-enabled private relations. No owner bypass.
create view public.caseproof_private_matters
    with (security_invoker = true, security_barrier = true)
as
select c.id as case_id,
       c.org_id,
       c.case_revision,
       c.scope_version,
       c.manifest_revision,
       c.state
from caseproof.cases c;

create view public.caseproof_private_source_versions
    with (security_invoker = true, security_barrier = true)
as
select d.org_id,
       d.case_id,
       d.id as document_id,
       v.id as version_id,
       v.version_number,
       v.original_sha256_hex,
       v.byte_length,
       v.media_type
from caseproof.documents d
join caseproof.document_versions v
    on v.org_id=d.org_id and v.document_id=d.id;

revoke all on public.caseproof_private_matters,
    public.caseproof_private_source_versions from public, anon, authenticated;
grant select on public.caseproof_private_matters,
    public.caseproof_private_source_versions to authenticated;

-- Do not grant anything to browser roles on private M2 writer or audit tables.
-- Views must remain genuinely INVOKER when opened via PostgREST.
do $verify_invoker$
declare
    view_count integer;
begin
    select count(*) into view_count
    from pg_class c join pg_namespace n on n.oid=c.relnamespace
    where n.nspname='public'
      and c.relname in ('caseproof_private_matters',
                        'caseproof_private_source_versions')
      and c.relkind='v'
      and 'security_invoker=true'=any(c.reloptions)
      and 'security_barrier=true'=any(c.reloptions)
      and has_table_privilege('authenticated',c.oid,'SELECT')
      and not has_table_privilege('anon',c.oid,'SELECT')
      and not has_table_privilege('authenticated',c.oid,'INSERT,UPDATE,DELETE');
    if view_count<>2 then
        raise exception 'read-only security invoker view boundary incomplete'
          using errcode='42501';
    end if;
end;
$verify_invoker$;
commit;
