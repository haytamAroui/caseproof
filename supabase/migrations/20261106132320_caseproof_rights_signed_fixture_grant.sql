-- Service-only grant of rights:manage to a VERIFIED synthetic M0.5 owner.
-- No right is approved here; the owner must sign caseproof_rights_manage.
-- Never exposes a general tenant or production matter permissions writer.
begin;
create function public.caseproof_rights_fixture_grant(
  p_run uuid,p_case uuid,p_owner uuid
) returns boolean language plpgsql security definer set search_path='' as $$
declare
  v_org uuid;
begin
  if auth.role()<>'service_role' or p_run is null or p_case is null
    or p_owner is null then
    raise exception 'synthetic rights fixture unavailable' using errcode='42501';
  end if;
  if not exists(
     select 1 from caseproof.test_run_registry r
     where r.run_id=p_run and r.resource_type='run'
       and r.resource_id=p_run::text and r.state in ('RESERVED','CREATED')
  ) or not exists(
     select 1 from caseproof.test_run_registry r
     where r.run_id=p_run and r.resource_type='auth_user'
       and r.resource_id='owner:'||p_owner::text and r.state='CREATED'
  ) or not exists(
     select 1 from caseproof.test_run_registry r
     where r.run_id=p_run and r.resource_type='matter'
       and r.resource_id=p_case::text and r.state='CREATED'
  ) then
    raise exception 'synthetic ownership not recorded' using errcode='42501';
  end if;
  select c.org_id into v_org from caseproof.cases c
    join caseproof._dev_journey_fixtures f on f.org_id=c.org_id
      and f.run_id=p_run and f.owner_id=p_owner
    where c.id=p_case and c.created_by_user=p_owner
      and c.effective_policy_version='caseproof-dev-txt-v1'
      and c.deleted_at is null and c.purge_started_at is null
    for update of c;
  if v_org is null then
    raise exception 'synthetic matter mismatch' using errcode='42501';
  end if;
  update caseproof.organization_members m set
    actions=case when 'rights:manage'=any(m.actions) then m.actions
      else array_append(m.actions,'rights:manage') end,
    membership_revision=m.membership_revision+1
    where m.org_id=v_org and m.user_id=p_owner and m.active;
  if not found then
    raise exception 'synthetic owner inactive' using errcode='42501';
  end if;
  update caseproof._m1_matter_grants g set
    permissions=case when 'rights:manage'=any(g.permissions) then g.permissions
      else array_append(g.permissions,'rights:manage') end
    where g.org_id=v_org and g.case_id=p_case and g.user_id=p_owner
      and g.role='reviewer' and g.active;
  if not found then
    raise exception 'synthetic reviewer grant unavailable' using errcode='42501';
  end if;
  return true;
end $$;
revoke all on function public.caseproof_rights_fixture_grant(uuid,uuid,uuid)
  from public,anon,authenticated,service_role;
grant execute on function public.caseproof_rights_fixture_grant(uuid,uuid,uuid)
  to service_role;
commit;
