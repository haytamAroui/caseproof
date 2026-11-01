-- Read-only metadata projection for the independently authenticated workspace.
-- Existing cases/membership/grants and dossier snapshots; no tables or indexes.
create function public.caseproof_workspace_reports(p_case uuid, p_after text default null)
returns jsonb language plpgsql security definer set search_path='' as $$
declare v_actor uuid:=auth.uid(); v_org uuid; v_reports jsonb; v_next text;
begin
 if v_actor is null or coalesce(auth.jwt()->>'role','')<>'authenticated'
 or coalesce(auth.jwt()->>'is_anonymous','false')='true'
 or p_case is null or (p_after is not null and p_after !~ '^[0-9a-f]{64}$')
 then raise exception 'matter unavailable' using errcode='42501'; end if;
 select c.org_id into v_org from caseproof.cases c
 join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=v_actor
 and m.active and m.actions @> array['case:read','evidence:read']::text[]
 join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id and g.user_id=v_actor
 and g.active and g.permissions @> array['case:read','evidence:read']::text[]
 where c.id=p_case and c.deleted_at is null for share of c;
 if v_org is null then raise exception 'matter unavailable' using errcode='42501'; end if;
 -- Existing unique (case_id,snapshot_hash) supports bounded hash keyset paging.
 -- Hash order is explicit, not a claim of chronological or current-source order.
 with candidates as (
  select s.snapshot_hash, s.created_at,
   (s.serialized::jsonb)->>'brief_id' as brief_id
  from caseproof.dossier_snapshots s where s.org_id=v_org and s.case_id=p_case
   and (p_after is null or s.snapshot_hash>p_after)
  order by s.snapshot_hash limit 21
 ), visible as (select * from candidates order by snapshot_hash limit 20)
 select coalesce((select jsonb_agg(jsonb_build_object(
  'brief_id',brief_id,'snapshot_hash',snapshot_hash,'created_at',created_at
 ) order by snapshot_hash) from visible),'[]'::jsonb),
 case when (select count(*) from candidates)>20 then (select max(snapshot_hash) from visible) else null end
 into v_reports,v_next;
 return jsonb_build_object('schema','caseproof-workspace-reports-v1','case_id',p_case,
  'reports',v_reports,'next_cursor',v_next);
end $$;
revoke all on function public.caseproof_workspace_reports(uuid,text) from public,anon,authenticated;
grant execute on function public.caseproof_workspace_reports(uuid,text) to authenticated;
