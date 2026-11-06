-- PR2: dormant, transactional rights checks on trusted source derivation and release.
-- This migration installs NO enforcement by default and creates NO policy rows.
-- Operator-controlled enablement requires explicit independent security approval.
begin;

create table caseproof._rights_enforcement_control (
  singleton boolean primary key default true check(singleton),
  enabled boolean not null default false,
  updated_at timestamptz not null default clock_timestamp()
);
insert into caseproof._rights_enforcement_control(singleton,enabled) values(true,false);
alter table caseproof._rights_enforcement_control enable row level security;
revoke all on caseproof._rights_enforcement_control
  from public,anon,authenticated,service_role;

-- Called by server-side triggers only. Never a client-exposed authorization API.
-- Lock the case BEFORE policy lookup: signed rights:manage acquires FOR UPDATE
-- on the same case row, so policy changes and protected writes serialize.
create function caseproof._rights_require_source(
  p_org uuid, p_case uuid, p_document uuid, p_version uuid,
  p_action text
) returns bigint language plpgsql security definer set search_path='' as $$
declare
  v_enabled boolean;
  v_digest text;
  v_policy caseproof.source_rights_policies%rowtype;
begin
  select enabled into v_enabled from caseproof._rights_enforcement_control
    where singleton=true;
  if v_enabled is null then
    raise exception 'rights enforcement configuration unavailable' using errcode='42501';
  end if;
  if v_enabled=false then return 0; end if;
  if p_action not in ('process','indexForSearch','export')
    or p_org is null or p_case is null or p_document is null or p_version is null then
    raise exception 'source rights unavailable' using errcode='42501';
  end if;

  perform 1 from caseproof.cases c
  where c.org_id=p_org and c.id=p_case and c.deleted_at is null
    and c.purge_started_at is null
  for share;
  if not found then
    raise exception 'source rights unavailable' using errcode='42501';
  end if;
  select v.original_sha256_hex into v_digest
    from caseproof.documents d
    join caseproof.document_versions v on v.org_id=d.org_id
      and v.document_id=d.id
   where d.org_id=p_org and d.case_id=p_case
     and d.id=p_document and v.id=p_version;
  if v_digest is null then
    raise exception 'source rights unavailable' using errcode='42501';
  end if;
  select * into v_policy from caseproof.source_rights_policies
   where org_id=p_org and case_id=p_case
     and document_id=p_document and version_id=p_version
   order by policy_version desc limit 1;
  if not found or v_policy.policy_version<1
    or v_policy.origin<>'CLIENT_UPLOAD'
    or v_policy.classification<>'CLIENT_CONFIDENTIAL'
    or (p_action='process' and
        (v_policy.process is distinct from true
         or nullif(btrim(v_policy.authorization_reference),'') is null))
    or (p_action='indexForSearch' and
        v_policy.index_for_search is distinct from true)
    or (p_action='export' and
        v_policy.export_same_matter is distinct from true)
  then
    raise exception 'source rights denied or unknown' using errcode='42501';
  end if;
  return v_policy.policy_version;
end $$;
revoke all on function caseproof._rights_require_source(uuid,uuid,uuid,uuid,text)
  from public,anon,authenticated,service_role;

-- All identities come from an existing server-authored, frozen report.
-- A missing/duplicated source and an inconsistent original SHA are denied.
create function caseproof._rights_require_bundle(
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
    if v_doc is null or v_ver is null or v_ver=any(v_seen)
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

-- Direct trusted SQL paths must not bypass the Python gates when an owner
-- explicitly enables enforcement. These fire in the SAME DB transaction
-- as the protected derived-artifact insert, independent of the caller.
create function caseproof._rights_protected_write()
returns trigger language plpgsql security definer set search_path='' as $$
declare
  v_document uuid;
  v_sources jsonb;
  v_enabled boolean;
begin
  -- Truly dormant: do not parse, query, or reject even historical/fixture
  -- writes when the operator has not explicitly enabled enforcement.
  select enabled into v_enabled from caseproof._rights_enforcement_control
    where singleton=true;
  if v_enabled is null then
    raise exception 'rights enforcement configuration unavailable' using errcode='42501';
  end if;
  if v_enabled=false then return new; end if;
  if tg_table_name='_dev_journey_sources' then
    perform caseproof._rights_require_source(
      new.org_id,new.case_id,new.document_id,new.version_id,'process');
  elsif tg_table_name='_dev_journey_parse_manifests' then
    select s.document_id into v_document from caseproof._dev_journey_sources s
      where s.org_id=new.org_id and s.case_id=new.case_id
        and s.version_id=new.version_id;
    if v_document is null then
      raise exception 'parsed source is not registered' using errcode='42501';
    end if;
    perform caseproof._rights_require_source(
      new.org_id,new.case_id,v_document,new.version_id,'process');
  elsif tg_table_name='dossier_snapshots' then
    begin v_sources:=(new.serialized::jsonb)->'sources';
    exception when others then
      raise exception 'rights snapshot malformed' using errcode='42501'; end;
    perform caseproof._rights_require_bundle(new.org_id,new.case_id,v_sources,'process');
  elsif tg_table_name='dossier_releases' then
    -- Always use the server-stored frozen snapshot, not supplied release JSON.
    select (s.serialized::jsonb)->'sources' into v_sources
      from caseproof.dossier_snapshots s
      where s.org_id=new.org_id and s.case_id=new.case_id
        and s.snapshot_hash=new.snapshot_hash;
    if v_sources is null then
      raise exception 'rights release snapshot unavailable' using errcode='42501';
    end if;
    perform caseproof._rights_require_bundle(new.org_id,new.case_id,v_sources,'export');
  else
    raise exception 'rights trigger misconfigured' using errcode='42501';
  end if;
  return new;
end $$;
revoke all on function caseproof._rights_protected_write()
  from public,anon,authenticated,service_role;

create trigger rights_process_ingest
 before insert on caseproof._dev_journey_sources
 for each row execute function caseproof._rights_protected_write();
create trigger rights_process_parse
 before insert on caseproof._dev_journey_parse_manifests
 for each row execute function caseproof._rights_protected_write();
create trigger rights_process_snapshot
 before insert on caseproof.dossier_snapshots
 for each row execute function caseproof._rights_protected_write();
create trigger rights_export_release
 before insert on caseproof.dossier_releases
 for each row execute function caseproof._rights_protected_write();
revoke all on caseproof.dossier_releases from service_role;
revoke all on caseproof.dossier_snapshots from service_role;
revoke all on caseproof._dev_journey_sources from service_role;
revoke all on caseproof._dev_journey_parse_manifests from service_role;

commit;
