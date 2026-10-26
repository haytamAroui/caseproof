# M1 full-completion gate audit — PIV-02 to PIV-06

**Date:** 2026-10-26. **Target:** NL / FR / EN Belgian litigation Evidence Library.
**Authority:** [principal roadmap](../ROADMAP.md), [workflow](../PRODUCT_WORKFLOW.md), [CONSTITUTION](../../CONSTITUTION.md), ADR-0011 and ADR-0016.

## Status: Backend integration OPEN; no UI needed for M1 backend

This historical release-gate matrix is supplemented by [M1 Backend Exit Contract](BACKEND_EXIT_CONTRACT.md). Backend work is graded in three distinct states: **M1-A contracts**, **M1-B real headless integrated pipeline** and **M1-C staging/product release**. M2 engineering can start when M1-A closes, *without requiring a frontend or real lawyer acceptance*. The open engineering tasks are tracked by [#37](https://github.com/haytamAroui/caseproof/issues/37), [#38](https://github.com/haytamAroui/caseproof/issues/38), and [#64](https://github.com/haytamAroui/caseproof/issues/64)–[#68](https://github.com/haytamAroui/caseproof/issues/68).

The dev Supabase project was read-only checked on 2026-10-26: 0 Auth users, 0 organization memberships, 0 matters and 0 documents. Supabase MCP has no supported Auth user-creation action. Never simulate real signed sessions by writing `auth.users` from SQL; use supported Auth test provisioning and secrets storage.

## Previous assessment: NOT DONE / NOT DEPLOYED

This branch is an integrated **M1 engineering completion candidate**, NOT a production release. No gate may be declared passed based solely on CI, mock identity, disposable PostgreSQL, synthetic fixtures or developer-mode UI. The owner's request to complete all M1 items does not waive C13 human approval for auth/RLS changes, privacy-sensitive integrations and production releases. Do not deploy confidential uploads automatically.

### What this big PR adds

- Pure application exhibit confirmation use case: exact authorized source universe, required explicitly confirmed entries, bounded canonical payload with frozen digest, mandatory human attestation, UUIDv4 intent, expected revision, audit receipt and replay consistency.
- Fixture-only atomic registry store exercises stale revision, refusal of unknown versions, revoked reviewers, and concurrent CAS. Fixture results **do not** prove durable production correctness.
- **Proposed** PostgreSQL schema for restricted same-organization matters, append-only exhibit events, audited revision CAS, idempotent replay and RLS default-deny tables; no authenticating client grants and no public route are installed. New worker/auth permission policy requires separate human review.
- Parameterized restricted matter repository; global org membership alone no longer suffices when this adapter is used. **Not** wired to the production identity session and therefore not a completed PIV-02 gate.
- Opt-in authenticated, read-only JSON API with real `AuthenticatedEvidenceLibrary` port: inventories and previews only after a server verifier authorizes the bearer and case, with no upload or review mutation routes. Service unset denies all real content. Legacy v1 remains isolated.
- Optional local PDF page OCR with Poppler/Tesseract, three-language allowlist and original/page/raster SHA + 150-dpi word bounding boxes; extraction remains **draft requiring human review**. No cloud OCR, no automatic source promotion or illusion of full OCR fidelity. Separate hardened sandbox and real image-backed accuracy benchmark needed.
- Disposable PostgreSQL checks exercise real persisted CAS, audit, idempotent replay, revocation, write denial and event immutability, **not Supabase-backed credential identity**.

### Acceptance gates that remain REQUIRED

| Requirement | Local/CI evidence | Live acceptance needed | Release status |
|---|---|---|---|
| **PIV-02** signed identity and restricted matter policy | Existing Supabase verifier and new restricted SQL adapter; read routes are opt-in only | Actual two signed project users, least-privilege role-bound DB sessions, same-org private matter denial and revocation, scoped worker delegation and mounted UI | BLOCKED |
| **PIV-03** private durable custody | Existing Vault read protocol and disposable PostgreSQL/FS integration | Reviewed production schema/storage bucket and audited immutability, quarantine, malware scanning, retention/deletion, backup/restore drill, restart/lost-ACK recovery on approved infrastructure | BLOCKED |
| **PIV-04** provider-independent durable processing | Existing no-LLM indexer, new audited exhibit state, real disposable CAS tests | Authorized write ingress, durable worker queue/lease/checkpoints for every file/page, budgets, observed economics, restart/invalidations on live services | BLOCKED |
| **PIV-05** PDF/DOCX and OCR/geometry | Real Poppler/Tesseract adapter code and strict synthetic geometry tests; existing DOCX/PDF parser | Install and pin approved binaries/sandbox, image-backed NL/FR/EN OCR benchmark, actual raster-to-PDF coordinate transformation and source-citation fidelity, security and throughput benchmarks | BLOCKED |
| **PIV-06** reviewer-confirmed exhibit mappings | Pure `ExhibitRegister`, application confirmation and disposable PostgreSQL CAS+audit proposal | Signed human confirmation with approved privilege, row-level case grants, durable UI/editor, separate communication/filing receipts, full undo/recheck invalidation | BLOCKED |

### Required operator decisions before live activation

1. Human security review of additive restricted-case and exhibit schema, SQL functions/grants, rollover policy for existing org-wide RLS and GDPR retention. No `SECURITY DEFINER` shortcuts.
2. Approve and execute a canonical migration (not the disposable proposal) only on the intended environment; run security advisors and a two-user Auth/PostgREST/RLS denial test.
3. Provision private object store, malware isolation, sealed keys, backup restore, short-lived retrieval and subject-consent controls. Never use AZComply's real customer data for this test.
4. Make available two genuine dev login sessions and at least two same-org matters with distinct grants. No user provisioning or password disclosure performed in this PR.
5. Record real, adjudicated NL/FR/EN OCR/parser examples and a lawyer walkthrough; capture provenance and CI + live acceptance receipts with exact SHAs.

**Constitution C13/C16/C17:** No autonomous production schema application, merge, deployment, auth/RLS policy relaxation or customer upload. A green branch means engineering checks passed, not that the above operational gates disappeared.
