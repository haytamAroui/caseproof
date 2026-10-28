-- DEV-ONLY teardown for one exact synthetic fixture after live review acceptance.
-- Restores M1 positive workflow to empty state; no user/customer data is eligible.
create or replace function caseproof._m2_deny_event_mutation()
returns trigger language plpgsql security invoker set search_path=pg_catalog,pg_temp as $$
begin
  if current_user='postgres'
    and current_setting('caseproof.dev_review_cleanup',true)='single_fixture'
  then return old; end if;
  raise exception 'M2 event history immutable' using errcode='55000';
end $$;

create or replace function caseproof._m2_brief_immutable()
returns trigger language plpgsql security invoker set search_path=pg_catalog,pg_temp as $$
begin
  if current_user='postgres'
    and current_setting('caseproof.dev_review_cleanup',true)='single_fixture'
  then return old; end if;
  raise exception 'immutable M2 brief history' using errcode='55000';
end $$;

create or replace function caseproof._m1_exhibit_event_guard()
returns trigger language plpgsql security invoker set search_path=pg_catalog,pg_temp as $$
begin
  if current_user='postgres'
    and current_setting('caseproof.dev_review_cleanup',true)='single_fixture'
  then return old; end if;
  raise exception 'exhibit history immutable' using errcode='55000';
end $$;

create function public.caseproof_dev_review_cleanup(p_run_id uuid,p_owner uuid)
returns boolean language plpgsql security definer set search_path='' as $$
declare f caseproof._dev_ci_fixture%rowtype;
begin
  select * into f from caseproof._dev_ci_fixture
    where run_id=p_run_id and owner_id=p_owner for update;
  if not found then return false; end if;
  if exists(select 1 from caseproof._m2_brief_versions
      where case_id=f.case_id and (actor_id<>p_owner
       or parser_id<>'dev-synthetic-preseed-v1'))
    or exists(select 1 from caseproof._m2_correction_plans where case_id=f.case_id)
    or exists(select 1 from caseproof._m2_correction_events where case_id=f.case_id)
    or exists(select 1 from caseproof.audit_events
      where case_id=f.case_id and action not in
        ('dev_synthetic_exhibit','dev_synthetic_brief','m2_review_disposition'))
    or exists(select 1 from caseproof._m2_review_events
      where case_id=f.case_id and actor_id<>p_owner)
  then raise exception 'refuse cleanup of non synthetic or externally touched matter'
     using errcode='42501'; end if;
  perform set_config('caseproof.dev_review_cleanup','single_fixture',true);
  delete from caseproof._m2_review_receipts where org_id=f.org_id and case_id=f.case_id;
  delete from caseproof._m2_review_events where org_id=f.org_id and case_id=f.case_id;
  delete from caseproof._m2_review_heads where org_id=f.org_id and case_id=f.case_id;
  delete from caseproof._m2_check_runs where org_id=f.org_id and case_id=f.case_id;
  delete from caseproof._m2_brief_assertions where org_id=f.org_id and case_id=f.case_id;
  delete from caseproof._m2_brief_references where org_id=f.org_id and case_id=f.case_id;
  delete from caseproof._m2_brief_events where org_id=f.org_id and case_id=f.case_id;
  delete from caseproof._m2_brief_heads where org_id=f.org_id and case_id=f.case_id;
  delete from caseproof._m2_brief_versions where org_id=f.org_id and case_id=f.case_id;
  delete from caseproof._m1_exhibit_events where org_id=f.org_id and case_id=f.case_id;
  delete from caseproof._m1_exhibit_heads where org_id=f.org_id and case_id=f.case_id;
  delete from caseproof.audit_events where org_id=f.org_id and case_id=f.case_id
    and action in ('dev_synthetic_exhibit','dev_synthetic_brief','m2_review_disposition');
  perform set_config('caseproof.dev_review_cleanup','',true);
  return true;
end $$;
revoke all on function public.caseproof_dev_review_cleanup(uuid,uuid)
  from public,anon,authenticated;
grant execute on function public.caseproof_dev_review_cleanup(uuid,uuid) to service_role;
