-- Serialize correction with concurrent review-head changes to reject stale decisions.
create or replace function public.caseproof_dev_correct_brief(
 p_case uuid,p_version uuid,p_snapshot text,p_expected_review integer,
 p_before text,p_after text,p_action text default 'preview',p_request uuid default null
) returns jsonb language plpgsql security definer set search_path='' as $body$
declare
 v_actor uuid:=auth.uid(); v_org uuid; v_case_revision bigint;
 v_old caseproof._m2_brief_versions%rowtype;
 v_head caseproof._m2_brief_heads%rowtype;
 v_claim caseproof._m2_brief_assertions%rowtype;
 v_rhead caseproof._m2_review_heads%rowtype;
 v_review caseproof._m2_review_events%rowtype;
 v_old_event caseproof._m2_brief_events%rowtype;
 v_old_audit caseproof.audit_events%rowtype;
 v_source caseproof._dev_journey_sources%rowtype;
 v_match integer; v_text text; v_new uuid; v_rep_sha text; v_graph text;
 v_input text; v_audit uuid; v_rev bigint; v_result jsonb;
begin
 if p_case is null or p_version is null or p_snapshot is null
 or p_snapshot !~ '^[0-9a-f]{64}$' or p_expected_review is null
 or p_expected_review not between 1 and 255
 or p_before is null or length(p_before) not between 3 and 100
 or p_after is null or length(p_after) not between 3 and 100
 or p_after=p_before or p_before !~ '[0-9]' or p_after !~ '[0-9]'
 or p_action not in ('preview','commit')
 or (p_action='commit' and p_request is null)
 or v_actor is null or coalesce(auth.jwt()->>'role','')<>'authenticated'
 or coalesce(auth.jwt()->>'is_anonymous','false')='true'
 then raise exception 'invalid signed correction request' using errcode='42501'; end if;

 -- Fresh distinct editing authority: neither reviewer nor draft checker
 -- permission alone allows editing.
 select c.org_id,c.case_revision into v_org,v_case_revision
 from caseproof.cases c
 join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=v_actor
   and m.active and m.actions @> array['case:read','evidence:read','draft:write']::text[]
 join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id
   and g.user_id=v_actor and g.active and g.role='reviewer'
   and g.permissions @> array['case:read','evidence:read','draft:write','draft:check','review:request']::text[]
 where c.id=p_case for share of c,m,g;
 if v_org is null then raise exception 'draft write unavailable' using errcode='42501'; end if;

 select b.* into v_old from caseproof._m2_brief_versions b
 where b.org_id=v_org and b.case_id=p_case and b.version_id=p_version
   and b.parser_id='dev-ingested-txt-brief-v1'
   and b.document_role='own_draft';
 if v_old.version_id is null or v_old.case_revision<>v_case_revision
 or encode(extensions.digest(convert_to(v_old.representation,'UTF8'),'sha256'),'hex')
    <> v_old.representation_sha256
 then raise exception 'unsupported or changed draft' using errcode='42501'; end if;
 select * into v_source from caseproof._dev_journey_sources
 where org_id=v_org and case_id=p_case and version_id=v_old.document_version_id;
 if v_source.version_id is null or v_source.original_sha<>v_old.original_sha256
 or not exists(select 1 from caseproof._m1_exhibit_heads e
     where e.org_id=v_org and e.case_id=p_case
      and e.revision=v_old.exhibit_revision
      and e.payload->>'snapshot_sha'=v_source.snapshot_sha)
 or not exists(select 1 from storage.objects o
     where o.bucket_id='caseproof-originals-dev'
      and o.name=concat_ws('/',v_org,p_case,v_old.document_id,
          v_old.document_version_id,v_source.original_sha))
 then raise exception 'source fidelity unavailable' using errcode='42501'; end if;
 select a.* into v_claim from caseproof._m2_brief_assertions a
 where a.org_id=v_org and a.case_id=p_case and a.brief_id=v_old.brief_id
   and a.version_id=p_version and a.claim_order=0;
 if v_claim.claim_id is null or v_claim.assertion_text<>p_before
 or substring(v_old.representation from v_claim.text_start+1
      for v_claim.text_end-v_claim.text_start)<>p_before
 then raise exception 'stale correction range' using errcode='40001'; end if;
 select * into v_rhead from caseproof._m2_review_heads h
 where h.org_id=v_org and h.case_id=p_case and h.snapshot_sha=p_snapshot
 for share;
 select * into v_review from caseproof._m2_review_events e
 where e.org_id=v_org and e.case_id=p_case and e.snapshot_sha=p_snapshot
 and e.revision=p_expected_review;
 if v_rhead.revision is null or v_rhead.revision<>p_expected_review
 or v_review.revision is null
 or v_review.decision::jsonb->>'observation_id' is distinct from v_claim.claim_id
 or not exists(select 1 from caseproof._m2_check_runs run
     where run.org_id=v_org and run.case_id=p_case
       and run.brief_version_id=p_version::text and run.snapshot_sha=p_snapshot
       and run.case_revision=v_case_revision and run.exhibit_revision=v_old.exhibit_revision)
 then raise exception 'current reviewed snapshot required' using errcode='42501'; end if;
 v_match:=v_claim.text_start+1;
 v_text:=substring(v_old.representation from 1 for v_match-1)||
    p_after||substring(v_old.representation from v_match+length(p_before));
 if octet_length(v_text) not between 1 and 8000
 then raise exception 'draft size limit' using errcode='22023'; end if;
 v_input:=encode(extensions.digest(convert_to(
   pg_catalog.jsonb_build_object('actor',v_actor,'case',p_case,
     'old_version',p_version,'old_graph',v_old.graph_sha256,
     'snapshot',p_snapshot,'review_revision',p_expected_review,
     'before',p_before,'after',p_after)::text,'UTF8'),'sha256'),'hex');

 if p_action='preview' then
  return pg_catalog.jsonb_build_object('schema','dev-signed-draft-correction-v1',
    'case_id',p_case,'parent_version_id',p_version,
    'expected_brief_revision',v_old.revision,'source_sha256',v_source.original_sha,
    'review_snapshot',p_snapshot,'preview_text',v_text,'old_text',v_old.representation,
    'new_quote',p_after,'replayed',false,'committed',false,
    'release_authorized',false,'file_modified',false);
 end if;

 select * into v_head from caseproof._m2_brief_heads h
 where h.org_id=v_org and h.case_id=p_case and h.brief_id=v_old.brief_id for update;
 -- After a lost ACK, first check exact old request and fingerprint rather than
 -- accidentally applying a second copy.
 select * into v_old_event from caseproof._m2_brief_events e
 where e.org_id=v_org and e.case_id=p_case and e.brief_id=v_old.brief_id
   and e.request_id=p_request;
 if v_old_event.version_id is not null then
   select * into v_old_audit from caseproof.audit_events
     where org_id=v_org and case_id=p_case and id=v_old_event.audit_id;
   if v_old_audit.input_sha256_hex<>v_input
      or v_old_event.expected_revision<>v_old.revision
   then raise exception 'correction idempotency conflict' using errcode='23505'; end if;
   return pg_catalog.jsonb_build_object('schema','dev-signed-draft-correction-v1',
      'case_id',p_case,'parent_version_id',p_version,
      'brief_id',v_old.brief_id,'brief_version_id',v_old_event.version_id,
      'revision',v_old_event.revision,'graph_sha',v_old_event.graph_sha256,
      'replayed',true,'committed',true,'release_authorized',false,'file_modified',false);
 end if;
 if v_head.version_id is distinct from p_version or v_head.revision<>v_old.revision
 or v_old.revision>=255 then raise exception 'stale brief head' using errcode='40001'; end if;

 v_rev:=v_old.revision+1; v_new:=gen_random_uuid();
 v_rep_sha:=encode(extensions.digest(convert_to(v_text,'UTF8'),'sha256'),'hex');
 v_graph:=encode(extensions.digest(convert_to(
   v_old.graph_sha256||':'||v_new::text||':'||v_rep_sha||':'||v_source.snapshot_sha,
   'UTF8'),'sha256'),'hex');
 insert into caseproof._m2_brief_versions(
   org_id,case_id,brief_id,version_id,revision,parent_version_id,
   document_id,document_version_id,vault_intent_id,original_sha256,
   representation_sha256,parser_id,representation,document_role,
   graph_sha256,case_revision,exhibit_revision,actor_id)
 values(v_org,p_case,v_old.brief_id,v_new,v_rev,p_version,
   v_old.document_id,v_old.document_version_id,v_old.vault_intent_id,
   v_old.original_sha256,v_rep_sha,v_old.parser_id,v_text,
   v_old.document_role,v_graph,v_old.case_revision,v_old.exhibit_revision,v_actor);
 insert into caseproof._m2_brief_references(
   org_id,case_id,brief_id,version_id,reference_order,reference_id,
   exhibit_label,exact_quote)
 select org_id,case_id,brief_id,v_new,reference_order,reference_id,
   exhibit_label,p_after
 from caseproof._m2_brief_references
 where org_id=v_org and case_id=p_case and brief_id=v_old.brief_id
   and version_id=p_version;
 insert into caseproof._m2_brief_assertions(
   org_id,case_id,brief_id,version_id,claim_order,claim_id,reference_id,
   text_start,text_end,assertion_text,kind,fact_role,language,source_language)
 values(v_org,p_case,v_old.brief_id,v_new,0,v_claim.claim_id,v_claim.reference_id,
   v_match-1,v_match-1+length(p_after),p_after,v_claim.kind,
   v_claim.fact_role,v_claim.language,v_claim.source_language);
 v_audit:=gen_random_uuid();
 insert into caseproof.audit_events(
    id,org_id,case_id,actor_type,actor_user_id,action,event_schema_version,
    correlation_id,input_sha256_hex)
 values(v_audit,v_org,p_case,'human',v_actor,'dev_brief_corrected',
    'dev-correction-v1',p_request,v_input);
 insert into caseproof._m2_brief_events(
    org_id,case_id,brief_id,revision,request_id,actor_id,version_id,
    graph_sha256,expected_revision,audit_id)
 values(v_org,p_case,v_old.brief_id,v_rev,p_request,v_actor,v_new,v_graph,
    v_old.revision,v_audit);
 update caseproof._m2_brief_heads
 set revision=v_rev,version_id=v_new
 where org_id=v_org and case_id=p_case and brief_id=v_old.brief_id
   and revision=v_old.revision and version_id=p_version;
 if not found then raise exception 'concurrent draft edit' using errcode='40001'; end if;
 return pg_catalog.jsonb_build_object('schema','dev-signed-draft-correction-v1',
    'case_id',p_case,'parent_version_id',p_version,
    'brief_id',v_old.brief_id,'brief_version_id',v_new,'revision',v_rev,
    'graph_sha',v_graph,'new_quote',p_after,'text',v_text,
    'replayed',false,'committed',true,'release_authorized',false,
    'file_modified',false);
end $body$;
revoke all on function public.caseproof_dev_correct_brief(
 uuid,uuid,text,integer,text,text,text,uuid) from public,anon;
grant execute on function public.caseproof_dev_correct_brief(
 uuid,uuid,text,integer,text,text,text,uuid) to authenticated;
