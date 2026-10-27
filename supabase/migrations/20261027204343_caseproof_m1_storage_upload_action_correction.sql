-- Correct installed organization-vs-matter upload permission split.
-- Organization actions allow evidence:read but not evidence:upload.
-- Exact matter grant must explicitly contain evidence:upload.
do $check$
begin
  if not exists (select 1 from supabase_migrations.schema_migrations
                 where version='20261027202734')
     or (select count(*) from pg_policies
         where schemaname='storage' and tablename='objects'
           and policyname='caseproof_m1_original_put_once'
           and cmd='INSERT') <> 1 then
    raise exception 'original M1 private Storage policy not installed'
      using errcode='55000';
  end if;
end
$check$;

drop policy caseproof_m1_original_put_once on storage.objects;

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
      and 'evidence:read'=any(m.actions)
      and 'case:read'=any(g.permissions)
      and 'evidence:upload'=any(g.permissions)
  )
);

do $verify$
begin
  if (select with_check from pg_policies
      where schemaname='storage' and tablename='objects'
        and policyname='caseproof_m1_original_put_once')
      not like '%evidence:upload%'
      or (select with_check from pg_policies
          where schemaname='storage' and tablename='objects'
            and policyname='caseproof_m1_original_put_once')
         not like '%evidence:read%'
      or exists (
        select 1 from pg_policies
        where schemaname='storage' and tablename='objects'
          and policyname like 'caseproof_m1_original_%'
          and cmd in ('UPDATE','DELETE','ALL')
      ) then
    raise exception 'private Storage upload action split is invalid'
      using errcode='42501';
  end if;
end
$verify$;
