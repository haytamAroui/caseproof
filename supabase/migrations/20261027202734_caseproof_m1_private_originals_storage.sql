-- CaseProof-dev: M1 immutable original bytes, RLS-scoped by verified matter.
-- Path is EXACTLY org_uuid/case_uuid/document_uuid/version_uuid/sha256_hex
-- Every UUID segment must correspond to an installed caseproof document version.
-- No user UPDATE or DELETE policies: upsert/replacement and deletion denied.
-- No service-role use and no browser-readable caseproof schema expansion.
do $gate$
begin
  if exists (select 1 from storage.buckets where id = 'caseproof-originals-dev')
     or exists (select 1 from pg_policies
                where schemaname = 'storage' and tablename = 'objects'
                and policyname like 'caseproof_m1_original_%') then
    raise exception 'CaseProof private originals storage already installed' using errcode='55000';
  end if;
  if not exists (select 1 from supabase_migrations.schema_migrations
                 where version='20261027160745')
     or to_regclass('caseproof._m1_matter_grants') is null
     or to_regclass('caseproof.document_versions') is null
     or to_regclass('caseproof.documents') is null
     or not (select relrowsecurity from pg_class
             where oid='storage.objects'::regclass)
     or not (select relrowsecurity from pg_class
             where oid='caseproof._m1_matter_grants'::regclass) then
    raise exception 'Storage RLS or reviewed M1 matter foundation not installed'
      using errcode='42501';
  end if;
end
$gate$;

insert into storage.buckets
  (id,name,public,file_size_limit,allowed_mime_types)
values
  ('caseproof-originals-dev','caseproof-originals-dev',false,20971520,
   array['application/pdf',
         'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
         'text/plain','image/png','image/jpeg']::text[]);

-- A file is visible only if its exact version belongs to an active matter
-- assignment and the caller has both case:read and evidence:read.
create policy caseproof_m1_original_read
on storage.objects for select to authenticated
using (
  bucket_id = 'caseproof-originals-dev'
  and name ~ '^[0-9a-f-]{36}/[0-9a-f-]{36}/[0-9a-f-]{36}/[0-9a-f-]{36}/[0-9a-f]{64}$'
  and exists (
    select 1 from caseproof.documents d
    join caseproof.document_versions v
      on v.org_id=d.org_id and v.document_id=d.id
    join caseproof.organization_members m
      on m.org_id=d.org_id and m.user_id=(select auth.uid())
    join caseproof._m1_matter_grants g
      on g.org_id=d.org_id and g.case_id=d.case_id
      and g.user_id=m.user_id
    where d.org_id::text = split_part(storage.objects.name,'/',1)
      and d.case_id::text = split_part(storage.objects.name,'/',2)
      and d.id::text = split_part(storage.objects.name,'/',3)
      and v.id::text = split_part(storage.objects.name,'/',4)
      and v.original_sha256_hex = split_part(storage.objects.name,'/',5)
      and m.active and g.active
      and 'case:read'=any(m.actions)
      and 'evidence:read'=any(m.actions)
      and 'case:read'=any(g.permissions)
      and 'evidence:read'=any(g.permissions)
  )
);

-- Version records are created through separately authorized server-side
-- ingestion, then the actual signed actor may store the matching original.
-- Digest is recomputed against the bytes in the application before promotion.
create policy caseproof_m1_original_put_once
on storage.objects for insert to authenticated
with check (
  bucket_id = 'caseproof-originals-dev'
  and name ~ '^[0-9a-f-]{36}/[0-9a-f-]{36}/[0-9a-f-]{36}/[0-9a-f-]{36}/[0-9a-f]{64}$'
  and exists (
    select 1 from caseproof.documents d
    join caseproof.document_versions v
      on v.org_id=d.org_id and v.document_id=d.id
    join caseproof.organization_members m
      on m.org_id=d.org_id and m.user_id=(select auth.uid())
    join caseproof._m1_matter_grants g
      on g.org_id=d.org_id and g.case_id=d.case_id
      and g.user_id=m.user_id
    where d.org_id::text=split_part(storage.objects.name,'/',1)
      and d.case_id::text=split_part(storage.objects.name,'/',2)
      and d.id::text=split_part(storage.objects.name,'/',3)
      and v.id::text=split_part(storage.objects.name,'/',4)
      and v.original_sha256_hex=split_part(storage.objects.name,'/',5)
      and m.active and g.active
      and 'case:read'=any(m.actions)
      and 'evidence:upload'=any(m.actions)
      and 'case:read'=any(g.permissions)
      and 'evidence:upload'=any(g.permissions)
  )
);

-- Guard against accidentally overlapping browser-writable policies.
do $verify$
begin
  if (select public from storage.buckets
      where id='caseproof-originals-dev') is distinct from false
     or (select count(*) from pg_policies
         where schemaname='storage' and tablename='objects'
         and policyname in ('caseproof_m1_original_read',
                            'caseproof_m1_original_put_once'))<>2
     or exists (select 1 from pg_policies where schemaname='storage'
                and tablename='objects' and
                policyname like 'caseproof_m1_original_%'
                and cmd in ('UPDATE','DELETE','ALL')) then
    raise exception 'private bucket or immutable policy check failed'
      using errcode='42501';
  end if;
end
$verify$;
