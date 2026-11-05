# CaseProof Phase A/B — DOCX editing engineering acceptance matrix

**As of:** 5 November 2026 · **Branch:** `feat/word-document-editor-tracked-changes` · [PR #191](https://github.com/haytamAroui/caseproof/pull/191)

This matrix records **engineering-only acceptance on `caseproof-dev`**. It is not a pilot, production, legal accuracy or document-formatting certification. A saved DOCX candidate is never a trusted reviewed draft until a durable actor-bound review, signed commit, source readback and fresh check succeed.

| Gate | Status | Verifiable evidence and limitations |
|---|---|---|
| Phase A — structured DOCX text editing | **COMPLETE — engineering** | OOXML paragraph, ordinary table cells, supported textboxes; unsupported complex content fails closed. |
| Phase A — full Word authoring channel | **COMPLETE — native Word handoff** | Source-bound download and native Office DOCX binary import; real Word provides rich editing. **No embedded Word clone** in the CaseProof browser. |
| Phase A — tracked revisions | **COMPLETE — engineering** | Native OOXML insert/delete, accept/reject and bounded revision identities; synthetic tests, no universal host-fidelity claim. |
| Phase A — candidate integrity | **COMPLETE — engineering** | Signed browser DOCX download/import, SHA-256, bounded bytes, active-content admission, immutable original. |
| Phase B — document-wide SQL authorization on `caseproof-dev` | **COMPLETE — dev deployment** | Supabase migration **`20261105081249`**; `caseproof.dossier_document_edit_reviews` with RLS enabled, no direct `anon`/`authenticated` table grants, four dedicated authenticated/service-limited RPCs. [Dev SQL record](../security/DEV_ONLY_APPLIED_DOCX_AUTH_MIGRATION_20261105081249.sql). **Not installed in production.** |
| Phase B — independent hostile SQL regression | **COMPLETE — automated** | [PR #191 disposable PostgreSQL test](https://github.com/haytamAroui/caseproof/actions/workflows/docx-editor-disposable.yml), including actor, replay, audit rollback, revoked grants and trusted activation. |
| Phase B — live signed document-wide review, activation and mandatory recheck | **COMPLETE — dev signed E2E** | [Successful run 42008220354](https://github.com/haytamAroui/caseproof/actions/runs/42008220354): `F5_DOCX_NATIVE_SIGNED_HUMAN_REVIEW_RECEIPT_PASSED`, `F5_DOCX_NATIVE_SIGNED_LOST_ACK_ACTIVATION_RECONCILED_PASSED`, `F5_DOCX_NATIVE_SIGNED_RECHECK_NEW_VERSION_PASSED`. |
| Phase B — historical integrity and revoked editing | **COMPLETE — dev signed E2E** | Same run: `F5_DOCX_NATIVE_HISTORICAL_SOURCE_IMMUTABLE_PASSED`, `F5_DOCX_NATIVE_SIGNED_EDIT_PERMISSION_REVOKE_DENIED_PASSED`, `F5_DOCX_DOCUMENT_WIDE_SIGNED_ACTIVATION_RECHECK_REVOKE_COLD_REOPEN_PASSED`. |
| Phase B — scoped fixture cleanup | **COMPLETE — dev signed E2E** | Same run: `M05_STORAGE_EMPTY_VERIFIED`, `ZERO_RESIDUAL_VERIFIED`, `DOSSIER_COMPLETE_SIGNED_JOURNEY_AND_TEARDOWN_PASSED`. One older failed fixture was cleared with the owned [dev-only cleanup guard](../security/DEV_ONLY_APPLIED_DOCX_FIXTURE_CLEANUP_GUARD_20261105.sql); no automatic production migration. |
| Sample DOCX LibreOffice smoke | **PASS — synthetic local sample only** | LibreOffice 25.2.3.2 opened, rendered and saved a synthetic NL/FR document, preserving checked text and table structure. Does **not** constitute practitioner/Word-host compatibility sign-off. |
| Independent Security review | **PENDING — Pilot Partner** | [Unsigned independent reviewer checklist](../security/DOCX_DOCUMENT_EDIT_INDEPENDENT_REVIEW.md); test pass cannot sign its own security review. |
| Actual Word + LibreOffice compatibility acceptance | **PENDING — Pilot Partner** | Rights-cleared real documents, native Microsoft Word hosts, LibreOffice revisions/comments/tables/fields and legal practitioner round-trip sign-off are required. |
| Production SQL/feature release | **BLOCKED** | Dev migration does not authorize production deployment. Owner/partner security approval required; do not auto-promote the dev-only SQL. |

**Merge engineering requirement:** The *exact final PR head* must pass all required GitHub Actions checks, with no unexplained failures, and remain consistent with the independent security/compatibility gates above. Merge is a code integration decision, **not** production/pilot acceptance.

**Evidence hygiene:** The signed run used only registered synthetic owner/matter/Storage objects. No test passwords, access tokens, legal texts or person identifiers belong in the acceptance matrix. Independent sign-off remains blank until provided by a separate reviewer.
