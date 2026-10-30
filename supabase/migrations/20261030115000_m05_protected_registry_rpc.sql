grant usage on schema caseproof to service_role;
grant select,insert,update,delete on caseproof.test_run_registry to service_role;
create or replace function public.caseproof_m05_registry(p_action text,p_run uuid,p_kind text default null,p_resource text default null,p_state text default null,p_cutoff timestamptz default null)
returns jsonb language plpgsql security definer set search_path='' as $$
declare result jsonb;
begin
 if auth.role() <> 'service_role' then raise exception 'service role required' using errcode='42501'; end if;
 if p_action='record' then
  if p_kind not in ('run','auth_user','matter','storage_file') or p_resource is null or length(p_resource)>512 then raise exception 'invalid ownership'; end if;
  insert into caseproof.test_run_registry(run_id,resource_type,resource_id,state) values(p_run,p_kind,p_resource,coalesce(p_state,'RESERVED'))
  on conflict(run_id,resource_type,resource_id) do update set state=excluded.state;
  return 'true'::jsonb;
 elsif p_action='rows' then
  select coalesce(jsonb_agg(to_jsonb(r) order by r.created_at),'[]'::jsonb) into result from caseproof.test_run_registry r where r.run_id=p_run;
  return result;
 elsif p_action='forget' then
  delete from caseproof.test_run_registry where run_id=p_run and resource_type=p_kind and resource_id=p_resource;
  return 'true'::jsonb;
 elsif p_action='stale' then
  select coalesce(jsonb_agg(distinct r.run_id),'[]'::jsonb) into result from caseproof.test_run_registry r where r.resource_type='run' and r.created_at < p_cutoff;
  return result;
 end if;
 raise exception 'unknown operation';
end $$;
revoke all on function public.caseproof_m05_registry(text,uuid,text,text,timestamptz,timestamptz) from public,anon,authenticated;
grant execute on function public.caseproof_m05_registry(text,uuid,text,text,timestamptz,timestamptz) to service_role;