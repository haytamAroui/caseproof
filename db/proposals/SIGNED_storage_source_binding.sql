-- Proposal only. Apply before the other SIGNED proposals. No shared mutation.
-- New records bind the existing immutable trusted-ingestion audit to the exact
-- private Storage path. Legacy intent IDs remain unchanged, never relabeled.
begin;
alter table caseproof._m2_brief_versions
 add column if not exists source_binding_kind text not null default 'legacy_vault_intent',
 add column if not exists source_binding jsonb;
alter table caseproof._m2_brief_versions alter column vault_intent_id drop not null;
do $$ begin
 if not exists(select 1 from pg_constraint where conrelid='caseproof._m2_brief_versions'::regclass
  and conname='_m2_brief_source_binding_shape') then
 alter table caseproof._m2_brief_versions add constraint _m2_brief_source_binding_shape check (
  (source_binding_kind='legacy_vault_intent' and vault_intent_id is not null and source_binding is null)
  or (source_binding_kind='trusted_storage_source_v1' and vault_intent_id is null and source_binding is not null
   and jsonb_typeof(source_binding)='object'
   and coalesce(source_binding->>'kind','')='trusted_storage_source_v1'
   and source_binding ?& array['audit_id','snapshot_sha256','bucket','object_key','original_sha256',
    'representation_sha256','byte_length','media_type']));
 end if;
end $$;

-- Internal, non-client-callable verifier. Actor/grant checks remain mandatory
-- in each public RPC. Presence is NOT byte verification: ingestion establishes
-- bytes/hash/length, and the Python read path independently re-downloads and
-- hashes bytes under the signed actor before checks. Deleted/archived objects,
-- missing audits, representation drift and wrong-case sources return NULL.
create or replace function caseproof._signed_storage_source_binding(
 p_org uuid,p_case uuid,p_document uuid,p_version uuid
) returns jsonb language sql stable security definer set search_path='' as $$
 select jsonb_build_object(
  'kind','trusted_storage_source_v1','audit_id',s.audit_id,
  'snapshot_sha256',s.snapshot_sha,'bucket','caseproof-originals-dev',
  'object_key',concat_ws('/',p_org,p_case,p_document,p_version,dv.original_sha256_hex),
  'original_sha256',dv.original_sha256_hex,'representation_sha256',s.representation_sha,
  'byte_length',dv.byte_length,'media_type',dv.media_type)
 from caseproof.documents d
 join caseproof.document_versions dv on dv.org_id=d.org_id and dv.document_id=d.id
 join caseproof._dev_journey_sources s on s.org_id=d.org_id and s.case_id=d.case_id
  and s.document_id=d.id and s.version_id=dv.id
  and s.original_sha=dv.original_sha256_hex
  and s.representation_sha=encode(sha256(convert_to(s.representation,'UTF8')),'hex')
 join caseproof.audit_events a on a.org_id=s.org_id and a.case_id=s.case_id
  and a.id=s.audit_id and a.input_sha256_hex=s.snapshot_sha
  and a.action in ('dev_txt_ingested','dev_binary_ingested','dev_parsed_ingested')
 where d.org_id=p_org and d.case_id=p_case and d.id=p_document and dv.id=p_version
  and dv.byte_length between 1 and 5242880
  and exists(select 1 from storage.objects o where o.bucket_id='caseproof-originals-dev'
   and o.name=concat_ws('/',p_org,p_case,p_document,p_version,dv.original_sha256_hex)
   and coalesce(to_jsonb(o)->>'is_delete_marker','false')='false'
   and (to_jsonb(o)->>'archived_at') is null)
$$;
revoke all on function caseproof._signed_storage_source_binding(uuid,uuid,uuid,uuid)
 from public,anon,authenticated,service_role;
-- Current exact draft binding for review/export. Legacy history is retained,
-- but cannot be reinterpreted as a storage-backed verification.
create or replace function caseproof._signed_brief_binding_current(
 p_org uuid,p_case uuid,p_version uuid
) returns boolean language sql stable security definer set search_path='' as $$
 select count(*)=1 and coalesce(bool_and(
  v.source_binding_kind='trusted_storage_source_v1' and v.vault_intent_id is null
  and v.source_binding is not null
  and v.source_binding=caseproof._signed_storage_source_binding(p_org,p_case,v.document_id,v.document_version_id)
  and v.source_binding->>'original_sha256'=v.original_sha256
  and v.source_binding->>'representation_sha256'=v.representation_sha256
  and v.representation_sha256=encode(sha256(convert_to(v.representation,'UTF8')),'hex')
 ),false)
 from caseproof._m2_brief_versions v
 where v.org_id=p_org and v.case_id=p_case and v.version_id=p_version
$$;
revoke all on function caseproof._signed_brief_binding_current(uuid,uuid,uuid)
 from public,anon,authenticated,service_role;
commit;
