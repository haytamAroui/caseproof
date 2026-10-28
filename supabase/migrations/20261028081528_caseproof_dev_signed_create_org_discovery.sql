-- Development only: enumerate memberships eligible for creating a new private matter.
create function public.caseproof_dev_journey_organizations()
returns jsonb language plpgsql security definer set search_path='' as $$
declare v_user uuid:=auth.uid();
begin
 if v_user is null or coalesce(auth.jwt()->>'role','')<>'authenticated'
 or coalesce(auth.jwt()->>'is_anonymous','false')='true'
 then raise exception 'signed identity required' using errcode='42501'; end if;
 return pg_catalog.jsonb_build_object('schema','caseproof-dev-create-orgs-v1',
   'organizations',coalesce(
    (select pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object(
       'org_id',m.org_id,'name',o.display_name))
     from caseproof.organization_members m
     join caseproof.organizations o on o.id=m.org_id
     where m.user_id=v_user and m.active and 'case:create'=any(m.actions)),
    '[]'::jsonb));
end $$;
revoke all on function public.caseproof_dev_journey_organizations() from public,anon;
grant execute on function public.caseproof_dev_journey_organizations() to authenticated;
