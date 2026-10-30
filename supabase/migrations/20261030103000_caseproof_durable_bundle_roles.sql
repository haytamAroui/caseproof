-- Durable legal role is attached to each document version; null retains legacy journeys.
alter table caseproof.document_versions add column if not exists bundle_role text;
alter table caseproof.document_versions add constraint document_versions_bundle_role_check
 check (bundle_role is null or bundle_role in ('inventory','exhibit'));
-- Replace registration implementation without changing its signed ownership guards.
create or replace function public.caseproof_dev_register_bundle(
  p_case uuid, p_request uuid, p_sources jsonb
) returns jsonb language plpgsql security definer set search_path='' as $$
declare
  v_actor uuid := auth.uid(); v_org uuid; v_item jsonb; v_role text;
  v_name text; v_sha text; v_mime text; v_length bigint;
  v_doc uuid; v_version uuid; v_items jsonb := '[]'::jsonb;
  v_seen text[] := array[]::text[]; v_inventory integer := 0;
  v_input text; v_old caseproof._dev_journey_operations%rowtype;
begin
  if v_actor is null or coalesce(auth.jwt()->>'role','') <> 'authenticated'
     or coalesce(auth.jwt()->>'is_anonymous','false') = 'true'
     or p_case is null or p_request is null
     or jsonb_typeof(p_sources) <> 'array'
     or jsonb_array_length(p_sources) <> 4
  then raise exception 'invalid signed bundle request' using errcode='42501'; end if;

  select c.org_id into v_org from caseproof.cases c
  join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=v_actor
    and m.active and m.actions @> array['case:read','evidence:read','finding:write','review:request']::text[]
  join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id
    and g.user_id=v_actor and g.active and g.role='reviewer'
    and g.permissions @> array['case:read','evidence:read','evidence:upload','draft:check','review:request']::text[]
  where c.id=p_case for update of c;
  if v_org is null then raise exception 'matter unavailable' using errcode='42501'; end if;
  v_input := encode(extensions.digest(convert_to(p_sources::text,'UTF8'),'sha256'),'hex');
  select * into v_old from caseproof._dev_journey_operations
    where org_id=v_org and actor_id=v_actor and operation='bundle_register'
      and request_id=p_request for update;
  if found then
    if v_old.input_sha <> v_input then raise exception 'idempotency conflict' using errcode='23505'; end if;
    return v_old.response || '{"replayed":true}'::jsonb;
  end if;
  if exists(select 1 from caseproof.documents where org_id=v_org and case_id=p_case)
  then raise exception 'matter already has registered originals' using errcode='23505'; end if;

  for v_item in select value from jsonb_array_elements(p_sources) loop
    if jsonb_typeof(v_item) <> 'object' then raise exception 'invalid source' using errcode='22023'; end if;
    v_role := v_item->>'role'; v_name := btrim(v_item->>'filename');
    v_sha := v_item->>'sha256'; v_mime := v_item->>'media_type';
    begin v_length := (v_item->>'byte_length')::bigint;
    exception when others then raise exception 'invalid source length' using errcode='22023'; end;
    if v_role not in ('inventory','exhibit') or v_role is null
       or v_name is null or length(v_name) not between 1 and 128
       or v_name = any(v_seen) or v_sha is null or v_sha !~ '^[0-9a-f]{64}$'
       or v_length not between 1 and 20971520
       or v_mime not in ('application/pdf','text/plain') or v_mime is null
       or (v_role='inventory' and v_mime <> 'text/plain')
       or (v_role='exhibit' and v_mime <> 'application/pdf')
    then raise exception 'invalid bundle source metadata' using errcode='22023'; end if;
    v_seen := array_append(v_seen,v_name);
    if v_role='inventory' then v_inventory:=v_inventory+1; end if;
    v_doc:=gen_random_uuid(); v_version:=gen_random_uuid();
    insert into caseproof.documents(id,org_id,case_id,source_label)
      values(v_doc,v_org,p_case,v_name);
    insert into caseproof.document_versions(
      id,org_id,document_id,version_number,original_sha256_hex,byte_length,media_type,bundle_role)
      values(v_version,v_org,v_doc,1,v_sha,v_length,v_mime,v_role);
    v_items := v_items || jsonb_build_array(jsonb_build_object(
      'role',v_role,'filename',v_name,'document_id',v_doc,
      'version_id',v_version,'sha256',v_sha,'byte_length',v_length,'media_type',v_mime));
  end loop;
  if v_inventory <> 1 then raise exception 'exactly one inventory required' using errcode='22023'; end if;
  insert into caseproof.audit_events(org_id,case_id,actor_type,actor_user_id,action,
      event_schema_version,correlation_id,input_sha256_hex)
    values(v_org,p_case,'human',v_actor,'dev_bundle_registered','dev-bundle-v1',p_request,v_input);
  insert into caseproof._dev_journey_operations(
      org_id,actor_id,operation,request_id,input_sha,response)
    values(v_org,v_actor,'bundle_register',p_request,v_input,
      jsonb_build_object('case_id',p_case,'sources',v_items));
  return jsonb_build_object('case_id',p_case,'sources',v_items);
end;
$$;
create or replace function public.caseproof_dev_bundle_manifest(p_case uuid)
returns jsonb language plpgsql security definer set search_path='' as $$
declare v_actor uuid:=auth.uid(); v_org uuid; v_manifest jsonb; v_sources jsonb;
begin
 if v_actor is null or p_case is null or coalesce(auth.jwt()->>'role','') <> 'authenticated'
    or coalesce(auth.jwt()->>'is_anonymous','false')='true'
 then raise exception 'matter unavailable' using errcode='42501'; end if;
 select c.org_id into v_org from caseproof.cases c
 join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=v_actor
   and m.active and m.actions @> array['case:read','evidence:read']::text[]
 join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id
   and g.user_id=v_actor and g.active
   and g.permissions @> array['case:read','evidence:read']::text[]
 where c.id=p_case;
 if v_org is null then raise exception 'matter unavailable' using errcode='42501'; end if;
 select op.response into v_manifest from caseproof._dev_journey_operations op
 where op.org_id=v_org and op.actor_id=v_actor and op.operation='bundle_register'
 and op.response->>'case_id'=p_case::text;
 if v_manifest is null or jsonb_array_length(v_manifest->'sources')<>4
 then raise exception 'bundle unavailable' using errcode='42501'; end if;
 select jsonb_agg(jsonb_build_object(
   'role',dv.bundle_role,'filename',d.source_label,'document_id',d.id,
   'version_id',dv.id,'version_number',dv.version_number,
   'sha256',dv.original_sha256_hex,'byte_length',dv.byte_length,'media_type',dv.media_type
 ) order by s.ordinality) into v_sources
 from jsonb_array_elements(v_manifest->'sources') with ordinality as s(item,ordinality)
 join caseproof.documents d on d.id=(s.item->>'document_id')::uuid and d.org_id=v_org and d.case_id=p_case
 join caseproof.document_versions dv on dv.id=(s.item->>'version_id')::uuid
 and dv.document_id=d.id and dv.org_id=v_org
 where d.source_label=s.item->>'filename'
 and dv.bundle_role=s.item->>'role'
 and dv.original_sha256_hex=s.item->>'sha256'
 and dv.media_type=s.item->>'media_type'
 and dv.byte_length=(s.item->>'byte_length')::bigint;
 if jsonb_array_length(coalesce(v_sources,'[]'::jsonb))<>4
 then raise exception 'bundle integrity mismatch' using errcode='42501'; end if;
 return jsonb_build_object('case_id',p_case,'sources',v_sources);
end $$;
