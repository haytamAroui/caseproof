-- Signed workbench read RPC for the review record (PROPOSED, not yet applied).
--
-- Design: the RPC authenticates the signed user, authorizes evidence read on
-- the matter and returns the RAW recorded state (brief head, check runs,
-- review heads/events), bounded. It never recomputes digests in SQL: the
-- calling service replays the review hash chain and verifies payload digests
-- with the exact Python canonicalization, failing closed on any mismatch.
-- Chain immutability remains enforced write-side by the existing triggers;
-- this function changes nothing.
--
-- security definer, search_path='', writes forbidden: read-only transcript.
-- Denials raise 42501 so PostgREST masks the matter; they never leak which
-- part was missing.

do $check$ begin
  if to_regclass('caseproof._m2_brief_heads') is null
    or to_regclass('caseproof._m2_brief_versions') is null
    or to_regclass('caseproof._m2_check_runs') is null
    or to_regclass('caseproof._m2_review_heads') is null
    or to_regclass('caseproof._m2_review_events') is null
    or to_regclass('caseproof.cases') is null
    or to_regclass('caseproof.organization_members') is null
    or to_regclass('caseproof._m1_matter_grants') is null
  then raise exception 'signed review record prerequisite absent' using errcode='55000';
  end if;
end $check$;

create or replace function public.caseproof_signed_review_record(
  p_case uuid, p_role text
) returns jsonb language plpgsql security definer set search_path=''
as $body$
declare
  v_actor uuid := auth.uid();
  v_org uuid;
  v_head record;
  v_checks jsonb;
  v_review_heads jsonb;
  v_review_events jsonb;
  v_count int;
begin
  if p_case is null or p_role not in ('own_draft','opponent_brief')
    or v_actor is null or coalesce(auth.jwt()->>'role','')<>'authenticated'
    or coalesce(auth.jwt()->>'is_anonymous','false')='true'
  then raise exception 'private signed user required' using errcode='42501'; end if;

  -- One exact current organization/matter grant with evidence read, never
  -- client-supplied actor or org.
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

  select h.revision, h.version_id, v.graph_sha256, v.original_sha256,
         v.document_id, v.document_version_id, v.case_revision, v.exhibit_revision
    into v_head
  from caseproof._m2_brief_heads h
  join caseproof._m2_brief_versions v on v.org_id=h.org_id and v.case_id=h.case_id
    and v.brief_id=h.brief_id and v.version_id=h.version_id
  where h.org_id=v_org and h.case_id=p_case and v.document_role=p_role
    and v.revision=h.revision;
  if v_head.version_id is null then
    raise exception 'matter unavailable' using errcode='42501';
  end if;

  select count(*) into v_count from caseproof._m2_check_runs r
  where r.org_id=v_org and r.case_id=p_case and r.brief_version_id=v_head.version_id::text;
  if v_count > 20 then
    raise exception 'unbounded recorded check history' using errcode='55000';
  end if;
  select coalesce(jsonb_agg(jsonb_build_object(
           'snapshot_sha256',r.snapshot_sha,'payload_sha256',r.payload_sha,
           'case_revision',r.case_revision,'exhibit_revision',r.exhibit_revision,
           'payload',r.payload) order by r.snapshot_sha), '[]'::jsonb)
    into v_checks
  from caseproof._m2_check_runs r
  where r.org_id=v_org and r.case_id=p_case and r.brief_version_id=v_head.version_id::text;

  select count(*) into v_count from caseproof._m2_review_events e
  where e.org_id=v_org and e.case_id=p_case;
  if v_count > 256 then
    raise exception 'unbounded recorded review history' using errcode='55000';
  end if;
  select coalesce(jsonb_agg(jsonb_build_object(
           'snapshot_sha256',h.snapshot_sha,'event_sha256',h.event_sha)
           order by h.snapshot_sha), '[]'::jsonb)
    into v_review_heads
  from caseproof._m2_review_heads h
  where h.org_id=v_org and h.case_id=p_case;
  select coalesce(jsonb_agg(jsonb_build_object(
           'snapshot_sha256',e.snapshot_sha,'revision',e.revision,
           'request_id',e.request_id,'actor_id',e.actor_id,
           'event_sha256',e.event_sha,'decision',e.decision)
           order by e.snapshot_sha, e.revision), '[]'::jsonb)
    into v_review_events
  from caseproof._m2_review_events e
  where e.org_id=v_org and e.case_id=p_case;

  return jsonb_build_object(
    'ok', true,
    'brief', jsonb_build_object(
      'head_revision', v_head.revision, 'version_id', v_head.version_id,
      'graph_sha256', v_head.graph_sha256, 'original_sha256', v_head.original_sha256,
      'document_id', v_head.document_id, 'document_version_id', v_head.document_version_id,
      'case_revision', v_head.case_revision, 'exhibit_revision', v_head.exhibit_revision),
    'checks', v_checks,
    'review_heads', v_review_heads,
    'review_events', v_review_events);
end;
$body$;

revoke all on function public.caseproof_signed_review_record(uuid,text) from public, anon;
grant execute on function public.caseproof_signed_review_record(uuid,text) to authenticated;
