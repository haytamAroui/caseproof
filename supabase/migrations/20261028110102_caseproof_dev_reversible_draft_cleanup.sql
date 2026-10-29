-- Scoped fixture teardown permits only owner-authored new draft correction events.
create or replace function public.caseproof_dev_journey_cleanup(p_run uuid,p_owner uuid)
returns boolean language plpgsql security definer set search_path='' as $$
declare v caseproof._dev_journey_fixtures%rowtype; c uuid; total int;
begin
 select * into v from caseproof._dev_journey_fixtures
 where run_id=p_run and owner_id=p_owner for update;
 if not found then return false; end if;
 select count(*),(array_agg(id))[1] into total,c from caseproof.cases where org_id=v.org_id;
 if total>1 or (total=1 and (
    not exists(select 1 from caseproof.cases where id=c and created_by_user=p_owner
      and effective_policy_version='caseproof-dev-txt-v1')
    or exists(select 1 from caseproof.audit_events where case_id=c and action not in
     ('dev_matter_created','dev_txt_registered','dev_txt_ingested',
      'dev_unconfirmed_source','dev_authored_brief','dev_brief_corrected','m2_review_disposition'))
    or exists(select 1 from caseproof._m1_matter_grants g
       where g.org_id=v.org_id and g.case_id=c and g.user_id<>p_owner)
    or exists(select 1 from caseproof.audit_events a
       where a.org_id=v.org_id and a.case_id=c
       and (a.actor_type<>'human' or a.actor_user_id is distinct from p_owner))
    or exists(select 1 from caseproof._m1_exhibit_events e
       where e.org_id=v.org_id and e.case_id=c and e.actor_user_id<>p_owner)
    or exists(select 1 from caseproof._m2_check_runs ch
       where ch.org_id=v.org_id and ch.case_id=c and ch.actor_id<>p_owner)
    or exists(select 1 from caseproof._dev_journey_operations op
       where op.org_id=v.org_id and op.actor_id<>p_owner)
    or exists(select 1 from caseproof._m2_brief_versions where case_id=c and
       (actor_id<>p_owner or parser_id<>'dev-ingested-txt-brief-v1'))
    or exists(select 1 from caseproof._m2_review_events where case_id=c and actor_id<>p_owner)
    or exists(select 1 from storage.objects o where o.bucket_id='caseproof-originals-dev'
       and o.name like v.org_id::text||'/'||c::text||'/%')
 )) then raise exception 'cleanup unsafe: unexpected matter activity or original remains' using errcode='42501'; end if;
 if total=1 then
   perform set_config('caseproof.dev_review_cleanup','single_fixture',true);
   delete from caseproof._m2_review_receipts where org_id=v.org_id and case_id=c;
   delete from caseproof._m2_review_events where org_id=v.org_id and case_id=c;
   delete from caseproof._m2_review_heads where org_id=v.org_id and case_id=c;
   delete from caseproof._m2_check_runs where org_id=v.org_id and case_id=c;
   delete from caseproof._m2_brief_assertions where org_id=v.org_id and case_id=c;
   delete from caseproof._m2_brief_references where org_id=v.org_id and case_id=c;
   delete from caseproof._m2_brief_events where org_id=v.org_id and case_id=c;
   delete from caseproof._m2_brief_heads where org_id=v.org_id and case_id=c;
   delete from caseproof._m2_brief_versions where org_id=v.org_id and case_id=c;
   delete from caseproof._m1_exhibit_events where org_id=v.org_id and case_id=c;
   delete from caseproof._m1_exhibit_heads where org_id=v.org_id and case_id=c;
   delete from caseproof._dev_journey_sources where org_id=v.org_id and case_id=c;
   delete from caseproof.audit_events where org_id=v.org_id and case_id=c;
   delete from caseproof.document_versions where org_id=v.org_id and document_id in
      (select id from caseproof.documents where org_id=v.org_id and case_id=c);
   delete from caseproof.documents where org_id=v.org_id and case_id=c;
   delete from caseproof._m1_matter_grants where org_id=v.org_id and case_id=c;
   delete from caseproof.cases where org_id=v.org_id and id=c;
   perform set_config('caseproof.dev_review_cleanup','',true);
 end if;
 delete from caseproof._dev_journey_operations where org_id=v.org_id;
 delete from caseproof.organization_members where org_id in (v.org_id,v.foreign_org_id);
 delete from caseproof._dev_journey_fixtures where run_id=p_run;
 delete from caseproof.organizations where id in (v.org_id,v.foreign_org_id);
 return true;
end $$;
revoke all on function public.caseproof_dev_journey_cleanup(uuid,uuid) from public,anon,authenticated;
grant execute on function public.caseproof_dev_journey_cleanup(uuid,uuid) to service_role;
