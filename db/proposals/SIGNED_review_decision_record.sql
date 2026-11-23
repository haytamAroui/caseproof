-- Proposal (not applied): signed review-decision append with compare-and-swap.
-- The RPC authorizes the reviewer, re-checks staleness and source custody from
-- the stored digest-verified run payload, validates the decision contract
-- (actor is the caller, disposition enum, bounded rationale, observation that
-- exists in THIS run), enforces replay-before-CAS idempotency by request
-- fingerprint, computes the event digest SQL-side over the canonical template,
-- and appends event + receipt + audit + head update in one transaction.
-- Digests follow the exact canonical form the Python adapters recompute; a
-- non-canonical decision text can never verify on read (fail closed).
-- Technical review only: NEVER legal, filing or release approval.
create or replace function public.caseproof_signed_review_decision(
 p_case uuid, p_snapshot_sha text, p_request uuid,
 p_expected bigint, p_decision text
) returns jsonb language plpgsql security definer set search_path='' as $$
declare
 v_actor uuid:=auth.uid(); v_org uuid; v_case_rev bigint; v_exhibit_rev bigint;
 v_run record; v_head record; v_payload jsonb; v_dec jsonb; v_pair record;
 v_sha text; v_fingerprint text; v_receipt record;
 v_new_rev bigint; v_event_sha text; v_audit uuid;
begin
 if p_case is null or p_snapshot_sha is null or p_request is null
 or p_expected is null or p_decision is null
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

 select r.payload,r.case_revision,r.exhibit_revision into v_run
 from caseproof._m2_check_runs r
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

 -- decision contract: exact ObservationReview shape, caller-bound actor,
 -- disposition enum, bounded rationale, observation of THIS run
 if octet_length(p_decision) not between 2 and 8192
 or p_decision ~ '[\x00-\x1f]' or p_expected<0
 then return jsonb_build_object('ok',false,'error','invalid'); end if;
 begin
   v_dec:=p_decision::jsonb;
   if jsonb_typeof(v_dec)<>'object'
   or (select count(*)<>4 or bool_and(k not in
         ('actor_id','disposition','observation_id','rationale'))
       from jsonb_object_keys(v_dec) k)
   or v_dec->>'actor_id'<>v_actor::text
   or v_dec->>'disposition' not in ('confirmed_candidate','dismissed','needs_information')
   or jsonb_typeof(v_dec->'observation_id')<>'string'
   or length(v_dec->>'observation_id') not between 1 and 160
   or jsonb_typeof(v_dec->'rationale')<>'string'
   or length(btrim(v_dec->>'rationale')) not between 1 and 2000
   or not (
     exists(select 1 from jsonb_array_elements(v_payload->'citations') c
            where 'citation:'||(c.value->>'reference_id')=v_dec->>'observation_id')
     or exists(select 1 from jsonb_array_elements(v_payload->'factual_candidates') f
               where 'fact:'||(f.value->>'claim_id')=v_dec->>'observation_id'))
   then return jsonb_build_object('ok',false,'error','invalid'); end if;
 exception when others then
   return jsonb_build_object('ok',false,'error','invalid');
 end;

 v_fingerprint:=encode(sha256(convert_to(
   '{"actor":"'||v_actor::text||'","decision":'||to_jsonb(p_decision)::text
   ||',"expected":'||p_expected||',"request":"'||p_request::text
   ||'","run":"'||p_snapshot_sha||'"}','UTF8')),'hex');

 select h.revision,h.event_sha into v_head from caseproof._m2_review_heads h
 where h.org_id=v_org and h.case_id=p_case and h.snapshot_sha=p_snapshot_sha
 for update;
 if v_head.revision is null then return jsonb_build_object('ok',false,'error','conflict'); end if;

 -- replay first: an identical recorded request replays regardless of the
 -- head revision the caller computed against; any difference conflicts
 select r.input_sha into v_receipt from caseproof._m2_review_receipts r
 where r.org_id=v_org and r.case_id=p_case and r.snapshot_sha=p_snapshot_sha
   and r.request_id=p_request;
 if found then
   if v_receipt.input_sha=v_fingerprint then
     return jsonb_build_object('ok',true,'replay',true,
       'revision',v_head.revision,'event_sha',v_head.event_sha);
   end if;
   return jsonb_build_object('ok',false,'error','conflict');
 end if;

 if v_head.revision<>p_expected
 then return jsonb_build_object('ok',false,'error','conflict','revision',v_head.revision); end if;
 if v_head.revision>=256
 then return jsonb_build_object('ok',false,'error','invalid'); end if;

 v_new_rev:=v_head.revision+1;
 v_event_sha:=encode(sha256(convert_to(
   '{"actor":"'||v_actor::text||'","decision":'||p_decision
   ||',"previous_sha":"'||v_head.event_sha||'","request":"'||p_request::text
   ||'","revision":'||v_new_rev||',"run":"'||p_snapshot_sha||'"}','UTF8')),'hex');

 insert into caseproof.audit_events(org_id,case_id,actor_type,actor_user_id,action,
   event_schema_version,correlation_id,input_sha256_hex)
 values(v_org,p_case,'human',v_actor,'m2_review_disposition','m2-v1',p_request,v_fingerprint)
 returning id into v_audit;
 insert into caseproof._m2_review_events(org_id,case_id,snapshot_sha,revision,request_id,
   actor_id,previous_sha,event_sha,decision,audit_id)
 values(v_org,p_case,p_snapshot_sha,v_new_rev,p_request,v_actor,
        v_head.event_sha,v_event_sha,p_decision,v_audit);
 insert into caseproof._m2_review_receipts(org_id,case_id,snapshot_sha,request_id,
   input_sha,revision,event_sha)
 values(v_org,p_case,p_snapshot_sha,p_request,v_fingerprint,v_new_rev,v_event_sha);
 update caseproof._m2_review_heads set revision=v_new_rev,event_sha=v_event_sha
 where org_id=v_org and case_id=p_case and snapshot_sha=p_snapshot_sha;
 return jsonb_build_object('ok',true,'replay',false,
   'revision',v_new_rev,'event_sha',v_event_sha);
end $$;
revoke all on function public.caseproof_signed_review_decision(uuid,text,uuid,bigint,text)
  from public,anon;
grant execute on function public.caseproof_signed_review_decision(uuid,text,uuid,bigint,text)
  to authenticated;
