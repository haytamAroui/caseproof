-- Forward-only development hardening and ingested TXT reviewer source.
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
      and g.permissions @> array['case:read','evidence:read','evidence:upload','draft:check','review:request']::text[]
   where c.id=p_case for share of c,m,g;
 end if;
 if v_org is null then raise exception 'matter unavailable' using errcode='42501'; end if;

 if p_action='state' then
   select jsonb_build_object(
    'schema','dev-live-txt-v1','case_id',p_case,
    'sources',coalesce((select jsonb_agg(jsonb_build_object(
       'document_id',s.document_id,'version_id',s.version_id,'original_sha',s.original_sha,
       'snapshot_sha',s.snapshot_sha,'text',s.representation,'representation_sha',s.representation_sha))
      from caseproof._dev_journey_sources s where s.org_id=v_org and s.case_id=p_case),'[]'::jsonb),
    'briefs',coalesce((select jsonb_agg(jsonb_build_object(
      'brief_id',b.brief_id,'brief_version_id',b.version_id,'text',b.representation,
      'graph_sha',b.graph_sha256))
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

create or replace function public.caseproof_dev_live_review(
  p_case uuid, p_version uuid, p_action text,
  p_snapshot text default null, p_request uuid default null,
  p_expected integer default null, p_observation text default null,
  p_disposition text default null, p_rationale text default null
) returns jsonb language plpgsql security definer set search_path=''
as $body$
declare
  v_actor uuid := auth.uid();
  v_org uuid;
  v_brief caseproof._m2_brief_versions%rowtype;
  v_exhibit caseproof._m1_exhibit_heads%rowtype;
  v_claim caseproof._m2_brief_assertions%rowtype;
  v_case_revision bigint;
  v_snapshot text;
  v_payload text;
  v_fingerprint text;
  v_head caseproof._m2_review_heads%rowtype;
  v_old caseproof._m2_review_receipts%rowtype;
  v_decision jsonb;
  v_event_hash text;
  v_audit uuid;
  v_replayed boolean := false;
  v_decisions jsonb;
  v_ingested caseproof._dev_journey_sources%rowtype;
  v_match boolean;
  v_scope text;
  v_outcome text;
begin
  if p_case is null or p_version is null or p_action not in ('check','state','review')
    or v_actor is null or coalesce(auth.jwt()->>'role','')<>'authenticated'
    or coalesce(auth.jwt()->>'is_anonymous','false')='true'
  then raise exception 'private signed user required' using errcode='42501'; end if;
  -- One exact CURRENT organization/matter grant, never client-supplied actor or org.
  select c.org_id,c.case_revision into v_org,v_case_revision
  from caseproof.cases c
  join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=v_actor
    and m.active and m.actions @> array['case:read','evidence:read','finding:write','review:request']::text[]
  join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id
    and g.user_id=v_actor and g.active and g.role='reviewer'
    and g.permissions @> array['case:read','evidence:read','draft:check','review:request']::text[]
  where c.id=p_case;
  if v_org is null then
    raise exception 'matter unavailable' using errcode='42501';
  end if;
  select b.* into v_brief from caseproof._m2_brief_versions b
  join caseproof._m2_brief_heads bh
    on bh.org_id=b.org_id and bh.case_id=b.case_id
    and bh.brief_id=b.brief_id and bh.version_id=b.version_id and bh.revision=b.revision
  where b.org_id=v_org and b.case_id=p_case and b.version_id=p_version;
  select * into v_exhibit from caseproof._m1_exhibit_heads
    where org_id=v_org and case_id=p_case;
  select a.* into v_claim from caseproof._m2_brief_assertions a
    where a.org_id=v_org and a.case_id=p_case and a.brief_id=v_brief.brief_id
      and a.version_id=p_version and a.claim_order=0;
  if v_brief.version_id is null or v_exhibit.revision is null or v_claim.claim_id is null
    or v_brief.case_revision <> v_case_revision
    or v_brief.exhibit_revision <> v_exhibit.revision
    or v_exhibit.payload->>'original_sha256' <> v_brief.original_sha256
    or v_exhibit.payload->>'source_id' <> v_brief.document_id::text
    or v_exhibit.payload->>'version_id' <> v_brief.document_version_id::text
    or encode(extensions.digest(convert_to(v_brief.representation,'UTF8'),'sha256'),'hex')
      <> v_brief.representation_sha256
    or substring(v_brief.representation from v_claim.text_start+1
       for v_claim.text_end-v_claim.text_start) <> v_claim.assertion_text
    or not exists (
      select 1 from caseproof.documents d
      join caseproof.document_versions dv on dv.org_id=d.org_id and dv.document_id=d.id
      join storage.objects o on o.bucket_id='caseproof-originals-dev'
        and o.name=concat_ws('/',v_org,p_case,d.id,dv.id,dv.original_sha256_hex)
      where d.org_id=v_org and d.case_id=p_case and d.id=v_brief.document_id
        and dv.id=v_brief.document_version_id
        and dv.original_sha256_hex=v_brief.original_sha256
    )
  then raise exception 'source or version check failed' using errcode='42501'; end if;
  select * into v_ingested from caseproof._dev_journey_sources s
    where s.org_id=v_org and s.case_id=p_case and s.version_id=v_brief.document_version_id;
  if v_brief.parser_id='dev-ingested-txt-brief-v1' and (
    v_ingested.version_id is null or v_ingested.original_sha<>v_brief.original_sha256
    or v_ingested.representation<>(v_exhibit.payload->>'source_text')
    or v_ingested.snapshot_sha<>v_exhibit.payload->>'snapshot_sha'
  ) then raise exception 'source snapshot fidelity failed' using errcode='42501'; end if;
  v_match := position(v_claim.assertion_text in (v_exhibit.payload->>'source_text'))>0;
  v_scope := case when v_ingested.version_id is not null then 'one signed-ingested immutable TXT source' else 'one synthetic pre-seeded TXT source only' end;
  v_outcome := case when v_match then 'candidate_quote_supported' else 'candidate_quote_mismatch' end;
  v_snapshot := encode(extensions.digest(convert_to(
    p_case::text || ':' || p_version::text || ':' || v_brief.graph_sha256
    || ':' || v_exhibit.payload_sha256 || ':' || v_brief.original_sha256
    || case when v_ingested.version_id is not null then ':'||v_ingested.snapshot_sha else '' end,
    'UTF8'),'sha256'),'hex');
  v_payload := pg_catalog.jsonb_build_object(
    'schema','dev-evidence-check-v1','snapshot_hash',v_snapshot,
    'case_id',p_case,'brief_version_id',p_version,'source_sha256',v_brief.original_sha256,
    'source_scope',v_scope,
    'observation_id',v_claim.claim_id,'assertion',v_claim.assertion_text,
    'source_quote_match',v_match,'outcome',v_outcome,
    'limits','not semantic or legal verification')::text;
  if p_action='check' then
    insert into caseproof._m2_check_runs(
      org_id,case_id,snapshot_sha,payload_sha,payload,brief_version_id,
      case_revision,exhibit_revision,actor_id)
    values(v_org,p_case,v_snapshot,
      encode(extensions.digest(convert_to(v_payload,'UTF8'),'sha256'),'hex'),
      v_payload,p_version::text,v_case_revision,v_exhibit.revision,v_actor)
    on conflict do nothing;
    if not exists(select 1 from caseproof._m2_check_runs
       where org_id=v_org and case_id=p_case and snapshot_sha=v_snapshot
         and payload=v_payload and brief_version_id=p_version::text
         and case_revision=v_case_revision and exhibit_revision=v_exhibit.revision)
    then raise exception 'snapshot conflict' using errcode='55000'; end if;
    insert into caseproof._m2_review_heads(org_id,case_id,snapshot_sha,event_sha)
      values(v_org,p_case,v_snapshot,repeat('0',64)) on conflict do nothing;
  else
    if p_snapshot is distinct from v_snapshot or not exists(
      select 1 from caseproof._m2_check_runs
      where org_id=v_org and case_id=p_case and snapshot_sha=v_snapshot
        and payload=v_payload and case_revision=v_case_revision
        and exhibit_revision=v_exhibit.revision
    ) then raise exception 'unknown or stale check snapshot' using errcode='42501'; end if;
  end if;
  if p_action='review' then
    if p_request is null or p_expected is null or p_expected<0 or p_expected>255
      or p_observation is distinct from v_claim.claim_id
      or p_disposition is null
      or p_disposition not in ('confirmed_candidate','dismissed','needs_information')
      or p_rationale is null or length(btrim(p_rationale))<1 or length(p_rationale)>2000
    then raise exception 'invalid review proposal' using errcode='42501'; end if;
    v_decision := pg_catalog.jsonb_build_object('observation_id',p_observation,
      'actor_id',v_actor,'disposition',p_disposition,'rationale',p_rationale);
    v_fingerprint := encode(extensions.digest(convert_to(
      pg_catalog.jsonb_build_object('snapshot',v_snapshot,'actor',v_actor,
        'request',p_request,'expected',p_expected,'decision',v_decision)::text,
      'UTF8'),'sha256'),'hex');
    select * into v_head from caseproof._m2_review_heads
      where org_id=v_org and case_id=p_case and snapshot_sha=v_snapshot for update;
    select * into v_old from caseproof._m2_review_receipts
      where org_id=v_org and case_id=p_case
        and snapshot_sha=v_snapshot and request_id=p_request;
    if v_old.request_id is not null then
      if v_old.input_sha <> v_fingerprint then
        raise exception 'idempotency collision' using errcode='23505'; end if;
      v_replayed := true;
    else
      if v_head.revision is null or v_head.revision<>p_expected then
        raise exception 'stale review revision' using errcode='40001'; end if;
      v_event_hash := encode(extensions.digest(convert_to(
        pg_catalog.jsonb_build_object('snapshot',v_snapshot,
          'revision',p_expected+1,'request',p_request,'actor',v_actor,
          'previous_sha',v_head.event_sha,'decision',v_decision)::text,
        'UTF8'),'sha256'),'hex');
      v_audit := gen_random_uuid();
      insert into caseproof.audit_events(
        id,org_id,case_id,actor_type,actor_user_id,action,
        event_schema_version,correlation_id,input_sha256_hex)
      values(v_audit,v_org,p_case,'human',v_actor,'m2_review_disposition',
        'dev-review-v1',p_request,v_fingerprint);
      insert into caseproof._m2_review_events(
        org_id,case_id,snapshot_sha,revision,request_id,actor_id,
        previous_sha,event_sha,decision,audit_id)
      values(v_org,p_case,v_snapshot,p_expected+1,p_request,v_actor,
        v_head.event_sha,v_event_hash,v_decision::text,v_audit);
      insert into caseproof._m2_review_receipts(
        org_id,case_id,snapshot_sha,request_id,input_sha,revision,event_sha)
      values(v_org,p_case,v_snapshot,p_request,v_fingerprint,p_expected+1,v_event_hash);
      update caseproof._m2_review_heads
        set revision=p_expected+1,event_sha=v_event_hash
      where org_id=v_org and case_id=p_case and snapshot_sha=v_snapshot;
    end if;
  end if;
  select * into v_head from caseproof._m2_review_heads
    where org_id=v_org and case_id=p_case and snapshot_sha=v_snapshot;
  -- Keep the receipt and reopening response bounded even at 256 revisions.
  -- Full append-only event history remains in the private M2 ledger.
  select coalesce(pg_catalog.jsonb_agg(
    pg_catalog.jsonb_build_object('revision',e.revision,'decision',e.decision::jsonb)
      order by e.revision),'[]'::jsonb) into v_decisions
  from (
    select revision,decision from caseproof._m2_review_events
    where org_id=v_org and case_id=p_case and snapshot_sha=v_snapshot
    order by revision desc limit 8
  ) e;
  return pg_catalog.jsonb_build_object('schema','caseproof-dev-signed-roundtrip-v1',
    'case_id',p_case,'brief_version_id',p_version,'snapshot_hash',v_snapshot,
    'observation_id',v_claim.claim_id,'outcome',v_outcome,
    'source_sha256',v_brief.original_sha256,'review_revision',v_head.revision,
    'replayed',v_replayed,'decisions',v_decisions,
    'history_truncated',v_head.revision>8,'release_authorized',false);
end $body$;


