-- Fence uploads already authorized before soft deletion: Storage metadata
-- writes take the same matter lock. Deny new objects for a missing/deleted case.
create function caseproof.retention_storage_guard() returns trigger
 language plpgsql security definer set search_path='' as $$
declare v_case uuid; v_org uuid; v_deleted timestamptz;
begin
 if new.bucket_id<>'caseproof-originals-dev' then return new; end if;
 begin
  v_org:=split_part(new.name,'/',1)::uuid;
  v_case:=split_part(new.name,'/',2)::uuid;
 exception when invalid_text_representation then
  raise exception 'invalid matter Storage path' using errcode='42501';
 end;
 select deleted_at into v_deleted from caseproof.cases
  where id=v_case and org_id=v_org for share;
 if not found or v_deleted is not null then
  raise exception 'matter unavailable' using errcode='42501'; end if;
 return new;
end $$;
revoke all on function caseproof.retention_storage_guard() from public,anon,authenticated;
create trigger caseproof_retention_storage_guard before insert or update on storage.objects
 for each row execute function caseproof.retention_storage_guard();

-- Once the destructive Storage phase begins, a new hold must fail explicitly
-- rather than misleading an operator that already-deleted bytes were held.
alter table caseproof.cases add column purge_started_at timestamptz;
create function caseproof.retention_hold_guard() returns trigger
 language plpgsql security invoker set search_path='' as $$
begin
 if old.purge_started_at is not null and new.legal_hold is distinct from old.legal_hold then
  raise exception 'purge already started; hold cannot be changed' using errcode='55000';
 end if;
 return new;
end $$;
revoke all on function caseproof.retention_hold_guard() from public,anon,authenticated;
create trigger retention_hold_guard before update on caseproof.cases
 for each row execute function caseproof.retention_hold_guard();
create or replace function public.caseproof_retention(p_action text,p_case uuid default null)
 returns jsonb language plpgsql security definer set search_path='' as $$
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
 delete from caseproof._m1_matter_grants where org_id=v.org_id and case_id=v.id;
 delete from caseproof.cases where org_id=v.org_id and id=v.id;
 perform set_config('caseproof.dev_review_cleanup','',true);
 return jsonb_build_object('purged',true,'matter_digest',v_digest);
end $$;
revoke all on function public.caseproof_retention(text,uuid) from public,anon,authenticated;
grant execute on function public.caseproof_retention(text,uuid) to service_role;

