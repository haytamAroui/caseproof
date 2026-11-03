-- REVIEW PROPOSAL ONLY. Actor-scoped recovery metadata; never returns correction text.
create function public.caseproof_dossier_draft_recovery(p_case uuid, p_parent uuid, p_snapshot text, p_reference text)
returns jsonb language plpgsql stable security definer set search_path='' as $$
declare a uuid:=auth.uid(); o uuid; result jsonb;
begin
 if a is null or coalesce(auth.jwt()->>'role','') <> 'authenticated'
 or coalesce(auth.jwt()->>'is_anonymous','false') = 'true'
 or p_case is null or p_parent is null or p_snapshot is null or p_snapshot !~ '^[0-9a-f]{64}$'
 or p_reference is null or length(p_reference) not between 1 and 256 then
  raise exception 'unavailable' using errcode='42501';
 end if;
 select c.org_id into o from caseproof.cases c
 join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=a and m.active
 and m.actions @> array['case:read','evidence:read','finding:write','review:request']::text[]
 join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id and g.user_id=a
 and g.active and g.role='reviewer'
 and g.permissions @> array['case:read','evidence:read','evidence:upload','draft:check','review:request']::text[]
 where c.id=p_case and c.deleted_at is null;
 if o is null then raise exception 'unavailable' using errcode='42501'; end if;
 select coalesce(jsonb_agg(jsonb_build_object('request_id', q.request_id, 'state', q.state,
    'version_id', case when q.state='active' then q.version_id else null end,
    'created_at', q.created_at) order by q.created_at desc), '[]'::jsonb)
 into result from (
  select r.request_id,r.state,r.version_id,r.created_at from caseproof.dossier_draft_revisions r
  where r.org_id=o and r.case_id=p_case and r.actor_id=a and r.parent_version_id=p_parent
    and r.parent_snapshot_hash=p_snapshot and r.reference_id=p_reference
  order by r.created_at desc, r.request_id desc limit 20
 ) q;
 return jsonb_build_object('operations', result);
end $$;
revoke all on function public.caseproof_dossier_draft_recovery(uuid,uuid,text,text) from public,anon,authenticated;
grant execute on function public.caseproof_dossier_draft_recovery(uuid,uuid,text,text) to authenticated;
