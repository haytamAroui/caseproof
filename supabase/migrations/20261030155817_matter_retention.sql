-- Authorized development retention architecture. No production deployment.
-- Current signed RPCs all require active matter grants. Soft deletion revokes
-- them atomically; the grant guard prevents subsequent resurrection.
alter table caseproof.cases add column deleted_at timestamptz;
alter table caseproof.cases add column legal_hold boolean not null default false;
create index cases_retention_due_idx on caseproof.cases(deleted_at,id)
 where deleted_at is not null and not legal_hold;

create table caseproof.retention_policy (
 singleton boolean primary key default true check(singleton),
 grace_days integer not null check(grace_days between 1 and 3650)
);
insert into caseproof.retention_policy values(true,30);
create table caseproof.erasure_receipts (
 matter_digest text primary key check(matter_digest ~ '^[0-9a-f]{64}$'),
 deleted_at timestamptz not null,
 purged_at timestamptz not null default clock_timestamp(),
 erased_audit_events bigint not null check(erased_audit_events>=0)
);
-- Deliberately retain no actor, org, filename, source hash, rationale, request
-- payload or original audit identifier. Digest is pseudonymous, not anonymous.
alter table caseproof.retention_policy enable row level security;
alter table caseproof.erasure_receipts enable row level security;
revoke all on caseproof.retention_policy,caseproof.erasure_receipts from public,anon,authenticated;

create policy retention_case_deny on caseproof.cases as restrictive
 for all to authenticated using(deleted_at is null) with check(deleted_at is null);
create policy retention_document_deny on caseproof.documents as restrictive
 for all to authenticated using(exists(select 1 from caseproof.cases c
 where c.org_id=documents.org_id and c.id=documents.case_id and c.deleted_at is null))
 with check(exists(select 1 from caseproof.cases c where c.org_id=documents.org_id
 and c.id=documents.case_id and c.deleted_at is null));

-- Serialize writes that have already passed a SECURITY DEFINER authorization
-- check against soft deletion. Never rely on RLS for privileged RPC writes.
create function caseproof.retention_write_guard() returns trigger
 language plpgsql security definer set search_path='' as $$
declare v_case uuid; v_deleted timestamptz;
begin
 if TG_TABLE_NAME='document_versions' then
  select d.case_id into v_case from caseproof.documents d
   where d.id=new.document_id and d.org_id=new.org_id;
 elsif TG_TABLE_NAME='ocr_geometry_sidecars' then
  select d.case_id into v_case from caseproof.document_versions v
   join caseproof.documents d on d.id=v.document_id and d.org_id=v.org_id
   where v.id=new.document_version_id;
 else v_case:=new.case_id;
 end if;
 select c.deleted_at into v_deleted from caseproof.cases c where c.id=v_case for share;
 if not found or v_deleted is not null then
  raise exception 'matter unavailable' using errcode='42501';
 end if;
 return new;
end $$;
revoke all on function caseproof.retention_write_guard() from public,anon,authenticated;
create trigger retention_write_guard before insert or update on caseproof.documents
 for each row execute function caseproof.retention_write_guard();
create trigger retention_write_guard before insert or update on caseproof.document_versions
 for each row execute function caseproof.retention_write_guard();
create trigger retention_write_guard before insert or update on caseproof.ocr_geometry_sidecars
 for each row execute function caseproof.retention_write_guard();
create trigger retention_write_guard before insert or update on caseproof._m1_matter_grants
 for each row execute function caseproof.retention_write_guard();
create trigger retention_write_guard before insert or update on caseproof._m1_exhibit_events
 for each row execute function caseproof.retention_write_guard();
create trigger retention_write_guard before insert or update on caseproof._m1_exhibit_heads
 for each row execute function caseproof.retention_write_guard();
create trigger retention_write_guard before insert or update on caseproof._m2_check_runs
 for each row execute function caseproof.retention_write_guard();
create trigger retention_write_guard before insert or update on caseproof._m2_review_events
 for each row execute function caseproof.retention_write_guard();
create trigger retention_write_guard before insert or update on caseproof._m2_review_receipts
 for each row execute function caseproof.retention_write_guard();
create trigger retention_write_guard before insert or update on caseproof._m2_review_heads
 for each row execute function caseproof.retention_write_guard();
create trigger retention_write_guard before insert or update on caseproof._m2_brief_versions
 for each row execute function caseproof.retention_write_guard();
create trigger retention_write_guard before insert or update on caseproof._m2_brief_references
 for each row execute function caseproof.retention_write_guard();
create trigger retention_write_guard before insert or update on caseproof._m2_brief_assertions
 for each row execute function caseproof.retention_write_guard();
create trigger retention_write_guard before insert or update on caseproof._m2_brief_events
 for each row execute function caseproof.retention_write_guard();
create trigger retention_write_guard before insert or update on caseproof._m2_brief_heads
 for each row execute function caseproof.retention_write_guard();
create trigger retention_write_guard before insert or update on caseproof._m2_correction_plans
 for each row execute function caseproof.retention_write_guard();
create trigger retention_write_guard before insert or update on caseproof._m2_correction_events
 for each row execute function caseproof.retention_write_guard();
create trigger retention_write_guard before insert or update on caseproof._dev_journey_sources
 for each row execute function caseproof.retention_write_guard();
create trigger retention_write_guard before insert or update on caseproof._dev_journey_parse_manifests
 for each row execute function caseproof.retention_write_guard();
create trigger retention_write_guard before insert or update on caseproof._phase4_reference_decisions
 for each row execute function caseproof.retention_write_guard();
create trigger retention_write_guard before insert or update on caseproof.audit_events
 for each row execute function caseproof.retention_write_guard();
create trigger retention_write_guard before insert or update on caseproof.idempotency_records
 for each row execute function caseproof.retention_write_guard();

create function public.caseproof_soft_delete_matter(p_case uuid) returns boolean
 language plpgsql security definer set search_path='' as $$
declare v caseproof.cases%rowtype; v_actor uuid:=auth.uid();
begin
 if v_actor is null or coalesce(auth.jwt()->>'role','')<>'authenticated'
 or coalesce(auth.jwt()->>'is_anonymous','false')='true' then
  raise exception 'matter unavailable' using errcode='42501'; end if;
 select * into v from caseproof.cases where id=p_case for update;
 if not found or v.created_by_user<>v_actor or not exists(
  select 1 from caseproof.organization_members m where m.org_id=v.org_id
  and m.user_id=v_actor and m.active and 'case:read'=any(m.actions))
 then raise exception 'matter unavailable' using errcode='42501'; end if;
 if v.deleted_at is not null then return true; end if;
 if not exists(select 1 from caseproof._m1_matter_grants g where g.org_id=v.org_id
  and g.case_id=v.id and g.user_id=v_actor and g.active and g.role='reviewer'
  and 'case:read'=any(g.permissions)) then
  raise exception 'matter unavailable' using errcode='42501'; end if;
 insert into caseproof.audit_events(org_id,case_id,actor_type,actor_user_id,action,
 event_schema_version,correlation_id,input_sha256_hex)
 values(v.org_id,v.id,'human',v_actor,'matter_soft_deleted','retention-v1',
 gen_random_uuid(),encode(sha256(convert_to(v.id::text,'UTF8')),'hex'));
 update caseproof._m1_matter_grants set active=false,revision=revision+1
  where org_id=v.org_id and case_id=v.id;
 update caseproof.cases set deleted_at=clock_timestamp(),updated_at=clock_timestamp()
  where id=v.id;
 return true;
end $$;
revoke all on function public.caseproof_soft_delete_matter(uuid) from public,anon,authenticated;
grant execute on function public.caseproof_soft_delete_matter(uuid) to authenticated;

-- The service cannot finalize until Storage's API has removed every object.
-- No SQL DELETE on storage.objects: that would orphan the actual bytes.
create function public.caseproof_retention(p_action text,p_case uuid default null)
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
  return jsonb_build_object('prefix',v.org_id::text||'/'||v.id::text||'/',
   'paths',(select coalesce(jsonb_agg(name),'[]'::jsonb) from storage.objects
    where bucket_id='caseproof-originals-dev' and name like v.org_id::text||'/'||v.id::text||'/%'));
 end if;
 if p_action<>'finalize' then raise exception 'unsupported retention action'; end if;
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

-- Exact-run development acceptance helper, not a general timestamp editor.
create function public.caseproof_retention_test(p_run uuid,p_case uuid,p_action text)
 returns jsonb language plpgsql security definer set search_path='' as $$
declare v_org uuid; v_count bigint; v_digest text;
begin
 if coalesce(auth.jwt()->>'role','')<>'service_role' then
  raise exception 'service role required' using errcode='42501'; end if;
 select f.org_id into v_org from caseproof._dev_journey_fixtures f
 where f.run_id=p_run and exists(select 1 from caseproof.test_run_registry r
  where r.run_id=p_run and r.resource_type='matter' and r.resource_id=p_case::text);
 if v_org is null then raise exception 'exact ephemeral run required' using errcode='42501'; end if;
 if p_action='age' then
  update caseproof.cases set deleted_at=now()-interval '31 days'
   where org_id=v_org and id=p_case and deleted_at is not null;
  if not found then raise exception 'soft-deleted fixture required'; end if;
  return 'true'::jsonb;
 end if;
 if p_action<>'verify' then raise exception 'unsupported test action'; end if;
 select count(*) into v_count from (
  select id from caseproof.cases where org_id=v_org and id=p_case
  union all select id from caseproof.documents where org_id=v_org and case_id=p_case
  union all select case_id from caseproof._phase4_reference_decisions where org_id=v_org and case_id=p_case
  union all select case_id from caseproof.audit_events where org_id=v_org and case_id=p_case
 ) q;
 v_digest:=encode(sha256(convert_to(p_case::text,'UTF8')),'hex');
 return jsonb_build_object('residual_rows',v_count,'receipt',
  (select to_jsonb(r) from caseproof.erasure_receipts r where matter_digest=v_digest));
end $$;
revoke all on function public.caseproof_retention_test(uuid,uuid,text) from public,anon,authenticated;
grant execute on function public.caseproof_retention_test(uuid,uuid,text) to service_role;
