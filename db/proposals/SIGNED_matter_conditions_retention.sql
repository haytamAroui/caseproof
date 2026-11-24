-- DRAFT, NOT APPLIED to any shared environment (no supabase/migrations entry).
-- Companion to SIGNED_matter_conditions.sql. The installed caseproof_retention('finalize') deletes matter history
-- table by table and then the case row; without this one extra delete, a matter that has condition revisions could
-- not be purged (FK to cases). Generated from the function as installed by the repo's disposable replay order,
-- adding only the delete of matter_condition_specs before the matter grants are removed. Owner, security definer,
-- search_path and ACL are restated unchanged.
create or replace function public.caseproof_retention(p_action text, p_case uuid DEFAULT NULL::uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare v caseproof.cases%rowtype; v_days integer; v_count bigint; v_digest text;
begin
 if coalesce(auth.jwt()->>'role','')<>'service_role' then
  raise exception 'service role required' using errcode='42501'; end if;
 select grace_days into strict v_days from caseproof.retention_policy where singleton;
 if p_action='due' then
  return (select coalesce(jsonb_agg(id),'[]'::jsonb) from
   (select id from caseproof.cases where deleted_at<=now()-make_interval(days=>v_days)
    and not legal_hold order by deleted_at,id limit 100) q);
 end if;
 if p_case is null then raise exception 'matter required'; end if;
 v_digest:=encode(sha256(convert_to(p_case::text,'UTF8')),'hex');
 select * into v from caseproof.cases where id=p_case for update;
 if not found then
  if exists(select 1 from caseproof.erasure_receipts where matter_digest=v_digest) then
   return jsonb_build_object('purged',true,'matter_digest',v_digest);
  end if;
  raise exception 'matter unavailable' using errcode='42501';
 end if;
 if v.deleted_at is null or v.deleted_at>now()-make_interval(days=>v_days) or v.legal_hold then
  raise exception 'matter not eligible for purge' using errcode='42501'; end if;
 if p_action='plan' then
  update caseproof.cases set purge_started_at=coalesce(purge_started_at,clock_timestamp()) where id=v.id;
  return jsonb_build_object('prefix',v.org_id::text||'/'||v.id::text||'/',
   'paths',(select coalesce(jsonb_agg(name),'[]'::jsonb) from storage.objects
    where bucket_id='caseproof-originals-dev' and name like v.org_id::text||'/'||v.id::text||'/%'));
 end if;
 if p_action<>'finalize' then raise exception 'unsupported retention action'; end if;
 if v.purge_started_at is null then raise exception 'Storage phase not started'; end if;
 if exists(select 1 from storage.objects where bucket_id='caseproof-originals-dev'
  and name like v.org_id::text||'/'||v.id::text||'/%') then
  raise exception 'Storage not empty; retry API deletion first'; end if;
 -- Existing immutable-history guards permit only postgres's bounded cleanup.
 -- Keep that bypass inside this service-only, locked, eligibility-checked RPC.
 perform set_config('caseproof.dev_review_cleanup','single_fixture',true);
 delete from caseproof._phase4_reference_decisions where org_id=v.org_id and case_id=v.id;
 delete from caseproof._m2_correction_events where org_id=v.org_id and case_id=v.id;
 delete from caseproof._m2_correction_plans where org_id=v.org_id and case_id=v.id;
 delete from caseproof._m2_review_receipts where org_id=v.org_id and case_id=v.id;
 delete from caseproof._m2_review_events where org_id=v.org_id and case_id=v.id;
 delete from caseproof._m2_review_heads where org_id=v.org_id and case_id=v.id;
 delete from caseproof._m2_check_runs where org_id=v.org_id and case_id=v.id;
 delete from caseproof._m2_brief_assertions where org_id=v.org_id and case_id=v.id;
 delete from caseproof._m2_brief_references where org_id=v.org_id and case_id=v.id;
 delete from caseproof._m2_brief_events where org_id=v.org_id and case_id=v.id;
 delete from caseproof._m2_brief_heads where org_id=v.org_id and case_id=v.id;
 delete from caseproof._m2_brief_versions where org_id=v.org_id and case_id=v.id;
 delete from caseproof._m1_exhibit_events where org_id=v.org_id and case_id=v.id;
 delete from caseproof._m1_exhibit_heads where org_id=v.org_id and case_id=v.id;
 delete from caseproof._dev_journey_sources where org_id=v.org_id and case_id=v.id;
 delete from caseproof.idempotency_records where org_id=v.org_id and case_id=v.id;
 delete from caseproof.ocr_geometry_sidecars where document_version_id in
  (select dv.id from caseproof.document_versions dv join caseproof.documents d
   on d.id=dv.document_id and d.org_id=dv.org_id where d.org_id=v.org_id and d.case_id=v.id);
 select count(*) into v_count from caseproof.audit_events where org_id=v.org_id and case_id=v.id;
 insert into caseproof.erasure_receipts(matter_digest,deleted_at,erased_audit_events)
  values(v_digest,v.deleted_at,v_count);
 delete from caseproof.audit_events where org_id=v.org_id and case_id=v.id;
 -- Operation receipts contain nested source IDs; match only the exact UUID.
 delete from caseproof._dev_journey_operations where org_id=v.org_id
  and response::text like '%'||v.id::text||'%';
 if to_regclass('caseproof._phase3_acceptance_registry') is not null then
  delete from caseproof._phase3_acceptance_registry where org_id=v.org_id and matter_id=v.id;
 end if;
 delete from caseproof.document_versions where org_id=v.org_id and document_id in
  (select id from caseproof.documents where org_id=v.org_id and case_id=v.id);
 delete from caseproof.documents where org_id=v.org_id and case_id=v.id;
 delete from caseproof.matter_condition_specs where org_id=v.org_id and case_id=v.id;
 delete from caseproof._m1_matter_grants where org_id=v.org_id and case_id=v.id;
 delete from caseproof.cases where org_id=v.org_id and id=v.id;
 perform set_config('caseproof.dev_review_cleanup','',true);
 return jsonb_build_object('purged',true,'matter_digest',v_digest);
end $function$;

revoke all on function public.caseproof_retention(text,uuid) from public,anon,authenticated;
grant execute on function public.caseproof_retention(text,uuid) to service_role;
