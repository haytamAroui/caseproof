-- Signed workbench document inventory RPCs (PROPOSED, not yet applied).
--
-- caseproof_signed_list_documents: authenticates the signed user, authorizes
-- evidence read on the matter and returns the document/version inventory,
-- bounded (<=512 documents, <=64 versions per document). Read-only.
--
-- caseproof_signed_register_source: declares a new document and its first
-- version (label, size, digest) before any byte upload; the later upload
-- must match the declared digest or fail closed. One insert pair, same
-- transaction.
--
-- security definer, search_path=''. Denials raise 42501 so PostgREST masks
-- the matter; invalid declarations return {ok:false,error:'invalid'}.

do $check$ begin
  if to_regclass('caseproof.documents') is null
    or to_regclass('caseproof.document_versions') is null
    or to_regclass('caseproof.cases') is null
    or to_regclass('caseproof.organization_members') is null
    or to_regclass('caseproof._m1_matter_grants') is null
  then raise exception 'signed document inventory prerequisite absent' using errcode='55000';
  end if;
end $check$;

create or replace function public.caseproof_signed_list_documents(
  p_case uuid
) returns jsonb language plpgsql security definer set search_path=''
as $body$
declare
  v_actor uuid := auth.uid();
  v_org uuid;
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

  return jsonb_build_object('ok', true, 'documents', coalesce((
    select jsonb_agg(jsonb_build_object(
             'document_id', d.id, 'label', d.source_label, 'versions', d.versions)
             order by d.received_at)
    from (
      select doc.id, doc.source_label, doc.received_at,
             (select jsonb_agg(jsonb_build_object(
                       'version_id', v.id, 'version_number', v.version_number,
                       'media_type', v.media_type, 'byte_length', v.byte_length,
                       'sha256_hex', v.original_sha256_hex)
                      order by v.version_number)
              from (select v.* from caseproof.document_versions v
                    where v.org_id=doc.org_id and v.document_id=doc.id
                    order by v.version_number limit 64) v) as versions
      from (select doc.* from caseproof.documents doc
            where doc.org_id=v_org and doc.case_id=p_case
            order by doc.received_at limit 512) doc
    ) d
  ), '[]'::jsonb));
end $body$;

revoke all on function public.caseproof_signed_list_documents(uuid) from public, anon;
grant execute on function public.caseproof_signed_list_documents(uuid) to authenticated;

create or replace function public.caseproof_signed_register_source(
  p_case uuid, p_label text, p_media_type text, p_byte_length bigint, p_sha256 text
) returns jsonb language plpgsql security definer set search_path=''
as $body$
declare
  v_actor uuid := auth.uid();
  v_org uuid;
  v_document uuid;
  v_version uuid;
begin
  if p_case is null
    or v_actor is null or coalesce(auth.jwt()->>'role','')<>'authenticated'
    or coalesce(auth.jwt()->>'is_anonymous','false')='true'
  then raise exception 'private signed user required' using errcode='42501'; end if;

  if p_label is null or length(btrim(p_label)) < 1 or length(p_label) > 200
    or p_label like '%'||chr(13)||'%' or p_label like '%'||chr(10)||'%'
    or p_media_type not in ('application/pdf','text/plain',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    or p_byte_length is null or p_byte_length < 1 or p_byte_length > 3145728
    or p_sha256 is null or p_sha256 !~ '^[0-9a-f]{64}$'
  then return jsonb_build_object('ok', false, 'error', 'invalid'); end if;

  select c.org_id into v_org
  from caseproof.cases c
  join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=v_actor
    and m.active and m.actions @> array['case:read','evidence:read','finding:write','review:request']::text[]
  join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id
    and g.user_id=v_actor and g.active and g.role='reviewer'
    and g.permissions @> array['case:read','evidence:read','evidence:upload']::text[]
  where c.id=p_case for share of c,m,g;
  if v_org is null then
    raise exception 'matter unavailable' using errcode='42501';
  end if;

  insert into caseproof.documents (org_id, case_id, source_label)
    values (v_org, p_case, p_label)
    returning id into v_document;
  insert into caseproof.document_versions
    (org_id, document_id, version_number, original_sha256_hex, byte_length, media_type)
    values (v_org, v_document, 1, p_sha256, p_byte_length, p_media_type)
    returning id into v_version;

  return jsonb_build_object('ok', true, 'document_id', v_document, 'version_id', v_version);
end $body$;

revoke all on function public.caseproof_signed_register_source(uuid,text,text,bigint,text) from public, anon;
grant execute on function public.caseproof_signed_register_source(uuid,text,text,bigint,text) to authenticated;
