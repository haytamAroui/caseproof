-- Additive dev candidate: read frozen private dossier bytes after the existing
-- signed authorization and current bundle/confirmation freshness checks.
-- No new tables, grants on tables, writes, role claims or approval authority.
create function public.caseproof_dossier_snapshot_read(p_case uuid, p_snapshot text)
returns jsonb language plpgsql security definer set search_path='' as $$
declare v_serial text;
begin
 -- Reuse the installed entrypoint's Auth, private matter grants, membership,
 -- deletion, snapshot hash, current bundle and confirmation checks. Its case
 -- row lock remains held for this transaction, including the following read.
 perform public.caseproof_dossier(p_case,'decisions',jsonb_build_object('snapshot_hash',p_snapshot));
 select s.serialized into strict v_serial
 from caseproof.dossier_snapshots s
 where s.case_id=p_case and s.snapshot_hash=p_snapshot
 and exists(select 1 from caseproof.cases c where c.id=p_case and c.org_id=s.org_id);
 return jsonb_build_object('serialized',v_serial);
end $$;
revoke all on function public.caseproof_dossier_snapshot_read(uuid,text) from public,anon,authenticated;
grant execute on function public.caseproof_dossier_snapshot_read(uuid,text) to authenticated;
