-- PR203: immutable signed rights evidence on NEW reviewed releases.
-- Existing HMAC-signed historical v1 releases remain readable and are never
-- backfilled, rewritten or described as having a signed rights attestation.
-- The runtime gate/SQL rights policy MUST already be enabled for enforcement.
begin;

create function caseproof._rights_export_manifest_fence()
returns trigger language plpgsql security definer set search_path='' as $$
declare
  v_enabled boolean;
  v_attestation jsonb;
  v_entries jsonb;
  v_frozen jsonb;
  v_entry jsonb;
  v_document uuid;
  v_version uuid;
  v_digest text;
  v_latest bigint;
  v_claimed bigint;
  v_count integer:=0;
  v_seen uuid[]:='{}'::uuid[];
begin
  select enabled into v_enabled
    from caseproof._rights_enforcement_control where singleton=true;
  if v_enabled is null then
    raise exception 'rights enforcement configuration unavailable'
      using errcode='42501';
  end if;
  if not v_enabled then
    -- Pre-enforcement disposable fixtures preserve the old release contract.
    -- Real enforced deployments must keep this switch ON. No policy inferred.
    return new;
  end if;

  v_attestation:=new.manifest->'rights_attestation';
  v_entries:=v_attestation->'sources';
  if jsonb_typeof(v_attestation) is distinct from 'object'
    or v_attestation->>'schema' is distinct from 'caseproof-export-rights-v1'
    or v_attestation->>'action' is distinct from 'export'
    or v_attestation->>'scope' is distinct from 'same_matter'
    or v_attestation->>'decision' is distinct from 'allow'
    or jsonb_typeof(v_entries) is distinct from 'array'
    or jsonb_array_length(v_entries) not between 1 and 32
  then
    raise exception 'signed export rights evidence missing or invalid'
      using errcode='42501';
  end if;

  -- The DB snapshot defines the *entire* set. Never trust browser-authored
  -- source arrays, export scope, version numbers or source digest claims.
  select s.serialized::jsonb->'sources' into v_frozen
  from caseproof.dossier_snapshots s
  where s.org_id=new.org_id and s.case_id=new.case_id
    and s.snapshot_hash=new.snapshot_hash;
  if jsonb_typeof(v_frozen) is distinct from 'array'
     or jsonb_array_length(v_frozen)<>jsonb_array_length(v_entries)
     or new.manifest->'sources' is null
     or jsonb_array_length(new.manifest->'sources')<>jsonb_array_length(v_entries)
  then
    raise exception 'signed export rights scope mismatch' using errcode='42501';
  end if;

  -- The same case row lock serializes this transaction against rights:manage
  -- revocation. The full active bundle and current export grant are rechecked
  -- in the existing release trigger, independently of our new receipt fields.
  perform caseproof._rights_require_bundle(
    new.org_id,new.case_id,v_frozen,'export'
  );

  for v_entry in select value from jsonb_array_elements(v_entries) loop
    if jsonb_typeof(v_entry) is distinct from 'object'
      or v_entry->>'decision' is distinct from 'allow'
      or jsonb_typeof(v_entry->'policy_version') is distinct from 'number'
      or v_entry->>'policy_version' !~ '^[1-9][0-9]{0,17}$'
    then
      raise exception 'signed export rights decision invalid' using errcode='42501';
    end if;
    begin
      v_document:=(v_entry->>'document_id')::uuid;
      v_version:=(v_entry->>'version_id')::uuid;
      v_claimed:=(v_entry->>'policy_version')::bigint;
    exception when others then
      raise exception 'signed export rights identity invalid' using errcode='42501';
    end;
    v_digest:=v_entry->>'original_sha256';
    if v_document is null or v_version is null
       or v_version=any(v_seen) or v_digest is null
       or v_digest !~ '^[0-9a-f]{64}$'
       or not exists (
         select 1 from jsonb_array_elements(v_frozen) s
         where s->>'document_id'=v_document::text
           and s->>'version_id'=v_version::text
           and s->>'sha256'=v_digest
       )
       or not exists (
         select 1 from jsonb_array_elements(new.manifest->'sources') s
         where s->>'version_id'=v_version::text
           and s->>'sha256'=v_digest
       )
    then
      raise exception 'signed export rights source mismatch' using errcode='42501';
    end if;

    -- The ancestor-aware effective export check is a deny-only fence.
    perform caseproof._rights_require_source(
      new.org_id,new.case_id,v_document,v_version,'export'
    );
    -- Compare the exact *child* policy revision issued by the signed reader;
    -- _rights_require_source may return an ancestor's version for derivatives.
    select p.policy_version into v_latest
    from caseproof.source_rights_policies p
    where p.org_id=new.org_id and p.case_id=new.case_id
      and p.document_id=v_document and p.version_id=v_version
    order by p.policy_version desc limit 1;
    if v_latest is null or v_latest<>v_claimed then
      raise exception 'signed export rights version changed'
        using errcode='42501';
    end if;
    v_seen:=array_append(v_seen,v_version);
    v_count:=v_count+1;
  end loop;
  if v_count<>jsonb_array_length(v_frozen) then
    raise exception 'signed export rights incomplete' using errcode='42501';
  end if;
  return new;
end $$;
revoke all on function caseproof._rights_export_manifest_fence()
  from public,anon,authenticated,service_role;
create trigger rights_export_manifest_fence
  before insert on caseproof.dossier_releases for each row
  execute function caseproof._rights_export_manifest_fence();

commit;
