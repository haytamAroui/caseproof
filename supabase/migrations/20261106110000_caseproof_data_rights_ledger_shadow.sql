-- Data Rights Ledger PR 1: append-only versioned rights, signed mutations, private reads.
-- Shadow ONLY. Does not change existing read, export, intake or purge authorization.
-- No default policy rows and NO backfill. Development profile pending approval.
begin;

-- Both the organization membership and the matter assignment are necessary.
-- A matter's single pilot owner is the only possible rights manager.
alter table caseproof.organization_members
  drop constraint organization_members_actions_check;
alter table caseproof.organization_members
  add constraint organization_members_actions_check check(actions <@ array[
    'case:read','case:create','coverage:read','evidence:read','finding:write',
    'review:request','conclusion:request_approval','exception:request',
    'draft:write','export:request','rights:manage'
  ]::text[]);
alter table caseproof._m1_matter_grants
  drop constraint _m1_matter_grants_permissions_check;
alter table caseproof._m1_matter_grants
  add constraint _m1_matter_grants_permissions_check check(permissions <@ array[
    'case:read','coverage:read','evidence:read','review:request','finding:write',
    'evidence:upload','evidence:index','exhibit:confirm','draft:check',
    'draft:write','export:request','rights:manage'
  ]::text[]);

create table caseproof.source_rights_policies (
  org_id uuid not null,
  case_id uuid not null,
  document_id uuid not null,
  version_id uuid not null,
  policy_version bigint not null check(policy_version between 1 and 9223372036854775806),
  request_id uuid not null,
  actor_user_id uuid not null,
  origin text not null check(origin='CLIENT_UPLOAD'),
  classification text not null check(classification='CLIENT_CONFIDENTIAL'),
  authorization_reference text check(
    authorization_reference is null or
    length(btrim(authorization_reference)) between 1 and 256
  ),
  process boolean not null,
  index_for_search boolean not null default false,
  use_across_matters boolean not null default false,
  export_same_matter boolean not null,
  payload_sha256_hex text not null check(payload_sha256_hex ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default clock_timestamp(),
  primary key(org_id,case_id,version_id,policy_version),
  unique(org_id,case_id,request_id),
  foreign key(org_id,case_id)
    references caseproof.cases(org_id,id) on delete cascade,
  foreign key(org_id,document_id)
    references caseproof.documents(org_id,id) on delete cascade,
  foreign key(org_id,version_id)
    references caseproof.document_versions(org_id,id) on delete cascade,
  foreign key(org_id,actor_user_id)
    references caseproof.organization_members(org_id,user_id),
  check (not process or authorization_reference is not null)
);
create index source_rights_policy_history_idx
  on caseproof.source_rights_policies
  (org_id,case_id,version_id,policy_version desc);
alter table caseproof.source_rights_policies enable row level security;
revoke all on caseproof.source_rights_policies from public,anon,authenticated;
-- Existing privileged retention_finalize deletes source versions and cases.
-- Its transaction-local cleanup flag and service JWT are BOTH required before
-- the foreign-key cascade may delete rights history. Never permit UPDATE.
create function caseproof.source_rights_immutable_guard()
returns trigger language plpgsql security invoker set search_path='' as $$
begin
  if tg_op='DELETE'
     and current_setting('caseproof.dev_review_cleanup',true)='single_fixture'
     and coalesce(auth.jwt()->>'role','')='service_role' then
    return old;
  end if;
  raise exception 'rights policy history is immutable' using errcode='42501';
end $$;
revoke all on function caseproof.source_rights_immutable_guard()
  from public,anon,authenticated;
create trigger source_rights_immutable
  before update or delete on caseproof.source_rights_policies
  for each row execute function caseproof.source_rights_immutable_guard();
create trigger retention_write_guard
  before insert on caseproof.source_rights_policies
  for each row execute function caseproof.retention_write_guard();

-- No direct table write from signed clients: only this narrow RPC can append.
-- Row-lock on cases serializes versions, revocation and purge across sessions.
create function public.caseproof_rights_manage(
  p_case uuid, p_document uuid, p_version uuid,
  p_expected_version bigint, p_request uuid, p_policy jsonb
) returns jsonb language plpgsql security definer set search_path='' as $$
declare
  a uuid := auth.uid();
  o uuid;
  v_current bigint;
  v_prior caseproof.source_rights_policies%rowtype;
  v_digest text;
  v_next bigint;
  v_process boolean;
  v_export boolean;
  v_index boolean;
  v_across boolean;
  v_reference text;
begin
  if a is null
     or coalesce(auth.jwt()->>'role','')<>'authenticated'
     or coalesce(auth.jwt()->>'is_anonymous','false')='true'
     or p_case is null or p_document is null or p_version is null
     or p_request is null
     or p_expected_version is null or p_expected_version<0
     or p_policy is null or jsonb_typeof(p_policy)<>'object'
  then raise exception 'rights unavailable' using errcode='42501'; end if;

  select c.org_id into o from caseproof.cases c
  join caseproof.organization_members m
    on m.org_id=c.org_id and m.user_id=a and m.active
    and m.actions @> array['case:read','rights:manage']::text[]
  join caseproof._m1_matter_grants g
    on g.org_id=c.org_id and g.case_id=c.id and g.user_id=a
    and g.active and g.role='reviewer'
    and g.permissions @> array['case:read','rights:manage']::text[]
  join caseproof.documents d on d.org_id=c.org_id
    and d.case_id=c.id and d.id=p_document
  join caseproof.document_versions v on v.org_id=d.org_id
    and v.document_id=d.id and v.id=p_version
  where c.id=p_case and c.created_by_user=a
    and c.deleted_at is null and c.purge_started_at is null
  for update of c;
  if o is null then
    raise exception 'rights unavailable' using errcode='42501'; end if;

  if exists(
    select 1 from jsonb_object_keys(p_policy) k
    where k not in (
      'origin','classification','authorization_reference','process',
      'indexForSearch','useAcrossMatters','export'
    )
  ) or p_policy->>'origin' is distinct from 'CLIENT_UPLOAD'
    or p_policy->>'classification' is distinct from 'CLIENT_CONFIDENTIAL'
    or jsonb_typeof(p_policy->'process') is distinct from 'boolean'
    or jsonb_typeof(p_policy->'export') is distinct from 'boolean'
    or (p_policy ? 'indexForSearch'
        and jsonb_typeof(p_policy->'indexForSearch') is distinct from 'boolean')
    or (p_policy ? 'useAcrossMatters'
        and jsonb_typeof(p_policy->'useAcrossMatters') is distinct from 'boolean')
    or (p_policy ? 'authorization_reference'
        and jsonb_typeof(p_policy->'authorization_reference') not in ('string','null'))
  then
    raise exception 'invalid rights policy' using errcode='22023';
  end if;
  v_process := (p_policy->>'process')::boolean;
  v_export := (p_policy->>'export')::boolean;
  v_index := coalesce((p_policy->>'indexForSearch')::boolean,false);
  v_across := coalesce((p_policy->>'useAcrossMatters')::boolean,false);
  v_reference := nullif(btrim(p_policy->>'authorization_reference'),'');
  if (v_reference is not null and length(v_reference)>256)
     or (v_process and v_reference is null)
     or (p_policy ? 'authorization_reference'
         and jsonb_typeof(p_policy->'authorization_reference')='string'
         and v_reference is null)
  then raise exception 'firm authorization reference invalid'
    using errcode='22023'; end if;

  v_digest := encode(sha256(convert_to(p_policy::text,'UTF8')),'hex');
  select * into v_prior from caseproof.source_rights_policies
   where org_id=o and case_id=p_case and request_id=p_request;
  if found then
    if v_prior.actor_user_id=a and v_prior.document_id=p_document
       and v_prior.version_id=p_version
       and v_prior.payload_sha256_hex=v_digest
       and v_prior.policy_version=p_expected_version+1 then
      return jsonb_build_object('policy_version',v_prior.policy_version,'replay',true);
    end if;
    raise exception 'rights request replay conflict' using errcode='23505';
  end if;

  select coalesce(max(policy_version),0) into v_current
  from caseproof.source_rights_policies
  where org_id=o and case_id=p_case and version_id=p_version;
  if v_current<>p_expected_version then
    raise exception 'stale rights policy version' using errcode='23505'; end if;
  v_next:=v_current+1;

  insert into caseproof.source_rights_policies(
    org_id,case_id,document_id,version_id,policy_version,
    request_id,actor_user_id,origin,classification,authorization_reference,
    process,index_for_search,use_across_matters,export_same_matter,payload_sha256_hex
  ) values(
    o,p_case,p_document,p_version,v_next,
    p_request,a,'CLIENT_UPLOAD','CLIENT_CONFIDENTIAL',v_reference,
    v_process,v_index,v_across,v_export,v_digest
  );
  insert into caseproof.audit_events(
    org_id,case_id,actor_type,actor_user_id,action,event_schema_version,
    correlation_id,previous_state,new_state,input_sha256_hex
  ) values(
    o,p_case,'human',a,'source_rights_changed','data-rights-ledger-v1',
    p_request,case when v_current=0 then null else v_current::text end,
    v_next::text,v_digest
  );
  return jsonb_build_object('policy_version',v_next,'replay',false);
end $$;
revoke all on function public.caseproof_rights_manage(
  uuid,uuid,uuid,bigint,uuid,jsonb) from public,anon,authenticated,service_role;
grant execute on function public.caseproof_rights_manage(
  uuid,uuid,uuid,bigint,uuid,jsonb) to authenticated;

-- A separate, read-only projection: never return the firm authorization text.
-- Auth checks are repeated here, not inherited from the prior original read.
create function public.caseproof_rights_current(
  p_case uuid,p_document uuid,p_version uuid
) returns jsonb language plpgsql security definer set search_path='' as $$
declare
  a uuid:=auth.uid();
  o uuid;
  p caseproof.source_rights_policies%rowtype;
begin
  if a is null or coalesce(auth.jwt()->>'role','')<>'authenticated'
     or coalesce(auth.jwt()->>'is_anonymous','false')='true'
     or p_case is null or p_document is null or p_version is null
  then raise exception 'rights unavailable' using errcode='42501'; end if;
  select c.org_id into o from caseproof.cases c
    join caseproof.organization_members m on m.org_id=c.org_id
      and m.user_id=a and m.active
      and m.actions @> array['case:read','evidence:read']::text[]
    join caseproof._m1_matter_grants g
      on g.org_id=c.org_id and g.case_id=c.id and g.user_id=a and g.active
      and g.permissions @> array['case:read','evidence:read']::text[]
    join caseproof.documents d on d.org_id=c.org_id and d.case_id=c.id
      and d.id=p_document
    join caseproof.document_versions v on v.org_id=d.org_id
      and v.document_id=d.id and v.id=p_version
    where c.id=p_case and c.deleted_at is null;
  if o is null then
    raise exception 'rights unavailable' using errcode='42501'; end if;
  select * into p from caseproof.source_rights_policies
    where org_id=o and case_id=p_case and document_id=p_document
      and version_id=p_version
    order by policy_version desc limit 1;
  if not found then return jsonb_build_object('policy_status','missing'); end if;
  return jsonb_build_object(
    'policy_status','present','policy_version',p.policy_version,
    'origin',p.origin,'classification',p.classification,
    'authorization_reference_present',p.authorization_reference is not null,
    'process',p.process,'indexForSearch',p.index_for_search,
    'useAcrossMatters',p.use_across_matters,'export',p.export_same_matter
  );
end $$;
revoke all on function public.caseproof_rights_current(uuid,uuid,uuid)
  from public,anon,authenticated,service_role;
grant execute on function public.caseproof_rights_current(uuid,uuid,uuid)
  to authenticated;

commit;
