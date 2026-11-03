# CaseProof F6 — M4 reviewed release and historical reopening evidence

**Engineering state:** F6 implementation candidate in [PR #178](https://github.com/haytamAroui/caseproof/pull/178). **Not customer-accepted, not authorized for confidential files, not approved for production.**

**Authority:** [ROADMAP M4](../ROADMAP.md), [M4 delivery contract](DELIVERY_ACCEPTANCE.md), [frontend/BLUEPRINT.md §13/§23](../../frontend/BLUEPRINT.md), [workflow v3.1 S10–S11](../CASEPROOF_WORKFLOW_BLUEPRINT_V3_1.md). This document records evidence and does not create another roadmap, legal certification, new finding state, or mandatory Word channel.

## Implementation boundary

- **Backend:** `apps/api/dossier_export_release.py` uses the current signed-user case and source reader, a *separate* `export:request` grant, a persisted human review, the current draft/snapshot fence, bounded JSON/Markdown/DOCX generation, SHA-256 artifact digests, a server HMAC receipt, and durable idempotent release status. Existing immutable originals are not overwritten. All replay, listing, status, and bytes reads recheck the receipt and immutable manifest digest. No qualified lawyer signature or semantic-certification claim.
- **SQL:** `20261103080000_f6_reviewed_release_ledger.sql` creates a private RLS-enabled `caseproof.dossier_releases` table, revokes direct table access, checks case+organization membership and explicit export grants in the `caseproof_dossier_export_release` signed-user RPC, fences source/inventory/decision changes before insert, bounds output sizes and per-matter release count, and retains historical artifacts subject to matter retention/purge. This is a **development migration candidate**; it has not been independently reviewed or installed on `caseproof-dev`.
- **Frontend:** `/workspace/matters/:caseId/exports?brief=<version>&snapshot=<hash>` shows exact current release readiness, coverage/uncertainty, saved human review count, historical release records and version identities, explicit create/download controls, unknown-outcome reconciliation, and no automatic POST retry. Binary downloads have session fencing, bounded streamed reads, matching type/size/snapshot and SHA-256 digest checks.
- **Separation:** Read/grant-denied export views do not silently promote findings, confer review permissions, or sign out an otherwise valid report reader; revoked session and stale-write controls remain enforced server-side.

## Executable evidence and limitations

1. `tests/test_f6_reviewed_exports.py`: synthetic HTTP route tests for preview, missing review, idempotent release, persisted historical bytes, DOCX reopening, tampered artifact, altered manifest, output size and permission denial.
2. `scripts/verify_retention_disposable.py`: **disposable localhost PostgreSQL** migration installation, separate signed export-grant positive/negative checks, other-matter denial, direct-table denial, revocation and release-erasure fixture; quota denial before dependent snapshot parsing. No customer data.
3. `frontend/src/features/exports/api.test.ts`: strict release payload parsing, historical snapshot binding and malformed-byte rejection.
4. `frontend/tests/exports.spec.ts`: **mocked backend, production-built browser** release creation, digest-verified download, cold UI reopening, lost acknowledgement followed by status reconciliation (no duplicate POST), denied export with surviving reader session, and tampered download rejection. This is **not** genuine signed-user backend browser acceptance.
5. Final-head CI, formatted code, security review, and post-deployment evidence must be recorded on [PR #178](https://github.com/haytamAroui/caseproof/pull/178). Earlier green commits do not prove later modifications.

## Release blockers separate from green CI

- **Live database installation:** Supabase `caseproof-dev` had neither `caseproof.dossier_releases` nor `public.caseproof_dossier_export_release` when read-only checked on 3 November 2026. Require independent SQL/grant/retention review and a controlled development installation. Disposable SQL success is not an installed development grant.
- **Genuine signed-browser journey:** Run signed, authorized current-vs-historical F5→F6 correction/recheck/review/release/download/cold-reopen against the real backend, with lost response, concurrency, revocation and cleanup. Do not label mocked Playwright tests as the signed acceptance gate.
- **Links and DOCX fidelity:** Independent practitioner and software checks must reopen real output DOCX and validate actual link destinations to the correct preserved PDF physical page/crop, as well as supported tables, footnotes, formatting and unsupported OOXML refusal. Existing source-navigation UI is not by itself a validated embedded DOCX hyperlink.
- **Independent policy and human acceptance:** SEC-01–16, data residency, confidentiality/professional secrecy, privacy/legal/security sign-off, manual accessibility, and lawyer acceptance remain outside functional CI and are **not** waived by merging code.

**Exit rule:** F6 is engineering complete only when the above functional acceptance is recorded against one final commit SHA, the development migration is reviewed/installed, all applicable CI checks pass, and unsafe or unsupported outputs explicitly abstain. A code PR merge is not pilot/production approval.
