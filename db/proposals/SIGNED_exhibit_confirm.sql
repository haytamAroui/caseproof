-- Signed workbench exhibit confirm RPC (PROPOSED, not yet applied).
--
-- Trust boundary (demonstrable, tested with adversarial direct calls): this
-- RPC is reachable by any authenticated user, so it NEVER trusts the caller's
-- payload. It enforces the complete register contract against authorized
-- database state:
--   * append-only: the new register must equal the current head entries plus
--     exactly ONE new entry, compare-and-swapped on the expected revision;
--   * the new entry is fully validated: name bounds (<=160), unique exhibit
--     id, confirmed=true / manual_inclusion=false (this flow only confirms),
--     bounded aliases without case-insensitive duplicates, and a page
--     inventory that references exactly the declared document/version of this
--     matter: for a PDF, every physical page 1..N of the registered parse
--     manifest, in order, with printed/bundle labels inside 1..100000; for
--     any other media, the sole UNPAGINATED marker row.
-- A direct caller therefore cannot rewrite history, confirm a foreign or
-- invented source, shrink or reorder the physical inventory, or smuggle a
-- page outside the verified manifest.
--
-- The stored payload digest p_sha is asserted by the caller and CANNOT be
-- recomputed here: sha256 needs pgcrypto, absent from the disposable test
-- environments, and jsonb::text does not reproduce the Python canonical
-- bytes. This is a deliberate boundary, not a trust decision: every read
-- path recomputes the digest and fails closed on mismatch, so a forged
-- digest only makes the caller's own register unreadable; it cannot inject
-- content, because content is fully validated above.
--
-- security definer, search_path=''. Denials raise 42501 so PostgREST masks
-- the matter. Contract errors return {ok:false,error:...} without writing:
-- 'invalid' (payload outside the enforced contract), 'stale_revision'
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
  p_expected bigint, p_payload jsonb, p_sha text
) returns jsonb language plpgsql security definer set search_path=''
as $body$
declare
  v_actor uuid := auth.uid();
  v_org uuid;
  v_media text;
  v_page_count int;
  v_rev bigint;
  v_head_entries jsonb;
  v_previous caseproof._m1_exhibit_events%rowtype;
  v_audit uuid;
  v_entries jsonb;
  v_old_count int;
  v_new jsonb;
  v_labels text[];
  v_page jsonb;
  v_pos int := 0;
  v_rows int := 0;
  v_pdf int;
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
  v_entries := p_payload->'entries';

  insert into caseproof._m1_exhibit_heads(org_id, case_id) values (v_org, p_case)
    on conflict do nothing;
  select h.revision, h.payload->'entries' into v_rev, v_head_entries
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

  -- Append-only: the new register is the current entries plus exactly one
  -- new entry; nothing already confirmed can be rewritten or dropped.
  v_old_count := coalesce(jsonb_array_length(v_head_entries), 0);
  if jsonb_array_length(v_entries) != v_old_count + 1
    or (v_old_count > 0 and (
      select coalesce(jsonb_agg(e.value order by e.ord), '[]'::jsonb)
      from jsonb_array_elements(v_entries) with ordinality as e(value, ord)
      where e.ord <= v_old_count) is distinct from v_head_entries)
  then return jsonb_build_object('ok', false, 'error', 'invalid'); end if;
  v_new := v_entries->v_old_count;

  -- New entry: shape and name bounds mirroring the domain contract.
  if jsonb_typeof(v_new) != 'object'
    or (select count(*) from jsonb_object_keys(v_new) as k(key)
        where k.key not in ('exhibit_id','display_label','aliases',
                            'confirmed','manual_inclusion','pages')) > 0
    or jsonb_typeof(v_new->'exhibit_id') != 'string'
    or length(btrim(v_new->>'exhibit_id')) < 1 or length(v_new->>'exhibit_id') > 160
    or jsonb_typeof(v_new->'display_label') != 'string'
    or length(btrim(v_new->>'display_label')) < 1 or length(v_new->>'display_label') > 160
    or jsonb_typeof(v_new->'confirmed') != 'boolean'
    or jsonb_typeof(v_new->'manual_inclusion') != 'boolean'
    or jsonb_typeof(v_new->'aliases') != 'array'
    or jsonb_array_length(v_new->'aliases') > 64
    or jsonb_typeof(v_new->'pages') != 'array'
    or jsonb_array_length(v_new->'pages') < 1
    or jsonb_array_length(v_new->'pages') > 512
  then return jsonb_build_object('ok', false, 'error', 'invalid'); end if;
  -- Boolean casts only after the type checks above (no short-circuit in SQL).
  if not (v_new->>'confirmed')::boolean
    or (v_new->>'manual_inclusion')::boolean
  then return jsonb_build_object('ok', false, 'error', 'invalid'); end if;

  -- Unique exhibit identity across the whole register.
  if exists (select 1 from jsonb_array_elements(v_head_entries) as e(value)
             where e.value->>'exhibit_id' = v_new->>'exhibit_id')
  then return jsonb_build_object('ok', false, 'error', 'invalid'); end if;

  -- Aliases: bounded names, no case-insensitive duplicate of the label or
  -- of each other. (lower() approximates Python casefold; a narrower check
  -- here can only produce a register the fail-closed reader rejects.)
  if exists (select 1 from jsonb_array_elements_text(v_new->'aliases') as a(value)
             where length(btrim(a.value)) < 1 or length(a.value) > 160)
  then return jsonb_build_object('ok', false, 'error', 'invalid'); end if;
  select array_agg(lower(btrim(a.value)))
    into v_labels
    from jsonb_array_elements_text(v_new->'aliases') as a(value);
  v_labels := coalesce(v_labels, '{}') || lower(btrim(v_new->>'display_label'));
  if (select count(*) from unnest(v_labels)) != (select count(distinct u) from unnest(v_labels) as u)
  then return jsonb_build_object('ok', false, 'error', 'invalid'); end if;

  -- Page inventory: exactly the declared source version, and exactly the
  -- registered physical inventory for a PDF, else the sole UNPAGINATED row.
  if v_media = 'application/pdf' then
    select jsonb_array_length(m.manifest->'pages') into v_page_count
    from caseproof._dev_journey_parse_manifests m
    where m.org_id=v_org and m.case_id=p_case and m.version_id=p_version;
    if v_page_count is null or v_page_count < 1
      or jsonb_array_length(v_new->'pages') != v_page_count
    then return jsonb_build_object('ok', false, 'error', 'invalid'); end if;
  else
    if jsonb_array_length(v_new->'pages') != 1
    then return jsonb_build_object('ok', false, 'error', 'invalid'); end if;
    v_page_count := null;
  end if;

  for v_page in select value from jsonb_array_elements(v_new->'pages') loop
    v_pos := v_pos + 1;
    if jsonb_typeof(v_page) != 'object'
      or (select count(*) from jsonb_object_keys(v_page) as k(key)
          where k.key not in ('source_id','version_id','pdf_page',
                              'printed_page','bundle_page')) > 0
      or v_page->>'source_id' != p_document::text
      or v_page->>'version_id' != p_version::text
    then return jsonb_build_object('ok', false, 'error', 'invalid'); end if;
    if v_page_count is null then
      if v_page->>'pdf_page' is not null or v_page->>'printed_page' is not null
        or v_page->>'bundle_page' is not null
      then return jsonb_build_object('ok', false, 'error', 'invalid'); end if;
    else
      if jsonb_typeof(v_page->'pdf_page') != 'number' then
        return jsonb_build_object('ok', false, 'error', 'invalid'); end if;
      v_pdf := (v_page->>'pdf_page')::numeric;
      if v_pdf != v_pos then
        return jsonb_build_object('ok', false, 'error', 'invalid'); end if;
      if (v_page->>'printed_page' is not null and (
            jsonb_typeof(v_page->'printed_page') != 'number'
            or (v_page->>'printed_page')::numeric < 1
            or (v_page->>'printed_page')::numeric > 100000))
        or (v_page->>'bundle_page' is not null and (
            jsonb_typeof(v_page->'bundle_page') != 'number'
            or (v_page->>'bundle_page')::numeric < 1
            or (v_page->>'bundle_page')::numeric > 100000))
      then return jsonb_build_object('ok', false, 'error', 'invalid'); end if;
    end if;
    v_rows := v_rows + 1;
  end loop;
  if v_rows != jsonb_array_length(v_new->'pages') then
    return jsonb_build_object('ok', false, 'error', 'invalid'); end if;

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

revoke all on function public.caseproof_signed_confirm_exhibit(uuid,uuid,uuid,uuid,bigint,jsonb,text) from public, anon;
grant execute on function public.caseproof_signed_confirm_exhibit(uuid,uuid,uuid,uuid,bigint,jsonb,text) to authenticated;
