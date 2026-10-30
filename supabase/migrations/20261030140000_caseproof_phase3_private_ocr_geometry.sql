-- Phase 3: private, immutable OCR geometry sidecars tied to original versions.
-- Never expose sidecars through anonymous access. Access follows live matter grants.
create table if not exists caseproof.ocr_geometry_sidecars (
  document_version_id uuid not null references caseproof.document_versions(id),
  page_number integer not null check (page_number between 1 and 64),
  original_sha256_hex text not null check (original_sha256_hex ~ '^[0-9a-f]{64}$'),
  geometry_sha256_hex text not null check (geometry_sha256_hex ~ '^[0-9a-f]{64}$'),
  coordinate_basis text not null check (length(coordinate_basis) between 1 and 100),
  word_count integer not null check (word_count between 0 and 20000),
  payload jsonb not null,
  created_at timestamptz not null default now(),
  primary key (document_version_id, page_number),
  check (octet_length(payload::text) <= 8388608)
);
alter table caseproof.ocr_geometry_sidecars enable row level security;
revoke all on caseproof.ocr_geometry_sidecars from public, anon, authenticated;
grant select on caseproof.ocr_geometry_sidecars to authenticated;
create policy ocr_sidecar_matter_read on caseproof.ocr_geometry_sidecars
  for select to authenticated using (
    exists (
      select 1 from caseproof.document_versions dv
      join caseproof.documents d on d.id = dv.document_id and d.org_id = dv.org_id
      join caseproof.organization_members m on m.org_id = d.org_id
        and m.user_id = (select auth.uid()) and m.active
        and m.actions @> array['case:read','evidence:read']::text[]
      join caseproof._m1_matter_grants g on g.org_id = d.org_id
        and g.case_id = d.case_id and g.user_id = (select auth.uid())
        and g.active and g.permissions @> array['case:read','evidence:read']::text[]
      where dv.id = ocr_geometry_sidecars.document_version_id
        and dv.original_sha256_hex = ocr_geometry_sidecars.original_sha256_hex
        and coalesce((select auth.jwt()->>'is_anonymous'), 'false') <> 'true'
    )
  );
-- Inserts are deliberately service-only; signed clients cannot forge OCR geometry.
