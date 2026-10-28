-- CaseProof-dev service-only source promotion AFTER a trusted server has
-- independently fetched the private Storage bytes with the signed actor's JWT
-- and verified exact original digest+length. Authenticated users cannot call
-- this function; user-originated p_action='ingest' is denied by prior migration.
create function public.caseproof_dev_ingest_verified(
 p_actor uuid,p_case uuid,p_request uuid,p_document uuid,p_version uuid,
 p_content_base64 text
) returns jsonb language plpgsql security definer set search_path='' as $body$
declare
 v_org uuid; v_original caseproof.document_versions%rowtype;
 v_doc caseproof.documents%rowtype; v_old caseproof._dev_journey_operations%rowtype;
 v_old_source caseproof._dev_journey_sources%rowtype;
 v_bytes bytea; v_text text; v_sha text; v_rep_sha text; v_snapshot text; v_input text;
 v_exhibit jsonb; v_exhibit_sha text; v_audit uuid; v_audit2 uuid; v_result jsonb;
begin
 if p_actor is null or p_case is null or p_request is null
 or p_document is null or p_version is null
 or p_content_base64 is null or length(p_content_base64)>1400000
 then raise exception 'trusted TXT ingestion unavailable' using errcode='42501'; end if;

 -- Explicit current actor permissions, rechecked as part of the same write transaction.
 select c.org_id into v_org from caseproof.cases c
 join caseproof.organization_members m on m.org_id=c.org_id
   and m.user_id=p_actor and m.active
   and m.actions @> array['case:read','evidence:read','finding:write','review:request']::text[]
 join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id
   and g.user_id=p_actor and g.active and g.role='reviewer'
   and g.permissions @> array['case:read','evidence:read','evidence:upload','draft:check','review:request']::text[]
 where c.id=p_case for share of c,m,g;
 if v_org is null then raise exception 'matter unavailable' using errcode='42501'; end if;

 -- Ingestion is exclusive per matter, even for different request IDs.
 perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
   'caseproof:dev-txt-ingest:'||p_case::text,0));
 begin
   v_bytes:=decode(p_content_base64,'base64');
   v_text:=convert_from(v_bytes,'UTF8');
 exception when others then
   raise exception 'strict UTF-8 TXT required' using errcode='22023';
 end;
 if octet_length(v_bytes) not between 1 and 1048576 or v_text='' then
   raise exception 'invalid TXT size' using errcode='22023'; end if;
 v_sha:=encode(extensions.digest(v_bytes,'sha256'),'hex');
 v_rep_sha:=encode(extensions.digest(convert_to(v_text,'UTF8'),'sha256'),'hex');
 select d.* into v_doc from caseproof.documents d
   where d.org_id=v_org and d.case_id=p_case and d.id=p_document;
 select dv.* into v_original from caseproof.document_versions dv
   where dv.org_id=v_org and dv.document_id=p_document and dv.id=p_version;
 if v_doc.id is null or v_original.id is null
 or v_original.original_sha256_hex<>v_sha
 or v_original.byte_length<>octet_length(v_bytes)
 or v_original.media_type<>'text/plain'
 or not exists(select 1 from storage.objects o
   where o.bucket_id='caseproof-originals-dev'
     and o.name=concat_ws('/',v_org,p_case,p_document,p_version,v_sha))
 then raise exception 'source lineage invalid' using errcode='42501'; end if;
 v_input:=encode(extensions.digest(convert_to(
    pg_catalog.jsonb_build_object('case',p_case,'document',p_document,
       'version',p_version,'original_sha',v_sha,'operation','ingest')::text,
    'UTF8'),'sha256'),'hex');
 select * into v_old from caseproof._dev_journey_operations
   where org_id=v_org and actor_id=p_actor and operation='ingest'
   and request_id=p_request for update;
 if found then
   if v_old.input_sha<>v_input then
     raise exception 'idempotency conflict' using errcode='23505'; end if;
   return v_old.response || '{"replayed":true}'::jsonb;
 end if;

 select * into v_old_source from caseproof._dev_journey_sources
   where org_id=v_org and case_id=p_case;
 if v_old_source.version_id is not null then
   if v_old_source.version_id<>p_version or v_old_source.original_sha<>v_sha
   or v_old_source.representation_sha<>v_rep_sha or v_old_source.representation<>v_text then
     raise exception 'matter has a different ingested original' using errcode='23505'; end if;
   v_result:=pg_catalog.jsonb_build_object(
      'case_id',p_case,'document_id',p_document,'version_id',p_version,
      'original_sha',v_sha,'representation_sha',v_rep_sha,
      'snapshot_sha',v_old_source.snapshot_sha,
      'text',v_text,'exhibit_confirmed',false);
 else
   v_snapshot:=encode(extensions.digest(convert_to(
      v_org::text||':'||p_case::text||':'||p_version::text||':'||v_sha
        ||':'||v_rep_sha||':strict-utf8-txt-v1','UTF8'),'sha256'),'hex');
   v_audit:=gen_random_uuid();
   insert into caseproof.audit_events(id,org_id,case_id,actor_type,actor_user_id,
     action,event_schema_version,correlation_id,input_sha256_hex)
   values(v_audit,v_org,p_case,'human',p_actor,'dev_txt_ingested',
     'dev-txt-v1',p_request,v_snapshot);
   insert into caseproof._dev_journey_sources(
     org_id,case_id,document_id,version_id,original_sha,representation_sha,
     snapshot_sha,representation,audit_id)
   values(v_org,p_case,p_document,p_version,v_sha,v_rep_sha,v_snapshot,v_text,v_audit);
   v_exhibit:=pg_catalog.jsonb_build_object('label','Unconfirmed',
      'source_id',p_document,'version_id',p_version,'original_sha256',v_sha,
      'source_text',v_text,'scope','processed',
      'origin','trusted-server-signed-storage-verified-ingestion',
      'confirmed',false,'snapshot_sha',v_snapshot);
   v_exhibit_sha:=encode(extensions.digest(convert_to(v_exhibit::text,'UTF8'),'sha256'),'hex');
   insert into caseproof._m1_exhibit_heads(org_id,case_id,revision,payload,payload_sha256)
     values(v_org,p_case,1,v_exhibit,v_exhibit_sha);
   v_audit2:=gen_random_uuid();
   insert into caseproof.audit_events(id,org_id,case_id,actor_type,actor_user_id,
       action,event_schema_version,correlation_id,input_sha256_hex)
   values(v_audit2,v_org,p_case,'human',p_actor,'dev_unconfirmed_source',
       'dev-txt-v1',p_request,v_exhibit_sha);
   insert into caseproof._m1_exhibit_events(org_id,case_id,revision,request_id,
     actor_user_id,expected_revision,payload_sha256,payload,audit_id)
   values(v_org,p_case,1,p_request,p_actor,0,v_exhibit_sha,v_exhibit,v_audit2);
   v_result:=pg_catalog.jsonb_build_object('case_id',p_case,'document_id',p_document,
      'version_id',p_version,'original_sha',v_sha,'representation_sha',v_rep_sha,
      'snapshot_sha',v_snapshot,'text',v_text,'exhibit_confirmed',false);
 end if;

 insert into caseproof._dev_journey_operations(
    org_id,actor_id,operation,request_id,input_sha,response)
 values(v_org,p_actor,'ingest',p_request,v_input,v_result);
 return v_result || '{"replayed":false}'::jsonb;
end $body$;

revoke all on function public.caseproof_dev_ingest_verified(
 uuid,uuid,uuid,uuid,uuid,text) from public,anon,authenticated;
grant execute on function public.caseproof_dev_ingest_verified(
 uuid,uuid,uuid,uuid,uuid,text) to service_role;
