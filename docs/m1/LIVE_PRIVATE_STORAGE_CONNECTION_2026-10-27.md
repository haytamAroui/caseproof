# CaseProof dev — signed private originals Storage connection

**Live deployment:** Supabase MCP migration `20261027202734_caseproof_m1_private_originals_storage` installed on `caseproof-dev` (`ldwmocpxwskvhoojndrd`), after the four earlier migrations.

This creates a **private**, 20 MiB-limited `caseproof-originals-dev` bucket for PDF, DOCX, TXT, PNG and JPEG. There are two authenticated `storage.objects` policies:
- `caseproof_m1_original_read`: only when the object path exactly matches a stored org/case/document/version/digest with active membership, active exact-matter grant, `case:read` and `evidence:read` on both memberships and grant.
- `caseproof_m1_original_put_once`: same exact path/version, with `case:read` and `evidence:upload` on both memberships and grant.

The path contract is `org_uuid/case_uuid/document_uuid/version_uuid/sha256_hex`. No UPDATE, DELETE, public URL, user-derived tenant header, Storage upsert or service-role bypass is granted. The signed transport is `apps/api/signed_supabase_originals.py`: bounded upload and verified SHA-256 readback over HTTPS using the real Supabase Auth token and a publishable key, with no response bodies or tokens in error messages.

## Already deployed vs tested

- Real migration and bucket: installed; `storage.objects` starts empty.
- Catalog/security inspection: RLS enabled and exact two policies installed, private bucket with finite MIME/size.
- CI unit tests: signed transport safeguards, failure categorization, SHA mismatch, no privileged key, immutable write request, bounded response.
- `scripts/verify_m1_live_signed_storage.py`: protected main-only extension of the **existing M1+M2 One-Click E2E** workflow; provisions three actual verified temporary Supabase Auth users using only the existing GitHub Auth secrets; each must be denied uploads/downloads to a nonexisting/grantless private matter. Deletes Auth users in a `finally` cleanup.
- The existing local M1→M2 integration remains unchanged and runs in the same protected workflow against ephemeral PostgreSQL/Vault.

**Remaining positive acceptance:** server-authorized matter/document/version creation, genuine temporary user whose audited permissions bind to those persisted rows, real signed upload, SHA readback and live M2 persisted processing/recheck. The adapter does **not** write authorized source metadata, grant matters or run the processing worker on its own. No customer documents; no production claim; no new secrets.

**Run:** After merging PR, choose [CaseProof M1 + M2 one-click signed E2E](https://github.com/haytamAroui/caseproof/actions/workflows/m1-m2-one-click-e2e.yml) → Run workflow → `main`. The extra live signed Storage denial step will run automatically using the existing `CASEPROOF_DEV_PUBLISHABLE_KEY` and `CASEPROOF_DEV_AUTH_ADMIN_KEY` protected environment secrets.

Do not conflate read-only MCP policy inspection, local CI signed-auth tests, and genuine positive live database+Storage acceptance.

## Live database-to-Storage application connection

`apps/api/signed_supabase_source_library.py` resolves the document-version and expected hash/length through the **installed** `public.caseproof_private_source_versions` security-invoker view, **using the same signed user JWT** subsequently passed to the private Storage bucket. It uploads only exact matching bytes; on download it verifies SHA-256, expected byte length and immediately re-reads the signed metadata view to detect permission/version changes. The transport never accepts a caller-chosen org ID or SHA.

The development-only, **loopback-guarded** `apps/api/litigation_development_app.py` now accepts the optional `signed_originals=SignedSourceLibrary(...)` dependency and exposes a signed original GET and bounded PUT under `/dev/signed/matters/{case_id}/documents/{document_id}/versions/{version_id}/original`. The separate existing version-bound evidence-original reader also accepts a signed Storage transport. Neither development route is mounted on the production `apps/api/main.py`.

The new `tests/test_signed_supabase_source_library.py` validates database→Storage same-bearer request choreography, missing/foreign version masking, digest/length verification and revocation between requests. `tests/test_litigation_signed_original_live_routes.py` tests the actual FastAPI route injection, direct signed read/upload and denial behavior.

These paths constitute a **wired dev integration**, not proof of a **positive remote user** uploading a real document: that awaits actor-audited server-side organization/matter/version fixture issuance and a genuine signed positive E2E run against the live project.
