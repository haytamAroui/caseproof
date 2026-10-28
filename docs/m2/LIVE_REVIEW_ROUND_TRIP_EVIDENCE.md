# Live review round trip — evidence and scope

**Status: LIVE SYNTHETIC SIGNED REVIEW ROUND-TRIP PASSED (development-only).** Baseline recorded before implementation. The live signed round-trip is wired to the protected GitHub workflow, and the main-merge job is guarded by the exact commit marker `[live-review-acceptance]`.

- Base main: `b1a24c57a88d1c7d9b657761e562ac1707d24b9f`; all nine checks on that commit reported success.
- Target commit: `d159819ae75df08fd70a31a059fff13d03e3f661` (merged PR #112).
- Environment: dedicated development Supabase project `ldwmocpxwskvhoojndrd`; development-only workbench. No customer documents.
- Execution: 28 October 2026, [protected GitHub Actions run #40649967154](https://github.com/haytamAroui/caseproof/actions/runs/40649967154) — **success**.

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

## Implementation readback — 28 October 2026

- Supabase MCP applied `20261028070156_caseproof_dev_signed_review_roundtrip` and `20261028070231_caseproof_dev_scoped_review_cleanup`, followed by security-hardening `20261028071554_caseproof_dev_signed_review_security_hardening` in dedicated `caseproof-dev`. Both SQL files were aligned byte-for-byte with their installed migration history after Supabase assigned versions.
- `public.caseproof_dev_review_seed(uuid,uuid)` and `public.caseproof_dev_review_cleanup(uuid,uuid)` have service-role EXECUTE only; `public.caseproof_dev_live_review(...)` has authenticated EXECUTE and anonymous EXECUTE revoked. Private M2 relations retain no direct client grants.
- The signed RPC is deliberately SECURITY DEFINER with an empty search path and checks `auth.uid()`, nonanonymous authenticated role, exact current case grant, live membership, brief/exhibit revisions, source digest, Storage object lineage and checked observation before atomic write. Supabase's security advisor flags the intentional callable definer as WARN; independent review is still required.
- The candidate check is intentionally **narrow**: it compares one pre-seeded synthetic TXT amount quote to the versioned brief and its exhibit text, not general-purpose semantic/factual evidence verification. This does not establish the full Evidence Kernel, ingestion, OCR, PDF/Word handling or legal approval.
- Protected check: `scripts/verify_dev_live_review_roundtrip.py` uses three confirmed GoTrue users, signed source upload and SHA-256 readback, atomic check/review, idempotent replay, stale revision denial, **actual uvicorn process stop/start**, fresh sign-in, SQL-backed reopening, ungranted and revoked access denial and scoped synthetic cleanup.
- The protected live Actions run #40649967154 executed all seven real signed-user acceptance stages and finished **success**. Disposable Postgres and mocked Auth tests alone would not have established this result.

- Automated Codex review identified direct RPC NULL disposition acceptance and unbounded full-history responses. Installed follow-up migration `20261028071554` rejects NULL dispositions and limits returned decisions to the latest eight, reporting `history_truncated` while retaining full private ledger events. The FastAPI response budget was increased to 256 KiB for bounded worst-case escaped text; no approval/release endpoint added.

## Observed development acceptance receipt — 28 October 2026

**Authoritative run:** [`caseproof-m1-m2-one-click-e2e` #40649967154](https://github.com/haytamAroui/caseproof/actions/runs/40649967154), one-time main push job at merged commit `d159819ae75df08fd70a31a059fff13d03e3f661`. The workflow and its signed acceptance step both concluded **success**. Existing environment: `caseproof-dev-live-auth`; project `ldwmocpxwskvhoojndrd`.

The protected job printed these observed stage receipts without exposing usernames, passwords, JWTs, signed URLs or original source bytes:

1. `LIVE_REVIEW_1`: three real signed dev GoTrue users verified.
2. `LIVE_REVIEW_2`: signed existing synthetic matter discovery, private Storage SHA-256 readback, pre-seeded live brief.
3. `LIVE_REVIEW_3`: candidate check persisted and two ungranted actors denied.
4. `LIVE_REVIEW_4`: real M2 review event, audit and receipt; idempotent replay succeeds; stale revision rejected.
5. `LIVE_REVIEW_5`: stopped server, new uvicorn PID, fresh GoTrue login and identical decision reopened from Supabase.
6. `LIVE_REVIEW_6`: ungranted and revoked actor read/write denied; revoked owner cannot enumerate the matter, check or read original.
7. `LIVE_REVIEW_7`: exact synthetic M2 journals, original Storage object, M1 fixture and ephemeral GoTrue identities cleaned.

Final successful sentinel: `LIVE_M2_SIGNED_COLD_RESTART_REVIEW_RLS_CLEANUP_PASSED`.

**Independent Supabase MCP cleanup readback:** counts were zero for `cases`, `_dev_ci_fixture`, `_m1_exhibit_heads`, `_m2_brief_versions`, `_m2_check_runs`, `_m2_review_events`, `_m2_review_receipts`, `audit_events`, private Storage objects and `auth.users`.

**Verified claim boundary:** One genuinely signed synthetic TXT source with pinned digest, seeded brief and deterministic quote-support candidate, versioned persisted M2 review, cold process restart, fresh authentication, unauthorized/revoked denial and cleanup are accepted in the development environment. General-purpose citation/semantic checking, PDF/DOCX/scanned ingestion, evidence-preview rendering, human correction/recheck, Word add-in, releases and final deliverables **were not** accepted by this run. Do not broaden this receipt to complete M1, M2, or production readiness. The callable development SECURITY DEFINER RPC remains flagged for explicit security review before any wider exposure.
