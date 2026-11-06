-- PR2 hardening: transactionally fence reviewed DOCX derivative reservations
-- and activation. The global rights control remains disabled by default.
-- A corrected draft is a distinct source version and requires a separately
-- approved rights record before subsequent protected recheck/export.
begin;

create function caseproof._rights_draft_revision_fence()
returns trigger language plpgsql security definer set search_path='' as $$
declare
  v_enabled boolean;
  v_sources jsonb;
  v_parent_sha text;
begin
  select enabled into v_enabled from caseproof._rights_enforcement_control
    where singleton=true;
  if v_enabled is null then
    raise exception 'rights control unavailable' using errcode='42501';
  end if;
  if v_enabled=false then return new; end if;

  -- The existing approved, server-frozen source snapshot defines the scope.
  -- Never authorize based on a source list supplied by a browser request.
  select (s.serialized::jsonb)->'sources' into v_sources
  from caseproof.dossier_snapshots s
  where s.org_id=new.org_id and s.case_id=new.case_id
    and s.snapshot_hash=new.parent_snapshot_hash;
  if v_sources is null then
    raise exception 'rights parent snapshot unavailable' using errcode='42501';
  end if;
  select dv.original_sha256_hex into v_parent_sha
  from caseproof.documents d
  join caseproof.document_versions dv
    on dv.org_id=d.org_id and dv.document_id=d.id
  where d.org_id=new.org_id and d.case_id=new.case_id
    and d.id=new.document_id and dv.id=new.parent_version_id
    and dv.bundle_role='draft';
  if v_parent_sha is null or not exists (
    select 1 from jsonb_array_elements(v_sources) s
    where s->>'document_id'=new.document_id::text
      and s->>'version_id'=new.parent_version_id::text
      and s->>'sha256'=v_parent_sha
  ) then
    raise exception 'rights parent source mismatch' using errcode='42501';
  end if;
  perform caseproof._rights_require_bundle(
    new.org_id,new.case_id,v_sources,'process');
  return new;
end $$;
revoke all on function caseproof._rights_draft_revision_fence()
  from public,anon,authenticated,service_role;

-- AFTER INSERT: the just-reserved child is excluded from the active
-- source bundle; a BEFORE INSERT would incorrectly count it as active.
create trigger rights_draft_revision_reservation
  after insert on caseproof.dossier_draft_revisions
  for each row execute function caseproof._rights_draft_revision_fence();

-- BEFORE activation: the parent is still active and rights must be checked
-- before the child supersedes it. A later recheck of the new source requires
-- a separately approved derivative-version policy.
create trigger rights_draft_revision_activation
  before update of state on caseproof.dossier_draft_revisions
  for each row when (new.state='active')
  execute function caseproof._rights_draft_revision_fence();

commit;
