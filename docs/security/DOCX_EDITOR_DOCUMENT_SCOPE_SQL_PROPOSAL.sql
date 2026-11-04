-- REVIEW PROPOSAL ONLY — DO NOT APPLY WITHOUT INDEPENDENT SECURITY APPROVAL.
-- Document-wide editing is NOT a citation correction; only explicit actor-scoped
-- reviewed command/candidate digests can reserve a new draft. This intentionally
-- adds no DIRECT authenticated table access, and reuses the already reviewed
-- immutable draft version/activation ledger after an independently approved
-- document-scoped review. Installed state and rollback are NOT asserted.
--
-- Dependency: accepted F5 document_versions, dossier_snapshots, current_signature,
-- _m1_matter_grants, retention_write_guard, audit_events and draft activation RPC.
-- Tests must install this in a disposable database before caseproof-dev review.

create table caseproof.dossier_document_edit_reviews (
  org_id uuid not null,
  case_id uuid not null,
  actor_id uuid not null,
  request_id uuid not null,
  parent_version_id uuid not null,
  snapshot_hash text not null check (snapshot_hash ~ '^[0-9a-f]{64}$'),
  original_sha256 text not null check (original_sha256 ~ '^[0-9a-f]{64}$'),
  command_sha256 text not null check (command_sha256 ~ '^[0-9a-f]{64}$'),
  candidate_sha256 text not null check (candidate_sha256 ~ '^[0-9a-f]{64}$'),
  rationale text not null check (length(rationale) between 10 and 2000),
  created_at timestamptz not null default clock_timestamp(),
  primary key (org_id, case_id, actor_id, request_id),
  foreign key (org_id, case_id) references caseproof.cases(org_id, id) on delete cascade,
  foreign key (org_id, parent_version_id) references caseproof.document_versions(org_id, id) on delete cascade
);
alter table caseproof.dossier_document_edit_reviews enable row level security;
revoke all on table caseproof.dossier_document_edit_reviews from public, anon, authenticated;
create trigger dossier_document_edit_retention_guard before insert or update
on caseproof.dossier_document_edit_reviews for each row
execute function caseproof.retention_write_guard();

create function public.caseproof_dossier_document_edit_review(
  p_case uuid, p_parent uuid, p_snapshot text, p_request uuid, p_data jsonb
)
returns jsonb language plpgsql security definer set search_path='' as $$
declare
  a uuid := auth.uid();
  o uuid;
  s caseproof.dossier_snapshots%rowtype;
  parent caseproof.document_versions%rowtype;
  record caseproof.dossier_document_edit_reviews%rowtype;
begin
  if a is null or coalesce(auth.jwt()->>'role','') <> 'authenticated'
    or coalesce(auth.jwt()->>'is_anonymous','false') = 'true'
    or p_case is null or p_parent is null or p_request is null
    or p_snapshot is null or p_snapshot !~ '^[0-9a-f]{64}$'
    or p_data->>'original_sha256' !~ '^[0-9a-f]{64}$'
    or p_data->>'command_sha256' !~ '^[0-9a-f]{64}$'
    or p_data->>'candidate_sha256' !~ '^[0-9a-f]{64}$'
    or length(coalesce(p_data->>'rationale','')) not between 10 and 2000
  then raise exception 'unavailable' using errcode='42501'; end if;

  select c.org_id into o from caseproof.cases c
  join caseproof.organization_members m on m.org_id=c.org_id
    and m.user_id=a and m.active
    and m.actions @> array['case:read','evidence:read','finding:write','review:request']::text[]
  join caseproof._m1_matter_grants g on g.org_id=c.org_id
    and g.case_id=c.id and g.user_id=a and g.active and g.role='reviewer'
    and g.permissions @> array['case:read','evidence:read','evidence:upload','draft:check','review:request']::text[]
  where c.id=p_case and c.deleted_at is null for update of c;
  if o is null then raise exception 'unavailable' using errcode='42501'; end if;

  select * into record from caseproof.dossier_document_edit_reviews
  where org_id=o and case_id=p_case and actor_id=a and request_id=p_request;
  if found then
    if record.parent_version_id is distinct from p_parent
       or record.snapshot_hash is distinct from p_snapshot
       or record.original_sha256 is distinct from p_data->>'original_sha256'
       or record.command_sha256 is distinct from p_data->>'command_sha256'
       or record.candidate_sha256 is distinct from p_data->>'candidate_sha256'
       or record.rationale is distinct from p_data->>'rationale'
    then raise exception 'document review replay conflict' using errcode='23505'; end if;
    return jsonb_build_object(
      'state','reviewed','review_request_id',record.request_id,
      'command_sha256',record.command_sha256,'candidate_sha256',record.candidate_sha256,
      'replayed',true);
  end if;

  perform public.caseproof_dossier(
    p_case, 'decisions', jsonb_build_object('snapshot_hash',p_snapshot)
  );
  select * into strict s from caseproof.dossier_snapshots
  where org_id=o and case_id=p_case and snapshot_hash=p_snapshot;
  if s.serialized::jsonb->>'brief_id' is distinct from p_parent::text
  then raise exception 'stale snapshot' using errcode='23505'; end if;
  select * into strict parent from caseproof.document_versions
  where org_id=o and id=p_parent and bundle_role='draft'
  and media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document';
  if parent.original_sha256_hex is distinct from p_data->>'original_sha256'
     or parent.original_sha256_hex = p_data->>'candidate_sha256'
  then raise exception 'source mismatch' using errcode='22023'; end if;

  insert into caseproof.dossier_document_edit_reviews (
    org_id,case_id,actor_id,request_id,parent_version_id,snapshot_hash,
    original_sha256,command_sha256,candidate_sha256,rationale
  ) values (
    o,p_case,a,p_request,p_parent,p_snapshot,p_data->>'original_sha256',
    p_data->>'command_sha256',p_data->>'candidate_sha256',p_data->>'rationale'
  ) returning * into record;

  insert into caseproof.audit_events (
    org_id,case_id,actor_type,actor_user_id,action,
    event_schema_version,correlation_id,input_sha256_hex
  ) values (
    o,p_case,'human',a,'dossier_document_edit_reviewed',
    'dossier-document-edit-v1',p_request,record.command_sha256
  );
  return jsonb_build_object(
    'state','reviewed','review_request_id',record.request_id,
    'command_sha256',record.command_sha256,
    'candidate_sha256',record.candidate_sha256,'replayed',false
  );
end $$;
revoke all on function public.caseproof_dossier_document_edit_review(
  uuid,uuid,text,uuid,jsonb
) from public,anon,authenticated;
grant execute on function public.caseproof_dossier_document_edit_review(
  uuid,uuid,text,uuid,jsonb
) to authenticated;

create function public.caseproof_dossier_document_edit_reserve(
  p_case uuid, p_parent uuid, p_snapshot text,
  p_request uuid, p_review uuid, p_data jsonb
)
returns jsonb language plpgsql security definer set search_path='' as $$
declare
  a uuid := auth.uid();
  o uuid;
  s caseproof.dossier_snapshots%rowtype;
  p caseproof.document_versions%rowtype;
  approval caseproof.dossier_document_edit_reviews%rowtype;
  r caseproof.dossier_draft_revisions%rowtype;
  current_confirmation uuid;
  version_id uuid;
  next_number bigint;
  ref text := 'doc-edit:' || p_review::text;
begin
  if a is null or coalesce(auth.jwt()->>'role','') <> 'authenticated'
    or coalesce(auth.jwt()->>'is_anonymous','false') = 'true'
    or p_case is null or p_parent is null or p_request is null or p_review is null
    or p_snapshot is null or p_snapshot !~ '^[0-9a-f]{64}$'
    or p_data->>'original_sha256' !~ '^[0-9a-f]{64}$'
    or p_data->>'command_sha256' !~ '^[0-9a-f]{64}$'
    or p_data->>'candidate_sha256' !~ '^[0-9a-f]{64}$'
    or coalesce((p_data->>'byte_length')::bigint,0) not between 1 and 5242880
  then raise exception 'unavailable' using errcode='42501'; end if;

  select c.org_id into o from caseproof.cases c
  join caseproof.organization_members m on m.org_id=c.org_id
    and m.user_id=a and m.active
    and m.actions @> array['case:read','evidence:read','finding:write','review:request']::text[]
  join caseproof._m1_matter_grants g on g.org_id=c.org_id
    and g.case_id=c.id and g.user_id=a and g.active and g.role='reviewer'
    and g.permissions @> array['case:read','evidence:read','evidence:upload','draft:check','review:request']::text[]
  where c.id=p_case and c.deleted_at is null for update of c;
  if o is null then raise exception 'unavailable' using errcode='42501'; end if;

  select * into r from caseproof.dossier_draft_revisions
  where org_id=o and case_id=p_case and actor_id=a and request_id=p_request;
  if found then
    if r.parent_version_id is distinct from p_parent or
      r.parent_snapshot_hash is distinct from p_snapshot or
      r.reference_id is distinct from ref or
      r.command_sha256 is distinct from p_data->>'command_sha256' or
      r.original_sha256 is distinct from p_data->>'candidate_sha256' or
      r.byte_length is distinct from (p_data->>'byte_length')::bigint
    then raise exception 'editor command replay conflict' using errcode='23505'; end if;
    return to_jsonb(r) || jsonb_build_object('replayed',true);
  end if;

  select * into strict approval from caseproof.dossier_document_edit_reviews
  where org_id=o and case_id=p_case and actor_id=a
    and request_id=p_review and parent_version_id=p_parent
    and snapshot_hash=p_snapshot
    and original_sha256=p_data->>'original_sha256'
    and command_sha256=p_data->>'command_sha256'
    and candidate_sha256=p_data->>'candidate_sha256';
  if approval.created_at < clock_timestamp() - interval '24 hours'
  then raise exception 'document review expired' using errcode='42501'; end if;

  perform public.caseproof_dossier(
    p_case, 'decisions', jsonb_build_object('snapshot_hash',p_snapshot)
  );
  select * into strict s from caseproof.dossier_snapshots
  where org_id=o and case_id=p_case and snapshot_hash=p_snapshot;
  select request_id into current_confirmation from caseproof.dossier_confirmations
  where org_id=o and case_id=p_case and bundle_signature=s.bundle_signature
  order by created_at desc,request_id desc limit 1;
  if s.serialized::jsonb->>'brief_id' is distinct from p_parent::text
    or s.bundle_signature is distinct from caseproof.dossier_current_signature(o,p_case)
    or s.confirmation_id is distinct from current_confirmation
  then raise exception 'stale parent' using errcode='23505'; end if;
  select * into strict p from caseproof.document_versions
  where org_id=o and id=p_parent and bundle_role='draft'
    and media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document';
  if p.original_sha256_hex is distinct from p_data->>'original_sha256'
  then raise exception 'source mismatch' using errcode='22023'; end if;

  select coalesce(max(version_number),0)+1 into next_number
  from caseproof.document_versions where org_id=o and document_id=p.document_id;
  version_id := gen_random_uuid();
  insert into caseproof.document_versions (
    id,org_id,document_id,version_number,original_sha256_hex,
    byte_length,media_type,bundle_role
  ) values (
    version_id,o,p.document_id,next_number,p_data->>'candidate_sha256',
    (p_data->>'byte_length')::bigint,p.media_type,'draft'
  );
  insert into caseproof.dossier_draft_revisions (
    org_id,case_id,request_id,actor_id,document_id,parent_version_id,
    version_id,parent_snapshot_hash,reference_id,
    command_sha256,original_sha256,byte_length
  ) values (
    o,p_case,p_request,a,p.document_id,p_parent,version_id,p_snapshot,ref,
    p_data->>'command_sha256',p_data->>'candidate_sha256',
    (p_data->>'byte_length')::bigint
  ) returning * into r;
  insert into caseproof.audit_events (
    org_id,case_id,actor_type,actor_user_id,action,
    event_schema_version,correlation_id,input_sha256_hex
  ) values (
    o,p_case,'human',a,'dossier_document_edit_reserved',
    'dossier-document-edit-v1',p_request,r.command_sha256
  );
  return to_jsonb(r) || jsonb_build_object('replayed',false);
end $$;
revoke all on function public.caseproof_dossier_document_edit_reserve(
  uuid,uuid,text,uuid,uuid,jsonb
) from public,anon,authenticated;
grant execute on function public.caseproof_dossier_document_edit_reserve(
  uuid,uuid,text,uuid,uuid,jsonb
) to authenticated;

-- Shared existing F5 caseproof_dossier_draft_activate() remains the ONLY
-- trusted signed-readback activation path; it must be independently audited
-- against document-wide rows and unknown-outcome/revocation cases before use.
-- This proposal is intentionally not in supabase/migrations and is not installed.
