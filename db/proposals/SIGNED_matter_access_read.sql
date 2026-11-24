-- Proposal (not applied): signed matter-access read. One masked snapshot of
-- the caller's current membership + matter grant for a case, mirroring the
-- trusted permission snapshot the check store builds server-side
-- (current_access in postgres_litigation_check_store.py). Read-only. Any
-- gap (not signed in, anonymous, inactive or absent membership/grant,
-- foreign case) raises the same masked 'matter unavailable' 42501: a
-- foreign same-organization case is not discoverable.
create or replace function public.caseproof_signed_matter_access(
 p_case uuid
) returns jsonb language plpgsql security definer set search_path='' as $$
declare
 v_actor uuid:=auth.uid();
 v_org uuid; v_case_rev bigint;
 v_member caseproof.organization_members%rowtype;
 v_grant caseproof._m1_matter_grants%rowtype;
begin
 if p_case is null
 or v_actor is null or coalesce(auth.jwt()->>'role','')<>'authenticated'
 or coalesce(auth.jwt()->>'is_anonymous','false')='true'
 then raise exception 'private signed user required' using errcode='42501'; end if;

 select c.org_id,c.case_revision into v_org,v_case_rev from caseproof.cases c
 join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=v_actor and m.active
 join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id
    and g.user_id=v_actor and g.active
 where c.id=p_case;
 if v_org is null then raise exception 'matter unavailable' using errcode='42501'; end if;

 select m.* into v_member from caseproof.organization_members m
 where m.org_id=v_org and m.user_id=v_actor and m.active;
 select g.* into v_grant from caseproof._m1_matter_grants g
 where g.org_id=v_org and g.case_id=p_case and g.user_id=v_actor and g.active;
 if v_member.user_id is null or v_grant.user_id is null
 then raise exception 'matter unavailable' using errcode='42501'; end if;

 return jsonb_build_object(
   'ok',true,
   'actor_id',v_actor,
   'org_id',v_org,
   'case_revision',v_case_rev,
   'member_actions',to_jsonb(v_member.actions),
   'membership_revision',v_member.membership_revision,
   'grant_role',v_grant.role,
   'grant_permissions',to_jsonb(v_grant.permissions),
   'grant_revision',v_grant.revision);
end $$;
revoke all on function public.caseproof_signed_matter_access(uuid) from public,anon;
grant execute on function public.caseproof_signed_matter_access(uuid) to authenticated;
