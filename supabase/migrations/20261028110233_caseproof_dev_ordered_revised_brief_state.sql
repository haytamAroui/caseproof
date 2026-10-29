-- Signed reopening lists ordered immutable authored draft revisions.
create or replace function public.caseproof_dev_journey(
 p_action text,p_case uuid default null,p_request uuid default null,
 p_data jsonb default '{}'::jsonb
) returns jsonb language plpgsql security definer set search_path='' as $$
declare
 v_actor uuid:=auth.uid(); v_org uuid; v_name text; v_sha text; v_input text;
 v_old caseproof._dev_journey_operations%rowtype; v_result jsonb;
 v_doc uuid; v_version uuid; v_brief uuid; v_brief_version uuid;
 v_source caseproof._dev_journey_sources%rowtype; v_length integer; v_bytes bytea;
 v_text text; v_quote text; v_pos integer; v_rep_sha text; v_snapshot text;
 v_exhibit jsonb; v_exhibit_sha text; v_graph text; v_audit uuid; v_audit2 uuid;
begin
 if v_actor is null or coalesce(auth.jwt()->>'role','')<>'authenticated'
 or coalesce(auth.jwt()->>'is_anonymous','false')='true'
 or p_data is null or pg_catalog.jsonb_typeof(p_data)<>'object'
 or p_action not in ('create','register','ingest','brief','state')
 then raise exception 'signed journey unavailable' using errcode='42501'; end if;

 if p_action='create' then
   begin v_org:=(p_data->>'org_id')::uuid;
   exception when others then raise exception 'invalid organization' using errcode='42501'; end;
   select m.org_id into v_org from caseproof.organization_members m
   where m.org_id=v_org and m.user_id=v_actor and m.active and 'case:create'=any(m.actions)
   for share;
 else
   select c.org_id into v_org from caseproof.cases c
   join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=v_actor
      and m.active and m.actions @> array['case:read','evidence:read','finding:write','review:request']::text[]
   join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id
      and g.user_id=v_actor and g.active and g.role='reviewer'
      and g.permissions @> array['case:read','evidence:read','evidence:upload','draft:check','draft:write','review:request']::text[]
   where c.id=p_case for share of c,m,g;
 end if;
 if v_org is null then raise exception 'matter unavailable' using errcode='42501'; end if;
 -- An authenticated user must never self-certify the bytes held in Storage.
 if p_action='ingest' then raise exception 'trusted server verifier required' using errcode='42501'; end if;
 if p_action='register' then
   perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended('caseproof:dev-txt-register:'||p_case::text,0));
 end if;

 if p_action='state' then
   select jsonb_build_object(
    'schema','dev-live-txt-v1','case_id',p_case,
    'sources',coalesce((select jsonb_agg(jsonb_build_object(
       'document_id',s.document_id,'version_id',s.version_id,'original_sha',s.original_sha,
       'snapshot_sha',s.snapshot_sha,'text',s.representation,'representation_sha',s.representation_sha))
      from caseproof._dev_journey_sources s where s.org_id=v_org and s.case_id=p_case),'[]'::jsonb),
    'briefs',coalesce((select jsonb_agg(jsonb_build_object(
      'brief_id',b.brief_id,'brief_version_id',b.version_id,'text',b.representation,
      'revision',b.revision,'parent_version_id',b.parent_version_id,
      'quote',(select a.assertion_text from caseproof._m2_brief_assertions a
        where a.org_id=b.org_id and a.case_id=b.case_id and a.brief_id=b.brief_id
          and a.version_id=b.version_id and a.claim_order=0),
      'graph_sha',b.graph_sha256) order by b.revision desc)
      from caseproof._m2_brief_versions b where b.org_id=v_org and b.case_id=p_case
      and b.parser_id='dev-ingested-txt-brief-v1'),'[]'::jsonb)) into v_result;
   return v_result;
 end if;
 if p_request is null then raise exception 'idempotency key required' using errcode='42501'; end if;
 v_input:=encode(extensions.digest(convert_to(
   pg_catalog.jsonb_build_object('case',p_case,'data',p_data,'action',p_action)::text,'UTF8'),'sha256'),'hex');
 perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(v_org::text||':'||v_actor::text||':'||p_action||':'||p_request::text,0));
 select * into v_old from caseproof._dev_journey_operations
 where org_id=v_org and actor_id=v_actor and operation=p_action and request_id=p_request for update;
 if found then
    if v_old.input_sha<>v_input then raise exception 'idempotency conflict' using errcode='23505'; end if;
    return v_old.response || '{"replayed":true}'::jsonb;
 end if;

 if p_action='create' then
   v_name:=btrim(p_data->>'name');
   if v_name is null or length(v_name) not between 1 and 160
      then raise exception 'invalid matter name' using errcode='22023'; end if;
   v_doc:=gen_random_uuid();
   insert into caseproof.cases(id,org_id,created_by_user,effective_policy_version)
   values(v_doc,v_org,v_actor,'caseproof-dev-txt-v1');
   insert into caseproof._m1_matter_grants(org_id,case_id,user_id,role,permissions)
   values(v_org,v_doc,v_actor,'reviewer',
      array['case:read','evidence:read','evidence:upload','draft:check','review:request']::text[]);
   insert into caseproof.audit_events(
       org_id,case_id,actor_type,actor_user_id,action,event_schema_version,correlation_id,input_sha256_hex)
   values(v_org,v_doc,'human',v_actor,'dev_matter_created','dev-txt-v1',p_request,v_input);
   v_result:=jsonb_build_object('case_id',v_doc,'org_id',v_org,'name',v_name);
 elsif p_action='register' then
   if exists(select 1 from caseproof.documents where org_id=v_org and case_id=p_case)
      then raise exception 'one TXT source per dev matter' using errcode='42501'; end if;
   v_sha:=p_data->>'sha256'; v_length:=nullif(p_data->>'byte_length','')::integer;
   v_name:=btrim(p_data->>'filename');
   if v_sha is null or v_sha !~ '^[0-9a-f]{64}$' or v_length not between 1 and 1048576
      or v_name is null or length(v_name) not between 1 and 128
      or p_data->>'media_type' is distinct from 'text/plain'
      then raise exception 'invalid TXT metadata' using errcode='22023'; end if;
   v_doc:=gen_random_uuid(); v_version:=gen_random_uuid();
   insert into caseproof.documents(id,org_id,case_id,source_label)
   values(v_doc,v_org,p_case,v_name);
   insert into caseproof.document_versions(
     id,org_id,document_id,version_number,original_sha256_hex,byte_length,media_type)
   values(v_version,v_org,v_doc,1,v_sha,v_length,'text/plain');
   insert into caseproof.audit_events(org_id,case_id,actor_type,actor_user_id,action,
      event_schema_version,correlation_id,input_sha256_hex)
   values(v_org,p_case,'human',v_actor,'dev_txt_registered','dev-txt-v1',p_request,v_input);
   v_result:=jsonb_build_object('case_id',p_case,'document_id',v_doc,'version_id',v_version,
      'original_sha',v_sha,'byte_length',v_length);
 elsif p_action='ingest' then
   begin v_doc:=(p_data->>'document_id')::uuid;v_version:=(p_data->>'version_id')::uuid;
   exception when others then raise exception 'invalid source identifier' using errcode='42501'; end;
   if p_data->>'content_base64' is null
     or length(p_data->>'content_base64')>1400000 then raise exception 'TXT payload limit' using errcode='22023'; end if;
   begin
     v_bytes:=decode(p_data->>'content_base64','base64');
     v_text:=convert_from(v_bytes,'UTF8');
   exception when others then raise exception 'invalid strict UTF-8 TXT' using errcode='22023'; end;
   v_length:=octet_length(v_bytes);v_sha:=encode(extensions.digest(v_bytes,'sha256'),'hex');
   if v_length not between 1 and 1048576 or v_text=''
   or not exists(
     select 1 from caseproof.documents d
     join caseproof.document_versions dv on dv.org_id=d.org_id and dv.document_id=d.id
     join storage.objects o on o.bucket_id='caseproof-originals-dev'
       and o.name=concat_ws('/',v_org,p_case,v_doc,v_version,v_sha)
     where d.org_id=v_org and d.case_id=p_case and d.id=v_doc and dv.id=v_version
       and dv.original_sha256_hex=v_sha and dv.byte_length=v_length and dv.media_type='text/plain')
   then raise exception 'original source fidelity failure' using errcode='42501'; end if;
   if exists(select 1 from caseproof._dev_journey_sources where org_id=v_org and case_id=p_case)
   then raise exception 'source already ingested' using errcode='23505'; end if;
   v_rep_sha:=encode(extensions.digest(convert_to(v_text,'UTF8'),'sha256'),'hex');
   v_snapshot:=encode(extensions.digest(convert_to(
      v_org::text||':'||p_case::text||':'||v_version::text||':'||v_sha||':'||v_rep_sha||':strict-utf8-txt-v1',
      'UTF8'),'sha256'),'hex');
   v_audit:=gen_random_uuid();
   insert into caseproof.audit_events(id,org_id,case_id,actor_type,actor_user_id,action,
     event_schema_version,correlation_id,input_sha256_hex)
   values(v_audit,v_org,p_case,'human',v_actor,'dev_txt_ingested','dev-txt-v1',p_request,v_snapshot);
   insert into caseproof._dev_journey_sources(
      org_id,case_id,document_id,version_id,original_sha,representation_sha,snapshot_sha,
      representation,audit_id)
   values(v_org,p_case,v_doc,v_version,v_sha,v_rep_sha,v_snapshot,v_text,v_audit);
   v_exhibit:=jsonb_build_object('label','Unconfirmed','source_id',v_doc,
    'version_id',v_version,'original_sha256',v_sha,'source_text',v_text,
    'scope','processed','origin','signed-upload-sha256-verified-ingestion',
    'confirmed',false,'snapshot_sha',v_snapshot);
   v_exhibit_sha:=encode(extensions.digest(convert_to(v_exhibit::text,'UTF8'),'sha256'),'hex');
   insert into caseproof._m1_exhibit_heads(org_id,case_id,revision,payload,payload_sha256)
      values(v_org,p_case,1,v_exhibit,v_exhibit_sha);
   v_audit2:=gen_random_uuid();
   insert into caseproof.audit_events(id,org_id,case_id,actor_type,actor_user_id,action,
      event_schema_version,correlation_id,input_sha256_hex)
   values(v_audit2,v_org,p_case,'human',v_actor,'dev_unconfirmed_source',
      'dev-txt-v1',p_request,v_exhibit_sha);
   insert into caseproof._m1_exhibit_events(org_id,case_id,revision,request_id,
      actor_user_id,expected_revision,payload_sha256,payload,audit_id)
   values(v_org,p_case,1,p_request,v_actor,0,v_exhibit_sha,v_exhibit,v_audit2);
   v_result:=jsonb_build_object('case_id',p_case,'document_id',v_doc,'version_id',v_version,
      'original_sha',v_sha,'representation_sha',v_rep_sha,'snapshot_sha',v_snapshot,
      'text',v_text,'exhibit_confirmed',false);
 elsif p_action='brief' then
   begin v_version:=(p_data->>'source_version_id')::uuid;
   exception when others then raise exception 'invalid source version' using errcode='42501'; end;
   select * into v_source from caseproof._dev_journey_sources
      where org_id=v_org and case_id=p_case and version_id=v_version;
   v_text:=p_data->>'text';v_quote:=p_data->>'quote';
   if v_source.version_id is null or v_text is null or octet_length(v_text) not between 1 and 8000
      or v_quote is null or length(v_quote) not between 3 and 100
      or v_quote !~ '[0-9]' or position(v_quote in v_text)=0
      or exists(select 1 from caseproof._m2_brief_versions where org_id=v_org and case_id=p_case)
   then raise exception 'invalid authored brief' using errcode='22023'; end if;
   v_pos:=position(v_quote in v_text)-1;
   v_brief:=gen_random_uuid();v_brief_version:=gen_random_uuid();
   v_rep_sha:=encode(extensions.digest(convert_to(v_text,'UTF8'),'sha256'),'hex');
   v_graph:=encode(extensions.digest(convert_to(
     v_text||v_brief::text||v_brief_version::text||v_source.snapshot_sha,'UTF8'),'sha256'),'hex');
   insert into caseproof._m2_brief_versions(
      org_id,case_id,brief_id,version_id,revision,document_id,document_version_id,
      vault_intent_id,original_sha256,representation_sha256,parser_id,representation,
      document_role,graph_sha256,case_revision,exhibit_revision,actor_id)
   values(v_org,p_case,v_brief,v_brief_version,1,v_source.document_id,v_source.version_id,
      gen_random_uuid(),v_source.original_sha,v_rep_sha,'dev-ingested-txt-brief-v1',
      v_text,'own_draft',v_graph,1,1,v_actor);
   insert into caseproof._m2_brief_references(
      org_id,case_id,brief_id,version_id,reference_order,reference_id,exhibit_label,exact_quote)
   values(v_org,p_case,v_brief,v_brief_version,0,'source:1','Unconfirmed source',v_quote);
   insert into caseproof._m2_brief_assertions(
      org_id,case_id,brief_id,version_id,claim_order,claim_id,reference_id,
      text_start,text_end,assertion_text,kind,fact_role,language,source_language)
   values(v_org,p_case,v_brief,v_brief_version,0,'fact:amount-1','source:1',
      v_pos,v_pos+length(v_quote),v_quote,'money','invoice','en','en');
   insert into caseproof._m2_brief_heads(org_id,case_id,brief_id,revision,version_id)
   values(v_org,p_case,v_brief,1,v_brief_version);
   v_audit:=gen_random_uuid();
   insert into caseproof.audit_events(id,org_id,case_id,actor_type,actor_user_id,
     action,event_schema_version,correlation_id,input_sha256_hex)
   values(v_audit,v_org,p_case,'human',v_actor,'dev_authored_brief',
     'dev-txt-v1',p_request,v_graph);
   insert into caseproof._m2_brief_events(org_id,case_id,brief_id,revision,
     request_id,actor_id,version_id,graph_sha256,expected_revision,audit_id)
   values(v_org,p_case,v_brief,1,p_request,v_actor,v_brief_version,v_graph,0,v_audit);
   v_result:=jsonb_build_object('case_id',p_case,'brief_id',v_brief,
     'brief_version_id',v_brief_version,'graph_sha',v_graph,'text',v_text);
 end if;
 insert into caseproof._dev_journey_operations(
   org_id,actor_id,operation,request_id,input_sha,response)
 values(v_org,v_actor,p_action,p_request,v_input,v_result);
 return v_result || '{"replayed":false}'::jsonb;
end $$;
revoke all on function public.caseproof_dev_journey(text,uuid,uuid,jsonb) from public,anon;
grant execute on function public.caseproof_dev_journey(text,uuid,uuid,jsonb) to authenticated;

