-- PR2: immutable, no-escalation derived DOCX source rights.
-- A derivative copies only the latest parent permissions; UNKNOWN stays UNKNOWN.
-- Descendants remain bounded by the parent's LATEST rights, even if revoked.
begin;

alter table caseproof.source_rights_policies
  add column inherited_from_version_id uuid;
alter table caseproof.source_rights_policies
  add constraint source_rights_derivative_parent_fk
  foreign key(org_id,inherited_from_version_id)
  references caseproof.document_versions(org_id,id) on delete cascade;
create index source_rights_derivative_parent_idx
  on caseproof.source_rights_policies(org_id,inherited_from_version_id)
  where inherited_from_version_id is not null;

create function caseproof._rights_inherit_docx_derivative()
returns trigger language plpgsql security definer set search_path='' as $$
declare
  v_parent caseproof.source_rights_policies%rowtype;
  v_payload jsonb;
  v_digest text;
begin
  -- Only a version linked by the existing durable signed reservation is
  -- eligible. The parent source must belong to the same org/matter/document.
  perform 1 from caseproof.documents d
    join caseproof.document_versions parent on parent.org_id=d.org_id
      and parent.document_id=d.id
    join caseproof.document_versions child on child.org_id=d.org_id
      and child.document_id=d.id
  where d.org_id=new.org_id and d.case_id=new.case_id
    and d.id=new.document_id and parent.id=new.parent_version_id
    and child.id=new.version_id;
  if not found then
    raise exception 'rights derivative source mismatch' using errcode='42501';
  end if;

  -- Serializes with rights:manage CAS and ongoing source mutations.
  perform 1 from caseproof.cases c
    where c.org_id=new.org_id and c.id=new.case_id
      and c.deleted_at is null and c.purge_started_at is null for share;
  if not found then raise exception 'rights matter unavailable' using errcode='42501'; end if;

  select * into v_parent from caseproof.source_rights_policies
    where org_id=new.org_id and case_id=new.case_id
      and document_id=new.document_id and version_id=new.parent_version_id
    order by policy_version desc limit 1;
  if not found then
    -- No blanket approved document_rights JSONB is created for legacy parents.
    -- Their derivatives remain UNKNOWN and protected processing fails closed.
    return new;
  end if;

  v_payload := jsonb_build_object(
    'origin',v_parent.origin,
    'classification',v_parent.classification,
    'authorization_reference',v_parent.authorization_reference,
    'process',v_parent.process,
    'indexForSearch',v_parent.index_for_search,
    'useAcrossMatters',v_parent.use_across_matters,
    'export',v_parent.export_same_matter
  );
  v_digest := encode(sha256(convert_to(v_payload::text,'UTF8')),'hex');

  insert into caseproof.source_rights_policies(
    org_id,case_id,document_id,version_id,policy_version,request_id,
    actor_user_id,origin,classification,authorization_reference,
    process,index_for_search,use_across_matters,export_same_matter,
    payload_sha256_hex,inherited_from_version_id
  ) values (
    new.org_id,new.case_id,new.document_id,new.version_id,1,gen_random_uuid(),
    new.actor_id,v_parent.origin,v_parent.classification,
    v_parent.authorization_reference,v_parent.process,
    v_parent.index_for_search,v_parent.use_across_matters,
    v_parent.export_same_matter,v_digest,new.parent_version_id
  );
  insert into caseproof.audit_events(
    org_id,case_id,actor_type,actor_user_id,action,event_schema_version,
    correlation_id,previous_state,new_state,input_sha256_hex
  ) values (
    new.org_id,new.case_id,'human',new.actor_id,'source_rights_changed',
    'data-rights-ledger-v1',new.request_id,
    'inherited-parent-policy-'||v_parent.policy_version::text,
    '1',v_digest
  );
  return new;
end $$;
revoke all on function caseproof._rights_inherit_docx_derivative()
from public,anon,authenticated,service_role;
create trigger rights_inherit_docx_policy
  after insert on caseproof.dossier_draft_revisions
  for each row execute function caseproof._rights_inherit_docx_derivative();

-- No derived source can outlive a parent's *latest* DENY by relying on an
-- old copied ALLOW. Keep the former source evaluator as a private base.
alter function caseproof._rights_require_source(uuid,uuid,uuid,uuid,text)
  rename to _rights_require_source_base;
revoke all on function caseproof._rights_require_source_base(uuid,uuid,uuid,uuid,text)
  from public,anon,authenticated,service_role;

create function caseproof._rights_require_source(
  p_org uuid,p_case uuid,p_document uuid,p_version uuid,p_action text
) returns bigint language plpgsql security definer set search_path='' as $$
declare
  v_enabled boolean;
  v_current uuid:=p_version;
  v_parent uuid;
  v_parent_doc uuid;
  v_depth integer:=0;
  v_version bigint;
begin
  select enabled into v_enabled from caseproof._rights_enforcement_control
    where singleton;
  if v_enabled is null then
    raise exception 'rights enforcement configuration unavailable' using errcode='42501';
  end if;
  if v_enabled=false then return 0; end if;
  loop
    v_version := caseproof._rights_require_source_base(
      p_org,p_case,p_document,v_current,p_action
    );
    select r.parent_version_id,r.document_id into v_parent,v_parent_doc
      from caseproof.dossier_draft_revisions r
      where r.org_id=p_org and r.case_id=p_case
        and r.version_id=v_current;
    if not found then return v_version; end if;
    if v_parent is null or v_parent_doc is distinct from p_document
      or v_parent=v_current or v_depth >= 32 then
      raise exception 'invalid derivative rights ancestry' using errcode='42501';
    end if;
    v_current:=v_parent;
    v_depth:=v_depth+1;
  end loop;
end $$;
revoke all on function caseproof._rights_require_source(uuid,uuid,uuid,uuid,text)
from public,anon,authenticated,service_role;

commit;
