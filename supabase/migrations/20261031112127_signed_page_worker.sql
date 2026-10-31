-- Additive development worker. Candidate processing never approves evidence.
create table caseproof.page_jobs (
 org_id uuid not null, case_id uuid not null, request_id uuid not null, actor_id uuid not null,
 manifest text not null check(octet_length(manifest)<=131072), manifest_hash text not null check(manifest_hash ~ '^[0-9a-f]{64}$'),
 bundle_signature text not null, state text not null default 'queued' check(state in ('queued','running','succeeded','cancelled')),
 created_at timestamptz not null default clock_timestamp(), deadline_at timestamptz not null default clock_timestamp()+interval '30 minutes',
 lease_token uuid, lease_until timestamptz, claims integer not null default 0 check(claims between 0 and 256),
 stored_bytes integer not null default 0 check(stored_bytes between 0 and 8388608),
 primary key(org_id,case_id,request_id),
 foreign key(org_id,case_id) references caseproof.cases(org_id,id) on delete cascade
);
create table caseproof.page_results (
 org_id uuid not null, case_id uuid not null, request_id uuid not null, page_key text not null,
 serialized text not null check(octet_length(serialized)<=262144), artifact_hash text not null check(artifact_hash ~ '^[0-9a-f]{64}$'),
 primary key(org_id,case_id,request_id,page_key),
 foreign key(org_id,case_id,request_id) references caseproof.page_jobs on delete cascade
);
create table caseproof.page_job_events (
 org_id uuid not null, case_id uuid not null, request_id uuid not null,
 revision bigint generated always as identity, operation text not null, created_at timestamptz not null default clock_timestamp(),
 primary key(org_id,case_id,request_id,revision),
 foreign key(org_id,case_id,request_id) references caseproof.page_jobs on delete cascade
);
alter table caseproof.page_jobs enable row level security;
alter table caseproof.page_results enable row level security;
alter table caseproof.page_job_events enable row level security;
revoke all on caseproof.page_jobs,caseproof.page_results,caseproof.page_job_events from public,anon,authenticated;
revoke all on sequence caseproof.page_job_events_revision_seq from public,anon,authenticated;

create function public.caseproof_page_job(p_case uuid,p_request uuid,p_action text,p_data jsonb default '{}'::jsonb)
returns jsonb language plpgsql security definer set search_path='' as $$
declare actor uuid:=auth.uid(); org uuid; signature text; job caseproof.page_jobs%rowtype;
 manifest_json jsonb; entry jsonb; artifact jsonb; old caseproof.page_results%rowtype;
 serialized text; hashed text; key text; result jsonb; expected integer;
begin
 if p_case is null or p_action is null or p_data is null or jsonb_typeof(p_data)<>'object'
 or actor is null or coalesce(auth.jwt()->>'role','')<>'authenticated'
 or coalesce(auth.jwt()->>'is_anonymous','false')='true' or p_request is null
 or p_action not in ('enqueue','status','claim','heartbeat','put','page','finish','yield','cancel')
 then raise exception 'page job unavailable' using errcode='42501'; end if;
 select c.org_id into org from caseproof.cases c
 join caseproof.organization_members m on m.org_id=c.org_id and m.user_id=actor and m.active
 and m.actions @> array['case:read','evidence:read','review:request']::text[]
 join caseproof._m1_matter_grants g on g.org_id=c.org_id and g.case_id=c.id and g.user_id=actor and g.active
 and g.role='reviewer' and g.permissions @> array['case:read','evidence:read','review:request']::text[]
 where c.id=p_case and c.deleted_at is null for update of c for share of m,g;
 if org is null then raise exception 'page job unavailable' using errcode='42501'; end if;
 signature:=public.caseproof_dossier(p_case,'context')->>'bundle_signature';
 if p_action='enqueue' then
  serialized:=p_data->>'manifest'; hashed:=p_data->>'manifest_hash'; manifest_json:=serialized::jsonb;
  if serialized is null or octet_length(serialized)>131072 or hashed is null
  or encode(sha256(convert_to(serialized,'UTF8')),'hex') is distinct from hashed
  or manifest_json->>'schema' is distinct from 'caseproof-page-job-v1'
  or manifest_json->>'case_id' is distinct from p_case::text
  or manifest_json->>'request_id' is distinct from p_request::text
  or manifest_json->>'bundle_signature' is distinct from signature
  or length(coalesce(manifest_json->>'engine_version','')) not between 1 and 512
  or (select count(*) from jsonb_object_keys(manifest_json))<>6
  or jsonb_typeof(manifest_json->'pages') is distinct from 'array'
  then raise exception 'invalid page manifest' using errcode='22023'; end if;
  expected:=jsonb_array_length(manifest_json->'pages');
  if expected not between 1 and 200 or
   (select count(distinct (value->>'version_id',value->>'pdf_page')) from jsonb_array_elements(manifest_json->'pages'))<>expected
  then raise exception 'invalid page inventory' using errcode='22023'; end if;
  for entry in select value from jsonb_array_elements(manifest_json->'pages') loop
   if (select count(*) from jsonb_object_keys(entry))<>5 or jsonb_typeof(entry->'pdf_page') is distinct from 'number'
   or (entry->>'pdf_page')::integer not between 1 and 64
   or jsonb_typeof(entry->'needs_ocr') is distinct from 'boolean'
   or not exists(select 1 from caseproof.document_versions dv
    join caseproof.documents d on d.id=dv.document_id and d.org_id=dv.org_id
    where d.org_id=org and d.case_id=p_case and dv.id=(entry->>'version_id')::uuid
    and d.id=(entry->>'document_id')::uuid and dv.original_sha256_hex=entry->>'original_sha256'
    and dv.media_type='application/pdf' and dv.bundle_role='exhibit')
   then raise exception 'page source unavailable' using errcode='42501'; end if;
  end loop;
  insert into caseproof.page_jobs(org_id,case_id,request_id,actor_id,manifest,manifest_hash,bundle_signature)
   values(org,p_case,p_request,actor,serialized,hashed,signature) on conflict do nothing;
 end if;
 select * into job from caseproof.page_jobs j where j.org_id=org and j.case_id=p_case and j.request_id=p_request for update;
 if not found or job.actor_id<>actor then raise exception 'page job unavailable' using errcode='42501'; end if;
 if job.bundle_signature is distinct from signature then raise exception 'page input changed' using errcode='23505'; end if;
 if p_action='enqueue' and (job.manifest_hash is distinct from hashed or job.manifest is distinct from serialized)
 then raise exception 'page manifest replay conflict' using errcode='23505'; end if;
 manifest_json:=job.manifest::jsonb;
 if p_action='cancel' then
  if job.state<>'succeeded' then
   update caseproof.page_jobs set state='cancelled',lease_token=null,lease_until=null
    where org_id=org and case_id=p_case and request_id=p_request;
  end if;
 elsif p_action='claim' then
  if job.state not in ('queued','running') or job.deadline_at<=clock_timestamp() or job.claims>=256
  or (job.state='running' and job.lease_until>clock_timestamp())
  then raise exception 'page job not claimable' using errcode='23505'; end if;
  update caseproof.page_jobs set state='running',lease_token=gen_random_uuid(),
   lease_until=least(deadline_at,clock_timestamp()+interval '120 seconds'),claims=claims+1
   where org_id=org and case_id=p_case and request_id=p_request;
 elsif p_action in ('heartbeat','put','finish','yield') then
  if job.state<>'running' or job.deadline_at<=clock_timestamp() or job.lease_until<=clock_timestamp()
  or job.lease_token is null or job.lease_token is distinct from (p_data->>'lease_token')::uuid
  then raise exception 'page lease lost' using errcode='23505'; end if;
  if p_action='heartbeat' then
   update caseproof.page_jobs set lease_until=least(deadline_at,clock_timestamp()+interval '120 seconds')
    where org_id=org and case_id=p_case and request_id=p_request;
  elsif p_action='put' then
   key:=p_data->>'page_key'; serialized:=p_data->>'serialized'; hashed:=p_data->>'artifact_hash'; artifact:=serialized::jsonb;
   if serialized is null or octet_length(serialized)>262144 or hashed is null
   or encode(sha256(convert_to(serialized,'UTF8')),'hex') is distinct from hashed
   or artifact->>'schema' is distinct from 'caseproof-page-artifact-v1'
   or artifact->>'actor_id' is distinct from actor::text
   or artifact->>'org_id' is distinct from org::text
   or artifact->>'case_id' is distinct from p_case::text or artifact->>'request_id' is distinct from p_request::text
   or artifact->>'manifest_hash' is distinct from job.manifest_hash
   or artifact->>'engine_version' is distinct from manifest_json->>'engine_version'
   or artifact->>'semantic_support' is distinct from 'not_assessed'
   or coalesce(artifact->>'server_receipt','') !~ '^[0-9a-f]{64}$'
   or coalesce(artifact->>'state','') not in ('text_extracted','ocr_candidate','ocr_unavailable')
   or not exists(select 1 from jsonb_array_elements(manifest_json->'pages') p
    where (p->>'version_id')||':'||(p->>'pdf_page')=key
    and p->>'document_id'=artifact->>'document_id' and p->>'version_id'=artifact->>'version_id'
    and p->>'original_sha256'=artifact->>'original_sha256' and p->>'pdf_page'=artifact->>'pdf_page')
   then raise exception 'invalid page artifact' using errcode='22023'; end if;
   select * into old from caseproof.page_results r where r.org_id=org and r.case_id=p_case and r.request_id=p_request and r.page_key=key;
   if found then
    if old.artifact_hash is distinct from hashed or old.serialized is distinct from serialized
    then raise exception 'page artifact replay conflict' using errcode='23505'; end if;
   else
    update caseproof.page_jobs set stored_bytes=stored_bytes+octet_length(serialized)
     where org_id=org and case_id=p_case and request_id=p_request;
    insert into caseproof.page_results values(org,p_case,p_request,key,serialized,hashed);
   end if;
  elsif p_action='finish' then
   if (select count(*) from caseproof.page_results r where r.org_id=org and r.case_id=p_case and r.request_id=p_request)
      <>jsonb_array_length(manifest_json->'pages')
   then raise exception 'page results incomplete' using errcode='23505'; end if;
   update caseproof.page_jobs set state='succeeded',lease_token=null,lease_until=null
    where org_id=org and case_id=p_case and request_id=p_request;
  else
   update caseproof.page_jobs set state='queued',lease_token=null,lease_until=null
    where org_id=org and case_id=p_case and request_id=p_request;
  end if;
 end if;
 if p_action='page' then
  select jsonb_build_object('serialized',r.serialized,'artifact_hash',r.artifact_hash) into result
  from caseproof.page_results r where r.org_id=org and r.case_id=p_case and r.request_id=p_request and r.page_key=p_data->>'page_key';
  if result is null then raise exception 'page unavailable' using errcode='42501'; end if;
 else
  select jsonb_build_object('request_id',j.request_id,'actor_id',j.actor_id,'org_id',j.org_id,
   'state',j.state,'manifest',j.manifest,'manifest_hash',j.manifest_hash,'deadline_at',j.deadline_at,
   'lease_token',case when p_action='claim' then j.lease_token else null end,'lease_until',j.lease_until,
   'claims',j.claims,'results',coalesce((select jsonb_agg(jsonb_build_object('page_key',r.page_key,'artifact_hash',r.artifact_hash) order by r.page_key)
    from caseproof.page_results r where r.org_id=org and r.case_id=p_case and r.request_id=p_request),'[]'::jsonb))
   into result from caseproof.page_jobs j where j.org_id=org and j.case_id=p_case and j.request_id=p_request;
 end if;
 if p_action not in ('status','page') then
  insert into caseproof.page_job_events(org_id,case_id,request_id,operation) values(org,p_case,p_request,p_action);
 end if;
 return result;
end $$;
revoke all on function public.caseproof_page_job(uuid,uuid,text,jsonb) from public,anon,authenticated;
grant execute on function public.caseproof_page_job(uuid,uuid,text,jsonb) to authenticated;
