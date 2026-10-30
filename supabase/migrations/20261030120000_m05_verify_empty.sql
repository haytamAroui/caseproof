create or replace function public.caseproof_m05_verify_empty(p_run uuid)
returns boolean language plpgsql security definer set search_path='' as $$
begin
 if auth.role() <> 'service_role' then
  raise exception 'service role required' using errcode='42501';
 end if;
 return not exists(select 1 from caseproof.test_run_registry where run_id=p_run)
 and not exists(select 1 from caseproof._dev_journey_fixtures where run_id=p_run)
 and not exists(select 1 from auth.users where email in
 ('caseproof-ci-owner-'||p_run::text||'@example.com',
 'caseproof-ci-ungranted-'||p_run::text||'@example.com',
 'caseproof-ci-foreign-'||p_run::text||'@example.com'));
end $$;
revoke all on function public.caseproof_m05_verify_empty(uuid) from public,anon,authenticated;
grant execute on function public.caseproof_m05_verify_empty(uuid) to service_role;
