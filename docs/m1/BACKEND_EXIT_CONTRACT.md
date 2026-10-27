# M1 Backend Exit Contract — PIV-02–06

**Effective decision proposal:** 2026-10-26. **Scope:** backend-only Belgian litigation Evidence Library; NL/FR/EN. **Principal source:** [ROADMAP](../ROADMAP.md), [Product Workflow](../PRODUCT_WORKFLOW.md), [M1 implementation gate matrix](COMPLETION_GATE_MATRIX.md), ADR-0011, ADR-0016 and [CONSTITUTION](../../CONSTITUTION.md).

## Architectural decision: do not confuse software milestones with product release

There is **NO frontend implementation prerequisite** to M1 backend completion. Neither a real lawyer nor a browser needs to click a UI to verify server behavior. Test the exact complete behavior using HTTP, genuine development Auth sessions where required, real disposable/staging Postgres, private object bytes, durable workers and tests with explicit source versions. The mandatory M3 Word and M4 completed-delivery workflow will consume these same contracts. A synthetic Office-host spike can progress early; see [M3](../m3/WORD_INTEGRATION_ACCEPTANCE.md) and [M4](../m4/DELIVERY_ACCEPTANCE.md).

Three independently reported gates:

| Gate | Definition | Status at this revision | Implication |
|---|---|---|---|
| **M1-A Contract freeze** | Explicit authorization model and stable typed matter/source/representation/processing/exhibit ports; schema versions; adversarial contract and unit regressions, architecture boundaries | **ENGINEERING CONTRACT IMPLEMENTED, DISPOSABLE CI PASS; LIVE SECURITY SIGNOFF OPEN** — ADR-0017 selects default-private litigation matter grants and explicit actions. RLS rollout still requires review; see [#64](https://github.com/haytamAroui/caseproof/issues/64) | **Must close before M2 relies on final contracts**. M2 experiments and isolated implementation may begin in parallel against frozen assumptions explicitly documented as provisional. |
| **M1-B Integrated backend** | Authenticated headless intake through actual scoped DB + private object store → durable parse/OCR → evidence preview → human-gated exhibit mapping → persisted audit → restart; automated positive and negative tests | **OPEN** — [#37](https://github.com/haytamAroui/caseproof/issues/37), [#38](https://github.com/haytamAroui/caseproof/issues/38), [#65](https://github.com/haytamAroui/caseproof/issues/65), [#66](https://github.com/haytamAroui/caseproof/issues/66), [#67](https://github.com/haytamAroui/caseproof/issues/67), [#68](https://github.com/haytamAroui/caseproof/issues/68) | **Backend M1 is NOT DONE until this is green**. Does not block isolated, feature-flagged M2 coding once M1-A is green. |
| **M1-C Staging/customer release approval** | Human security review, approved migrations/grants/storage/OCR isolation, operational backup/retention, observed staging receipts, authorized deployment; later real lawyer UX | **DEFERRED** — not a code-test replacement | Blocks customer confidentiality/production claims, **not backend M2 development**. UI/workbench accessibility, translations and usability belong to the future frontend/product release lane, not M1 backend sign-off. |

M1-A, M1-B and M1-C are NEVER interchangeable. A passing test suite on disposable PostgreSQL is NOT a production release, but the absence of a UI is NOT a technical blocker to backend development.

## Existing engineering evidence vs gaps

**Observed on 2026-10-27:** merged #62–63 provide typed Evidence Kernel and dispute register, bounded deterministic PDF/DOCX extraction, audited exhibit CAS candidates, Poppler/Tesseract adapter with mock raster tests and disposable PostgreSQL CI. **Merged #86–88** add default-private exact case grant RLS proposal, verified-bearer non-BYPASSRLS reader and atomic empty-dev-schema candidate with rollback/deny tests. **None of those SQL proposals are installed on live Supabase.** No real signed-user→installed private DB→private Storage→genuine OCR→durable exhibit mapping acceptance exists. [#88 rollout packet](EXACT_DEV_PRIVATE_SCHEMA_ROLLOUT.md).

**Live Supabase read-only status (2026-10-27, caseproof-dev):** 0 Auth users, 0 matters, no installed `_m1_matter_grants`, and **three legacy organization-wide SELECT policies still present**. The candidate migration has not been applied. The connected Supabase MCP exposes no supported Auth Admin user-creation operation. Do not fabricate users by inserting into `auth.users` through SQL. To run a real two- or three-user integration test, create dedicated test accounts by supported Auth sign-up/Admin API or Dashboard, keep passwords outside this repository and chat, verify actual issued JWT via pinned Auth endpoint, and clean up via approved flow. A synthetic JWT or arbitrary `SET request.jwt.claim.sub` is only a negative/SQL-fixture test and does not prove signed identity.

## Engineering packets (open until tested)

| ID | Milestone | Headless acceptance evidence | Task |
|---|---|---|---|
| **M1-01 / PIV-02** | M1-A/B | Adopt ADR-0017 default-private per-matter grants with explicit action scopes; freeze worker delegation. Live security approval is pending. Two active same-org users with differently granted cases + foreign org; compare RLS/current app permissions and revocation via actual bearer. Negative forged/tampered/expired token and pooled-connection tests | [#64](https://github.com/haytamAroui/caseproof/issues/64), [#37](https://github.com/haytamAroui/caseproof/issues/37) |
| **M1-02 / PIV-03** | M1-B | Put-once verified originals in private non-public bucket, audited persistent intents, quarantine, SHA readback, loss/corruption/unknown outcome, independent process restart and retention/deletion/legal hold behavior. No service-role bypass | [#38](https://github.com/haytamAroui/caseproof/issues/38) |
| **M1-03 / PIV-04** | M1-B | Actual authenticated POST/upload equivalent + queued worker + checkpoint/page status + status endpoint; cold restart/retry/duplicate/idempotency + processing budgets. No LLM required | [#65](https://github.com/haytamAroui/caseproof/issues/65) |
| **M1-04 / PIV-05** | M1-B | Genuine NL/FR/EN scanned-image PDF OCR using pinned binaries and sandbox; transformed source-coordinate fidelity, per-page completeness/failed states, DOCX textboxes/tables/notes caveats and actual benchmark fixtures | [#66](https://github.com/haytamAroui/caseproof/issues/66) |
| **M1-05 / PIV-06** | M1-B | Read/confirm/edit Stuk/Pièce aliases and actual source pages via **authenticated headless endpoint**; atomic durable CAS + audit + immutable events, ambiguity/invalidations and reboot; never infer legal approval from sign-in | [#67](https://github.com/haytamAroui/caseproof/issues/67) |
| **M1-06 / all** | M1-B | One executable cross-process test proves end-to-end inventory, original retrieval, OCR warnings, confirm/reopen, user/matter isolation, audit, idempotency, recovery; NL/FR/EN and mixed cases. Include exact run SHA and runner/database identity | [#68](https://github.com/haytamAroui/caseproof/issues/68) |

Do not expand M1 into the entire general findings/coverage and legal review graph from [#39](https://github.com/haytamAroui/caseproof/issues/39); its M2+ parts remain explicit separate dependencies. Scope M1 review to **exhibit-register confirmation**, not approval of legal conclusions. No Word integration or customer UI acceptance in M1 backend.

## Backend-only end-to-end acceptance scenario

1. **Identity:** provision approved ephemeral test identities A1/A2 (same organization) and B1 (different organization) via real Supabase Auth, not hand-written JWTs. Signed JWT is remotely verified; active membership, matter grant and action are loaded from a current database policy. The choice of restricted vs org-wide access must follow approved [#64](https://github.com/haytamAroui/caseproof/issues/64), not test preference.
2. **Matter:** headless create/list/read two matter IDs and assert unauthorized case is masked. Revocation must be effective on the next relevant request/transaction.
3. **Ingest:** POST permitted fixture bytes from test client (PDF born-digital, PDF scanned, DOCX, corrupt input) → durable `PENDING` intent → private put-once store → SHA-256 readback → verified source/version/audit receipt. Unknown ACK reconciles by request ID.
4. **Process:** durable page-level parse/OCR job runs isolated; source/version and representation lineage recorded, processed+unprocessed denominator exposed; no OCR or model fabricated fallback.
5. **Inspect:** GET inventory + derived preview with exact source identity, page coordinates/warnings; download original only through authorization, digest must equal uploaded bytes.
6. **Confirm exhibits:** human-originated action, signed session and dedicated `exhibit:confirm` (or approved equivalent) check → map Stuk 1 / Pièce 1 + aliases and differing printed/PDF pages → persisted expected-revision CAS and append-only audit. Password sign-in alone does **not** authorize legal approval; define ordinary exhibit-mapping confirmation separately. Stale versions, ambiguous labels and cross-matter references are denied.
7. **Restart:** kill API/worker, restart independently, load exact original/representations/mapping/audit and repair any half-finished jobs. Mutate source availability and ensure derived mappings invalidate.
8. **Negative controls:** revoke one user; deny same-org matter according to chosen policy; deny cross-org; corrupt stored bytes; force audit failure; duplicate request; OCR timeout; lose worker lease; unsupported document; assert no source content or credentials in logs.
9. **Receipt:** generate machine-readable CI/staging evidence with code SHA, migration version, role policy ID, fixture digests, parser version, test names/outcome, and storage/worker configuration IDs **excluding secrets**.

**No lawyer UI necessary** for any step. Any production or confidential live-data claim still requires M1-C approval and no test may be reported as passed unless actually run.

## When M2 may start

**M2 wedge contract update (2026-10-26):** the first M2 acceptance must run **cited exhibit existence + optional literal quote fidelity + typed same-role date/value comparison** together; see [feedback audit](../research/BELGIAN_WEDGE_FEEDBACK_AUDIT_2026-10-26.md). A zero-quote brief still has two meaningful check families; clean cases may yield no warnings. This change affects M2 only, not the M1-A/B/C release separation.

**Go for isolated M2 implementation** once the ADR-0017 default-private policy contract and tests are accepted, typed ports and source/citation/exhibit revisions are pinned, M1 architecture+unit+adversarial CI passes and the M2 suite never routes real customer files into unapproved infrastructure. The M2 branch uses **contract-tested fake adapters** only where the capability does not require live security, and records unavailable/partial as such.

**No-go for M2 customer release** until M1-B and M1-C are verified and active. M2 code must not invent evidence versions, silently promote draft OCR, widen permissions or change established kernel/domain boundaries.

## Review obligations

- Owner accepts the M1-A authorization policy and M1-B exit checklist.
- Independent security review of RLS/migrations, signed session role plumbing, private bucket, OCR sandbox, and exhibit transaction implementation before live activation.
- Merge/production grants/deployment under CONSTITUTION C13 rules, after required green CI. No tool or PR creation constitutes release approval.
