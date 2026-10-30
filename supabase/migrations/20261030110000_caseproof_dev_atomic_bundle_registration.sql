-- Development-only atomic metadata registration for a complete four-file bundle.
-- Storage writes are a separate distributed operation and cannot share this SQL transaction.
-- Keep the legacy single-TXT registration RPC unchanged for its existing acceptance.
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
      id,org_id,document_id,version_number,original_sha256_hex,byte_length,media_type)
      values(v_version,v_org,v_doc,1,v_sha,v_length,v_mime);
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
revoke all on function public.caseproof_dev_register_bundle(uuid,uuid,jsonb) from public,anon;
grant execute on function public.caseproof_dev_register_bundle(uuid,uuid,jsonb) to authenticated;
-- Extend the existing operation check without weakening other accepted actions.
alter table caseproof._dev_journey_operations drop constraint _dev_journey_operations_operation_check;
alter table caseproof._dev_journey_operations add constraint _dev_journey_operations_operation_check
  check(operation in ('create','register','ingest','brief','bundle_register'));
