-- Atomic trusted parsed ingest with OCR sidecars; distinct RPC avoids changing old callers.
create function public.caseproof_dev_ingest_parsed_with_geometry(
 p_actor uuid,p_case uuid,p_request uuid,p_document uuid,p_version uuid,
 p_content_base64 text,p_representation text,p_manifest jsonb,p_geometry jsonb
) returns jsonb language plpgsql security definer set search_path='' as $body$
declare
 v_org uuid; v_dv caseproof.document_versions%rowtype;
 v_old caseproof._dev_journey_operations%rowtype;
 v_source caseproof._dev_journey_sources%rowtype;
 v_bytes bytea; v_sha text; v_rep text; v_man text; v_snapshot text;
 v_input text; v_audit uuid; v_audit2 uuid; v_geometry_count integer;
 v_exhibit jsonb; v_exhibit_sha text; v_result jsonb;
begin
 if p_actor is null or p_case is null or p_request is null or
    p_document is null or p_version is null or
    p_content_base64 is null or length(p_content_base64)>6990600 or
    p_representation is null or octet_length(p_representation)>480000 or
    p_manifest is null or pg_catalog.jsonb_typeof(p_manifest)<>'object' or
    p_manifest->>'schema'<>'dev-document-parse-v1' or
    p_manifest->>'media_type' not in ('application/pdf',
     'application/vnd.openxmlformats-officedocument.wordprocessingml.document') or
    p_manifest->>'parser_id' is null or
    length(p_manifest->>'parser_id') not between 1 and 256 or
    pg_catalog.jsonb_typeof(p_manifest->'complete')<>'boolean' or
    pg_catalog.jsonb_typeof(p_manifest->'blocks')<>'array' or
    pg_catalog.jsonb_typeof(p_manifest->'warnings')<>'array' or
    pg_catalog.jsonb_typeof(p_manifest->'pages')<>'array' or
    pg_catalog.jsonb_array_length(p_manifest->'blocks')>2048 or
    pg_catalog.jsonb_array_length(p_manifest->'pages')>64 or
    octet_length(p_manifest::text)>300000
 then raise exception 'invalid trusted parsed ingestion' using errcode='42501'; end if;
 if p_geometry is null or jsonb_typeof(p_geometry)<>'array' or jsonb_array_length(p_geometry)>64
 then raise exception 'invalid OCR geometry payload' using errcode='42501'; end if;
 if (select count(*) from jsonb_array_elements(coalesce(p_manifest->'ocr_candidates','[]'::jsonb)) c
     where c->>'geometry_sha256' is not null) <> jsonb_array_length(p_geometry)
 then raise exception 'OCR geometry references incomplete' using errcode='42501'; end if;
 -- Recheck current signed actor authorization inside this transaction.
 select c.org_id into v_org from caseproof.cases c
 join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=p_actor
   and m.active and m.actions @> array['case:read','evidence:read','finding:write','review:request']::text[]
 join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id
   and g.user_id=p_actor and g.active and g.role='reviewer'
   and g.permissions @> array['case:read','evidence:read','evidence:upload','draft:check','review:request']::text[]
 where c.id=p_case for share of c,m,g;
 if v_org is null then raise exception 'private matter unavailable' using errcode='42501'; end if;
 perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
   'caseproof:dev-txt-ingest:'||p_case::text,0));
 begin v_bytes:=decode(p_content_base64,'base64');
 exception when others then raise exception 'invalid exact original bytes' using errcode='22023'; end;
 if octet_length(v_bytes) not between 1 and 5242880 then
   raise exception 'bounded original required' using errcode='22023'; end if;
 v_sha:=encode(extensions.digest(v_bytes,'sha256'),'hex');
 v_rep:=encode(extensions.digest(convert_to(p_representation,'UTF8'),'sha256'),'hex');
 v_man:=encode(extensions.digest(convert_to(p_manifest::text,'UTF8'),'sha256'),'hex');
 if p_manifest->>'original_sha256' is distinct from v_sha or
    p_manifest->>'representation_sha256' is distinct from v_rep or
    p_manifest->>'media_type' is null or
    (p_manifest->>'complete')::boolean and
       (p_manifest->'warnings'<>'[]'::jsonb or p_representation='')
 then raise exception 'parse manifest does not match exact bytes' using errcode='42501'; end if;
 select dv.* into v_dv from caseproof.document_versions dv
 join caseproof.documents d on d.org_id=dv.org_id and d.id=dv.document_id
 where d.org_id=v_org and d.case_id=p_case and d.id=p_document
   and dv.id=p_version;
 if v_dv.id is null or v_dv.original_sha256_hex<>v_sha or
    v_dv.byte_length<>octet_length(v_bytes) or
    v_dv.media_type is distinct from p_manifest->>'media_type' or
    not exists(select 1 from storage.objects o
      where o.bucket_id='caseproof-originals-dev'
      and o.name=concat_ws('/',v_org,p_case,p_document,p_version,v_sha))
 then raise exception 'original and verified parser identity mismatch' using errcode='42501'; end if;
 v_input:=encode(extensions.digest(convert_to(pg_catalog.jsonb_build_object(
  'case',p_case,'document',p_document,'version',p_version,
  'sha',v_sha,'representation_sha',v_rep,'manifest_sha',v_man,'geometry',p_geometry)::text,'UTF8'),'sha256'),'hex');
 select * into v_old from caseproof._dev_journey_operations
 where org_id=v_org and actor_id=p_actor and operation='ingest' and request_id=p_request
 for update;
 if found then
   if v_old.input_sha<>v_input then
      raise exception 'ingest idempotency conflict' using errcode='23505'; end if;
   return v_old.response||'{"replayed":true}'::jsonb;
 end if;
 select * into v_source from caseproof._dev_journey_sources
 where org_id=v_org and case_id=p_case for update;
 if v_source.version_id is not null then
   if v_source.version_id<>p_version or
      v_source.original_sha<>v_sha or v_source.representation_sha<>v_rep or
      v_source.representation<>p_representation or not exists(
        select 1 from caseproof._dev_journey_parse_manifests x
        where x.org_id=v_org and x.case_id=p_case and x.version_id=p_version
          and x.manifest_sha256=v_man)
   then raise exception 'different original already ingested' using errcode='23505'; end if;
   v_snapshot:=v_source.snapshot_sha;
 else
   v_snapshot:=encode(extensions.digest(convert_to(
     v_org::text||':'||p_case::text||':'||p_version::text||':'||v_sha||':'||v_rep||':'||v_man,
      'UTF8'),'sha256'),'hex');
   v_audit:=gen_random_uuid();
   insert into caseproof.audit_events(
    id,org_id,case_id,actor_type,actor_user_id,action,
    event_schema_version,correlation_id,input_sha256_hex)
   values(v_audit,v_org,p_case,'human',p_actor,'dev_binary_ingested',
     'dev-binary-v1',p_request,v_snapshot);
   insert into caseproof._dev_journey_sources(
    org_id,case_id,document_id,version_id,original_sha,
    representation_sha,snapshot_sha,representation,audit_id)
   values(v_org,p_case,p_document,p_version,v_sha,v_rep,v_snapshot,p_representation,v_audit);
   insert into caseproof._dev_journey_parse_manifests(
    org_id,case_id,version_id,original_sha256,representation_sha256,
    manifest_sha256,manifest)
   values(v_org,p_case,p_version,v_sha,v_rep,v_man,p_manifest);
   v_exhibit:=pg_catalog.jsonb_build_object(
      'label','Unconfirmed','source_id',p_document,'version_id',p_version,
      'original_sha256',v_sha,'source_text',p_representation,
      'scope',case when (p_manifest->>'complete')::boolean then 'processed'
        else 'partial' end,
      'origin','trusted-signed-original-bounded-parser-v1',
      'confirmed',false,'snapshot_sha',v_snapshot);
   v_exhibit_sha:=encode(extensions.digest(convert_to(v_exhibit::text,'UTF8'),'sha256'),'hex');
   insert into caseproof._m1_exhibit_heads(org_id,case_id,revision,payload,payload_sha256)
     values(v_org,p_case,1,v_exhibit,v_exhibit_sha);
   v_audit2:=gen_random_uuid();
   insert into caseproof.audit_events(id,org_id,case_id,actor_type,actor_user_id,
    action,event_schema_version,correlation_id,input_sha256_hex)
   values(v_audit2,v_org,p_case,'human',p_actor,'dev_unconfirmed_source',
     'dev-binary-v1',p_request,v_exhibit_sha);
   insert into caseproof._m1_exhibit_events(
    org_id,case_id,revision,request_id,actor_user_id,expected_revision,
    payload_sha256,payload,audit_id)
   values(v_org,p_case,1,p_request,p_actor,0,v_exhibit_sha,v_exhibit,v_audit2);
 end if;
 -- Exact Python UTF-8 JSON bytes are preserved as TEXT and hashed before storage.
 select count(*) into v_geometry_count
 from jsonb_array_elements(p_geometry) g
 join lateral jsonb_array_elements(coalesce(p_manifest->'ocr_candidates','[]'::jsonb)) c
   on c->>'pdf_page'=g->>'page_number'
 where ((g->>'payload_text')::jsonb)->>'schema'='caseproof.ocr.geometry.v1'
   and ((g->>'payload_text')::jsonb)->>'original_sha256'=v_sha
   and ((g->>'payload_text')::jsonb)->>'page_number'=g->>'page_number'
   and g->>'coordinate_basis'=((g->>'payload_text')::jsonb)->>'coordinate_basis'
   and jsonb_typeof(((g->>'payload_text')::jsonb)->'words')='array'
   and c->>'original_sha256'=v_sha
   and c->>'geometry_sha256'=g->>'geometry_sha256'
   and g->>'geometry_sha256'=encode(extensions.digest(convert_to(g->>'payload_text','UTF8'),'sha256'),'hex');
 if v_geometry_count <> jsonb_array_length(p_geometry)
 then raise exception 'OCR geometry hash or identity mismatch' using errcode='42501'; end if;
 insert into caseproof.ocr_geometry_sidecars(
   document_version_id,page_number,original_sha256_hex,geometry_sha256_hex,
   coordinate_basis,word_count,payload
 )
 select p_version,(g->>'page_number')::integer,v_sha,g->>'geometry_sha256',
   g->>'coordinate_basis',jsonb_array_length(((g->>'payload_text')::jsonb)->'words'),g->>'payload_text'
 from jsonb_array_elements(p_geometry) g
 on conflict (document_version_id,page_number) do nothing;
 if (select count(*) from caseproof.ocr_geometry_sidecars x
     join jsonb_array_elements(p_geometry) g on x.page_number=(g->>'page_number')::integer
     where x.document_version_id=p_version
       and x.geometry_sha256_hex=g->>'geometry_sha256'
       and x.original_sha256_hex=v_sha) <> jsonb_array_length(p_geometry)
 then raise exception 'OCR geometry persistence incomplete' using errcode='42501'; end if;
 v_result:=pg_catalog.jsonb_build_object(
  'case_id',p_case,'document_id',p_document,'version_id',p_version,
  'original_sha',v_sha,'representation_sha',v_rep,'snapshot_sha',v_snapshot,
  'text',p_representation,'parse_manifest',p_manifest,
  'exhibit_confirmed',false);
 insert into caseproof._dev_journey_operations(org_id,actor_id,operation,request_id,input_sha,response)
 values(v_org,p_actor,'ingest',p_request,v_input,v_result);
 return v_result||'{"replayed":false}'::jsonb;
end $body$;
revoke all on function public.caseproof_dev_ingest_parsed_with_geometry(
 uuid,uuid,uuid,uuid,uuid,text,text,jsonb,jsonb) from public,anon,authenticated;
grant execute on function public.caseproof_dev_ingest_parsed_with_geometry(
 uuid,uuid,uuid,uuid,uuid,text,text,jsonb,jsonb) to service_role;
