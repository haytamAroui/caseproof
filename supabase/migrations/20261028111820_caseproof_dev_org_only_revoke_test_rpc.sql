-- Service-role-only synthetic dev fixture action toggle.
-- This is NOT a general admin endpoint or customer grant management.
create function public.caseproof_dev_journey_org_write(
 p_run uuid,p_owner uuid,p_case uuid,p_enabled boolean
) returns boolean language plpgsql security definer set search_path='' as $$
declare v caseproof._dev_journey_fixtures%rowtype; v_actions text[];
begin
 if p_enabled is null then raise exception 'explicit enabled flag required' using errcode='42501'; end if;
 select * into v from caseproof._dev_journey_fixtures
   where run_id=p_run and owner_id=p_owner for update;
 if not found or not exists(
    select 1 from caseproof.cases
    where id=p_case and org_id=v.org_id and created_by_user=p_owner
      and effective_policy_version='caseproof-dev-txt-v1'
 ) then raise exception 'unknown scoped synthetic matter' using errcode='42501'; end if;
 select actions into v_actions from caseproof.organization_members
   where org_id=v.org_id and user_id=p_owner and active for update;
 if v_actions is null then raise exception 'unavailable dev owner' using errcode='42501'; end if;
 update caseproof.organization_members
 set actions=case when p_enabled then
   case when 'draft:write'=any(v_actions) then v_actions
     else pg_catalog.array_append(v_actions,'draft:write') end
 else pg_catalog.array_remove(v_actions,'draft:write') end,
 membership_revision=membership_revision+1
 where org_id=v.org_id and user_id=p_owner and active;
 return true;
end $$;
revoke all on function public.caseproof_dev_journey_org_write(uuid,uuid,uuid,boolean)
 from public,anon,authenticated;
grant execute on function public.caseproof_dev_journey_org_write(uuid,uuid,uuid,boolean) to service_role;
