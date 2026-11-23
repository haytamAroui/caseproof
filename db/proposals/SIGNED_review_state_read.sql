-- Proposal (not applied): signed review-ledger state read. One masked call
-- returns the digest-verified check-run row, the review head and the bounded
-- event history; the adapter re-derives every digest from the returned
-- content and folds the packet itself. Reviewer-only: every authorization,
-- existence or bound failure raises the same masked 42501, so the endpoint
-- is no existence oracle. Staleness (case/exhibit revision moved) and
-- custody drift are typed failures, never silent reads.
create or replace function public.caseproof_signed_review_state(
 p_case uuid, p_snapshot_sha text
) returns jsonb language plpgsql security definer set search_path='' as $$
declare
 v_actor uuid:=auth.uid(); v_org uuid; v_case_rev bigint; v_exhibit_rev bigint;
 v_run record; v_head record; v_payload jsonb; v_pair record; v_sha text;
 v_events jsonb;
begin
 if p_case is null or p_snapshot_sha is null
 or v_actor is null or coalesce(auth.jwt()->>'role','')<>'authenticated'
 or coalesce(auth.jwt()->>'is_anonymous','false')='true'
 then raise exception 'private signed user required' using errcode='42501'; end if;

 select c.org_id,c.case_revision into v_org,v_case_rev from caseproof.cases c
 join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=v_actor
   and m.active and m.actions @> array['case:read','review:request']::text[]
 join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id
   and g.user_id=v_actor and g.active and g.role='reviewer'
   and g.permissions @> array['case:read','review:request']::text[]
 where c.id=p_case;
 if v_org is null then raise exception 'matter unavailable' using errcode='42501'; end if;

 select r.payload,r.payload_sha,r.brief_version_id,r.case_revision,r.exhibit_revision
   into v_run from caseproof._m2_check_runs r
 where r.org_id=v_org and r.case_id=p_case and r.snapshot_sha=p_snapshot_sha;
 if v_run.payload is null then raise exception 'matter unavailable' using errcode='42501'; end if;

 select e.revision into v_exhibit_rev from caseproof._m1_exhibit_heads e
 where e.org_id=v_org and e.case_id=p_case;
 if v_run.case_revision<>v_case_rev or v_exhibit_rev is null
 or v_run.exhibit_revision<>v_exhibit_rev
 then return jsonb_build_object('ok',false,'error','stale'); end if;

 v_payload:=v_run.payload::jsonb;
 for v_pair in
   select (p.value->>0)::uuid s,(p.value->>1)::uuid v
   from jsonb_array_elements(v_payload->'sources'->'processed') p
 loop
   select dv.original_sha256_hex into v_sha from caseproof.documents d
   join caseproof.document_versions dv on dv.org_id=d.org_id and dv.document_id=d.id
   join caseproof._s2_009b_vault_intents i on i.org_id=dv.org_id and i.case_id=d.case_id
     and i.document_id=d.id and i.document_version_id=dv.id
     and i.sha256_hex=dv.original_sha256_hex and i.state='verified'
   where d.org_id=v_org and d.case_id=p_case and d.id=v_pair.s and dv.id=v_pair.v;
   if v_sha is null then return jsonb_build_object('ok',false,'error','conflict'); end if;
 end loop;

 select h.revision,h.event_sha into v_head from caseproof._m2_review_heads h
 where h.org_id=v_org and h.case_id=p_case and h.snapshot_sha=p_snapshot_sha;
 if v_head.revision is null then return jsonb_build_object('ok',false,'error','conflict'); end if;

 select coalesce(jsonb_agg(jsonb_build_object(
   'revision',e.revision,'request_id',e.request_id,'actor_id',e.actor_id,
   'previous_sha',e.previous_sha,'event_sha',e.event_sha,'decision',e.decision)
   order by e.revision),'[]'::jsonb) into v_events
 from (select * from caseproof._m2_review_events e
       where e.org_id=v_org and e.case_id=p_case and e.snapshot_sha=p_snapshot_sha
       order by e.revision limit 257) e;

 return jsonb_build_object(
   'ok',true,
   'run',jsonb_build_object(
     'payload',v_run.payload,'payload_sha',v_run.payload_sha,
     'brief_version_id',v_run.brief_version_id,
     'case_revision',v_run.case_revision,'exhibit_revision',v_run.exhibit_revision),
   'head',jsonb_build_object('revision',v_head.revision,'event_sha',v_head.event_sha),
   'events',v_events);
end $$;
revoke all on function public.caseproof_signed_review_state(uuid,text) from public,anon;
grant execute on function public.caseproof_signed_review_state(uuid,text) to authenticated;
