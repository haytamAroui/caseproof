-- F6: private, immutable, bounded reviewed output ledger for the development
-- delivery path. Database and browser never accept an artifact as legal truth.
-- The only authoring surface is a narrowly scoped signed-user function.
begin;

alter table caseproof.organization_members drop constraint organization_members_actions_check;
alter table caseproof.organization_members add constraint organization_members_actions_check
  check(actions <@ array[
    'case:read','case:create','coverage:read','evidence:read',
    'finding:write','review:request','conclusion:request_approval',
    'exception:request','draft:write','export:request'
  ]::text[]);
alter table caseproof._m1_matter_grants drop constraint _m1_matter_grants_permissions_check;
alter table caseproof._m1_matter_grants add constraint _m1_matter_grants_permissions_check
  check(permissions <@ array[
    'case:read','coverage:read','evidence:read','review:request','finding:write',
    'evidence:upload','evidence:index','exhibit:confirm','draft:check','draft:write',
    'export:request'
  ]::text[]);

create table caseproof.dossier_releases (
  org_id uuid not null,
  case_id uuid not null,
  release_id uuid not null,
  actor_id uuid not null,
  brief_id uuid not null,
  snapshot_hash text not null check(snapshot_hash ~ '^[0-9a-f]{64}$'),
  manifest jsonb not null,
  -- Bounded ZIP, Markdown and JSON. Private TOASTed bytes; no public bucket,
  -- direct table select or client-controlled put/upsert.
  artifacts jsonb not null,
  created_at timestamptz not null default clock_timestamp(),
  primary key (org_id, case_id, release_id),
  foreign key (org_id, case_id)
    references caseproof.cases(org_id,id) on delete cascade,
  check(octet_length(artifacts::text) between 1 and 15000000),
  check(octet_length(manifest::text) between 1 and 2000000)
);
create index dossier_releases_history_idx on caseproof.dossier_releases
  (org_id,case_id,brief_id,created_at desc,release_id);
alter table caseproof.dossier_releases enable row level security;
revoke all on caseproof.dossier_releases from public, anon, authenticated;
create trigger retention_write_guard before insert or update on caseproof.dossier_releases
 for each row execute function caseproof.retention_write_guard();

create function public.caseproof_dossier_export_release(
  p_case uuid, p_action text, p_export uuid default null,
  p_data jsonb default '{}'::jsonb, p_actor uuid default null
) returns jsonb language plpgsql security definer set search_path='' as $$
declare
 a uuid := auth.uid();
 v_role text := coalesce(auth.jwt()->>'role','');
 o uuid;
 row_record caseproof.dossier_releases%rowtype;
 v_manifest jsonb;
 v_contents jsonb;
 v_snapshot jsonb;
 v_report jsonb;
 v_reviews jsonb;
 v_sources jsonb;
 v_format text;
 v_encoded text;
 v_raw bytea;
 v_digest text;
 v_info jsonb;
 v_brief uuid;
 v_current_draft_count integer;
 v_requested_draft_count integer;
 v_signature text;
 v_latest_confirmation uuid;
begin
 -- Release writes require a server-verified signed actor plus the trusted
 -- backend service key. Browser JWTs cannot forge release bytes or HMACs.
 if p_action='release' then
   if v_role <> 'service_role' or p_actor is null then
     raise exception 'trusted release service required' using errcode='42501';
   end if;
   a := p_actor;
 elsif v_role <> 'authenticated'
       or coalesce(auth.jwt()->>'is_anonymous','false')='true'
       or p_actor is not null then
   raise exception 'release unavailable' using errcode='42501';
 end if;
 if a is null or p_case is null
    or p_action not in ('authorize','status','list','artifact','release')
    or p_data is null or jsonb_typeof(p_data)<>'object' then
   raise exception 'release unavailable' using errcode='42501';
 end if;

 -- Export has its OWN permission, separate from read/review and draft write.
 select c.org_id into o from caseproof.cases c
 join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=a
 and m.active and m.actions @> array['case:read','evidence:read','export:request']::text[]
 join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id and g.user_id=a
 and g.active and g.permissions @> array['case:read','evidence:read','export:request']::text[]
 -- Acquire the case write lock BEFORE invoking the snapshot helper (which
 -- also locks the same case). Two simultaneous releases must not each hold
 -- SHARE then deadlock while upgrading to UPDATE.
 where c.id=p_case and c.deleted_at is null for update of c for share of m,g;
 if o is null then raise exception 'release unavailable' using errcode='42501'; end if;

 if p_action='authorize' then return jsonb_build_object('authorized',true); end if;

 if p_action='list' then
   begin v_brief:=(p_data->>'brief_id')::uuid;
   exception when others then raise exception 'invalid release scope' using errcode='42501'; end;
   if v_brief is null then raise exception 'invalid release scope' using errcode='42501'; end if;
   return jsonb_build_object('releases', coalesce((
     select jsonb_agg(jsonb_build_object(
       'state','released','release_id',q.release_id,'brief_id',q.brief_id,
       'snapshot_hash',q.snapshot_hash,'created_at',q.created_at,'manifest',q.manifest
     ) order by q.created_at desc,q.release_id desc)
     from (select release_id,brief_id,snapshot_hash,created_at,manifest
       from caseproof.dossier_releases where org_id=o and case_id=p_case
       and brief_id=v_brief order by created_at desc,release_id desc limit 50) q
   ), '[]'::jsonb));
 end if;
 if p_export is null then raise exception 'release identifier required' using errcode='42501'; end if;

 select * into row_record from caseproof.dossier_releases
 where org_id=o and case_id=p_case and release_id=p_export;
 if p_action='status' then
   -- Recovery status is actor-specific. Historical list and binary retrieval
   -- are intentionally available to any currently authorized exporter.
   if not found or row_record.actor_id is distinct from a then
     return jsonb_build_object('state','absent');
   end if;
   return jsonb_build_object('state','released','release_id',p_export,
      'brief_id',row_record.brief_id,'snapshot_hash',row_record.snapshot_hash,
      'manifest',row_record.manifest,'created_at',row_record.created_at);
 end if;
 if p_action='artifact' then
   v_format:=p_data->>'format';
   if not found or v_format not in ('json','markdown','docx') then
     raise exception 'release unavailable' using errcode='42501'; end if;
   return jsonb_build_object('manifest',row_record.manifest,
      'content_base64',row_record.artifacts->>v_format);
 end if;

 v_manifest:=p_data->'manifest';
 v_contents:=p_data->'contents';
 if jsonb_typeof(v_manifest)<>'object' or jsonb_typeof(v_contents)<>'object'
 or v_manifest->>'schema' is distinct from 'caseproof-reviewed-release-v1'
 or v_manifest->>'case_id' is distinct from p_case::text
 or v_manifest->>'release_id' is distinct from p_export::text
 or v_manifest->>'snapshot_hash' !~ '^[0-9a-f]{64}$'
 or v_manifest->>'server_receipt' !~ '^[0-9a-f]{64}$'
 or v_manifest->>'manifest_sha256' !~ '^[0-9a-f]{64}$'
 or jsonb_typeof(v_manifest->'artifacts') <> 'object'
 or jsonb_typeof(p_data->'human_decisions') <> 'array'
 or (select count(*) from jsonb_object_keys(v_contents)) <> 3
 then raise exception 'invalid release manifest' using errcode='42501'; end if;

 -- Same idempotency key may only replay an identical frozen manifest.
 if row_record.release_id is not null then
   if row_record.actor_id is distinct from a
   or row_record.manifest is distinct from v_manifest
   then raise exception 'release replay conflict' using errcode='23505'; end if;
   return jsonb_build_object('state','released','release_id',p_export,
       'brief_id',row_record.brief_id,'snapshot_hash',row_record.snapshot_hash,
       'manifest',row_record.manifest,'created_at',row_record.created_at);
 end if;

 -- Bounded per-matter private release storage. Already-released operation IDs
 -- have been reconciled above, so they do not consume quota on retries.
 -- The case row is locked before this check, fencing competing inserts.
 if (select count(*) from caseproof.dossier_releases
     where org_id=o and case_id=p_case) >= 50 then
   raise exception 'release capacity reached' using errcode='23505';
 end if;

 -- Release runs as a trusted server role, so do not call the user-only
 -- snapshot RPC. Instead reproduce its current bundle + confirmation fence
 -- against the preserved snapshot under this transaction's case row lock.
 select jsonb_build_object('serialized',s.serialized),s.bundle_signature
   into v_snapshot,v_signature
 from caseproof.dossier_snapshots s
 where s.org_id=o and s.case_id=p_case
   and s.snapshot_hash=v_manifest->>'snapshot_hash';
 if not found then raise exception 'snapshot unavailable' using errcode='23505'; end if;
 select request_id into v_latest_confirmation
 from caseproof.dossier_confirmations c
 where c.org_id=o and c.case_id=p_case and c.bundle_signature=v_signature
 order by c.created_at desc,c.request_id desc limit 1;
 if v_signature is distinct from caseproof.dossier_current_signature(o,p_case)
   or v_latest_confirmation::text is distinct from v_manifest->>'confirmation_id'
   or v_latest_confirmation is null then
   raise exception 'stale confirmation or source bundle' using errcode='23505';
 end if;
 v_report:=(v_snapshot->>'serialized')::jsonb;
 begin v_brief:=(v_manifest->>'brief_id')::uuid;
 exception when others then raise exception 'invalid draft' using errcode='42501'; end;
 if v_report->>'case_id' is distinct from p_case::text
 or v_report->>'brief_id' is distinct from v_brief::text
 or v_report->>'bundle_signature' is distinct from v_manifest->>'bundle_signature'
 or v_report->>'confirmation_id' is distinct from v_manifest->>'confirmation_id'
 then raise exception 'stale reviewed draft release' using errcode='23505'; end if;
 -- Only the exactly active draft is releasable. An old draft row can exist
 -- indefinitely after activation; existence alone must not authorize it.
 select count(*),count(*) filter(where dv.id=v_brief)
 into v_current_draft_count,v_requested_draft_count
 from caseproof.documents d
 join caseproof.document_versions dv
   on dv.document_id=d.id and dv.org_id=d.org_id
 where d.org_id=o and d.case_id=p_case and dv.bundle_role='draft'
   and not exists (
     select 1 from caseproof.dossier_draft_revisions dr
     where dr.org_id=o and dr.case_id=p_case
       and ((dr.version_id=dv.id and dr.state='reserved')
         or (dr.parent_version_id=dv.id and dr.state='active'))
   );
 if v_current_draft_count <> 1 or v_requested_draft_count <> 1 then
   raise exception 'superseded draft cannot be released' using errcode='23505';
 end if;
 select coalesce(jsonb_agg(jsonb_build_object(
   'reference_id',reference_id,'decision',decision,'rationale',rationale,
   'reviewer_id',actor_id,'request_id',request_id,'timestamp',created_at,
   'reviewed_region_ids',reviewed_region_ids
 ) order by created_at,request_id),'[]'::jsonb) into v_reviews
 from caseproof._phase4_reference_decisions
 where org_id=o and case_id=p_case and snapshot_sha=v_manifest->>'snapshot_hash';
 if v_reviews <> p_data->'human_decisions' or jsonb_array_length(v_reviews)<1
 or (v_manifest->>'review_count')::integer <> jsonb_array_length(v_reviews)
 then raise exception 'stale or absent human review' using errcode='23505'; end if;
 select coalesce(jsonb_agg(jsonb_build_object(
   'role',e.value->>'role','version_id',e.value->>'version_id',
   'sha256',e.value->>'sha256') order by e.ordinality),'[]'::jsonb)
 into v_sources from jsonb_array_elements(v_report->'sources') with ordinality e(value,ordinality);
 if v_sources is distinct from v_manifest->'sources' then
   raise exception 'changed source lineage' using errcode='23505'; end if;

 for v_format in select unnest(array['json','markdown','docx']) loop
   v_encoded:=v_contents->>v_format;
   v_info:=v_manifest->'artifacts'->v_format;
   if v_encoded is null or v_info is null or length(v_encoded)>7500000 then
     raise exception 'missing or oversized release bytes' using errcode='42501'; end if;
   begin v_raw:=decode(v_encoded,'base64');
   exception when others then raise exception 'invalid release bytes' using errcode='42501'; end;
   if octet_length(v_raw)<1
    or octet_length(v_raw) > (case when v_format='docx' then 5242880 else 2000000 end)
    or (v_info->>'byte_length')::integer is distinct from octet_length(v_raw)
    or (v_info->>'sha256') is distinct from encode(extensions.digest(v_raw,'sha256'),'hex')
   then raise exception 'artifact integrity failure' using errcode='42501'; end if;
 end loop;
 insert into caseproof.dossier_releases(
   org_id,case_id,release_id,actor_id,brief_id,snapshot_hash,manifest,artifacts
 ) values(o,p_case,p_export,a,v_brief,v_manifest->>'snapshot_hash',v_manifest,v_contents);
 return jsonb_build_object('state','released','release_id',p_export,
   'brief_id',v_brief,'snapshot_hash',v_manifest->>'snapshot_hash','manifest',v_manifest);
end $$;

-- Development-only fixture setup. Only the service-role wrapper may toggle
-- the exact owner/case registered by the ephemeral run. A regular user or an
-- unrelated service-role case ID cannot acquire another actor's export grant.
create function public.caseproof_f6_fixture_export_grant(
 p_run uuid,p_owner uuid,p_case uuid,p_enable boolean
) returns boolean language plpgsql security definer set search_path='' as $
declare o uuid;
begin
 if coalesce(auth.jwt()->>'role','') <> 'service_role'
   or p_run is null or p_owner is null or p_case is null or p_enable is null then
   raise exception 'test grant unavailable' using errcode='42501';
 end if;
 select c.org_id into o
 from caseproof._dev_journey_fixtures f
 join caseproof.cases c on c.org_id=f.org_id and c.id=p_case
 where f.run_id=p_run and f.owner_id=p_owner
   and c.created_by_user=p_owner and c.deleted_at is null
 for update of c;
 if o is null then raise exception 'test grant unavailable' using errcode='42501'; end if;
 if not exists (
   select 1 from caseproof.organization_members m
   where m.org_id=o and m.user_id=p_owner and m.active
 ) or not exists (
   select 1 from caseproof._m1_matter_grants g
   where g.org_id=o and g.case_id=p_case and g.user_id=p_owner and g.active
 ) then raise exception 'test owner grant unavailable' using errcode='42501'; end if;
 update caseproof.organization_members m
 set actions=case when p_enable
   then array(select distinct v from unnest(m.actions||array['export:request']::text[]) v order by v)
   else array_remove(m.actions,'export:request') end
 where m.org_id=o and m.user_id=p_owner;
 update caseproof._m1_matter_grants g
 set permissions=case when p_enable
   then array(select distinct v from unnest(g.permissions||array['export:request']::text[]) v order by v)
   else array_remove(g.permissions,'export:request') end
 where g.org_id=o and g.case_id=p_case and g.user_id=p_owner;
 return true;
end $;
revoke all on function public.caseproof_f6_fixture_export_grant(uuid,uuid,uuid,boolean)
 from public,anon,authenticated,service_role;
grant execute on function public.caseproof_f6_fixture_export_grant(uuid,uuid,uuid,boolean)
 to service_role;

revoke all on function public.caseproof_dossier_export_release(uuid,text,uuid,jsonb,uuid)
 from public,anon,authenticated,service_role;
grant execute on function public.caseproof_dossier_export_release(uuid,text,uuid,jsonb,uuid)
 to authenticated,service_role;
commit;
