-- PR2 forward hardening: require the complete active source-version scope.
-- Do not mutate the already-applied 20261106105558 migration.
-- No policy backfill; the private enforcement switch remains OFF.
begin;
create or replace function caseproof._rights_require_bundle(
  p_org uuid,p_case uuid,p_sources jsonb,p_action text
) returns void language plpgsql security definer set search_path='' as $$
declare
  v_enabled boolean;
  v_entry jsonb;
  v_doc uuid;
  v_ver uuid;
  v_sha text;
  v_known text;
  v_count integer:=0;
  v_seen uuid[]:='{}'::uuid[];
  v_expected_ids uuid[];
begin
  select enabled into v_enabled from caseproof._rights_enforcement_control where singleton;
  if v_enabled is null then
    raise exception 'rights enforcement configuration unavailable' using errcode='42501';
  end if;
  if v_enabled=false then return; end if;
  if p_sources is null or jsonb_typeof(p_sources)<>'array'
     or jsonb_array_length(p_sources) not between 1 and 32 then
     raise exception 'invalid rights bundle' using errcode='42501';
  end if;
  -- Lock the matter before sampling the active version set. This is the
  -- same parent lock used by the rights:manage CAS and the release RPC.
  perform 1 from caseproof.cases c where c.org_id=p_org and c.id=p_case
    and c.deleted_at is null and c.purge_started_at is null for share;
  if not found then
    raise exception 'rights matter unavailable' using errcode='42501';
  end if;
  select coalesce(array_agg(dv.id),'{}'::uuid[]) into v_expected_ids
  from caseproof.documents d
  join caseproof.document_versions dv on dv.org_id=d.org_id and dv.document_id=d.id
  where d.org_id=p_org and d.case_id=p_case
    and not exists (
      select 1 from caseproof.dossier_draft_revisions r
      where r.org_id=p_org and r.case_id=p_case
      and ((r.version_id=dv.id and r.state='reserved')
        or (r.parent_version_id=dv.id and r.state='active'))
    );
  if cardinality(v_expected_ids)<>jsonb_array_length(p_sources) then
    raise exception 'incomplete active rights bundle' using errcode='42501';
  end if;
  for v_entry in select value from jsonb_array_elements(p_sources) loop
    if jsonb_typeof(v_entry)<>'object' then
      raise exception 'invalid rights source' using errcode='42501';
    end if;
    begin
      v_doc:=(v_entry->>'document_id')::uuid;
      v_ver:=(v_entry->>'version_id')::uuid;
    exception when others then
      raise exception 'invalid rights source' using errcode='42501';
    end;
    v_sha:=v_entry->>'sha256';
    if v_doc is null or v_ver is null or not (v_ver=any(v_expected_ids))
       or v_ver=any(v_seen)
       or v_sha is null or v_sha !~ '^[0-9a-f]{64}$' then
      raise exception 'invalid rights source scope' using errcode='42501';
    end if;
    select dv.original_sha256_hex into v_known
      from caseproof.documents d
      join caseproof.document_versions dv on dv.org_id=d.org_id
        and dv.document_id=d.id
      where d.org_id=p_org and d.case_id=p_case
        and d.id=v_doc and dv.id=v_ver;
    if v_known is distinct from v_sha then
      raise exception 'rights source digest changed' using errcode='42501';
    end if;
    perform caseproof._rights_require_source(p_org,p_case,v_doc,v_ver,p_action);
    v_count:=v_count+1;
    v_seen:=array_append(v_seen,v_ver);
  end loop;
  if v_count<1 then raise exception 'empty rights source set' using errcode='42501'; end if;
end $$;
revoke all on function caseproof._rights_require_bundle(uuid,uuid,jsonb,text)
  from public,anon,authenticated,service_role;
commit;
