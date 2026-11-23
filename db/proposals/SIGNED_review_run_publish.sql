-- Proposal (not applied): signed check-run publish for the review ledger.
-- A signed reviewer records a server-computed VerificationRun payload; the
-- RPC authorizes by caller JWT, verifies the payload digest and the payload's
-- binding to the path keys, pins the current case/exhibit revisions, and
-- re-verifies verified custody of every processed source plus the digest of
-- every citation/factual observation that points at one. Replay of the same
-- snapshot is idempotent; a diverging stored payload conflicts. Technical
-- review records only: NEVER legal, filing or release approval.
create or replace function public.caseproof_signed_review_run_publish(
 p_case uuid, p_snapshot_sha text, p_brief_version text,
 p_exhibit_revision bigint, p_payload text, p_payload_sha text
) returns jsonb language plpgsql security definer set search_path='' as $$
declare
 v_actor uuid:=auth.uid(); v_org uuid; v_case_rev bigint; v_exhibit_rev bigint;
 v_payload jsonb; v_inserted boolean;
 v_stored record; v_pair record; v_sha text;
 v_declared text[]; v_processed text[]; v_incomplete text[]; v_excluded text[];
begin
 if p_case is null or p_snapshot_sha is null or p_brief_version is null
 or p_exhibit_revision is null or p_payload is null or p_payload_sha is null
 or v_actor is null or coalesce(auth.jwt()->>'role','')<>'authenticated'
 or coalesce(auth.jwt()->>'is_anonymous','false')='true'
 then raise exception 'private signed user required' using errcode='42501'; end if;

 select c.org_id,c.case_revision into v_org,v_case_rev from caseproof.cases c
 join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=v_actor
   and m.active and m.actions @> array['case:read','finding:write']::text[]
 join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id
   and g.user_id=v_actor and g.active
   and g.permissions @> array['case:read','draft:check']::text[]
 where c.id=p_case;
 if v_org is null then raise exception 'matter unavailable' using errcode='42501'; end if;

 if p_snapshot_sha !~ '^[0-9a-f]{64}$' or p_payload_sha !~ '^[0-9a-f]{64}$'
 or octet_length(p_payload) not between 2 and 262144
 or length(p_brief_version) not between 1 and 128 or p_exhibit_revision<1
 or p_payload ~ '[\x00-\x08\x0b\x0c\x0e-\x1f]'
 then return jsonb_build_object('ok',false,'error','invalid'); end if;

 begin
   -- digest verified at write: the stored payload is exactly the bytes digested
   if encode(sha256(convert_to(p_payload,'UTF8')),'hex')<>p_payload_sha
   then return jsonb_build_object('ok',false,'error','invalid'); end if;
   v_payload:=p_payload::jsonb;
   if jsonb_typeof(v_payload)<>'object'
   or v_payload->>'schema'<>'caseproof-litigation-verification-run-v1'
   or v_payload->>'engine'<>'caseproof-disputes-unified-factual-v1'
   or v_payload->>'case_id'<>p_case::text
   or v_payload->>'brief_version_id'<>p_brief_version
   or v_payload->>'snapshot_hash'<>p_snapshot_sha
   or (v_payload->>'exhibit_revision')::bigint<>p_exhibit_revision
   or coalesce(v_payload->'reviewer_dispositions','[]'::jsonb)<>'[]'::jsonb
   or jsonb_typeof(v_payload->'sources')<>'object'
   or jsonb_typeof(v_payload->'sources'->'declared')<>'array'
   or jsonb_typeof(v_payload->'sources'->'processed')<>'array'
   or jsonb_typeof(v_payload->'sources'->'incomplete')<>'array'
   or jsonb_typeof(v_payload->'sources'->'excluded')<>'array'
   or jsonb_typeof(v_payload->'citations')<>'array'
   or jsonb_typeof(v_payload->'factual_candidates')<>'array'
   or (v_payload ? 'human_passage_flags' and (
         jsonb_typeof(v_payload->'human_passage_flags')<>'array'
         or jsonb_array_length(v_payload->'human_passage_flags')>512
         or exists(select 1 from jsonb_array_elements(v_payload->'human_passage_flags') h
                   where jsonb_typeof(h.value)<>'object'
                    or coalesce(h.value->>'origin','')<>'human_reported_not_automatically_detected'
                    or coalesce(h.value->>'semantic_support','')<>'not_assessed')))
   or (v_payload ? 'event_candidates' and (
         jsonb_typeof(v_payload->'event_candidates')<>'array'
         or jsonb_array_length(v_payload->'event_candidates')>128
         or exists(select 1 from jsonb_array_elements(v_payload->'event_candidates') e
                   where jsonb_typeof(e.value)<>'object'
                      or jsonb_typeof(e.value->'observation_id')<>'string'
                      or coalesce(e.value->>'semantic_support','')<>'not_assessed'
                      or coalesce(e.value->>'state','')<>'needs_context')))
   or (v_payload ? 'suitability' and (
         jsonb_typeof(v_payload->'suitability')<>'array'
         or jsonb_array_length(v_payload->'suitability')>128
         or exists(select 1 from jsonb_array_elements(v_payload->'suitability') s
                   where jsonb_typeof(s.value)<>'object'
                      or jsonb_typeof(s.value->'rule_id')<>'string'
                      or (s.value->>'status') not in ('PASS','FAIL','UNDETERMINED','UNVERIFIED'))))
   or (v_payload ? 'legal_references' and (
         jsonb_typeof(v_payload->'legal_references')<>'array'
         or jsonb_array_length(v_payload->'legal_references')>512
         or exists(select 1 from jsonb_array_elements(v_payload->'legal_references') l
                   where jsonb_typeof(l.value)<>'object'
                      or jsonb_typeof(l.value->'reference_id')<>'string'
                      or (l.value->>'status') not in ('PASS','FAIL','UNDETERMINED','UNVERIFIED')
                      or ((l.value->>'status')='UNVERIFIED'
                          and (l.value->>'reason')<>'article_absent_from_chosen_corpus'))))
   then return jsonb_build_object('ok',false,'error','invalid'); end if;

   -- source denominator: bounded uuid pairs, subsets and disjointness
   if (select count(*) from (
         select value from jsonb_array_elements(v_payload->'sources'->'declared')
         union all select value from jsonb_array_elements(v_payload->'sources'->'processed')
         union all select value from jsonb_array_elements(v_payload->'sources'->'incomplete')
         union all select value from jsonb_array_elements(v_payload->'sources'->'excluded')) p
       where jsonb_typeof(p.value)<>'array' or jsonb_array_length(p.value)<>2
         or (p.value->>0) !~ '^[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$'
         or (p.value->>1) !~ '^[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$')>0
   then return jsonb_build_object('ok',false,'error','invalid'); end if;
   select coalesce(array_agg(lower((p.value->>0)||'/'||(p.value->>1))),'{}'::text[])
     into v_declared
   from jsonb_array_elements(v_payload->'sources'->'declared') p;
   select coalesce(array_agg(lower((p.value->>0)||'/'||(p.value->>1))),'{}'::text[])
     into v_processed
   from jsonb_array_elements(v_payload->'sources'->'processed') p;
   select coalesce(array_agg(lower((p.value->>0)||'/'||(p.value->>1))),'{}'::text[])
     into v_incomplete
   from jsonb_array_elements(v_payload->'sources'->'incomplete') p;
   select coalesce(array_agg(lower((p.value->>0)||'/'||(p.value->>1))),'{}'::text[])
     into v_excluded
   from jsonb_array_elements(v_payload->'sources'->'excluded') p;
   if cardinality(v_declared)>32 or cardinality(v_processed)>32
   or cardinality(v_incomplete)>32 or cardinality(v_excluded)>32
   or not (v_processed<@v_declared and v_incomplete<@v_declared and v_excluded<@v_declared)
   or (v_processed&&v_incomplete) or (v_processed&&v_excluded)
   then return jsonb_build_object('ok',false,'error','invalid'); end if;
 exception when others then
   return jsonb_build_object('ok',false,'error','invalid');
 end;

 -- staleness: the run must pin the current exhibit register revision
 select e.revision into v_exhibit_rev from caseproof._m1_exhibit_heads e
 where e.org_id=v_org and e.case_id=p_case;
 if v_exhibit_rev is null or v_exhibit_rev<>p_exhibit_revision
 then return jsonb_build_object('ok',false,'error','conflict'); end if;

 -- verified custody for every processed source; every observation pointing
 -- at a processed source must carry that source's exact original digest
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
   if v_sha is null then return jsonb_build_object('ok',false,'error','invalid'); end if;
   if exists(select 1 from jsonb_array_elements(v_payload->'citations') c
             where c.value->>'source_id'=v_pair.s::text
               and c.value->>'source_version_id'=v_pair.v::text
               and coalesce(c.value->>'source_sha256','')<>v_sha)
   or exists(select 1 from jsonb_array_elements(v_payload->'factual_candidates') f
             where f.value->>'source_id'=v_pair.s::text
               and f.value->>'source_version_id'=v_pair.v::text
               and coalesce(f.value->>'source_sha256','')<>v_sha)
   or exists(select 1 from jsonb_array_elements(coalesce(v_payload->'event_candidates','[]'::jsonb)) e
             where e.value->>'source_id'=v_pair.s::text
               and e.value->>'source_version_id'=v_pair.v::text
               and coalesce(e.value->>'source_sha256','')<>v_sha)
   then return jsonb_build_object('ok',false,'error','invalid'); end if;
 end loop;

 insert into caseproof._m2_check_runs(org_id,case_id,snapshot_sha,payload_sha,payload,
   brief_version_id,case_revision,exhibit_revision,actor_id)
 values(v_org,p_case,p_snapshot_sha,p_payload_sha,p_payload,p_brief_version,
        v_case_rev,p_exhibit_revision,v_actor)
 on conflict do nothing;
 v_inserted:=found;
 -- replay coherence: a stored snapshot must be byte-identical and still pinned
 select r.payload,r.case_revision,r.exhibit_revision,r.brief_version_id into v_stored
 from caseproof._m2_check_runs r
 where r.org_id=v_org and r.case_id=p_case and r.snapshot_sha=p_snapshot_sha;
 if v_stored.payload<>p_payload or v_stored.case_revision<>v_case_rev
 or v_stored.exhibit_revision<>p_exhibit_revision
 or v_stored.brief_version_id<>p_brief_version
 then return jsonb_build_object('ok',false,'error','conflict'); end if;

 insert into caseproof._m2_review_heads(org_id,case_id,snapshot_sha,event_sha)
 values(v_org,p_case,p_snapshot_sha,repeat('0',64)) on conflict do nothing;
 return jsonb_build_object('ok',true,'replay',not v_inserted);
end $$;
revoke all on function public.caseproof_signed_review_run_publish(uuid,text,text,bigint,text,text)
  from public,anon;
grant execute on function public.caseproof_signed_review_run_publish(uuid,text,text,bigint,text,text)
  to authenticated;
