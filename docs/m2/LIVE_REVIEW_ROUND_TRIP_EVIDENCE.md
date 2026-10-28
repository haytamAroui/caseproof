# Live review round trip — evidence and scope

**Status: NOT EXECUTED.** Evidence baseline recorded before implementation.

- Base main: `b1a24c57a88d1c7d9b657761e562ac1707d24b9f`; all nine checks on that commit reported success.
- Target commit: pending final implementation and successful CI.
- Environment: dedicated development Supabase project `ldwmocpxwskvhoojndrd`; development-only workbench. No customer documents.
- Date, owner, execution links and receipts: pending actual run.

## Claim

A real signed development user lists an authorized existing matter, opens a seeded live brief and its source evidence, runs the deterministic check, saves a version-bound review in the live M2 store, then restarts the server and signs in again in a fresh browser session and reopens the same decision. Ungranted and revoked users are denied.

Configuration of real application components is expected. The acceptance path must not replace Auth, the live database, signed Storage or the review ledger with synthetic identities, fixture databases, memory storage or fixture fallback. Isolated automated tests are useful but cannot establish this claim.

## Scope and provenance

Use a temporary synthetic, rights-cleared existing matter with seeded (not ingested) brief graph, source metadata and original bytes. Record the seed method, timestamp, immutable IDs and cleanup receipt without logging documents, credentials or JWTs. Original byte SHA-256 is compared with the registered version; the hash establishes integrity, not authenticity. List exact failed, excluded and incomplete source scope.

The following are explicitly excluded: lawyer-created matter, ingestion, OCR, complete PDF/DOCX rendering, correction application, Word host, output generation, filing, legal opinions and production readiness.

## Acceptance evidence

| Step | Required evidence |
| --- | --- |
| Signed matter discovery | Real Supabase Auth session; target appears for granted actor; ungranted actor cannot enumerate it; PR #111 path exercised. |
| Live brief and evidence | Brief graph and metadata read from the live development database and signed Storage; record version and digest, forbid fixture fallback. |
| Check | Deterministic candidate observations, exact snapshot/source scope, limitations and same result for unchanged inputs. |
| Save | Real authorized actor and current matter grant revalidated; immutable version/snapshot, idempotent request ID, revision CAS and audit/receipt committed atomically. Capture safe row identifiers and database role; no secret or source bytes in logs. |
| Cold restart | Stop and restart actual app/server; start a fresh browser session and authenticate again; identical review is read from live database, not process memory. |
| Adversarial access | Ungranted same-org and foreign-org actors cannot list/read/write; stale snapshots and replay conflicts fail closed; revoke current grant and verify subsequent access denied. |
| Cleanup | Remove only temporary synthetic fixture objects and users via authorized interfaces; record cleanup outcome and report failures. |

## Security and design gate

The installed M2 tables deny direct authenticated client read/write. Do not imply that browser sessions have those privileges. Choose a narrowly scoped server or database transaction that derives the signed actor independently, revalidates current organization and exact matter grant at execution time, verifies source/brief snapshots, and atomically persists the review/audit/receipt. Review function ownership, search path, privileges and RLS behavior for the selected mechanism. A privileged MCP catalog query or simulated JWT claim does not establish real signed-user access.

Live development migration `20261028065430_caseproof_m1_private_exhibit_storage` installed `_m1_exhibit_heads` and `_m1_exhibit_events`; these remain inaccessible to authenticated and anon roles. M2 brief, check and review tables exist. The existing disposable checker additionally references `_s2_009b_vault_intents`, which is absent from the live development schema. A genuine implementation must bridge or replace these dependencies; do not point the disposable owner adapter at live data and claim acceptance.

The existing service-role CI fixture only seeds M1 matter/source rows and explicitly cannot clean up M2 immutable journals. Do not reuse its cleanup as proof for a populated review round trip; implement a narrowly scoped disposable-run cleanup and verify it before creating fixture data.

## Completion

All rows above must be linked to observed outcomes, target SHA, green relevant CI, role/privilege evidence, cold-restart proof and cleanup results. Mark unknown or failed steps explicitly. Independent review and the development migration workflow remain applicable. Until then the milestone remains **open**.
