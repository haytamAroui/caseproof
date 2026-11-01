# CaseProof — latest verified direction and engineering state (31 October 2026)

**Source of truth:** [ROADMAP M0–M6](ROADMAP.md) and [ADR 0019 vision](adr/0019-evidence-engine-and-first-market.md); one focused product: independent **post-assembly Belgian Stuk/Pièce exhibit verification** through a web-first, four-dimension reviewer. Research comparisons are hypotheses, not an exclusive market claim. Word, authority research, German, local installer and publicly hosted MCP are not v1 prerequisites.

**Latest verified `main`:** [PR #154](https://github.com/haytamAroui/caseproof/pull/154) squash merged to [`d3374b8f78599b33bff7ce098a746b70af29b094`](https://github.com/haytamAroui/caseproof/commit/d3374b8f78599b33bff7ce098a746b70af29b094). Its 21 post-merge job conclusions were **17 success, 4 intentionally skipped live jobs and 0 failures**. The real-process 200-page PostgreSQL recovery, crash/resume, OCR/visual checks and read-only hosted MCP contract passed as **synthetic/disposable CI**, not as actual production hosting or live OAuth acceptance. PRs #146/#147 (representation gate), #149 (P3 translation/inventory/DOCX coverage), #150 (frozen canonical report) and #151–153 (worker/MCP architecture) are also **merged**; older 'feature-branch candidate' sections below are dated historical log entries.

**Implementation versus gates:** M1/M2 have major signed synthetic/backend evidence; the full real-world corpus and approved client OCR boundary remain open. M3 still lacks user-created matter intake, complete original page/crop browser viewer and applied correction. M4 has bounded JSON/Markdown/DOCX appendix primitives, but not independently accepted corrected DOCX, complete source-link reopens and end-to-end browser release. M5 lawyer interviews, controlled representative validation and priced demand are not proven. SEC-01–16, professional-secrecy approval, deployed OAuth/real consent, restore/retention and independent security review remain separate gates.

**Next development:** complete one authenticated **web M1→M4 journey** with a real-format synthetic NL/FR dossier and negative security/restart/retry cases; run practitioner interviews and deployment confidentiality/egress assessment in parallel. No new isolated verifier authority or Word-first pivot. Previous dated sections document historical heads only.

---

## PostgreSQL two-process recovery + hosted OAuth MCP candidate — 31 October 2026

Feature branch `feat/postgres-process-recovery-hosted-mcp-oauth` builds the missing real-PostgreSQL
200-page worker crash/resume scenario under the actual signed page-job SQL
function (disposable PostgreSQL, synthetic actor role), with lease fencing,
200 verified HMAC artifact readbacks, checkpoint/audit counts, revocation
denial and fresh OS process takeover. Unlike the earlier SQLite recovery
proof, this does not mirror PostgreSQL behavior in a mock.

An independent, optional, stateless MCP JSON-RPC HTTP host and OAuth protected
resource discovery boundary are added, with pinned project Auth /user
verification, resource audience and scope checks, exact read-only canonical
tool projection, host-only per-call content release and no review/approval
writes. This is **an engineering/CI candidate** pending final-head checks.
It does **not** provide a deployed OAuth issuer/client or approved, persistent
firm consent registry, and is NOT a production-validated hosted service.
Read [acceptance and outstanding release gates](m3/POSTGRES_HOSTED_MCP_OAUTH_ACCEPTANCE.md).
Existing web-first lawyer workflow remains the product priority.

## PR #150 — canonical report and processing hardening candidate, 31 October 2026

Implementation: frozen-snapshot MCP dispatch; shared application report projection;
caller/matter/brief/snapshot/destination/expiry-bound host release checked before
return; exact export digests; byte-parity HTTP regressions; isolated fresh PDF
inspection and no reparse on frozen reads; actual signed-upload archive preflight;
privacy-safe OpenTelemetry tool spans/durations with real in-memory SDK capture.
Markdown evidence is inert JSON code-block data; DOCX derivatives refuse external
relationships, macros/active objects and active fields without editing originals.

Local locked suite after these changes: **1,730 passed, 4 skipped**; Ruff, affected
strict mypy and architecture checks passed. Required executable OCR/browser and
PostgreSQL/live workflows remain authoritative for this candidate's exact head.
Cloud readiness is not asserted here. See
[acceptance matrix](m3/CANONICAL_PROCESSING_ACCEPTANCE.md).

Page processing: bounded coordinator and isolated parser composition, immutable
input manifests, per-page checkpoints, persistent deadline, cancellation/revocation
guards, finite local retry and artifact-persistence ports. A 200-page text-bundle
benchmark and separate-process disposable PostgreSQL restart proof are wired to
CI. This does **not** expand the signed dossier's four-page visual budget, install
a live page worker, prove 200-page OCR, or close P1 production acceptance. Hosted
MCP/OAuth remains deferred; no production or live schema change is introduced.

## Representation fidelity v2 — 31 October 2026

PR #142 merged v1 at `53354f0`: optional comparison contract and fixture foundation.
The current `feat/complete-representation-gate` candidate adds signed dossier
integration, bounded region/crop provenance, conservative normalization, immutable
snapshot readback, human inspection UI, executable corpus measurement and signed
acceptance. See [v2 acceptance](m3/REPRESENTATION_GATE_ACCEPTANCE.md).
No calibrated legal-corpus artifact ships; agreement stays unassessed. Cloud executable OCR, browser and signed development receipts are available on
PR #146. Final-head reruns and review status determine acceptance. Dev migrations
`20261030235107` and `20261030235456` are installed; production is unchanged.
No M3 closure, customer-data authorization or production deployment is claimed.
## 30 October 2026 — product vision and current evidence

[ADR 0019](adr/0019-evidence-engine-and-first-market.md), [roadmap](ROADMAP.md) and [workflow](PRODUCT_WORKFLOW.md) now separate the reusable engine ambition from Belgian litigation as the first market. Expansion is conditional on customer pull, technical reuse, measured benefit and commercial commitment with explicit owner approval. This documentation update adds no product features, UI, migration, client-data permission or release.

PR #140 signed-workflow baseline (before representation gate PR #142): PR #140, merge `5ab54710c21d797bd41295754e7a95e4331c0449`; tested head `82330f205084ffa7204540c2cd0bfe6131793d09`, all 15 workflows green. [Dossier](https://github.com/haytamAroui/caseproof/actions/runs/41105503131), [benchmark](https://github.com/haytamAroui/caseproof/actions/runs/41105503677), [CLI](https://github.com/haytamAroui/caseproof/actions/runs/41105503385), [retention](https://github.com/haytamAroui/caseproof/actions/runs/41105503401). Benchmark discovery: 2,627.645 ms, 89,060 KiB API peak RSS, synthetic reference detection 60 TP / 0 FP / 0 FN. Dossier normal/edge counts: 8/9 detected, 3/3 identity-page checked, 5/6 unresolved; fully checked remains false. These are scoped development observations, not legal accuracy, browser acceptance, confidential-client approval or commercial proof. Earlier dated baselines below remain historical.

Next work: validate practitioner pain and total effort; close supported verification/coverage and output gaps for the existing task. Web implementation remains a separately scoped task; no UI work is initiated by this update.
## Representation fidelity candidate — 30 October 2026

Feature branch `feat/representation-conflict`: paired clean/redlined/scan fixture
factory, conservative pixel midline candidate detector, source-bound regional
comparison and unresolved literal-check gate. See [ADR 0020](adr/0020-representation-conflict-gate.md).
Live adapter/persistence/UI wiring remains open; no M3 completion or detector
accuracy claim. Exact CI evidence belongs to the feature PR.

<!-- PR #140 verification receipt; measured code head, not production authorization. -->
## PR #140 OCR hardening verification (30 October 2026)

Code head `d4e0a4d061f2caaebc36ecfa30342c5c6b6a4738` passed signed benchmark,
CLI and retention acceptance. Benchmark run [41104740806](https://github.com/haytamAroui/caseproof/actions/runs/41104740806)
measured 3,248.863 ms discovery and 88,928 KiB API peak RSS, with 60/0/0
reference-detection TP/FP/FN on the synthetic intended-150-page draft.
This is extraction evidence, not legal support accuracy or general corpus recall.
[Raw benchmark artifact](https://github.com/haytamAroui/caseproof/actions/runs/41104740806/artifacts/13001455392)
contains the tested SHA, run ID and input hashes.
[Signed CLI run](https://github.com/haytamAroui/caseproof/actions/runs/41104740765)
verified separate dimensions, saved review, restart, downloaded report and cleanup;
[report artifact](https://github.com/haytamAroui/caseproof/actions/runs/41104740765/artifacts/12999997734).
[Signed retention run](https://github.com/haytamAroui/caseproof/actions/runs/41104740935)
proved immediate access denial, Storage/DB purge, retry and minimal receipt, followed
by zero-residual verification. Full final-head workflow status is recorded in PR #140.

OCR Docker mode uses no networking, the workspace owner's UID/GID, dropped
capabilities, a read-only root, CPU/memory/process/file limits and forced container
cleanup after timeout. A missing sandbox fails closed. The Docker launcher itself
must not inherit the OCR binary address-space limit. Real scan CI includes hostile
PDF metadata/URI data; the separate required network probe proves HTTP denial.
No client-data or production approval follows from these synthetic tests.
Independent security/privacy review and verified backup restore/erasure replay remain open.

# CaseProof — current product scope and status pointer (28 October 2026)

**Active product direction:** [ADR 0018](adr/0018-pre-submission-verification-freeze.md), [ROADMAP M0–M6](ROADMAP.md) and [web workflow](PRODUCT_WORKFLOW.md): pre-submission factual exhibit verification, web-first, Word/MCP optional. The dated reports below are **historical engineering receipts**, not a current Word-mandatory, finance-first or broader litigation product instruction. Follow the roadmap for live-vs-open gate distinctions.

**Historical 28 October narrow proof (superseded by the current receipt above):** [PR #119](https://github.com/haytamAroui/caseproof/pull/119) and [signed synthetic TXT live receipt](m2/LIVE_SIGNED_CORRECTION_RECHECK_2026-10-28.md) establish a particular authenticated TXT source/brief/review/correction/recheck/restart scenario. **Open:** verified full PDF/DOCX/scanned corpus and OCR cropping, reference/page split, web reviewer, released actual DOCX/report, confidentiality review, pilot and paid demand. No claim that other historical M1/M2 status below is current; dates and exact receipts decide what was actually tested.


**30 October 2026 retention engineering update (PR #136):** Two-phase matter
retention is installed on `caseproof-dev` only, with signed creator deletion,
owner/crop/original/review/export denial, 30-day grace, legal-hold checks,
Storage-first purge and minimal pseudonymous erasure receipt. Initial signed
OCR/review/restart/deletion acceptance and teardown passed in
[run 41085730618](https://github.com/haytamAroui/caseproof/actions/runs/41085730618).
Real concurrent Storage-upload denial passed in
[run 41086260235](https://github.com/haytamAroui/caseproof/actions/runs/41086260235).
Canonical deployed migrations: `20261030155817` and `20261030160341`.
See [retention design](security/RETENTION_DESIGN.md) and [backup limitations](../SECURITY.md).
This does not approve confidential client data, full worker egress, legal
accuracy, a production restore procedure or a commercial launch.


**30 October 2026 connected dossier update (PR #138):** The signed backend/API
journey passed on synthetic DOCX + inventory + text PDF + image-only scan:
8 detected, 3 identity/page checks, 5 unresolved, 8 unprocessed DOCX parts; original
hash readbacks, OCR crop, persisted decision, scoped JSON/Markdown/annotated DOCX,
identical cold-restart reopening, stale-review rejection, ungranted/revoked denial
and finally teardown. The separate live unreadable-DOCX negative also passed.
See [exact acceptance evidence and limitations](journey/ACCEPTANCE_RECEIPT.md)
and [eight-task integration audit](journey/IMPLEMENTATION_AUDIT.md).
This proves the stated synthetic backend journey, not full M1–M5 completion,
confidential-client readiness, arbitrary reference recall or commercial demand.

---

## Historical dated status log (retained; superseded for product direction)

### Current product direction — M1 backend-first, M2 may be developed in parallel — 2026-10-26

> **27 October 2026 live M1 update:** Supabase `caseproof-dev` has applied the exact default-private M1 migration `20261027160745`; read-only policy/role/privilege inspection verified deployment. **M1-B is still OPEN**: zero Auth users, matters and grants, absent dedicated least-privilege app DB login, no signed-user actual-db acceptance or independent security signoff. **27 October 2026 later live update:** All 11 private M2 tables and the 2 restricted M1 security-invoker read views are now **installed in `caseproof-dev`** via Supabase MCP (`20261027195417`, `20261027195451`). Verified RLS/private privileges. **M1-B and M2-B are still open** for positive live signed-user matter access, real private Storage bytes and full persisted live correction/recheck, not SQL installation. [Current receipt](m1/M1_M2_LIVE_DEV_MIGRATION_RECEIPT_2026-10-27.md). [Earlier M1 receipt](m1/LIVE_DEV_PRIVATE_MIGRATION_RECEIPT_2026-10-27.md). Earlier dated PR and Supabase snapshots below are historical.

**Principal source:** [Belgian litigation roadmap](ROADMAP.md) and [complete user workflow](PRODUCT_WORKFLOW.md). [ADR 0016](adr/0016-belgian-litigation-product-pivot.md) supersedes *finance-first product sequencing* only; sector-neutral Kernel, constitution, ADR-0011 architecture and finance compatibility remain unchanged. The snapshots below record historical engineering state; their finance-first action recommendations are no longer the active product order.

**Current M1 delivery status:** [M1 Backend Exit Contract](m1/BACKEND_EXIT_CONTRACT.md) defines **M1-A contract freeze**, **M1-B integrated headless backend**, and **M1-C release approval**. M1-A/M1-B are OPEN; frontend and manual lawyer walkthrough are **not M1 backend prerequisites**. After M1-A action/matter semantics are frozen, M2 may begin on contract-tested fake data while hardening/storage/auth in M1-B proceeds. [PR #62](https://github.com/haytamAroui/caseproof/pull/62) merged; [PR #63](https://github.com/haytamAroui/caseproof/pull/63) remains open and CI-verified as an engineering candidate, not a production deployment.

**Historical M1 PR #62 scope (now merged):** [implementation/gate matrix](m1/IMPLEMENTATION.md) and [hexagonal task audit](m1/HEXAGONAL_AUDIT.md). Authenticated *read-side* composition, deterministic preserved-source preview, bounded DOCX/text and PDF page warning labels, immutable versioned Stuk/Pièce mapping proposals and adversarial tests. This does not install matter-write grants, real Storage, customer upload, parser OCR, exhibit review persistence or public API. Keep M1 flagged IN PROGRESS until genuine signed Auth→DB, private custody/recovery and reviewer confirmation succeed. Do not mark M1 complete merely because synthetic CI passes.

**M0 single-PR work:** PIV-00 owner/contract and code-status matrix ([BASELINE](m0/BASELINE.md)), unresolved public claims ([CLAIMS REGISTER](m0/CLAIMS_REGISTER.md)), and PIV-01 synthetic NL/FR/EN/mixed fixtures, validator/tests and pre-registered [BENCHMARK PROTOCOL](m0/BENCHMARK_PROTOCOL.md). No actual human/competitor benchmark, independently adjudicated gold, OCR scan evaluation, or Belgian legal opinion. Acceptance remains conditional on PR-head CI, scope review and evaluation-label adjudication.

**Not implemented:** a production litigation web/Word journey, Stuk/Pièce register, authenticated matter authorization with restricted same-org scope, real confidential Storage, DOCX/OCR/filing integrations, release authority or linked legal bundles. These are PIV-02 onward. Open PR #57 remains an unmerged extraction candidate until separately reviewed; do not credit its changes to current main.

---

# CaseProof / ExceptionDesk — verified engineering status

## 2026-10-23 — Persisted exact text evidence increment

PR #51 is merged at `9dabe59a4ddeea2f9aaed9b4d83c32af67683099`; its
verified feature head passed 881 unit tests, eight real disposable Vault
integration tests, type/lint/architecture and migration checks in
[CI 39938192806](https://github.com/haytamAroui/caseproof/actions/runs/39938192806).

[TEXT-INT-001](tasks/TEXT-INT-001.md) adds internal read composition for the
existing persisted graph plus actual Vault bytes. Its first identity UTF-8
representation reuses original bytes, preserves exact code-point offsets and
separates citation/fidelity from support/approval. A separate-process PostgreSQL
fixture demonstrates recovery and negative cases; new-head CI evidence must
be recorded on its PR. No live migration, new authoritative facts table,
production identity, parser/OCR/LLM pipeline or human decision is introduced.

## 2026-10-23 — Vault integration increment (feature branch)

Base `main` is `901c51d08dfac577d56799889701416e9139940d`, including PRs
#45/#46/#50; its architecture, disposable PostgreSQL and canonical migration
checks were verified successful. PR #49 supplies private filesystem bytes;
PR #50 supplies the disposable DB-API VaultLedger driver. Neither is a live
Supabase Storage deployment. Older snapshots below predate those merges.

[VAULT-INT-001](tasks/VAULT-INT-001.md) adds a real psycopg + filesystem +
coordinator integration command to required PostgreSQL CI. It exercises
fresh-process recovery, retry/concurrency, lost acknowledgments, tampering,
audited availability loss, rollback and scoped denial. New-head CI evidence
must be recorded on its PR before this increment is called verified.
Synthetic actors and postgres-owner fixtures do not establish genuine Auth,
runtime RLS or production read authorization. No live grants, migrations,
storage buckets, HTTP routes or approved decisions are introduced.

**Last verified:** 2026-10-22 UTC against `main` commit `66db73667cc4932995e0376d7f1b7c9279c70041`, merged PR #35. **Not a live release certificate.** Recheck GitHub before acting; this file can become stale.

**Product direction:** ExceptionDesk finance-first supplier invoice ↔ purchase-order exception resolution; CaseProof factual dispute dossiers only after finance validation. Repository name stays `caseproof`. AZComply remains independent.

## Implemented and tested

| Slice | Status and supporting evidence | Not proven / not wired |
|---|---|---|
| Stage 0 / finance reference | Modular Python kernel, initial `Decimal` total-amount discrepancy comparator, CI. | Full VAT, line-item, amendments or customer-facing finance pipeline. |
| Stage 1 KRN-101–109 | In-memory immutable source/representation versions, typed anchors, fidelity vs semantic support, findings, scoped source/issue coverage, promotion gates, provenance, API v2 proposal and adversarial tests. | Persisted complete graph, genuine authenticated approval. |
| S2-001/002/002A | Application access boundary, seven-table canonical `caseproof` migration in dedicated development Supabase project, PostgreSQL 17 disposable RLS/CAS/rollback tests. | Production role and user-issued session-to-live-DB proof. |
| S2-003/005/006 | Remote Supabase `/user` Auth verifier, read-only case adapter, manual signed-user test harness. | Real A/B accounts and completed signed-Auth test run; application wiring. |
| S2-004 / PR #28 | Internal **disposable-only** atomic observation + audit + receipt proof with concurrent and failure tests. | Production transaction service, human decision/approval route. |
| S2-007 / PR #29 | Synthetic two-tenant RLS and revocation fixture; protected manual genuine-Auth workflow. | Real signed-user test, live least-privilege DB session binding and revocation tests. |
| S2-008 / PRs #30–33 | Durable graph design; **disposable** SQL source/representation/anchor graph, typed locator codec and read-only PostgreSQL JSONB reconstruction. | Installed graph migration, full finding/assessment/coverage persistence, object-backed source authenticity. |
| S2-009 / PRs #34–35 | **Internal** put-once/read-back Vault protocol + recovery; **disposable** PostgreSQL pending-intent, case revision, audited availability and idempotent replay proof. | Real private Storage bucket, verified object bytes, real VaultLedger driver, availability-head publication. |

**CI snapshot:** main `66db736` had successful `Kernel boundary` run [39746350280](https://github.com/haytamAroui/caseproof/actions/runs/39746350280) and migration integrity run [39746350518](https://github.com/haytamAroui/caseproof/actions/runs/39746350518). The PR #35 test branch passed 778 Python tests + PostgreSQL 17 fixture in [39745880251](https://github.com/haytamAroui/caseproof/actions/runs/39745880251). **Fixtures and unit doubles are not proof of cloud authorization or customer readiness.**

## Architecture contract consolidation (stacked proposal, NOT merged)

[ADR 0011](adr/0011-architecture-freeze-and-first-finance-slice.md) freezes the original six-responsibility architecture and shifts execution to parallel secure-foundation and synthetic-only finance product tracks. [Architecture baseline](../contracts/architecture_baseline_v1.json) and [Action catalog](../contracts/action_catalog.v1.json) are checked by tests: API ↔ KRN-102 ↔ persistence exact locator round trip (canonical `sheet_range`, PDF decimal strings, text normalization, sheet table ID), all uninstalled v2 approval actions blocked, no new permission grants or enabled routes. This feature PR is **stacked on unmerged PR #36**; no statement here implies it is live on main or deployed.

## Real blockers — must remain open until verified

**SEC-01: owner-controlled merge protection.** Repeated main CI succeeds; architecture negative-control PR #4 failed explicitly on `forbidden import domains.finance.reconciliation` in [run 39555343328](https://github.com/haytamAroui/caseproof/actions/runs/39555343328). GitHub rulesets query returned an empty list on 2026-10-22 and branch protection read returned 403 to the connector. **Neither proves main is protected.** Owner must enable/prove branch protection, mandatory status checks and review. [Issue #5](https://github.com/haytamAroui/caseproof/issues/5) stays open until verified. Never merge sabotage PR #4.

**[SEC-02: real signed Auth and secure DB runtime](https://github.com/haytamAroui/caseproof/issues/37).** Create two separate confirmed **development** Auth accounts, configure approved protected GitHub environment, run S2-007 manual workflow, then implement/test true verified bearer-to-least-privilege tenant DB authorization, session revocation and pool cleanup. Signed Auth→synthetic SQL claims in the fixture is **not** true live database identity propagation.

**[STORAGE-01: actual immutable private bytes](https://github.com/haytamAroui/caseproof/issues/38).** No private bucket/real object bridge, scanning/quarantine, row-level object access, signed URL threat tests, persistent object availability recovery, or verified external Storage transaction boundary.

**[DATA-01: durable kernel and authorized decisions](https://github.com/haytamAroui/caseproof/issues/39).** S2-008 proposal schema remains under `db/proposals/`. No installed representation/anchor/assessment/coverage/head migrations; no server-bound `/v2` approval route, authenticated human-attestation policy, or fully persisted case resolution.

**OPS-01: crash recovery and [MVP-01 end-to-end product](https://github.com/haytamAroui/caseproof/issues/40).** S2-010 leased durable workers/recovery unimplemented. The current `apps/api/main.py` is a development-only `/v1/claims` in-memory app trusting caller-provided `X-Tenant-Id`. `apps/web` does not exist. No real invoice/PO upload, extraction, issue inbox, review or export customer journey.

## Next work — prioritize an actual usable outcome

1. **Resolve SEC-01** with owner-approved merge enforcement; don't silently relax constitution C13/C25.
2. **Connect trusted Auth and data layer:** SEC-02 real signed-user integration + least-privilege app DB session, scoped positive and negative test evidence.
3. **Implement real private Vault:** STORAGE-01 private bucket adapter, proper intent/availability migration/ledger, verified byte read-back and automatic quarantine/reconciliation (no direct public URL).
4. **Finish the narrow persisted evidence/decision graph**, not another full suite of unrelated prototypes. Retain exact source/version/anchor/coverage/revision and audit semantics.
5. **One complete deterministic finance vertical slice:** signed-in user uploads invoice + PO, inspects exact cited source, sees discrepancy, records permitted human resolution and downloads evidence-linked report.
6. Validate customer time saved; only then implement optional agent orchestration, ERP/Peppol integrations and dispute expansion.

**Do not invent** real accounts, Storage buckets, approval status, CI checks, revenue or deployment. Update this file after each substantive change; mark human approval/production states separately.

## EI-001 — integrated extraction candidate runtime (feature branch)

Branch `feat/evidence-intelligence-v1`, based on main `6e8290faa638f3d1159add37e52a3558a870a7ba`. Adds Requesty-only HTTP integration, bounded discovery/extraction/repair strategies, independent entity boundaries, item-level quote and signal checks, rejected-candidate/conflict ledger, Kernel finding/link/coverage projection and disposable PostgreSQL checkpoints/events. [ADR 0012](adr/0012-evidence-intelligence-candidate-runtime.md) and [task/persistence review](tasks/EI-001.md) delimit scope. No Kernel changes, production migration, provider SDK, live model request, customer documents, approval route or deployment. Finance-first product remains; construction is an experimental second vocabulary only.

Local locked pytest (988 tests), Ruff, strict extraction mypy, architecture check, compilation and offline demo pass. Real PostgreSQL recovery tests are wired into CI, not locally executed; the final suite count and cloud results will be recorded on the combined PR. Live provider quality/cost baseline **not measured**. Production Auth/Vault authorization, rich parsers, reviewer UI/decisions, durable accepted evidence graph and independently verifiable dossier remain open gates.

## EI-002 — source-preserving document intake (stacked feature PR)

Branch `feat/document-intake-extraction`, based on PR #53 HEAD `26b2946e2775045eed5372b9c05a72372d2ddf85` (still open, not silently merged). Implements bounded Linux PDF/XML/MIME parsers, page/path/part mappings, checkpointed normalization and explicit failures, internal authorization+Vault composition, native XML scalar citations and deterministic UBL comparison. The shared extraction runtime is reused without Kernel changes. [ADR 0013](adr/0013-document-normalization-and-evaluation.md), [review/test specification](tasks/EI-002.md).

Four repository-owned synthetic files and an evaluator distinguish scripted safety checks from opt-in live Requesty measurement. Requesty credentials/model are **not configured here**; no live model accuracy or cost is claimed. No production route, canonical migration, mailbox, customer upload, OCR service or deployment. The MIME extension affects the internal/disposable Vault reference only. Production identity, malware scanning/isolation, review/decision and dossier gates remain open. Final local/CI evidence belongs to the combined PR.

## EI-003 — synthetic reviewer workflow and draft export (stacked feature PR)

Branch `feat/reviewer-resolution-pack`, based on open PR #54 HEAD `7cff7a211a72b348103b86e76c372c4283146d1a`; prerequisites remain unmerged. Adds frozen review recommendations, append-only correction/history, disposable atomic revision/audit/receipt repository, loopback-only synthetic workbench and bounded integrity-verifiable draft export. [ADR 0014](adr/0014-review-recommendations-and-draft-pack.md) and [data/access/test review](tasks/EI-003.md) preserve disabled approval authority. Kernel, canonical migration, installed grants and public production routes remain unchanged.

Default UI persistence is explicitly session memory; real PostgreSQL replay/restart/CAS/revocation/rollback and browser flows are wired into CI. Local browser installation was unavailable; cloud runner's installed Chrome will run the browser checks. Refero subscription is inactive; design extends the existing prototype using bundled craft guidance. No real human attestation, production Auth/DB/Vault or legal/payment approval is claimed. All verification outcomes are recorded on the PR after actual execution.

## EI-004 — internal leased extraction execution (stacked feature PR)

Branch `feat/durable-extraction-worker`, based on open #55 HEAD `8ebcd60fd342ae09b9276520b2bafce47c62cee6`. Adds immutable source-referenced job plans, internal authenticated scheduling, disposable PostgreSQL database-time leases/heartbeats/attempts/events, transaction-bound checkpoint fencing, bounded retry/cancellation and source-to-review worker composition. [ADR 0015](adr/0015-leased-document-jobs.md), [data/test review](tasks/EI-004.md). Received replies replay under the original run; unresolved dispatches never retry automatically. Execution completion cannot approve evidence or legal/payment decisions.

SQL remains disposable, routes unmounted, sources synthetic and inference scripted in tests. No provider/routing/dependency changes, live Requesty call, Kernel change, production migration, role grant or worker deployment. This is a recovery reference; real service identity/delegation, least-privilege Auth/DB, production Storage, accepted evidence/decision graph, external-effects outbox and customer outcome gates remain open. CI verification results will be recorded on the combined PR.


**M0 language correction in PR #62:** NL / FR / EN are the equal product-language targets for UI, search/workflow and supported output; M0 v1 fixtures remain historical, while M0 v2 adds English and trilingual examples. This does not establish production translations, retrieval quality or approved benchmark results.


## Word synthetic spike (development branch)

The Word development branch has progressed beyond its original read-only spike; the current synthetic search, citation, download and authentication candidates are described below. It has not been tested in a Word host and does not close M3 or the M1/M2 live integration gates. See `apps/word_addin/README.md`.


## M2 bounded source preview candidate

An opt-in internal check-store adapter can derive PDF/DOCX previews from verified original bytes using the existing bounded parser and evidence indexer. The default remains unchanged; DOCX physical pages remain unverified and parser warnings retain partial coverage. This is disposable engineering only, not signed-user/live database, OCR, Word, or M1/M2 release acceptance. No customer data or production routes are authorized.


## M3 private lexical search candidate

An unmounted search adapter reads only a version-pinned M2 private-matter bundle, checks signed identity and both draft-check and evidence-read grants, returns bounded literal matches with representation and source identifiers, and revalidates access and snapshot before return. Partial or missing source coverage is disclosed. It is connected to the synthetic Word development pane, not to a production route or live-authenticated matter. Search tests use synthetic identities.


## M3 synthetic Word citation development

The development task pane and localhost-only synthetic API support selecting a unique body passage, searching a synthetic matter, viewing a bounded text excerpt and inserting a uniquely mapped exhibit citation. The synthetic client rechecks source search and document body/selection before insertion, and blocks retries following an unknown outcome. Automated tests use a mocked Word host; no real Office host, save/reopen, coauthoring, tracked changes, actual signed session, private source viewer or authorized live edit has been verified. Body-text comparison is not atomic compare-and-swap. M3 remains open and confidential documents must not be used.


## Word authentication adaptation candidate

The PR adds a Vaquill-derived Office dialog/PKCE adapter, public-key-only Supabase SDK composition with in-memory storage, an opt-in development sign-in form, and a bounded DOCX slice reader. It has mock Office tests and a real SDK PKCE URL test, not a real Word host or real Supabase login. The API remains unmounted and live citation editing is disabled; see `apps/word_addin/README.md`.


## M1–M3 loopback composition candidate

A loopback-only injected development app combines versioned factual checking, matter-scoped evidence search, and guarded original-byte download. Original reads require evidence permission, source inclusion, matching SHA-256 and a second authorization/snapshot check; responses are attachments and no-store. Disposable PostgreSQL acceptance uses synthetic identity and an owner fixture; it does not prove least-privilege live RLS, private Supabase Storage, real session revocation, Word-host behavior or customer readiness. The API is not mounted in `main.py`.

## Genuine signed Auth to disposable RLS receipt

[Manual run 40531773053](https://github.com/haytamAroui/caseproof/actions/runs/40531773053) passed on main commit `866158a51c780dad88a63d48769282f96addfc8a`: three real Supabase dev identities were signed in and tested against a least-privilege disposable PostgreSQL RLS fixture; the job reported cleanup of all ephemeral identities. On 2026-10-27, at the owner's explicit direction, migration `20261027160745_caseproof_m1_dev_atomic_private_grants` was applied to the empty `caseproof-dev` project. Read-only inspection confirmed the M1 grant table, RLS enabled, and replacement of legacy case/document policies. Independent human security review has not been verified. The M2 brief tables are absent. This does not test real signed users against the live database, live Storage, the PR branch's M2 composition, or an Office host.

### PR #147 corrective follow-up (31 October 2026; feature branch)

Removed word-overlap exemptions: regional comparisons without geometry still gate
all references on their page. Added serialized comparison-presence, coverage and
not-assessed/conflict/unreliable fields, plus explicit engine/rules versions.
Regression coverage includes unrelated regional conflicts and clean common-word
regions with unknown coverage. Full web rendering, geometry-based scoping and live
adapter/crop acceptance remain open. Cloud CI must pass on the new head before
merge; prior-head green results do not verify this correction.

## Product planning refinement — 31 October 2026 (PR #141)

The [detailed direction update](PRODUCT_DEFINITION_2026-10-31.md) is a proposed acceptance plan, not delivered software. PR #146 (`bcd52ff`) and #147 (`ff154a1`) were open at review with passing independent CI; integration is not proven. Preserve #146 regional anchors while assessing #147 normalization/coverage/versioning fixes; no merge or supersession is claimed. Local packaging, new exports, qualified signatures and German remain conditional work. No confidential-client authorization or paid validation follows from documentation.


## PR #148 read-only MCP contract correction — 31 October 2026

The optional [MCP contract ADR 0021](adr/0021-readonly-mcp-adapter-contract.md)
reserves representation ADR 0020 and remains a proposal. Two read-only tools share
headless HTTP discovery/export functions. Host identity stays outside model inputs;
unknown/write arguments are rejected before access. Content release defaults denied
until the host separately approves the exact matter/destination for each call.
Detached listing copies prevent consumers from mutating the dispatch schemas.
No MCP server, remote-model egress, installer, live acceptance or client-data approval
is delivered. Local and cloud verification evidence belongs to the current PR head.
### #146/#147 combined branch review — 31 October 2026

#146 now includes #147's explicit serialized coverage and rules version while
retaining validated raw-offset regional selection. Unlocated comparisons remain
page gates, including no-quotation references. Source/text binding is checked
before offsets can exempt a disjoint region. Shared ligature/soft-hyphen folding
retains original codepoint ranges. This is a branch integration, not a main merge
or customer release. The existing signout cancellation regression is retained.
Current-head cloud/live receipts must supersede historical run references.


## Executable verification contract/report candidate — 31 October 2026

Feature `feat/verification-contract-report` implements the signed dossier gaps in
P3-01..04, structured/hidden DOCX omission accounting, translation/OCR coexistence,
identity abstention and consistent frozen web/JSON/Markdown/DOCX output. See
[matrix](m3/VERIFICATION_CONTRACT_ACCEPTANCE.md). No migration, confidential input,
new provider, local installer, Word host or legal/practitioner approval. Exact tests
and cloud/live receipts belong to the PR; no complete M3/M4 release claim.

## 1 November 2026 — dossier correction and recheck candidate (PR #159)

The canonical dossier service now includes source/snapshot-bound DOCX correction
preview, two-phase reserve/upload/fresh-readback/activate commit, idempotent retry
and canonical recheck of the active new draft. The SQL implementation remains a
**reviewed-installation proposal**, not a live deployment. Pending revisions leave
the current manifest/signature unchanged; activation switches the manifest and
invalidates dependent confirmation/review snapshots without changing originals.

The dedicated disposable PostgreSQL workflow passed on candidate `58eb209`,
including concurrent activation, competing children, audit rollback, fresh report
persistence and revoked access. Subsequent hardening binds reservations to the
exact parent snapshot and reference; use the PR's current commit CI as authority.
Local full-suite evidence before that hardening: 1,880 passed, four skipped.

The protected dossier workflow has opt-in correction/replay/recheck/cold-restart
acceptance with pre-upload cleanup registration. It remains unexecuted against
shared staging because the proposed schema has not been independently reviewed
and installed. No migration was applied and no client data was processed. Formal
M1/M2 acceptance, representative accuracy and independent security/legal approval
remain open. See `docs/m1/DRAFT_REVISION_PERSISTENCE_DESIGN.md` and PR #159.

### Development installation update

At the owner's explicit request, connected Supabase MCP applied the exact draft
revision SQL as `20261031234906` to `caseproof-dev`. Post-install grants, RLS and
search_path were inspected; no revision data was created. This supersedes the
uninstalled-schema status above. See `docs/m1/LIVE_DRAFT_REVISION_INSTALLATION.md`.
Genuine signed correction/recheck acceptance remains pending.

## 1 November — merged M0–M2 baseline and closure follow-up

PR #159 merged as `05576ba`. Protected live run 41258188700 passed the genuine-user
correction/recheck, cold restart, revocation and zero-residual cleanup gates on code
`9c587f4`; failed-fixture recovery 41258188830 passed. Installed revision/cleanup
migrations and those receipts supersede earlier pending-install/run entries.
See `docs/m0/M0_M2_CLOSURE_STATUS_2026-11-01.md` for remaining actual evidence gates.
The follow-up detects English Exhibit labels as explicitly unsupported review
items and adds a completeness validator for genuine independent submissions.
Neither change fabricates outside assessments or grants confidential-client use.

## 1 November — PR #161 deployment evidence and model-note controls

Branch `docs/deployment-retention-model-authority` adds ADR 0025, four explicit
mode evidence/retention records, a completeness CLI, separate immutable model notes
and synthetic namespace capture CI. Model annotations cannot supply canonical
finding or human-decision fields; no provider, persistence or production route is
introduced. Hashes, references, verdicts and timing are treated as potentially
sensitive. Backup expiry/restore/re-deletion and legal holds require evidence.

Local locked suite: 1,899 passed, four live gates skipped; added profile regression
also passes. Cloud capture [41279255356](https://github.com/haytamAroui/caseproof/actions/runs/41279255356)
passed actual bitmap OCR, missing-input failure/retry, loopback control and denied
outbound probe with no captured non-loopback traffic. This is OCR-namespace-only,
not full deployment-mode approval. Final-head checks remain authoritative on the PR.
Named owners, configured per-mode retention, whole-deployment capture and independent
SEC-01–16 approval remain open. No database, production or customer data changes.

## 1 November — structured frontend foundation candidate

Branch `feat/frontend-foundation` adds the unmounted `frontend` React/Vite/TypeScript client, ADR 0026, Python-generated response projection/schema/types, precompiled CSP-compatible runtime validation, feature import checks and session cancellation/cache clearing. First screen is read-only exact-snapshot inspection. No viewer engine, matter intake, review writes, login provider or production route is connected. Existing temporary clients remain regression references. Cloud CI and browser artifacts on the PR are authoritative; full M3/M4 and confidential-client acceptance remain open.

### UI foundation specification consolidation

`frontend/BLUEPRINT.md` is the single maintained frontend execution and acceptance entry point. It incorporates corrected workspace UX while preserving generated backend contracts, authorized durable decisions, honest uncertainty, measured viewer geometry and deployment evidence. Client guidance files and ADR 0026 link to it; no new UI capability or acceptance is claimed by this documentation consolidation.

## M3 rules and CI candidate — 1 November 2026

`feat/m3-rules` extends the single frontend blueprint with database ownership and product philosophy, executable design/security policy, stronger AST boundaries and deliberate negative controls. It does not add a database schema, viewer or signed-user UI feature. CI evidence on the PR determines acceptance.

## M3 permitted-matter navigation candidate — 1 November 2026

Branch `feat/m3-permitted-matter-navigation` starts P02/F1 after merged #163.
The real frontend now consumes a generated, bounded read-only catalog projection
over the existing signed matter adapter, only in the loopback development
composition. Matter selection pre-fills the preserved-report form; brief/snapshot
identifiers remain required. No migration, production mount, auth-provider change
or client data. See [frontend blueprint increment](../frontend/BLUEPRINT.md#20-m3-implementation-increment--permitted-matter-navigation).

Local affected Python tests: 15 passed; frontend unit/architecture tests: 29 passed;
lint, typing, generated-contract checks, policy and production build passed.
Local Playwright could not launch because Chromium is absent and its download
returned an invalid archive. Cloud/browser results are pending at this entry.
F1 genuine signed-browser acceptance and the remaining F2–F6 flows stay open.

## Complete F1 candidate — 1 November 2026

Branch `feat/f1-signed-workspace` implements same-origin existing-provider password
sign-in, verified access expiry, memory-only host, provider sign-out, idle expiry and
masked-read clearing, explicit loopback static runtime and authorized frozen-report
keyset navigation. ADR 0027 and frontend blueprint section 21 define scope,
authority, proposal/rollback and acceptance. No new provider, client database SDK,
refresh-token persistence, production mount or client data.

A read-only catalog function proposal over the existing membership/grants/snapshots
is prepared; it is not installed at this entry. Synthetic browser and actual
disposable PostgreSQL checks are added. Protected genuine signed browser workflow
requires native dev function installation and the exact reviewed protected branch;
it reuses registered synthetic fixtures and finally zero-residual cleanup. No live
F1 completion or independent security review is claimed before actual receipts.
