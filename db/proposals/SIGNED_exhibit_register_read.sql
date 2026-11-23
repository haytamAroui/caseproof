-- Signed workbench exhibit register read RPC (PROPOSED, not yet applied).
--
-- Preparation read for the confirm flow: returns the RAW current register
-- head (revision, canonical payload, stored digest) plus, when p_version is
-- supplied, that version's media type and its physical page count from the
-- registered parse manifest (PDFs only; null for unpaginated sources). The
-- calling service verifies the digest against the exact Python
-- canonicalization (failing closed on mismatch), builds the appended
-- register and commits it through caseproof_signed_confirm_exhibit, which
-- re-validates everything server-side. This read changes nothing and
-- authorizes evidence read only.
--
-- security definer, search_path='', read-only. Denials raise 42501 so
-- PostgREST masks the matter.

do $check$ begin
  if to_regclass('caseproof._m1_exhibit_heads') is null
    or to_regclass('caseproof._dev_journey_parse_manifests') is null
    or to_regclass('caseproof.document_versions') is null
    or to_regclass('caseproof.documents') is null
    or to_regclass('caseproof.cases') is null
    or to_regclass('caseproof.organization_members') is null
    or to_regclass('caseproof._m1_matter_grants') is null
  then raise exception 'signed exhibit register prerequisite absent' using errcode='55000';
  end if;
end $check$;

create or replace function public.caseproof_signed_exhibit_register(
  p_case uuid, p_version uuid default null
) returns jsonb language plpgsql security definer set search_path=''
as $body$
declare
  v_actor uuid := auth.uid();
  v_org uuid;
  v_rev bigint;
  v_payload jsonb;
  v_sha text;
  v_media text;
  v_page_count int;
begin
  if p_case is null
    or v_actor is null or coalesce(auth.jwt()->>'role','')<>'authenticated'
    or coalesce(auth.jwt()->>'is_anonymous','false')='true'
  then raise exception 'private signed user required' using errcode='42501'; end if;

  select c.org_id into v_org
  from caseproof.cases c
  join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=v_actor
    and m.active and m.actions @> array['case:read','evidence:read']::text[]
  join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id
    and g.user_id=v_actor and g.active
    and g.permissions @> array['case:read','evidence:read']::text[]
  where c.id=p_case;
  if v_org is null then
    raise exception 'matter unavailable' using errcode='42501';
  end if;

  if p_version is not null then
    select v.media_type into v_media
    from caseproof.document_versions v
    join caseproof.documents d on d.id=v.document_id and d.org_id=v.org_id
    where v.id=p_version and d.case_id=p_case and d.org_id=v_org;
    if v_media is null then
      raise exception 'matter unavailable' using errcode='42501';
    end if;
    if v_media = 'application/pdf' then
      select jsonb_array_length(m.manifest->'pages') into v_page_count
      from caseproof._dev_journey_parse_manifests m
      where m.org_id=v_org and m.case_id=p_case and m.version_id=p_version;
    end if;
  end if;

  select h.revision, h.payload, h.payload_sha256 into v_rev, v_payload, v_sha
  from caseproof._m1_exhibit_heads h
  where h.org_id=v_org and h.case_id=p_case;

  return jsonb_build_object(
    'ok', true,
    'register_revision', coalesce(v_rev, 0),
    'payload', v_payload,
    'payload_sha256', v_sha,
    'media_type', v_media,
    'page_count', v_page_count);
end $body$;

revoke all on function public.caseproof_signed_exhibit_register(uuid,uuid) from public, anon;
grant execute on function public.caseproof_signed_exhibit_register(uuid,uuid) to authenticated;
