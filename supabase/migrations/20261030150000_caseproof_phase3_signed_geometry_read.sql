-- Expose only a narrow authenticated, RLS-enforced read function.
-- The private caseproof schema remains absent from PostgREST exposed schemas.
create or replace function public.caseproof_signed_ocr_geometry(
  p_version uuid, p_page integer
) returns table (
  page_number integer, original_sha256_hex text, geometry_sha256_hex text,
  coordinate_basis text, word_count integer, payload text
)
language sql stable security invoker
set search_path = ''
as $$
 select s.page_number, s.original_sha256_hex, s.geometry_sha256_hex,
        s.coordinate_basis, s.word_count, s.payload
 from caseproof.ocr_geometry_sidecars s
 where s.document_version_id = p_version and s.page_number = p_page
$$;
revoke all on function public.caseproof_signed_ocr_geometry(uuid,integer) from public,anon;
grant execute on function public.caseproof_signed_ocr_geometry(uuid,integer) to authenticated;
