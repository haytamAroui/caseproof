-- Proposal (not applied): trusted-registry ingestion for parsed originals
-- (DOCX, and text-native PDF on a complete zero-warning parse only — the
-- coverage gate runs in the fail-closed service derivation, never here),
-- where the parse cannot run in SQL. The TXT path decodes
-- UTF-8 inside caseproof_dev_journey; a DOCX needs the bounded fail-closed
-- service parser, so the trusted writer here is service_role ONLY and the
-- function re-verifies everything SQL can verify without trusting the
-- caller:
--  * the document version exists in the case with media_type DOCX and its
--    registered original digest;
--  * the immutable Storage object exists at the exact custody path
--    org/case/document/version/sha with that digest (mirrors the TXT
--    ingest fidelity check against storage.objects);
--  * a vault intent in state 'verified' binds this version and digest
--    (the same contract caseproof_signed_publish_uploaded resolves);
--  * the registry row does not exist yet; the immutability trigger on
--    _dev_journey_sources then freezes it;
--  * the representation is bounded and its digest is computed in SQL from
--    the exact submitted text — never trusted from the caller;
--  * parser_id is bounded and must not impersonate the SQL TXT parser
--    identity 'strict-utf8-txt-v1', which stays reserved to the
--    byte-decoding ingest that SQL performs itself.
-- No exhibit head is written: confirmation stays with the signed
-- exhibit-confirm flow. service_role is the only grantee; a signed user
-- can never call this.
drop function if exists public.caseproof_registry_ingest_parsed(uuid,uuid,uuid,uuid,text,text);
create or replace function public.caseproof_registry_ingest_parsed(
 p_case uuid,p_document uuid,p_version uuid,p_request uuid,
 p_representation text,p_parser_id text,p_manifest jsonb default null
) returns jsonb language plpgsql security definer set search_path='' as $$
declare
 v_org uuid; v_sha text; v_rep_sha text;
 v_snapshot text; v_audit uuid:=gen_random_uuid();
 v_media text; v_man text; v_pages int; v_prev_end int; v_block jsonb; v_i int:=0;
begin
 -- service_role JWTs carry no sub: the role claim alone gates this call.
 if coalesce(auth.jwt()->>'role','')<>'service_role'
 then raise exception 'parsed ingestion requires the service role'
  using errcode='42501'; end if;
 if p_case is null or p_document is null or p_version is null or p_request is null
 or p_representation is null or p_representation=''
 or octet_length(p_representation) not between 1 and 1048576
 or position(E'\\x00'::bytea in convert_to(p_representation,'UTF8'))>0
 or p_parser_id is null or length(p_parser_id) not between 1 and 256
 or p_parser_id='strict-utf8-txt-v1'
 then raise exception 'invalid parsed ingestion' using errcode='22023'; end if;

 select d.org_id, dv.original_sha256_hex into v_org, v_sha
 from caseproof.documents d
 join caseproof.document_versions dv on dv.org_id=d.org_id and dv.document_id=d.id
 where d.case_id=p_case and d.id=p_document and dv.id=p_version
   and dv.media_type in (
     'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
     'application/pdf')
   and exists(
     select 1 from storage.objects o
     where o.bucket_id='caseproof-originals-dev'
       and o.name=concat_ws('/',d.org_id,p_case,p_document,p_version,dv.original_sha256_hex))
   and exists(
     select 1 from caseproof._s2_009b_vault_intents i
     where i.org_id=d.org_id and i.case_id=p_case and i.document_id=p_document
       and i.document_version_id=p_version and i.sha256_hex=dv.original_sha256_hex
       and i.state='verified');
 if v_org is null then raise exception 'original source fidelity failure' using errcode='42501'; end if;
 if exists(select 1 from caseproof._dev_journey_sources s
   where s.org_id=v_org and s.case_id=p_case and s.version_id=p_version)
 then raise exception 'source already ingested' using errcode='23505'; end if;

 v_rep_sha:=encode(sha256(convert_to(p_representation,'UTF8')),'hex');
 select dv.media_type into v_media from caseproof.document_versions dv
  where dv.id=p_version and dv.org_id=v_org;
 -- A PDF registers its physical page inventory (caseproof._dev_journey_parse_manifests,
 -- the table the signed exhibit-confirm/register-read RPCs resolve PDF pages from).
 -- The service parser produced the manifest; everything SQL can check is re-checked
 -- here against the exact submitted text and the registered original digest, so a
 -- manifest cannot claim pages, coverage or digests the bytes do not support.
 if v_media='application/pdf' then
  if p_manifest is null or jsonb_typeof(p_manifest)<>'object'
   or p_manifest->>'schema'<>'dev-document-parse-v1'
   or p_manifest->>'media_type'<>'application/pdf'
   or p_manifest->>'original_sha256' is distinct from v_sha
   or p_manifest->>'representation_sha256' is distinct from v_rep_sha
   or p_manifest->>'parser_id' is distinct from p_parser_id
   or jsonb_typeof(p_manifest->'complete')<>'boolean' or (p_manifest->>'complete')::boolean is not true
   or jsonb_typeof(p_manifest->'warnings')<>'array' or p_manifest->'warnings'<>'[]'::jsonb
   or jsonb_typeof(p_manifest->'pages')<>'array' or jsonb_typeof(p_manifest->'blocks')<>'array'
   or jsonb_array_length(p_manifest->'pages') not between 1 and 64
   or jsonb_array_length(p_manifest->'blocks') not between 1 and 2048
   or octet_length(p_manifest::text)>300000
  then raise exception 'invalid parse manifest' using errcode='22023'; end if;
  v_pages:=jsonb_array_length(p_manifest->'pages');
  for v_i in 0..v_pages-1 loop
   if (p_manifest->'pages'->v_i->>'pdf_page') is distinct from (v_i+1)::text
    or p_manifest->'pages'->v_i->>'status' is distinct from 'text_extracted'
   then raise exception 'invalid parse manifest' using errcode='22023'; end if;
  end loop;
  v_prev_end:=-2;
  for v_block in select value from jsonb_array_elements(p_manifest->'blocks') loop
   if jsonb_typeof(v_block->'start')<>'number' or jsonb_typeof(v_block->'end')<>'number'
    or jsonb_typeof(v_block->'page_index')<>'number'
    or v_block->>'kind' is distinct from 'pdf_page'
    or (v_block->>'start')::int is distinct from v_prev_end+2
    or (v_block->>'end')::int <= (v_block->>'start')::int
    or (v_block->>'page_index')::int not between 0 and v_pages-1
   then raise exception 'invalid parse manifest' using errcode='22023'; end if;
   v_prev_end:=(v_block->>'end')::int;
  end loop;
  if v_prev_end<>char_length(p_representation)
  then raise exception 'invalid parse manifest' using errcode='22023'; end if;
  v_man:=encode(sha256(convert_to(p_manifest::text,'UTF8')),'hex');
 elsif p_manifest is not null
 then raise exception 'invalid parse manifest' using errcode='22023'; end if;
 v_snapshot:=encode(sha256(convert_to(
   v_org::text||':'||p_case::text||':'||p_version::text||':'||v_sha||':'||v_rep_sha||':'||p_parser_id,
   'UTF8')),'hex');
 insert into caseproof.audit_events(id,org_id,case_id,actor_type,actor_user_id,action,
   event_schema_version,correlation_id,input_sha256_hex)
 values(v_audit,v_org,p_case,'service',null,'dev_parsed_ingested','dev-parsed-v1',p_request,v_snapshot);
 insert into caseproof._dev_journey_sources(
   org_id,case_id,document_id,version_id,original_sha,representation_sha,snapshot_sha,
   representation,parser_id,audit_id)
 values(v_org,p_case,p_document,p_version,v_sha,v_rep_sha,v_snapshot,p_representation,
   p_parser_id,v_audit);
 if v_man is not null then
  insert into caseproof._dev_journey_parse_manifests(
   org_id,case_id,version_id,original_sha256,representation_sha256,manifest_sha256,manifest)
  values(v_org,p_case,p_version,v_sha,v_rep_sha,v_man,p_manifest);
 end if;
 return jsonb_build_object('case_id',p_case,'document_id',p_document,'version_id',p_version,
   'original_sha',v_sha,'representation_sha',v_rep_sha,'snapshot_sha',v_snapshot);
end $$;
revoke all on function public.caseproof_registry_ingest_parsed(uuid,uuid,uuid,uuid,text,text,jsonb) from public,anon,authenticated;
grant execute on function public.caseproof_registry_ingest_parsed(uuid,uuid,uuid,uuid,text,text,jsonb) to service_role;
