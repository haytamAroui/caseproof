-- Forward-only dev repair: lock member/grant rows during rights mutation.
-- Deployed after the initial rights ledger migration; no policy-row changes.
begin;
create or replace function public.caseproof_rights_manage(
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
     or p_expected_version>9223372036854775805
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
  for update of c for share of m,g;
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
commit;
