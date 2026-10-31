-- REVIEW PROPOSAL ONLY. Not an installed migration or deployment authorization.
-- Two-phase draft revisions. Runtime tables remain inaccessible directly.
create table caseproof.dossier_draft_revisions (
 org_id uuid not null,
 case_id uuid not null,
 request_id uuid not null,
 actor_id uuid not null,
 document_id uuid not null,
 parent_version_id uuid not null,
 version_id uuid not null,
 parent_snapshot_hash text not null check(parent_snapshot_hash ~ '^[0-9a-f]{64}$'),
 reference_id text not null check(length(reference_id) between 1 and 256),
 command_sha256 text not null check(command_sha256 ~ '^[0-9a-f]{64}$'),
 original_sha256 text not null check(original_sha256 ~ '^[0-9a-f]{64}$'),
 byte_length bigint not null check(byte_length between 1 and 5242880),
 state text not null default 'reserved' check(state in ('reserved','active')),
 created_at timestamptz not null default clock_timestamp(),
 activated_at timestamptz,
 primary key(org_id,case_id,actor_id,request_id),
 unique(org_id,version_id),
 foreign key(org_id,case_id) references caseproof.cases(org_id,id) on delete cascade,
 foreign key(org_id,document_id) references caseproof.documents(org_id,id) on delete cascade,
 foreign key(org_id,parent_version_id) references caseproof.document_versions(org_id,id) on delete cascade,
 foreign key(org_id,version_id) references caseproof.document_versions(org_id,id) on delete cascade,
 check((state='active') = (activated_at is not null))
);
alter table caseproof.dossier_draft_revisions enable row level security;
revoke all on caseproof.dossier_draft_revisions from public,anon,authenticated;
create index dossier_draft_revision_parent_idx
 on caseproof.dossier_draft_revisions(org_id,case_id,parent_version_id,state);
create unique index dossier_one_active_child_idx
 on caseproof.dossier_draft_revisions(org_id,case_id,parent_version_id)
 where state='active';
create trigger retention_write_guard before insert or update
 on caseproof.dossier_draft_revisions for each row
 execute function caseproof.retention_write_guard();

-- Current signature ignores pending children and superseded parents.
create function caseproof.dossier_current_signature(p_org uuid,p_case uuid)
returns text language sql stable security invoker set search_path='' as $$
 select encode(sha256(convert_to(jsonb_agg(jsonb_build_object(
 'document_id',d.id,'version_id',dv.id,'sha256',dv.original_sha256_hex,
 'role',dv.bundle_role,'label',d.source_label,'byte_length',dv.byte_length,'media_type',dv.media_type
 ) order by dv.id)::text,'UTF8')),'hex')
 from caseproof.documents d join caseproof.document_versions dv
 on dv.document_id=d.id and dv.org_id=d.org_id
 where d.org_id=p_org and d.case_id=p_case
 and not exists(select 1 from caseproof.dossier_draft_revisions r
   where r.org_id=p_org and r.case_id=p_case and
   ((r.version_id=dv.id and r.state='reserved') or (r.parent_version_id=dv.id and r.state='active')))
$$;
revoke all on function caseproof.dossier_current_signature(uuid,uuid) from public,anon,authenticated;

create function public.caseproof_dossier_draft_reserve(p_case uuid,p_request uuid,p_action text,p_data jsonb)
returns jsonb language plpgsql security definer set search_path='' as $$
declare a uuid:=auth.uid(); o uuid; r caseproof.dossier_draft_revisions%rowtype;
 s caseproof.dossier_snapshots%rowtype; parent caseproof.document_versions%rowtype;
 v uuid; n bigint; command text:=p_data->>'command_sha256';
begin
 if a is null or coalesce(auth.jwt()->>'role','')<>'authenticated'
 or coalesce(auth.jwt()->>'is_anonymous','false')='true' or p_request is null
 or p_action not in ('status','reserve') or command is null or command !~ '^[0-9a-f]{64}$'
 then raise exception 'unavailable' using errcode='42501'; end if;
 select c.org_id into o from caseproof.cases c
 join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=a and m.active
 and m.actions @> array['case:read','evidence:read','finding:write','review:request']::text[]
 join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id and g.user_id=a
 and g.active and g.role='reviewer'
 and g.permissions @> array['case:read','evidence:read','evidence:upload','draft:check','review:request']::text[]
 where c.id=p_case and c.deleted_at is null for update of c;
 if o is null then raise exception 'unavailable' using errcode='42501'; end if;
 select * into r from caseproof.dossier_draft_revisions
 where org_id=o and case_id=p_case and actor_id=a and request_id=p_request;
 if found then
  if r.command_sha256<>command then raise exception 'command conflict' using errcode='23505'; end if;
  return to_jsonb(r)||jsonb_build_object('replayed',true);
 end if;
 if p_action='status' then return jsonb_build_object('state','absent'); end if;
 perform public.caseproof_dossier(p_case,'decisions',jsonb_build_object('snapshot_hash',p_data->>'snapshot_hash'));
 select * into strict s from caseproof.dossier_snapshots where org_id=o and case_id=p_case
 and snapshot_hash=p_data->>'snapshot_hash';
 if s.serialized::jsonb->>'brief_id' is distinct from p_data->>'parent_version_id'
 or not exists(select 1 from caseproof._phase4_reference_decisions d
 where d.org_id=o and d.case_id=p_case and d.snapshot_sha=s.snapshot_hash
 and d.reference_id=p_data->>'reference_id' and d.actor_id=a)
 then raise exception 'review required' using errcode='42501'; end if;
 select * into strict parent from caseproof.document_versions
 where org_id=o and id=(p_data->>'parent_version_id')::uuid and bundle_role='draft';
 if parent.original_sha256_hex is distinct from p_data->>'parent_sha256'
 or p_data->>'sha256' is null or p_data->>'sha256' !~ '^[0-9a-f]{64}$'
 or coalesce((p_data->>'byte_length')::bigint,0) not between 1 and 5242880
 then raise exception 'invalid source' using errcode='22023'; end if;
 select max(version_number)+1 into n from caseproof.document_versions where org_id=o and document_id=parent.document_id;
 v:=gen_random_uuid();
 insert into caseproof.document_versions(id,org_id,document_id,version_number,original_sha256_hex,byte_length,media_type,bundle_role)
 values(v,o,parent.document_id,n,p_data->>'sha256',(p_data->>'byte_length')::bigint,parent.media_type,'draft');
 insert into caseproof.dossier_draft_revisions(org_id,case_id,request_id,actor_id,document_id,parent_version_id,
 version_id,parent_snapshot_hash,reference_id,command_sha256,original_sha256,byte_length)
 values(o,p_case,p_request,a,parent.document_id,parent.id,v,s.snapshot_hash,p_data->>'reference_id',command,p_data->>'sha256',(p_data->>'byte_length')::bigint)
 returning * into r;
 insert into caseproof.audit_events(org_id,case_id,actor_type,actor_user_id,action,event_schema_version,correlation_id,input_sha256_hex)
 values(o,p_case,'human',a,'dossier_draft_reserved','dossier-correction-v1',p_request,command);
 return to_jsonb(r)||jsonb_build_object('replayed',false);
end $$;
revoke all on function public.caseproof_dossier_draft_reserve(uuid,uuid,text,jsonb) from public,anon,authenticated;
grant execute on function public.caseproof_dossier_draft_reserve(uuid,uuid,text,jsonb) to authenticated;

-- Only a trusted server may attest to a freshly signed private Storage readback.
create function public.caseproof_dossier_draft_activate(p_actor uuid,p_case uuid,p_request uuid,p_sha256 text,p_length bigint)
returns jsonb language plpgsql security definer set search_path='' as $$
declare o uuid; r caseproof.dossier_draft_revisions%rowtype; s caseproof.dossier_snapshots%rowtype; latest uuid;
begin
 if coalesce(auth.jwt()->>'role','')<>'service_role' or p_actor is null
 then raise exception 'trusted server required' using errcode='42501'; end if;
 select c.org_id into o from caseproof.cases c
 join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=p_actor and m.active
 and m.actions @> array['case:read','evidence:read','finding:write','review:request']::text[]
 join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id and g.user_id=p_actor
 and g.active and g.role='reviewer'
 and g.permissions @> array['case:read','evidence:read','evidence:upload','draft:check','review:request']::text[]
 where c.id=p_case and c.deleted_at is null for update of c;
 if o is null then raise exception 'unavailable' using errcode='42501'; end if;
 select * into strict r from caseproof.dossier_draft_revisions
 where org_id=o and case_id=p_case and actor_id=p_actor and request_id=p_request for update;
 if r.original_sha256 is distinct from p_sha256 or r.byte_length is distinct from p_length
 then raise exception 'readback mismatch' using errcode='22023'; end if;
 if r.state='active' then return to_jsonb(r)||jsonb_build_object('replayed',true); end if;
 select * into strict s from caseproof.dossier_snapshots where org_id=o and case_id=p_case and snapshot_hash=r.parent_snapshot_hash;
 select request_id into latest from caseproof.dossier_confirmations
 where org_id=o and case_id=p_case and bundle_signature=s.bundle_signature order by created_at desc,request_id desc limit 1;
 if s.bundle_signature is distinct from caseproof.dossier_current_signature(o,p_case)
 or s.confirmation_id is distinct from latest
 then raise exception 'stale parent' using errcode='23505'; end if;
 update caseproof.dossier_draft_revisions set state='active',activated_at=clock_timestamp()
 where org_id=o and case_id=p_case and actor_id=p_actor and request_id=p_request returning * into r;
 insert into caseproof.audit_events(org_id,case_id,actor_type,actor_user_id,action,event_schema_version,correlation_id,input_sha256_hex)
 values(o,p_case,'human',p_actor,'dossier_draft_activated','dossier-correction-v1',p_request,r.command_sha256);
 return to_jsonb(r)||jsonb_build_object('replayed',false);
end $$;
revoke all on function public.caseproof_dossier_draft_activate(uuid,uuid,uuid,text,bigint) from public,anon,authenticated;
grant execute on function public.caseproof_dossier_draft_activate(uuid,uuid,uuid,text,bigint) to service_role;

-- Preserve the installed registration receipt; overlay the active version at read time.
alter function public.caseproof_dev_bundle_manifest(uuid) rename to caseproof_dev_bundle_manifest_original;
revoke all on function public.caseproof_dev_bundle_manifest_original(uuid) from public,anon,authenticated;
create function public.caseproof_dev_bundle_manifest(p_case uuid)
returns jsonb language plpgsql security definer set search_path='' as $$
declare m jsonb; rows jsonb:='[]'::jsonb; item jsonb; v record;
begin
 m:=public.caseproof_dev_bundle_manifest_original(p_case);
 for item in select value from jsonb_array_elements(m->'sources') loop
  if item->>'role'='draft' then
   select dv.* into v from caseproof.document_versions dv
   join caseproof.dossier_draft_revisions r on r.org_id=dv.org_id and r.version_id=dv.id
   where r.case_id=p_case and r.document_id=(item->>'document_id')::uuid and r.state='active'
   order by dv.version_number desc limit 1;
   if found then item:=item||jsonb_build_object('version_id',v.id,'version_number',v.version_number,
     'sha256',v.original_sha256_hex,'byte_length',v.byte_length); end if;
  end if;
  rows:=rows||jsonb_build_array(item);
 end loop;
 return m||jsonb_build_object('sources',rows);
end $$;
revoke all on function public.caseproof_dev_bundle_manifest(uuid) from public,anon,authenticated;
grant execute on function public.caseproof_dev_bundle_manifest(uuid) to authenticated;

-- Existing RPC, with current-version signature semantics.
create or replace function public.caseproof_dossier(p_case uuid,p_action text,p_data jsonb default '{}'::jsonb)
 returns jsonb language plpgsql security definer set search_path='' as $$
declare v_actor uuid:=auth.uid(); v_org uuid; v_signature text; v_confirm caseproof.dossier_confirmations%rowtype;
 v_request uuid; v_payload jsonb; v_hash text; v_serial text; v_snapshot caseproof.dossier_snapshots%rowtype;
 v_decision caseproof._phase4_reference_decisions%rowtype; v_brief uuid; v_entry jsonb;
 v_expected jsonb; v_reviewed jsonb;
begin
 if v_actor is null or coalesce(auth.jwt()->>'role','')<>'authenticated'
 or coalesce(auth.jwt()->>'is_anonymous','false')='true' or p_case is null
 or p_action not in ('context','confirm','snapshot','review','decisions')
 then raise exception 'matter unavailable' using errcode='42501'; end if;
 select c.org_id into v_org from caseproof.cases c
 join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=v_actor and m.active
 and m.actions @> array['case:read','evidence:read']::text[]
 join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id and g.user_id=v_actor
 and g.active and g.permissions @> array['case:read','evidence:read']::text[]
 where c.id=p_case and c.deleted_at is null for update of c;
 if v_org is null then raise exception 'matter unavailable' using errcode='42501'; end if;
 v_signature:=caseproof.dossier_current_signature(v_org,p_case);
 if v_signature is null then raise exception 'source bundle unavailable' using errcode='42501'; end if;
 select * into v_confirm from caseproof.dossier_confirmations
 where org_id=v_org and case_id=p_case and bundle_signature=v_signature
 order by created_at desc,request_id desc limit 1;
 if p_action='context' then
  return jsonb_build_object('bundle_signature',v_signature,'confirmation',
   case when v_confirm.request_id is null then null else jsonb_build_object(
    'request_id',v_confirm.request_id,'payload',v_confirm.payload,
    'reviewer_id',v_confirm.actor_id,'timestamp',v_confirm.created_at) end);
 end if;
 if p_action in ('confirm','review') and (not exists(
  select 1 from caseproof.organization_members m where m.org_id=v_org and m.user_id=v_actor
  and m.active and 'review:request'=any(m.actions)) or not exists(
  select 1 from caseproof._m1_matter_grants g where g.org_id=v_org and g.case_id=p_case
  and g.user_id=v_actor and g.active and g.role='reviewer' and 'review:request'=any(g.permissions)))
 then raise exception 'review permission required' using errcode='42501'; end if;
 if p_action='confirm' then
  if p_data->>'bundle_signature' is distinct from v_signature then
   raise exception 'source bundle changed' using errcode='23505'; end if;
  v_request:=(p_data->>'request_id')::uuid; v_payload:=p_data->'payload';
  if v_request is null or jsonb_typeof(v_payload->'inventory_complete') is distinct from 'boolean'
  or jsonb_typeof(v_payload->'entries') is distinct from 'array'
  or jsonb_array_length(v_payload->'entries')>512 then raise exception 'invalid confirmation'; end if;
  for v_entry in select value from jsonb_array_elements(v_payload->'entries') loop
   if v_entry->>'label' not in ('stuk','piece') or v_entry->>'number' !~ '^[0-9]{1,4}(bis|ter)?$'
   or jsonb_typeof(v_entry->'pages') is distinct from 'array' then raise exception 'invalid identity'; end if;
   if v_entry->>'source_version_id' is not null and not exists(
    select 1 from caseproof.documents d join caseproof.document_versions dv on dv.document_id=d.id and dv.org_id=d.org_id
    where d.org_id=v_org and d.case_id=p_case and dv.id=(v_entry->>'source_version_id')::uuid and dv.bundle_role='exhibit')
   then raise exception 'source outside matter' using errcode='42501'; end if;
  end loop;
  insert into caseproof.dossier_confirmations(org_id,case_id,request_id,bundle_signature,payload,actor_id)
   values(v_org,p_case,v_request,v_signature,v_payload,v_actor) on conflict do nothing;
  select * into v_confirm from caseproof.dossier_confirmations where org_id=v_org and case_id=p_case and request_id=v_request;
  if v_confirm.bundle_signature is distinct from v_signature or v_confirm.payload is distinct from v_payload
   or v_confirm.actor_id is distinct from v_actor then raise exception 'confirmation replay conflict' using errcode='23505'; end if;
  return jsonb_build_object('request_id',v_request,'reviewer_id',v_actor);
 end if;
 v_hash:=p_data->>'snapshot_hash';
 if v_hash is null or v_hash !~ '^[0-9a-f]{64}$' then raise exception 'invalid snapshot'; end if;
 if p_action='snapshot' then
  v_serial:=p_data->>'serialized'; v_payload:=v_serial::jsonb;
  if octet_length(v_serial)>2000000 or encode(sha256(convert_to(v_serial,'UTF8')),'hex')<>v_hash
  or v_payload->>'case_id' is distinct from p_case::text
  or v_payload->>'bundle_signature' is distinct from v_signature
  or v_payload->>'confirmation_id' is distinct from v_confirm.request_id::text
  then raise exception 'stale snapshot' using errcode='23505'; end if;
  v_brief:=(v_payload->>'brief_id')::uuid;
  if not exists(select 1 from caseproof.document_versions dv join caseproof.documents d on d.id=dv.document_id and d.org_id=dv.org_id
    where dv.id=v_brief and d.case_id=p_case and d.org_id=v_org and dv.bundle_role='draft')
  then raise exception 'draft outside matter' using errcode='42501'; end if;
  insert into caseproof.dossier_snapshots(org_id,case_id,snapshot_hash,bundle_signature,confirmation_id,serialized)
   values(v_org,p_case,v_hash,v_signature,v_confirm.request_id,v_serial) on conflict do nothing;
  return jsonb_build_object('snapshot_hash',v_hash);
 end if;
 select * into v_snapshot from caseproof.dossier_snapshots where org_id=v_org and case_id=p_case and snapshot_hash=v_hash;
 if not found or v_snapshot.bundle_signature is distinct from v_signature
  or v_snapshot.confirmation_id is distinct from v_confirm.request_id then
  raise exception 'stale dossier' using errcode='23505'; end if;
 v_payload:=v_snapshot.serialized::jsonb; v_brief:=(v_payload->>'brief_id')::uuid;
 if p_action='decisions' then
  return jsonb_build_object('decisions',(select coalesce(jsonb_agg(jsonb_build_object(
  'reference_id',reference_id,'decision',decision,'rationale',rationale,'reviewer_id',actor_id,
  'request_id',request_id,'timestamp',created_at,'reviewed_region_ids',reviewed_region_ids) order by created_at,request_id),'[]'::jsonb)
  from caseproof._phase4_reference_decisions where org_id=v_org and case_id=p_case and snapshot_sha=v_hash));
 end if;
 if not exists(select 1 from jsonb_array_elements(v_payload->'findings') f where f->>'reference_id'=p_data->>'reference_id'
  and (p_data->>'decision'<>'CONFIRMED_SUPPORTED' or f->>'technical_check'='checked'))
 or p_data->>'decision' not in ('CONFIRMED_SUPPORTED','CONFIRMED_QUALIFIED','CONFIRMED_CONTRADICTED')
 or length(p_data->>'rationale') not between 1 and 2000 then raise exception 'invalid review'; end if;
 -- Authoritative attestation check: direct authenticated RPC callers must
 -- inspect exactly the selected regions in the immutable finding snapshot.
 select coalesce(jsonb_agg(x.region_id order by x.region_id),'[]'::jsonb) into v_expected
 from (select distinct r->>'region_id' as region_id
       from jsonb_array_elements(v_payload->'findings') f,
       lateral jsonb_array_elements(coalesce(f->'visual_assessment'->'regions','[]'::jsonb)) r
       where f->>'reference_id'=p_data->>'reference_id') x;
 if p_data ? 'reviewed_region_ids' and
    (jsonb_typeof(p_data->'reviewed_region_ids') is distinct from 'array') then
   raise exception 'invalid visual attestation'; end if;
 if jsonb_array_length(coalesce(p_data->'reviewed_region_ids','[]'::jsonb))>96 then
   raise exception 'visual attestation budget'; end if;
 if exists(select 1 from jsonb_array_elements(coalesce(p_data->'reviewed_region_ids','[]'::jsonb)) x
           where jsonb_typeof(x) is distinct from 'string' or (x#>>'{}') !~ '^[0-9a-f]{64}$') then
   raise exception 'invalid visual region'; end if;
 select coalesce(jsonb_agg(x.region_id order by x.region_id),'[]'::jsonb) into v_reviewed
 from (select distinct value#>>'{}' as region_id
       from jsonb_array_elements(coalesce(p_data->'reviewed_region_ids','[]'::jsonb))) x;
 if v_reviewed is distinct from v_expected then
   raise exception 'visual regions must be inspected' using errcode='23505'; end if;
 v_request:=(p_data->>'request_id')::uuid;
 insert into caseproof._phase4_reference_decisions(org_id,case_id,brief_version_id,snapshot_sha,reference_id,request_id,actor_id,decision,rationale,reviewed_region_ids)
 values(v_org,p_case,v_brief,v_hash,p_data->>'reference_id',v_request,v_actor,p_data->>'decision',p_data->>'rationale',v_reviewed) on conflict do nothing;
 select * into v_decision from caseproof._phase4_reference_decisions where org_id=v_org and case_id=p_case and request_id=v_request;
 if v_decision.snapshot_sha is distinct from v_hash or v_decision.reference_id is distinct from p_data->>'reference_id'
 or v_decision.decision is distinct from p_data->>'decision' or v_decision.rationale is distinct from p_data->>'rationale'
 or v_decision.reviewed_region_ids is distinct from v_reviewed
 or v_decision.actor_id is distinct from v_actor then raise exception 'review replay conflict' using errcode='23505'; end if;
 return jsonb_build_object('request_id',v_request,'reviewer_id',v_actor,'reference_id',v_decision.reference_id,'decision',v_decision.decision);
end $$;
revoke all on function public.caseproof_dossier(uuid,text,jsonb) from public,anon,authenticated;
grant execute on function public.caseproof_dossier(uuid,text,jsonb) to authenticated;
