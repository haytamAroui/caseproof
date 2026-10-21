# CaseProof execution roadmap — vertical slices and explicit gates

**Planning:** Solo founder + coding agents; time estimates are relative. Every completed task requires implementation, tests, evidence, and decision-record updates.

## Gate 0 — Commercial, legal, and privacy validation
| ID | Implementation | Acceptance |
|---|---|---|
| G0-01 | Interview 8–12 Belgian accountants, recovery professionals and commercial lawyers | At least five anonymized workflows mapped |
| G0-02 | Specify v1: factual B2B disputed-invoice dossier, excluding automated procedural decisions | Reviewed product boundaries and exclusion matrix |
| G0-03 | Get Belgian legal review for IOS, debt rules, interests, terminology | Source-backed legal assumptions, unresolved questions listed |
| G0-04 | DPA, processor inventory, retention policy and threat model | Approval for pilot data handling |
| G0-05 | Create 20–30 synthetic or de-identified gold cases | Adjudicated expected outcomes, adversarial counterexamples |

## Phase 1 — Repository, architecture and CI
- P1-01: Configure Python lint/type/test tools, lockfile, CI, security scanning, pre-commit. **Done:** clean checkout passes a single `make check` command.
- P1-02: Create hexagonal bounded modules with import-lint enforcement. **Done:** domain layer cannot import FastAPI, Supabase, model SDKs.
- P1-03: Dedicated EU-hosted database and private object storage after vendor review. **Done:** dev/prod isolation, safe secrets, tenant tests.
- P1-04: Approve ADRs for tenancy, queue, evidence verification, model routing and money precision.

## Phase 2 — Secure intake and immutable sources
- P2-01: Tenant and actor capabilities, strict repository authorization and database RLS. **Done:** cross-tenant read/write/upload/download denied.
- P2-02: Case intake, file quarantine, type sniffing, caps, malware controls, immutable SHA-256. **Done:** malicious/oversized/replayed input tests.
- P2-03: Immutable document versions and parse lineage with source offsets and page anchors. **Done:** reproduce source references from frozen bytes.
- P2-04: PDF, DOCX and text parsers. **Done:** fixtures for scans, rotations, dates, tables, encoding and parser errors.

## Phase 3 — Evidence extraction and verification
- P3-01: Reuse minimal source-block, offset and quote-verification algorithms from AZComply; isolate AI Act types. **Done:** cross-product regression fixtures pass.
- P3-02: Provider-neutral EvidenceExtractor port, structured output, schema/version metadata, cost caps. **Done:** model timeouts, malformed JSON, injection, fake-source tests.
- P3-03: Verify quotations independently of factual truth. **Done:** fabricated quote can never become verified.
- P3-04: Benchmark whole-context and segmented extraction on gold data. **Done:** record critical recall, objection omissions, unsupported quotes, latency and costs.

## Phase 4 — Reconciliation and finance
- P4-01: Match parties, invoices, purchase orders, delivery, payments, contracts. **Done:** similar-party and duplicate adversarial tests.
- P4-02: Evidence/assertion relations support, contradict, qualify, uncertain. **Done:** conflicting source claims preserved, not overwritten.
- P4-03: Decimal finance reconciliation, VAT, credits, partial payment, rounding. **Done:** property-based and golden calculations.
- P4-04: Missing-information and exception detection. **Done:** NOT_PROVIDED never means DOES_NOT_EXIST.

## Phase 5 — Conditional legal rule packs
- P5-01: Versioned `RulePack` interface with jurisdiction, applicability, effective date, normative reference, review/approval. **Done:** missing legal predicate yields indeterminate.
- P5-02: Conditional interest/fee calculation using approved source tables; no hard-coded universal rates, no blanket 60-day conclusions. **Done:** boundary-date, rate-change and contested-term tests.
- P5-03: Write-ahead audit with linked provenance and reviewer authority. **Done:** failure of required audit persistence blocks governed completion.

## Phase 6 — Durable workflow, review and dossier
- P6-01: Transactional Postgres jobs, leases, heartbeats, checkpoints, retry and dead-letter. **Done:** worker-kill/retry creates no duplicated charge or dossier.
- P6-02: Typed factual dossier: chronology, documentary support and conflicts, reconciliation, gaps and caveats. **Done:** every material statement has source/version provenance.
- P6-03: Deterministic ReportLab PDF rendering and verified source index. **Done:** stable golden outputs and reproducible snapshots.
- P6-04: Exception-based approval queue with actor capability, reason, freshness and transaction boundaries. **Done:** stale/unauthorized approvals denied.

## Phase 7 — Paid pilot
- P7-01: Minimal internal intake and review UI. **Done:** five cases processed with review timings and corrections logged.
- P7-02: Test 5–10 permitted real-world cases with professional users. **Done:** recorded outcomes, repeated-use intent, serious error review.
- P7-03: Measure cost, critical missed objections, reviewer minutes and liability. **Done:** explicit go/no-go memo.

## Phase 8 — Conditional SaaS productization
- P8-01: Accessible case dashboard, source viewer, exception queue, reviewer history.
- P8-02: Organization invitations, role-based permissions, billing ledger, retention and export.
- P8-03: SLOs, logging, alerting, restore drills and incident runbooks.
- P8-04: Public API/MCP or other integrations **only** on proven partner demand.

## Phase 9 — Expansion
Add jurisdiction packs only with local legal review. Enable retrieval indexing only after measurements show direct-source reading does not meet case-size requirements. Extract services only when scaling and ownership data support doing so.

## Quality and stop/go rules
- Zero known cross-tenant disclosures, unsupported source citations in approved dossiers or unapproved legal actions.
- Record objection detection and critical assertion recall by scenario, not one confidence percentage.
- Track end-to-end processing time and human review time separately.
- Never claim production-readiness from passing happy-path tests alone.

## Definition of Done
Each issue requires: intent, ADR impact, code, success/failure/security tests, tenant review, observability, documentation, test commands/output, independent review for consequential changes, and explicit acceptance.
