-- Phase 4: append-only, signed, scoped headless reference review ledger.
create table if not exists caseproof._phase4_reference_decisions (
  org_id uuid not null,
  case_id uuid not null,
  brief_version_id uuid not null,
  snapshot_sha text not null check (snapshot_sha ~ '^[0-9a-f]{64}$'),
  reference_id text not null check (reference_id ~ '^ref-[0-9]{4}$'),
  request_id uuid not null,
  actor_id uuid not null,
  decision text not null check (decision in ('CONFIRMED_SUPPORTED','CONFIRMED_QUALIFIED','CONFIRMED_CONTRADICTED')),
  rationale text not null check (length(rationale) between 1 and 2000),
  created_at timestamptz not null default clock_timestamp(),
  primary key (org_id,case_id,request_id)
);
revoke all on caseproof._phase4_reference_decisions from public,anon,authenticated;
alter table caseproof._phase4_reference_decisions enable row level security;

create or replace function public.caseproof_phase4_review(
 p_case uuid, p_brief uuid, p_action text, p_snapshot text,
 p_reference text default null, p_request uuid default null,
 p_decision text default null, p_rationale text default null
) returns jsonb language plpgsql security definer set search_path='' as $$
declare v_actor uuid:=auth.uid(); v_org uuid; v_row caseproof._phase4_reference_decisions%rowtype;
 v_result jsonb;
begin
 if v_actor is null or coalesce(auth.jwt()->>'role','') <> 'authenticated'
 or coalesce(auth.jwt()->>'is_anonymous','false')='true'
 or p_case is null or p_brief is null or p_snapshot !~ '^[0-9a-f]{64}$'
 or p_action not in ('record','list') then
 raise exception 'review unavailable' using errcode='42501'; end if;
 select c.org_id into v_org from caseproof.cases c
 join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=v_actor
 and m.active and m.actions @> array['case:read','evidence:read']::text[]
 join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id
 and g.user_id=v_actor and g.active
 and g.permissions @> array['case:read','evidence:read']::text[]
 where c.id=p_case;
 if v_org is null or not exists (
 select 1 from caseproof.document_versions dv
 join caseproof.documents d on d.id=dv.document_id and d.org_id=dv.org_id
 where dv.id=p_brief and d.case_id=p_case and d.org_id=v_org
 and dv.bundle_role='draft'
 ) then raise exception 'review unavailable' using errcode='42501'; end if;
 if p_action='list' then
 select coalesce(jsonb_agg(jsonb_build_object(
 'reference_id',r.reference_id,'decision',r.decision,'rationale',r.rationale,
 'reviewer_id',r.actor_id,'timestamp',r.created_at,'request_id',r.request_id
 ) order by r.created_at,r.request_id),'[]'::jsonb) into v_result
 from caseproof._phase4_reference_decisions r
 where r.org_id=v_org and r.case_id=p_case and r.brief_version_id=p_brief and r.snapshot_sha=p_snapshot;
 return jsonb_build_object('decisions',v_result);
 end if;
 if not exists(select 1 from caseproof.organization_members m where m.org_id=v_org and m.user_id=v_actor
 and m.active and m.actions @> array['review:request']::text[])
 or not exists(select 1 from caseproof._m1_matter_grants g where g.org_id=v_org
 and g.case_id=p_case and g.user_id=v_actor and g.active and g.role='reviewer'
 and g.permissions @> array['review:request']::text[])
 or p_request is null or p_reference !~ '^ref-[0-9]{4}$'
 or p_decision not in ('CONFIRMED_SUPPORTED','CONFIRMED_QUALIFIED','CONFIRMED_CONTRADICTED')
 or length(p_rationale) not between 1 and 2000
 then raise exception 'review unavailable' using errcode='42501'; end if;
 insert into caseproof._phase4_reference_decisions(
 org_id,case_id,brief_version_id,snapshot_sha,reference_id,request_id,actor_id,decision,rationale)
 values(v_org,p_case,p_brief,p_snapshot,p_reference,p_request,v_actor,p_decision,p_rationale)
 on conflict do nothing;
 select * into v_row from caseproof._phase4_reference_decisions
 where org_id=v_org and case_id=p_case and request_id=p_request;
 if v_row.brief_version_id is distinct from p_brief or v_row.snapshot_sha is distinct from p_snapshot
 or v_row.reference_id is distinct from p_reference or v_row.actor_id is distinct from v_actor
 or v_row.decision is distinct from p_decision or v_row.rationale is distinct from p_rationale
 then raise exception 'idempotency conflict' using errcode='23505'; end if;
 return jsonb_build_object('reference_id',v_row.reference_id,'decision',v_row.decision,
 'rationale',v_row.rationale,'reviewer_id',v_row.actor_id,'timestamp',v_row.created_at,
 'request_id',v_row.request_id);
end $$;
revoke all on function public.caseproof_phase4_review(uuid,uuid,text,text,text,uuid,text,text) from public,anon;
grant execute on function public.caseproof_phase4_review(uuid,uuid,text,text,text,uuid,text,text) to authenticated;
