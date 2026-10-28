-- DEV-ONLY: signed Auth scoped check/review of a pre-seeded synthetic source.
-- Private M2 tables stay deny-by-default. This is NOT the production review API.
-- Seed RPC requires service_role; check/review RPC requires an actual Auth JWT.
do $gate$
begin
  if to_regclass('caseproof._dev_ci_fixture') is null
    or to_regclass('caseproof._m1_exhibit_heads') is null
    or to_regclass('caseproof._m2_brief_versions') is null
    or to_regclass('caseproof._m2_review_receipts') is null
    or (select count(*) from storage.buckets where id='caseproof-originals-dev' and not public) <> 1
  then raise exception 'pinned dev fixture and M1/M2 private schema required' using errcode='55000';
  end if;
end $gate$;

create function public.caseproof_dev_review_seed(p_run_id uuid, p_owner uuid)
returns jsonb language plpgsql security definer set search_path=''
as $body$
declare
  f caseproof._dev_ci_fixture%rowtype;
  v_text text := 'CASEPROOF CI 2026: synthetic proof of 125 EUR on 23 October. Not client evidence.' || chr(10);
  v_brief uuid := gen_random_uuid();
  v_version uuid := gen_random_uuid();
  v_exhibit jsonb;
  v_audit uuid := gen_random_uuid();
  v_brief_audit uuid := gen_random_uuid();
  v_graph text;
begin
  select * into f from caseproof._dev_ci_fixture where run_id=p_run_id and owner_id=p_owner for update;
  if not found or exists(select 1 from caseproof._m2_brief_versions where case_id=f.case_id)
    or exists(select 1 from caseproof._m2_check_runs where case_id=f.case_id)
    or exists(select 1 from caseproof._m1_exhibit_heads where case_id=f.case_id)
    or encode(extensions.digest(convert_to(v_text,'UTF8'),'sha256'),'hex') <> f.original_sha256
    or not exists (
      select 1 from storage.objects o
      where o.bucket_id='caseproof-originals-dev'
        and o.name=concat_ws('/',f.org_id,f.case_id,f.document_id,f.version_id,f.original_sha256)
    )
  then raise exception 'signed original not uploaded or synthetic seed already exists'
    using errcode='42501';
  end if;
  v_exhibit := pg_catalog.jsonb_build_object(
    'label','P1','source_id',f.document_id,'version_id',f.version_id,
    'original_sha256',f.original_sha256,'source_text',v_text,'scope','processed',
    'origin','verified synthetic Storage download only');
  insert into caseproof._m1_exhibit_heads(org_id,case_id,revision,payload,payload_sha256)
    values(f.org_id,f.case_id,1,v_exhibit,
      encode(extensions.digest(convert_to(v_exhibit::text,'UTF8'),'sha256'),'hex'));
  insert into caseproof.audit_events(
    id,org_id,case_id,actor_type,actor_user_id,action,event_schema_version,
    correlation_id,input_sha256_hex)
    values(v_audit,f.org_id,f.case_id,'human',p_owner,'dev_synthetic_exhibit',
      'dev-review-v1',p_run_id,f.original_sha256);
  insert into caseproof._m1_exhibit_events(
    org_id,case_id,revision,request_id,actor_user_id,expected_revision,
    payload_sha256,payload,audit_id)
    values(f.org_id,f.case_id,1,p_run_id,p_owner,0,
      encode(extensions.digest(convert_to(v_exhibit::text,'UTF8'),'sha256'),'hex'),
      v_exhibit,v_audit);
  v_graph := encode(extensions.digest(
    convert_to(v_text || v_brief::text || v_version::text,'UTF8'),'sha256'),'hex');
  insert into caseproof._m2_brief_versions(
    org_id,case_id,brief_id,version_id,revision,document_id,document_version_id,
    vault_intent_id,original_sha256,representation_sha256,parser_id,
    representation,document_role,graph_sha256,case_revision,exhibit_revision,actor_id)
  values(f.org_id,f.case_id,v_brief,v_version,1,f.document_id,f.version_id,
    gen_random_uuid(),f.original_sha256,
    encode(extensions.digest(convert_to(v_text,'UTF8'),'sha256'),'hex'),
    'dev-synthetic-preseed-v1',v_text,'own_draft',v_graph,1,1,p_owner);
  insert into caseproof._m2_brief_references(
    org_id,case_id,brief_id,version_id,reference_order,reference_id,exhibit_label,exact_quote)
  values(f.org_id,f.case_id,v_brief,v_version,0,'P1','P1','125 EUR');
  insert into caseproof._m2_brief_assertions(
    org_id,case_id,brief_id,version_id,claim_order,claim_id,reference_id,
    text_start,text_end,assertion_text,kind,fact_role,language,source_language)
  values(f.org_id,f.case_id,v_brief,v_version,0,'fact:money-1','P1',
    position('125 EUR' in v_text)-1,position('125 EUR' in v_text)-1+7,
    '125 EUR','money','invoice','en','en');
  insert into caseproof._m2_brief_heads(org_id,case_id,brief_id,revision,version_id)
  values(f.org_id,f.case_id,v_brief,1,v_version);
  insert into caseproof.audit_events(
    id,org_id,case_id,actor_type,actor_user_id,action,event_schema_version,
    correlation_id,input_sha256_hex)
    values(v_brief_audit,f.org_id,f.case_id,'human',p_owner,'dev_synthetic_brief',
      'dev-review-v1',p_run_id,v_graph);
  insert into caseproof._m2_brief_events(
    org_id,case_id,brief_id,revision,request_id,actor_id,version_id,
    graph_sha256,expected_revision,audit_id)
  values(f.org_id,f.case_id,v_brief,1,p_run_id,p_owner,v_version,v_graph,0,v_brief_audit);
  return pg_catalog.jsonb_build_object('case_id',f.case_id,'brief_id',v_brief,
    'brief_version_id',v_version,'original_sha256',f.original_sha256,
    'seed','stored private brief and exhibit; no ingestion/OCR/Vault intent');
end $body$;

create function public.caseproof_dev_live_review(
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
      and a.version_id=p_version and a.claim_id='fact:money-1';
  if v_brief.version_id is null or v_exhibit.revision is null or v_claim.claim_id is null
    or v_brief.case_revision <> v_case_revision
    or v_brief.exhibit_revision <> v_exhibit.revision
    or v_exhibit.payload->>'original_sha256' <> v_brief.original_sha256
    or v_exhibit.payload->>'source_id' <> v_brief.document_id::text
    or v_exhibit.payload->>'version_id' <> v_brief.document_version_id::text
    or encode(extensions.digest(convert_to(v_brief.representation,'UTF8'),'sha256'),'hex')
      <> v_brief.representation_sha256
    or pg_catalog.substring(v_brief.representation from v_claim.text_start+1
       for v_claim.text_end-v_claim.text_start) <> v_claim.assertion_text
    or pg_catalog.position(v_claim.assertion_text in (v_exhibit.payload->>'source_text')) = 0
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
  v_snapshot := encode(extensions.digest(convert_to(
    p_case::text || ':' || p_version::text || ':' || v_brief.graph_sha256
    || ':' || v_exhibit.payload_sha256 || ':' || v_brief.original_sha256,
    'UTF8'),'sha256'),'hex');
  v_payload := pg_catalog.jsonb_build_object(
    'schema','dev-evidence-check-v1','snapshot_hash',v_snapshot,
    'case_id',p_case,'brief_version_id',p_version,'source_sha256',v_brief.original_sha256,
    'source_scope','one synthetic pre-seeded TXT source only',
    'observation_id',v_claim.claim_id,'assertion',v_claim.assertion_text,
    'source_quote_match',true,'outcome','candidate_quote_supported',
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
  select coalesce(pg_catalog.jsonb_agg(
    pg_catalog.jsonb_build_object('revision',e.revision,'decision',e.decision::jsonb)
      order by e.revision),'[]'::jsonb) into v_decisions
  from caseproof._m2_review_events e
  where e.org_id=v_org and e.case_id=p_case and e.snapshot_sha=v_snapshot;
  return pg_catalog.jsonb_build_object('schema','caseproof-dev-signed-roundtrip-v1',
    'case_id',p_case,'brief_version_id',p_version,'snapshot_hash',v_snapshot,
    'observation_id',v_claim.claim_id,'outcome','candidate_quote_supported',
    'source_sha256',v_brief.original_sha256,'review_revision',v_head.revision,
    'replayed',v_replayed,'decisions',v_decisions,'release_authorized',false);
end $body$;

revoke all on function public.caseproof_dev_review_seed(uuid,uuid)
  from public,anon,authenticated;
grant execute on function public.caseproof_dev_review_seed(uuid,uuid) to service_role;
revoke all on function public.caseproof_dev_live_review(
  uuid,uuid,text,text,uuid,integer,text,text,text) from public,anon,authenticated;
grant execute on function public.caseproof_dev_live_review(
  uuid,uuid,text,text,uuid,integer,text,text,text) to authenticated;
