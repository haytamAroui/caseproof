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
