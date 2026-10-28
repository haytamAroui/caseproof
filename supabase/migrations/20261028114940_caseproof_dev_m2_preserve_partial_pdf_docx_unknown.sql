-- Incomplete parsed PDF/DOCX coverage never becomes verified quote support or mismatch.
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
  v_scope := case when exists(select 1 from caseproof._dev_journey_parse_manifests pm
    where pm.org_id=v_org and pm.case_id=p_case and pm.version_id=v_ingested.version_id
      and pm.manifest->>'complete'='false')
    then 'one verified original with incomplete PDF/DOCX extraction, missing coverage'
    when v_ingested.version_id is not null then 'one verified signed-ingested source'
    else 'one synthetic pre-seeded TXT source only' end;
  v_outcome := case when exists(select 1 from caseproof._dev_journey_parse_manifests pm
    where pm.org_id=v_org and pm.case_id=p_case and pm.version_id=v_ingested.version_id
      and pm.manifest->>'complete'='false')
    then 'candidate_quote_not_assessed_partial'
    when v_match then 'candidate_quote_supported'
    else 'candidate_quote_mismatch' end;
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


