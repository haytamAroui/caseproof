-- Signed workbench exhibit confirm RPC (PROPOSED, not yet applied).
--
-- The exhibit register head is a canonical JSON document whose digest is the
-- sha256 of its exact Python serialization (sort keys, UTF-8, tight
-- separators). SQL cannot reproduce that byte sequence (jsonb::text has its
-- own formatting and no pgcrypto is available in disposable environments),
-- so this RPC never builds or re-hashes the register: the calling service
-- reads the raw head, appends the confirmed entry with the shared Python
-- serialization and passes the new payload, its digest and the expected
-- head revision. The RPC authenticates, authorizes, validates the declared
-- page mappings against the registered parse-manifest inventory (PDFs) or
-- rejects mappings on unpaginated sources, then commits compare-and-swap.
--
-- security definer, search_path=''. Denials raise 42501 so PostgREST masks
-- the matter. Contract errors return {ok:false,error:...} without writing:
-- 'invalid' (declaration or payload outside contract), 'stale_revision'
-- (expected head no longer current), 'conflict' (same request id replayed
-- with a different command). An identical replay returns the committed
-- revision with replay=true.

do $check$ begin
  if to_regclass('caseproof._m1_exhibit_heads') is null
    or to_regclass('caseproof._m1_exhibit_events') is null
    or to_regclass('caseproof._dev_journey_parse_manifests') is null
    or to_regclass('caseproof.documents') is null
    or to_regclass('caseproof.document_versions') is null
    or to_regclass('caseproof.audit_events') is null
    or to_regclass('caseproof.cases') is null
    or to_regclass('caseproof.organization_members') is null
    or to_regclass('caseproof._m1_matter_grants') is null
  then raise exception 'signed exhibit confirm prerequisite absent' using errcode='55000';
  end if;
end $check$;

create or replace function public.caseproof_signed_confirm_exhibit(
  p_case uuid, p_document uuid, p_version uuid, p_request uuid,
  p_expected bigint, p_payload jsonb, p_sha text,
  p_page_mappings jsonb default null
) returns jsonb language plpgsql security definer set search_path=''
as $body$
declare
  v_actor uuid := auth.uid();
  v_org uuid;
  v_media text;
  v_page_count int;
  v_rev bigint;
  v_previous caseproof._m1_exhibit_events%rowtype;
  v_audit uuid;
  v_mapping jsonb;
  v_seen int[];
  v_pdf int;
  v_value int;
  v_key text;
begin
  if p_case is null or p_document is null or p_version is null
    or v_actor is null or coalesce(auth.jwt()->>'role','')<>'authenticated'
    or coalesce(auth.jwt()->>'is_anonymous','false')='true'
  then raise exception 'private signed user required' using errcode='42501'; end if;

  select c.org_id into v_org
  from caseproof.cases c
  join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=v_actor
    and m.active and m.actions @> array['case:read','review:request']::text[]
  join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id
    and g.user_id=v_actor and g.active and g.role='reviewer'
    and 'exhibit:confirm' = any(g.permissions)
  where c.id=p_case;
  if v_org is null then
    raise exception 'matter unavailable' using errcode='42501';
  end if;

  -- The version must belong to the declared document of this matter.
  select v.media_type into v_media
  from caseproof.document_versions v
  join caseproof.documents d on d.id=v.document_id and d.org_id=v.org_id
  where v.id=p_version and d.id=p_document and d.case_id=p_case and d.org_id=v_org;
  if v_media is null then
    raise exception 'matter unavailable' using errcode='42501';
  end if;

  if p_request is null or p_expected is null or p_expected < 0
    or p_payload is null or jsonb_typeof(p_payload) != 'object'
    or p_payload->>'schema' != 'caseproof-exhibit-register-v1'
    or jsonb_typeof(p_payload->'entries') != 'array'
    or jsonb_array_length(p_payload->'entries') > 512
    or octet_length(p_payload::text) > 300000
    or p_sha is null or p_sha !~ '^[0-9a-f]{64}$'
  then return jsonb_build_object('ok', false, 'error', 'invalid'); end if;

  -- Page mappings mirror the service contract exactly: a PDF declares labels
  -- on pages inside the registered parse-manifest inventory; any other media
  -- is unpaginated and accepts no mapping. Unknown keys, duplicates and
  -- out-of-inventory pages fail closed.
  if v_media = 'application/pdf' then
    select jsonb_array_length(m.manifest->'pages') into v_page_count
    from caseproof._dev_journey_parse_manifests m
    where m.org_id=v_org and m.case_id=p_case and m.version_id=p_version;
    if v_page_count is null then
      return jsonb_build_object('ok', false, 'error', 'invalid'); end if;
  else
    if p_page_mappings is not null then
      return jsonb_build_object('ok', false, 'error', 'invalid'); end if;
    v_page_count := null;
  end if;

  if p_page_mappings is not null then
    if jsonb_typeof(p_page_mappings) != 'array'
      or jsonb_array_length(p_page_mappings) < 1
      or jsonb_array_length(p_page_mappings) > 512
    then return jsonb_build_object('ok', false, 'error', 'invalid'); end if;
    v_seen := '{}';
    for v_mapping in select value from jsonb_array_elements(p_page_mappings) loop
      if jsonb_typeof(v_mapping) != 'object'
        or (select count(*) from jsonb_object_keys(v_mapping) as k(key)
            where k.key not in ('pdf_page','printed_page','bundle_page')) > 0
        or v_mapping->>'pdf_page' is null
        or jsonb_typeof(v_mapping->'pdf_page') != 'number'
      then return jsonb_build_object('ok', false, 'error', 'invalid'); end if;
      v_pdf := (v_mapping->>'pdf_page')::numeric;
      if v_pdf < 1 or v_pdf > v_page_count or v_pdf = any(v_seen) then
        return jsonb_build_object('ok', false, 'error', 'invalid'); end if;
      v_seen := v_seen || v_pdf;
      for v_key in select e.key from jsonb_each(v_mapping) as e(key, value) loop
        if v_key in ('printed_page','bundle_page') then
          if jsonb_typeof(v_mapping->v_key) != 'number' then
            return jsonb_build_object('ok', false, 'error', 'invalid'); end if;
          v_value := (v_mapping->>v_key)::numeric;
          if v_value < 1 or v_value > 100000 then
            return jsonb_build_object('ok', false, 'error', 'invalid'); end if;
        end if;
      end loop;
    end loop;
  end if;

  insert into caseproof._m1_exhibit_heads(org_id, case_id) values (v_org, p_case)
    on conflict do nothing;
  select h.revision into v_rev
  from caseproof._m1_exhibit_heads h
  where h.org_id=v_org and h.case_id=p_case for update;

  select * into v_previous from caseproof._m1_exhibit_events e
  where e.org_id=v_org and e.case_id=p_case and e.request_id=p_request;
  if found then
    if v_previous.payload_sha256 != p_sha
      or v_previous.payload != p_payload
      or v_previous.actor_user_id != v_actor
      or v_previous.expected_revision != p_expected
    then return jsonb_build_object('ok', false, 'error', 'conflict'); end if;
    return jsonb_build_object('ok', true,
      'exhibit_revision', v_previous.revision, 'replay', true);
  end if;

  if v_rev is null or v_rev != p_expected then
    return jsonb_build_object('ok', false, 'error', 'stale_revision'); end if;

  v_audit := gen_random_uuid();
  insert into caseproof.audit_events(
    id, org_id, case_id, actor_type, actor_user_id, action,
    event_schema_version, correlation_id, input_sha256_hex
  ) values (
    v_audit, v_org, p_case, 'human', v_actor, 'm1_exhibit_register_confirm',
    'm1-v1', p_request, p_sha
  );
  update caseproof._m1_exhibit_heads h
    set revision=p_expected+1, payload=p_payload, payload_sha256=p_sha, updated_at=now()
    where h.org_id=v_org and h.case_id=p_case and h.revision=p_expected;
  if not found then
    return jsonb_build_object('ok', false, 'error', 'stale_revision'); end if;
  insert into caseproof._m1_exhibit_events (
    org_id, case_id, revision, request_id, actor_user_id,
    expected_revision, payload_sha256, payload, audit_id
  ) values (v_org, p_case, p_expected+1, p_request, v_actor, p_expected, p_sha, p_payload, v_audit);
  return jsonb_build_object('ok', true, 'exhibit_revision', p_expected+1, 'replay', false);
end $body$;

revoke all on function public.caseproof_signed_confirm_exhibit(uuid,uuid,uuid,uuid,bigint,jsonb,text,jsonb) from public, anon;
grant execute on function public.caseproof_signed_confirm_exhibit(uuid,uuid,uuid,uuid,bigint,jsonb,text,jsonb) to authenticated;
