-- Read-only historical snapshot metadata; never authorizes review/export writes.
-- Installation requires reviewed development migration and signed acceptance.
create function public.caseproof_dossier_historical_read(p_case uuid,p_snapshot text)
returns jsonb language plpgsql security definer set search_path='' as $$
declare a uuid:=auth.uid(); o uuid; result text;
begin
 if a is null or coalesce(auth.jwt()->>'role','')<>'authenticated'
 or coalesce(auth.jwt()->>'is_anonymous','false')='true'
 or p_snapshot is null or p_snapshot !~ '^[0-9a-f]{64}$'
 then raise exception 'snapshot unavailable' using errcode='42501'; end if;
 select c.org_id into o from caseproof.cases c
 join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=a
 and m.active and m.actions @> array['case:read','evidence:read']::text[]
 join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id and g.user_id=a
 and g.active and g.permissions @> array['case:read','evidence:read']::text[]
 where c.id=p_case and c.deleted_at is null for share of c;
 if o is null then raise exception 'snapshot unavailable' using errcode='42501'; end if;
 select s.serialized into result from caseproof.dossier_snapshots s
 where s.org_id=o and s.case_id=p_case and s.snapshot_hash=p_snapshot;
 if result is null then raise exception 'snapshot unavailable' using errcode='42501'; end if;
 return jsonb_build_object('serialized',result);
end $$;
revoke all on function public.caseproof_dossier_historical_read(uuid,text) from public,anon,authenticated;
grant execute on function public.caseproof_dossier_historical_read(uuid,text) to authenticated;
