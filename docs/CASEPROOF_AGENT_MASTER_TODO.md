# CaseProof — Agent Master Implementation TODO v1.1

**Date:** 3 November 2026, Europe/Brussels.  
**Repository baseline:** `2a5420db21c010c39a27fc3d49fd05b2585d0f88` (`main`, plan merged by PR #179).  
**Purpose:** One operational task list combining the frontend blueprint, workflow v3.1 and implementation/reuse plan v1.2. Read this document to select and execute routine work. Source links are for provenance and decisions, not a requirement to reread three documents before every task.  
**Suggested repository location:** `docs/CASEPROOF_AGENT_MASTER_TODO.md`.  
**Status:** Proposed execution backlog. This file creates no production approval, reviewer sign-off, new API or completed milestone.

## 5 November 2026 — Engineering reconciliation

| Area | Verified evidence | Open acceptance |
| --- | --- | --- |
| P2 reviewer workspace | [PR #189](https://github.com/haytamAroui/caseproof/pull/189) merged. Its [final-head signed F4 run](https://github.com/haytamAroui/caseproof/actions/runs/41910465683) passed. The PR also added the T52 mixed-size PDF and non-zero CropBox regression. | Independent authorization review, representative corpus and manual accessibility. |
| P3 / T65 table-cell correction | The changes from [PR #190](https://github.com/haytamAroui/caseproof/pull/190) landed through [PR #191](https://github.com/haytamAroui/caseproof/pull/191) at [`b0e500fc`](https://github.com/haytamAroui/caseproof/commit/b0e500fccf77a875bd4d10e61cd9b09f1d91dff7). The [signed table-cell run](https://github.com/haytamAroui/caseproof/actions/runs/41916090652) passed on the original PR #190 head. PR #190 was closed as superseded. | Independent authorization and provenance review and actual desktop Word compatibility. |
| P3 document-wide DOCX editing | Dev migrations `20261105081249` and `20261105100916` are applied. The [signed Phase A/B run](https://github.com/haytamAroui/caseproof/actions/runs/42008220354) passed activation, recheck, revocation, and cleanup. | Independent security and actual document-host compatibility remain pending with the pilot partner. |
| T70 dev migration reconciliation | [Supabase migration history](https://supabase.com/dashboard/project/ldwmocpxwskvhoojndrd/database/migrations) records the signed page worker as `20261105104752`. The recorded SQL matches [the repository migration](https://github.com/haytamAroui/caseproof/blob/b0e500fccf77a875bd4d10e61cd9b09f1d91dff7/supabase/migrations/20261031112127_signed_page_worker.sql), version `20261031112127`. All three tables have RLS enabled and no direct anonymous or authenticated grants. The catalog audit found no additional approved dev SQL to apply. | Migration history has timestamp drift. The authenticated security-definer RPC still needs independent review and live signed worker acceptance. |
| P6 pilot readiness | T77 signed engineering acceptance passed for its recorded scope. | T61 document hosts, T70 independent security, T72 dependency risk, T73 privacy/egress, T74 operational Supabase restore, T75 manual accessibility, T76 rights-cleared corpus, T78 practitioner evidence and T79 pilot approval remain open. |

> **4 Nov 2026 P5/P6 engineering evidence:** [PR #185](https://github.com/haytamAroui/caseproof/pull/185) implements readable DOCX export, frozen reference-drift explanations, real **LibreOffice Writer** synthetic document round-trip, disposable PostgreSQL 17 restore/erasure-replay, production-vs-dev npm audit, visible non-offline Supabase intake disclosure, and automated multilingual accessibility checks. The [dated acceptance matrix](pilot/P5_P6_ACCEPTANCE_MATRIX.md) identifies individual CI run receipts. **11 npm moderate advisories affect dev tooling, not shipped production dependencies, and remain subject to owner review.** T61 Word, T70 independent security, T73 actual privacy/egress approval, T74 real operational restore, T75 manual AT, T76 representative corpus, T78 practitioner results and T79 pilot declaration are **NOT DONE**. Synthetic success does not waive the real pilot gates.

## 0. P5/P6 task truth after engineering merge — 4 November 2026

**Source:** [merged PR #185](https://github.com/haytamAroui/caseproof/pull/185), squash merge `b162a5f7a08975949a32671cbea774b7f0a7bb09`, tested PR head `3c6058a054ffd5172413cba5b90eb9af4bb44586`. At that head, 19 workflows succeeded, four narrower live workflows were intentionally skipped, none failed. The final combined signed F6 passed and covered F3/F4/F5 journeys, but skipped independent jobs are not counted as passed. [P5/P6 evidence matrix](pilot/P5_P6_ACCEPTANCE_MATRIX.md) is the evidence ledger; [PR #186](https://github.com/haytamAroui/caseproof/pull/186) reconciles task records and makes P6 workflow branch-neutral.

| Task | Current evidence-based state | Still required to close |
| --- | --- | --- |
| T15 / T60 readable DOCX | Engineering implemented; [kernel final-head run](https://github.com/haytamAroui/caseproof/actions/runs/41829163374); [P6 host/restore/supply-chain acceptance](https://github.com/haytamAroui/caseproof/actions/runs/41829163280) | Independent code review and supported-host sign-off |
| T47 / T48 / T66 finding drift | Engineering implemented; [frontend final-head run](https://github.com/haytamAroui/caseproof/actions/runs/41829163384) | Independent review; uncertain results never transfer approval |
| T61 document hosts | LibreOffice synthetic round-trip passed | Actual desktop Word and manual formatting inspection |
| T70 live security | Dev catalog/adviser inspected | Independent review of 15 privileged RPCs, grants/roles and auth settings |
| T72 dependencies | Production graph 0 known advisories; dev graph 11 moderate | Patch or explicit accountable risk disposition |
| T73 privacy and egress | Accurate intake disclosure; synthetic privacy contracts | Deployment-specific providers, regions, retention, capture and approval |
| T74 restore | Actual disposable PostgreSQL restore + synthetic erasure replay | Authorized operational Supabase backup/retention restore proof |
| T75 accessibility | Automated keyboard/axe/locale/resize checks | Manual screen-reader, browser and WCAG 2.2 AA acceptance |
| T76 corpus | Author-supplied synthetic NL/FR/EN fixtures | Rights-cleared representative data and independent labels |
| T77 final signed E2E | **Passed** [signed F6 final-head run](https://github.com/haytamAroui/caseproof/actions/runs/41829162860), exact final PR head and zero-residual teardown | None for the bounded T77 engineering check; pilot gates are independent |
| T78 practitioner evidence | Written protocol only | Two independent reviewers, authorized dossiers, timed/comparative observations |
| T79 pilot declaration | **Blocked**, no approval | Signed owner decisions after T61/T70/T72–T78 are accepted |

**Closure rule:** A green CI job or an agent-authored status note is not human sign-off. Keep external gates unchecked until actual evidence and accountable reviewer/owner decisions exist. T62–T65 remain conditional, not silently required or accepted.

## 1. Agent start here

1. Read applicable `AGENTS.md` and repository constitutional rules. Read this task list once, then the selected task and actual relevant code/tests. Check current branch, working tree, upstream head and exact installed contracts. Preserve unrelated changes.
2. Select the first unblocked task in section 3. Continue through a complete implementation bundle: backend, generated contracts, UI, recovery, tests and evidence as applicable. Do not repeatedly stop after tiny partial changes.
3. Reuse existing services, endpoint paths and features. Baseline F0–F6 implementation exists. Repair/extend it rather than rebuild it from a stale OPEN status in an older document.
4. Each task states scope, dependencies and acceptance. A task with local code but incomplete review/CI remains IN_PROGRESS. A plan checkbox is never evidence of working behavior.
5. Reopen source documents only when this consolidation is ambiguous, an underlying contract changed, or a material decision requires its exact text. Resolve conflicts in favor of constitutional/accepted ADR authority, frontend architecture rules and actual versioned contracts. Amend this list and affected authoritative document together.
6. Preserve a stable task ID and update its evidence record. Finish relevant checks, review and complete PR content before declaring merge readiness. Follow protected-branch rules. Production promotion and confidential customer data require their own approvals.

### Task state and closure

Use `TODO`, `IN_PROGRESS`, `BLOCKED_DECISION`, `VERIFY_EXISTING`, `DONE` or `CONDITIONAL`. Markdown checkboxes below remain unchecked until task evidence is recorded. `VERIFY_EXISTING` means inspect existing code/evidence and close a demonstrated gap; it does not instruct a rewrite. `CONDITIONAL` includes a decision/experiment task now, while capability adoption remains gated.

A completed task record contains:

```text
task_id:
status:
owner_or_reviewer: actual person/role acceptance; never invented
commit_and_pr:
changed_paths_and_contracts:
checks_and_run_links:
observed_results:
remaining_limits_and_gates:
rollback:
next_task:
```

### Current local work — preserve and finish

At generation time branch `feat/pilot-hardening` contains uncommitted changes in `docx_region_inventory.py`, `docx_text_regions.py`, `dossier_journey.py`, `dossier_export_release.py` and `tests/test_docx_region_inventory.py`. They start T10–T13. A focused command reported **20 passing tests** for inventory, reference discovery and F6 export/transport regressions. This is historical local evidence from the active branch, not a commit, complete bundle, fresh execution in this documentation task or cloud acceptance. Add missing malformed-response/manifest regressions and inspect exception/type handling before shipping.

## 2. Governing implementation rules — included here

### Product and authority

- Deliver the authenticated web journey: authorized matter → preserved DOCX/inventory/exhibits → inventory and page confirmation → deterministic report → source inspection → human review → optional correction and mandatory recheck → reviewed release → exact historical reopen.
- Python application/domain services own evidence verification, authorization, workflow, persisted review and release. React displays validated server results. No parallel engine/store/ledger in Word, an editing tool or the browser.
- Preserve separate identity, page mapping, fidelity and human support; disclose extraction/visual coverage independently. No overall green/verified document badge. A quote match establishes neither legal support nor authenticity.
- Original bytes remain immutable. A corrected draft and an annotated report are different derivatives. Historical sources, snapshots, reviews and releases retain their original identities.
- English Exhibit notation remains explicitly unsupported where that is the installed parser behavior. NL/FR/EN UI does not establish equal detection support. Do not label unsupported notices as successful matches.

### Canonical states and contracts

```text
identity: not_assessed | not_in_inventory | source_missing | ambiguous | resolved
page_mapping: mapped | unmapped | conflicting
fidelity: not_assessed | ocr_unreliable | representation_conflict |
          translation_review_required | multiple_matches | exact_match | quote_not_found
support: not_assessed | supported | qualified | contradicted
```

`not_in_inventory` requires confirmed-complete inventory. Source absence, mapping ambiguity, OCR uncertainty and semantic support stay distinct. Do not add tolerance of ±2 pages. Guard amounts, dates, currency, negation and accents; only existing calibrated normalization may equate text. Zero coordinates are valid; null is not zero. Physical PDF page, printed label and bundle page are separate spaces; Roman labels remain strings.

Requests retain appropriate strictness; `DossierView`/`FindingView` intentionally permit response extensions. Consume Python-generated JSON Schema → TypeScript/AJV and reject unknown consumed states safely. Do not hand-edit generated types. Explanatory correspondence/guarded-token metadata does not become a canonical verdict or automatic review lineage.

### Stack and module ownership

Use the existing Vite static SPA, React/TypeScript, React Router, TanStack Query, PDF.js adapter and canonical CSS tokens. `package.json`, lockfiles and policy checks control installed versions. The checked baseline uses React 19, Vite 8, TypeScript 6, Router 8, Query 5 and Node 24. Use compatible stable updates after review; do not copy older Router 7/Tailwind/shadcn/diff-library proposals as installed facts.

| Owner | Responsibility / dependency rule |
|---|---|
| `frontend/src/app` | Composition, routes, providers, cross-feature coordination and session lifecycle |
| `features/matters`, `intake`, `verification`, `evidence`, `review`, `corrections`, `exports` | Real feature behavior; expose public `index.ts`; no imports of another feature's internals or app |
| `shared/api` | Generated contracts, validation, bounded authenticated transport |
| `shared/session` | Memory credentials, cancellation/generation fences, query and resource cleanup |
| `shared/ui` / theme | Accessible controls, shared intent/status patterns, runtime design tokens |
| Application/domain | Business policy and evidence authority; kernel remains pure and inward-facing |

Do not introduce empty scaffolding, another viewer stack, global state bus, heavy table library or generic framework without a demonstrated need. No direct DB calls/raw fetch shortcuts from feature screens.

### Reads, writes and recovery

Authorize every sensitive operation for actor, organization/matter, version and snapshot. Validate response bindings before rendering. Bound time and size, check content type, reject redirects where required, support cancellation, and discard late body/status/render results after session/source/finding change.

On expiry/signout or applicable denied-access responses: abort reads, invalidate the session generation, clear private caches/forms, revoke object URLs, terminate rendering, and remove private views. Avoid confidential content in URLs, logs, analytics, titles and persistent browser/Office storage. Previously downloaded bytes cannot be recalled by clearing app memory.

Each consequential write uses one stable operation ID for one immutable payload. Disable duplicates; classify pending, saved, rejected, stale and unknown outcome. Saved/released requires a backend receipt. Reconcile unknown outcomes by the existing authorized status/readback contract; never issue a blind new operation or automatic mutation retry. Do not treat HTTP 409 as success.

Correction preserves the existing review-receipt check → current snapshot/source → reserve → derivative put-once → authorized exact hash readback → activation → mandatory recheck flow. No silent decision transfer and no stale-draft recheck. Release must recompute policy at commit and validate HMAC/manifest/artifact digest and bytes at read/replay.

### Viewer, design and accessibility

Use preserved pixels with separately labeled extracted/OCR text and provenance. Geometry carries original/representation hashes, physical page, space/origin/units, bounds, rotation and CropBox/MediaBox. Transform using the actual viewport, CSS geometry and device-pixel-ratio separately; percentage coordinates alone are insufficient. No fabricated highlight for unresolved anchors. Browser DOCX is derived and cannot promise Word pagination.

Evidence and uncertainty lead the layout. Use readable local typography, stable geometry, adjustable reading space and shared tokens. Stack gracefully at narrow widths; provide keyboard pane resizing and plain-text/side-by-side alternatives. Keep detailed hashes/provenance in accessible disclosures rather than crowding the primary reading flow.

Target WCAG 2.2 AA: native semantics, real labels, visible focus, inline errors/first-invalid focus, contrast, accessible modal focus/Escape/restore, no color/hover/drag-only meaning. Review pending/unknown/save feedback must be announced. J/K/arrows, Space and correction shortcuts are discoverable and scoped; ignore editable targets and IME; shortcuts cannot silently approve. Test long NL/FR/EN copy, narrow layout, 200% zoom, forced colors and reduced motion. Automated axe checks do not replace manual assessment.

### Hostile files and deployment

Keep bounded backend and browser parsing, private originals, strict same-origin CSP and pinned local scripts/workers/fonts. No CDN/remote fonts/analytics, unsafe-inline/eval, wildcard remote sources, service worker or persistent recovery cache introduced casually. Workers and scratch directories are not security sandboxes. Check actual response headers, not only a config file. No claim of zero egress, professional-secrecy compliance or production readiness without measured deployment evidence.

SQL/security-sensitive changes require exact grant/RLS/revocation and independent review. For live CaseProof development DB work use the configured Supabase connection, pinned project `ldwmocpxwskvhoojndrd`; do not introduce admin DSN secrets into CI. Separately approved migrations require repo/deployed-version reconciliation. Synthetic/disposable SQL claims do not establish actual signed-user live-RLS acceptance.

## 3. Work order and decisions

| Order | Bundle | Tasks | Required outcome |
|---|---|---|---|
| 1 | Factual records and hardening | T01–T09, T10–T17 | Accurate evidence; controlled parser/service failures |
| 2 | Capacity through the full journey | T20–T29 | Measured, approved envelope; signed end-to-end recovery |
| 3 | Release preflight and navigation | T30–T35 | Eligibility/completeness/coverage explained and enforced |
| 4 | Correction, comparison and coverage | T40–T49, T50–T57 | Safe supported editing, contextual preview and explained recheck |
| 5 | Useful DOCX and optional engine capability | T60–T66 | Readable validated output; experiments have explicit decisions |
| Alongside | Operational / practitioner acceptance | T70–T79 | Evidence, real owners and pilot gates |
| Conditional | Word/MCP/model/redaction extensions | T80–T85 | Decisions made; features implemented only if activated |

The order above is recommended delivery sequencing, not a dependency between every bundle. Task-level dependencies govern execution: T20 measurements precede D01/T21; release work follows D02/T30; correction behavior follows D03/T40; readable output follows T15/D06. Preserve downstream implementation/test dependencies. Candidate capacity profiles may be benchmarked while D01 is pending, but unmeasured provisional numbers must not become the supported production policy.

Do not impose an eighteen-PR sequence. Implement coherent backend/frontend bundles with meaningful review boundaries. Begin security inspection, measurements, corpus gathering and practitioner discovery immediately. They do not wait for all UI work.

| Decision | Who / when | Required recorded choice | Safe work while pending |
|---|---|---|---|
| D01 Capacity | Product/engineering; T21 | Exhibit count, bytes, pages, visual budget, job/output/browser limits using T20 measurements | Existing-boundary hardening and benchmark candidates |
| D02 Release policy | Product; T30 | Partial releases allowed for which types; zero findings/decisions; meaning of complete | Inspect existing policy and test existing behavior |
| D03 Revision view | Engineering/product; T40 | One extraction/resolver/writer rule for tracked changes outside target | Isolated fixtures; refuse target revisions |
| D04 Tracked output | Practitioners/product; T64 | Whether pilot requires native Word tracked changes | Readable appendix and Python D1/D2 work |
| D05 Encoding | Engineering; T10 | Supported XML encodings, controlled UTF-32 rejection if needed | Safe-parser regression tests |
| D06 Invalid characters | Engineering/product; T60 | Controlled refusal or visible substitution with disclosure | Preserve original bytes; ordinary report formatting |

These are substantive decisions, not permission gates for every routine edit. Use provisional ADR numbering only after checking the current index. Existing policy remains active until amended. Do not invent a choice merely to make tests pass.

## 4. Existing F0–F6 and workflow coverage

F0–F6 are merged implementation at the baseline, with independent product/deployment gates still open. Older planning tables and receipts retain their dates. Do not rebuild them or mark all requirements accepted simply because they merged.

| Stage | Existing path / owner | What the agent must preserve and verify | Follow-up tasks |
|---|---|---|---|
| S0 / F1 | Auth host, session/shared API, matters catalog | Real signed access, permitted matter list/create entry, masked denial, memory-only recovery, late-response fences | T02, T50, T55, T73 |
| S1 / F3 | `apps/api/workspace_intake.py`, intake feature | Whole-intake preflight; reserve/upload/readback; immutable source versions; stable recovery | T20–T23, T28 |
| S2 / F2 | Existing OCR/page jobs, geometry, evidence viewer | Correct original/crop/hash/page provenance; rotations/CropBox/zero; honest unavailable OCR | T10–T11, T24–T26, T52 |
| S3 / F3 | Inventory/page confirmation models and screen | Complete-inventory declaration; four labeled source selectors in current fixture; printed/PDF/bundle states | T23, T51 |
| S4 | DOCX discovery and regional extraction | Coverage denominator, unsupported regions/notation, repeated references; no zero-found completeness claim | T10–T11, T49, T56 |
| S5 | Canonical verification and frozen dossier projection | Separate deterministic dimensions, calibrated normalization, immutable snapshot, stale denial | T25, T46, T54, T56 |
| S6 | Optional advisory channel | Deferred; never required for deterministic review/export | T84 |
| S7 / F4 | Verification, evidence, review features | Exceptions-first/show-all, keyboard queue, context/three page spaces, scoped inspection | T49–T57 |
| S8 / F4 | Existing signed review endpoints/ledger | Actual persisted enum and rationale, required inspected regions, save receipt, Save & Next | T53, T55 |
| S9 / F5 | `dossier_journey.py`, anchor/writer, corrections feature | Exact preview, same-actor review, durable commit/readback, new draft, mandatory recheck and historical decisions | T40–T48 |
| S10 / F6 | Release service, exports feature and private ledger | Explicit supported JSON/MD/DOCX scope; authorization, integrity, idempotency | T12–T13, T27, T30–T35, T60–T66 |
| S11 / F1/F4–F6 | Existing report/source/release history | Exact old bytes and current permissions after restart; historical/current distinction | T35, T57, T77 |
| S12 | Shared session/transport and durable job/operation lifecycle | Unknown-outcome reconciliation, cancellation, worker crash, stale leases and competing writes | T24, T28, T45, T55, T77 |
| S13 | Existing authorization, retention and deployment boundaries | Processing disclosure, private Storage/RLS, erasure/backup policy, no unsupported compliance claims | T70–T79 |

### Pages and workspace panels — complete coverage

Existing code and router determine actual paths. The paths below are blueprint identifiers, not permission to invent a route or endpoint. Keep existing deep links compatible.

| ID | Required behavior | Task owner |
|---|---|---|
| P01 session | Trusted host connect, expiry/denial, safe return navigation and processing disclosure | T50, T73 |
| P02 permitted matters | Loading/empty/unavailable/denied distinction; server-scoped list | T50 |
| P03 create matter | Authorized organization/title, inline validation, stable operation and receipt | T23, T50 |
| P04 matter overview | Active draft, confirmation, processing coverage, latest snapshot and next valid action | T50 |
| P05 sources | Role/version/hash/limits, transfer/readback/ingest stages, recovery and cancellation | T22–T24 |
| P06 inventory | Aliases, source binding, completeness and page-space mapping; current revision acknowledgment | T23, T51 |
| P07 findings/checks | Explicit check; frozen reads do not silently run verification; selected finding and four dimensions | T25, T50–T56 |
| P08 history | Scoped listing where implemented, original versions, historical decisions and snapshots | T35, T57 |
| P09 exports | Preview policy, limitations, supported output/digest, release and historical download | T30–T35, T60 |
| P10 data disclosure | Actual mode/OCR location, retention/backup/access; destructive controls only with approved contracts | T70, T73–T75 |
| W01 queue | Filters/search/count scope, keyboard, stable selection | T54 |
| W02 draft context | Supported exact source-bound context/anchor; derived preview limits | T42, T44, T52 |
| W03 evidence | Pixels/crop/three page spaces, stale-safe navigation | T51–T52 |
| W04 coverage drawer | Extraction versus visual versus editability, actionable exceptions | T49 |
| W05 review | Rationale, inspection, receipt and reconciliation | T53, T55 |
| W06 correction | Contextual preview, exact commit and recovery | T40–T45 |
| W07 recheck | Current version, processing progress and explained comparison | T46–T48 |
| W08 notes | Optional advisory panel, separately governed | T84 |

## 5. Detailed task cards

Each unchecked task below starts at TODO unless its Status says otherwise. Acceptance is a required target, not an observed result. Implementations should use the actual file owner found in code; likely paths are orientation, not speculative API instructions.

### 5.1 Records, authority and developer workflow

#### T01 — Reconcile stage and route inventory

- [ ] Complete T01 and record its acceptance evidence.

**Status:** VERIFY_EXISTING. **Depends on:** None.  
**Build:** Map each S0–S13 stage to actual route/model/feature/test/receipt and existing owner. Resolve stale OPEN and unimplemented-route claims. Check ADR numbering before reserving new decisions.  
**Done when:** Every capability is implemented with linked evidence, explicitly missing or conditional. No invented endpoint or owner.  
**Touch points:** docs/STATUS.md; frontend/BLUEPRINT.md; ADR index; router. **Trace:** Workflow §7/11; plan 0.2/0.4.

#### T02 — Update F4–F6 status and evidence

- [ ] Complete T02 and record its acceptance evidence.

**Status:** TODO. **Depends on:** T01.  
**Build:** Record PRs #176/#177/#178, exact final heads/merge commits, actual run URLs and remaining gates. Include later F6 run 41623751514 at c0e7d44; retain earlier receipts as historical.  
**Done when:** Status agrees with history. PR-head and post-merge runs remain distinguishable; no claims of independent or pilot approval.  
**Touch points:** docs/STATUS.md; docs/m3/F4_V31_REVIEW_ACCEPTANCE.md; F5_IMPLEMENTATION_ACCEPTANCE.md; docs/m4. **Trace:** Plan 0.1/0.5.

#### T03 — Track decisions and contract changes

- [ ] Complete T03 and record its acceptance evidence.

**Status:** TODO. **Depends on:** T01.  
**Build:** Maintain D01–D06 with actual accountable owners, date, alternatives, contract impact, migration/rollback and acceptance. Add ADR/amendment for material change; routine compatible repairs do not need a new ADR.  
**Done when:** No duplicate authority, guessed ADR number or silent public-state change.  
**Touch points:** ADR index; generated-contract sources. **Trace:** Plan §12/13.

#### T04 — Improve local format/lint workflow

- [ ] Complete T04 and record its acceptance evidence.

**Status:** TODO. **Depends on:** None.  
**Build:** Existing hooks run architecture checks/pytest. Add documented appropriate formatter/linter steps and hook installation; avoid whole-tree unrelated rewrites.  
**Done when:** Changed files pass relevant commands locally; CI remains authoritative. No metric promising zero formatter commits.  
**Touch points:** .githooks; frontend/package.json; developer docs. **Trace:** Plan 0.3.

#### T05 — Keep one task/evidence record

- [ ] Complete T05 and record its acceptance evidence.

**Status:** TODO. **Depends on:** None.  
**Build:** Use this backlog to record task state, scope, PR/head, checks, limits and next task. Cross-link authoritative changes rather than create another roadmap.  
**Done when:** An agent can resume without rereading every audit or confusing local work with merged acceptance.  
**Touch points:** This task file; status/evidence docs. **Trace:** Plan 0.6; blueprint §14.

#### T06 — Pin dependency and reuse provenance

- [ ] Complete T06 and record its acceptance evidence.

**Status:** TODO. **Depends on:** Before adding dependency/copied code.  
**Build:** Check current compatible versions, origin revision, license/NOTICE, transitive components and existing tooling. Preserve chosen StetDoc dual-license obligations and Vaquill Apache notices. Record CaseProof license decision without inventing it.  
**Done when:** Lockfiles and applicable notices match delivered bytes; no unreviewed git+ssh package.  
**Touch points:** pyproject.toml; uv.lock; frontend/package-lock.json; third-party notices. **Trace:** StetDoc S12; Vaquill V9/V15; plan §20.5.


#### T07 — Verify historical schema compatibility

- [ ] Complete T07 and record its acceptance evidence.

**Status:** VERIFY_EXISTING. **Depends on:** None; informs T32 and T35 before manifest changes ship.  
**Build:** Inventory installed snapshot, report, manifest and receipt schema identifiers and reader dispatch. Document existing compatibility rules before proposing versions or migrations. Add preserved old-format fixtures where missing; unknown versions must fail explicitly without rewriting historical artifacts.  
**Done when:** Supported historical formats reopen with unchanged bytes and valid receipts; unsupported versions have a controlled outcome. Record actual schema paths and tests. No new registry is required unless an observed gap warrants it.  
**Touch points:** Existing projection, snapshot and release readers/writers; generated contracts. **Trace:** Historical reopening; T32/T35.

#### T08 — Inventory service errors and recovery behavior

- [ ] Complete T08 and record its acceptance evidence.

**Status:** VERIFY_EXISTING. **Depends on:** None; informs T12–T13, T33, T45 and T55.  
**Build:** Trace actual backend error codes, HTTP statuses and frontend states for authentication expiry, action denial, stale state, malformed upstream data, capacity refusal and unknown mutation outcomes. Record endpoint-specific differences and regression coverage. Preserve installed contracts unless a deliberate compatible change is documented.  
**Done when:** One mapping links existing code to UI behavior and tests. Action-specific denial does not automatically invalidate a valid reader session. Unknown outcomes reconcile through the existing operation contract; HTTP status alone does not prove success or authorize automatic mutation retries.  
**Touch points:** API error mapping, shared transport/session and feature recovery. **Trace:** V8; S12.

#### T09 — Map acceptance requirements to executable evidence

- [ ] Complete T09 and record its acceptance evidence.

**Status:** TODO. **Depends on:** None; complete the affected mapping before T17 closure.  
**Build:** Maintain the acceptance-to-layer table in section 8 with actual test paths, commands and CI run links at the implementation head. Add missing regressions in the appropriate implementation tasks. Distinguish unit, integration, browser, signed backend and manual host evidence.  
**Done when:** Every affected Done-when requirement names its proving layer and observed result or explicit open gate. No invented test file, arbitrary coverage percentage or mocked replacement for signed acceptance.  
**Touch points:** Section 8 and existing test/workflow configuration. **Trace:** Bundle closure and evidence rules.

### 5.2 Bundle 1 — parser and service hardening

#### T10 — Harden every discovery XML parse

- [ ] Complete T10 and record its acceptance evidence.

**Status:** ENGINEERING EVIDENCED; independent security sign-off pending. **Depends on:** D05.  
**Evidence:** [P1 parser acceptance](p1/PARSER_ACCEPTANCE_2026-11-04.md) records shared defused XML parsing, UTF-8 and UTF-16 variants, DTD/entity rejection, explicit UTF-32 rejection and ordinary extraction coverage. [PR #187](https://github.com/haytamAroui/caseproof/pull/187) merged the hardening. The [independent parser review](security/PARSER_SECURITY_REVIEW.md) remains unsigned.  
**Build:** Use a shared safe parsing boundary with forbid_dtd/entities/external in inventory and text extraction; raw byte search is only a pre-check. Catch parser-security exceptions into existing controlled outcomes. Preserve omissions and denial semantics.  
**Done when:** DTD/entity cannot expand in UTF-8 or UTF-16 LE/BE with/without BOM. Unsupported UTF-32 rejects explicitly. Ordinary supported extraction remains unchanged.  
**Touch points:** infrastructure/parsers/docx_region_inventory.py; docx_text_regions.py. **Trace:** A1–A3; StetDoc S6.

#### T11 — Prove package and processing bounds

- [ ] Complete T11 and record its acceptance evidence.

**Status:** PARTIAL — package protections evidenced; complete processing bounds and independent review remain open. **Depends on:** T10.  
**Evidence:** [P1 parser acceptance](p1/PARSER_ACCEPTANCE_2026-11-04.md) records hostile ZIP cases, decompression limits and 1,024 synthetic mutations under a bounded CI process. This does not establish a production processing deadline or coverage-guided fuzzing. The [capacity profile](pilot/PILOT_CAPACITY_PROFILE.md) leaves 100 OCR pages and 50 MB files for pilot validation.  
**Build:** Preserve byte/part/count/expanded limits; inspect actual decompression enforcement. Define missing depth/node/time bounds and corrupt-part versus package rejection; avoid pretending all corruption is salvageable.  
**Done when:** Corrupt/encrypted/duplicate/traversal/oversize packages fail predictably; denominator remains trustworthy. No claim that defusedxml alone provides resource isolation.  
**Touch points:** Parser adapters; file boundary; tests/test_asvs_file_boundaries.py. **Trace:** A4; StetDoc S6.

#### T12 — Handle malformed RPC responses

- [ ] Complete T12 and record its acceptance evidence.

**Status:** IN_PROGRESS. **Depends on:** None.  
**Build:** Wrap DossierStore.rpc JSON decoding, retaining current non-dict and bounded-read checks. Compare other adapters; never expose raw response bodies. Add malformed JSON, invalid encoding and non-dict regressions.  
**Done when:** Controlled service failure for malformed HTTP-200 responses; no success or retry on unknown consequential outcomes.  
**Touch points:** apps/api/dossier_journey.py; RPC adapter tests. **Trace:** A5; Vaquill V8.

#### T13 — Validate release report fields

- [ ] Complete T13 and record its acceptance evidence.

**Status:** IN_PROGRESS. **Depends on:** None.  
**Build:** Validate keys/types once at the frozen-report boundary, including source rows and finding link identifiers. Avoid unguarded indexing or unhashable wrong-type membership. Add missing/wrong-type field cases.  
**Done when:** Bad backend data yields a controlled service failure, not an unhandled exception or misleading client validation error. Valid artifacts/receipts remain compatible.  
**Touch points:** apps/api/dossier_export_release.py; tests/test_f6_reviewed_exports.py. **Trace:** A6.

#### T14 — Verify correction reservation digest semantics

- [ ] Complete T14 and record its acceptance evidence.

**Status:** TODO. **Depends on:** None.  
**Build:** Trace original_sha256 versus parent and derivative digest through reservation SQL and adapter. Keep wire compatibility; rename internal variables or document a historical field name only after confirming semantics.  
**Done when:** Actual SQL-backed test binds parent and derivative correctly; do not remove a hash check because its name looks odd.  
**Touch points:** dossier_journey.py; dossier_draft_revisions.py; corresponding migrations. **Trace:** A7.

#### T15 — Define safe annotation text serialization

- [ ] Complete T15 and record its acceptance evidence.

**Status:** IMPLEMENTED_REVIEW_PENDING. **Depends on:** D06.  
**Evidence (4 Nov 2026, merged PR #185):** Safe XML annotation serialization is in the merged DOCX exporter; structural and XML regressions passed in [kernel final-head run](https://github.com/haytamAroui/caseproof/actions/runs/41829163374). Independent code review remains unrecorded.  
**Build:** Preserve significant whitespace with xml:space where needed. Reject XML-invalid characters or visibly substitute with a transformation disclosure. Preserve raw source and OCR representation; add emitted XML/reopen regressions.  
**Done when:** No silent stripping, malformed derivative or corruption of originals. Normal multilingual text survives.  
**Touch points:** infrastructure/parsers/dossier_docx_export.py. **Trace:** A8; F1.

#### T16 — Add bounded fuzz entry points

- [ ] Complete T16 and record its acceptance evidence.

**Status:** TODO. **Depends on:** T10–T11.  
**Build:** Seed package/document/rels/content-type entry points with legal and hostile fragments; minimize failures. Integrate a bounded, reproducible CI mode with controlled resources. Inspect current fuzz/testing tooling first.  
**Done when:** Reproducible failures and regression seeds; resource exhaustion is bounded; private data never enters public corpus.  
**Touch points:** Parser tests; isolated fuzz harness; affected workflow. **Trace:** A9; StetDoc S6/S7.

#### T17 — Close hardening bundle

- [ ] Complete T17 and record its acceptance evidence.

**Status:** TODO. **Depends on:** T02, T10–T15.  
**Build:** Complete focused security/error-path tests, relevant locked tests, architecture/Ruff/mypy and actual cloud checks. Obtain independent review appropriate to security/evidence changes. Record changed contracts and final-head evidence.  
**Done when:** No unhandled parser/JSON/manifest error; meaningful negative tests pass. Local 20-test result alone does not close task.  
**Touch points:** Changed code/tests; PR evidence. **Trace:** A10; bundle 1 closure.


### 5.3 Bundle 2 — capacity and signed processing

#### T20 — Measure candidate dossier envelopes

- [ ] Complete T20 and record its acceptance evidence.

**Status:** TODO. **Depends on:** Existing baseline.  
**Build:** Benchmark authenticated intake/OCR/visual/report/export and browser navigation with candidate exhibit/page/byte shapes; record time, peak memory and versions. Separate worker capacity from product capacity.  
**Done when:** Reproducible measurements include scans, repeated pages and baseline visual-budget refusal. Owner receives realistic options.  
**Touch points:** Existing benchmark and signed journey harnesses. **Trace:** B4; no new performance claim.

#### T21 — Approve one capacity profile

- [ ] Complete T21 and record its acceptance evidence.

**Status:** BLOCKED_DECISION. **Depends on:** T20, D01.  
**Build:** Specify versioned limits for files/bytes/pages, assessment, concurrency/CPU/memory/time, reports/artifacts and browser rendering. Decide visual-budget rejection versus explicit partial snapshot.  
**Done when:** ADR and stable refusal reasons exist; each layer and UI use the same policy. Candidate 50–200 pages is not an accepted number until measured.  
**Touch points:** Application capacity policy; ADR. **Trace:** B1–B2.

#### T22 — Extend transport and whole-intake admission

- [ ] Complete T22 and record its acceptance evidence.

**Status:** TODO. **Depends on:** T21.  
**Build:** Extend existing preflight to approved envelope; validate complete intake before writes. Keep stable registration/readback and digest binding. Bound transfer parsing/base64 or adopt reviewed transport suited to measured sizes.  
**Done when:** Invalid final source causes no earlier original writes; interrupted/corrupt/over-limit input returns correct stable outcomes.  
**Touch points:** workspace_intake.py; existing original transport; frontend intake. **Trace:** B3; S1/P05.

#### T23 — Align intake and confirmation models/UI

- [ ] Complete T23 and record its acceptance evidence.

**Status:** TODO. **Depends on:** T21–T22.  
**Build:** Apply profile to count/type/size/page validation, source selection and confirmations. Regenerate contracts; replace fixed page bounds only where actual new profile requires it. Preserve labels, roles, page spaces and source-version checks.  
**Done when:** Current four-source fixture exposes exactly four selects named Preserved exhibit; larger approved fixture binds correct sources; duplicates/stale revision fail.  
**Touch points:** Intake/confirmation DTOs; InventoryScreen.tsx; generated contracts. **Trace:** B7; S3/P03/P06.

#### T24 — Integrate durable bounded processing

- [ ] Complete T24 and record its acceptance evidence.

**Status:** TODO. **Depends on:** T21.  
**Build:** Reuse existing signed jobs, leases, checkpoints and cancellation. Extend real application composition for measured long work, including concurrency and process isolation; do not create a competing job authority.  
**Done when:** Process death resumes in a fresh process; expired leases cannot overwrite; cancel and permission loss have explicit outcomes.  
**Touch points:** Existing page-job services/stores; signed composition. **Trace:** B5; S12.

#### T25 — Implement selected visual-budget policy

- [ ] Complete T25 and record its acceptance evidence.

**Status:** TODO. **Depends on:** T21, T24.  
**Build:** Preserve all findings. If partial assessment adopted, version stable scheduling, assessed/eligible page-pair and finding denominators, missing-engine reasons and resumption/export behavior. Keep mapped page distinct from crop pointer.  
**Done when:** Boundary and over-budget cases follow ADR; no arbitrary omitted finding, false exact match or hidden assessed-scope change.  
**Touch points:** dossier_journey.py; visual services; report projection. **Trace:** B6; S2/S5.

#### T26 — Keep source reads and viewer work bounded

- [ ] Complete T26 and record its acceptance evidence.

**Status:** VERIFY_EXISTING. **Depends on:** T21.  
**Build:** Reuse verified originals/parse-once where appropriate, scoped to version/session; cancel obsolete PDF rendering, free workers/documents and measure long-list/page navigation. Do not persist document bytes in browser caches.  
**Done when:** Envelope navigation/memory targets pass; signout and source switches cannot show stale overlays or retain private resources.  
**Touch points:** SourceViewer.tsx; existing PDF adapter; source-read application code. **Trace:** B4/B8; blueprint §7.

#### T27 — Bound reports and artifacts at envelope

- [ ] Complete T27 and record its acceptance evidence.

**Status:** TODO. **Depends on:** T21.  
**Build:** Measure actual report/manifest/output growth, transport limits and release-history storage constraints. Expand only approved caps and preserve bounded readback/digest verification.  
**Done when:** Envelope artifacts fit or refuse explicitly before commit; oversized data cannot cause incomplete report success.  
**Touch points:** Release service; report serialization; SQL only if needed. **Trace:** B/report layer; S10.

#### T28 — Prove signed full-envelope recovery

- [ ] Complete T28 and record its acceptance evidence.

**Status:** TODO. **Depends on:** T22–T27.  
**Build:** Run genuine signed create/intake/confirm/check/review/correction/recheck/release/reopen with interrupted upload, lost ack, worker restart, competing commands and revoked actor. Include above-limit negatives.  
**Done when:** Exact evidence on final implementation; no duplicate versions/results; zero-residual disposable cleanup.  
**Touch points:** Signed browser/live fixture and recovery harness. **Trace:** B acceptance; UF01–UF05.

#### T29 — Publish supported limits and metrics

- [ ] Complete T29 and record its acceptance evidence.

**Status:** TODO. **Depends on:** T28.  
**Build:** Show backend limits and truthful partial/unsupported processing disclosure. Record privacy-safe counts/durations/memory and exact environment/policy version; no quotes or signed URLs in telemetry.  
**Done when:** Supported envelope is visible and backed by evidence; worker-only 200-page result is labeled as such.  
**Touch points:** UI disclosure; capacity acceptance; operational metrics. **Trace:** B8–B9.


### 5.4 Bundle 3 — release preflight

#### T30 — Define release eligibility and completeness

- [ ] Complete T30 and record its acceptance evidence.

**Status:** BLOCKED_DECISION. **Depends on:** D02.  
**Build:** Preserve ADR0032 until amended. Define release types, incomplete review, zero findings/decisions, qualified/contradicted decisions, coverage and historical access. Count applicable unique finding decisions instead of raw ledger rows.  
**Done when:** Decision table and backend tests establish partial versus complete labels without implying certification.  
**Touch points:** Release policy; ADR amendment/new ADR. **Trace:** C1.

#### T31 — Share server policy between preview and commit

- [ ] Complete T31 and record its acceptance evidence.

**Status:** TODO. **Depends on:** T30.  
**Build:** Return can_release, reason codes, total/required/reviewed/unreviewed counts, review_complete, coverage and currentness. Recompute with fresh permissions/state at commit; never trust a submitted preview flag.  
**Done when:** Preview/commit share rules; a race or changed snapshot denies commit; old preview grants nothing.  
**Touch points:** dossier_export_release.py; generated response contract. **Trace:** C2; S10.

#### T32 — Freeze scope in new release manifests

- [ ] Complete T32 and record its acceptance evidence.

**Status:** TODO. **Depends on:** T31; T07 compatibility verification before schema changes ship.  
**Build:** Record counts/completeness/limitations under compatible or explicitly versioned schema. Preserve old manifest/HMAC validation and exact old artifact bytes; never mutate historical signed records.  
**Done when:** Old and new releases reopen under correct schemas with unchanged historical bytes.  
**Touch points:** Manifest/receipt reader and writer; migration only if required. **Trace:** C3/C6.

#### T33 — Build actionable export checklist

- [ ] Complete T33 and record its acceptance evidence.

**Status:** TODO. **Depends on:** T31.  
**Build:** Show eligibility, review completeness and coverage separately. Link authorized items to finding/source/region through existing route context. Preserve historical selection; expose pending/unknown/rejected/released states.  
**Done when:** Partial label matches policy; failed release never shows completion; keyboard/screen reader can act on each issue.  
**Touch points:** frontend/src/features/exports; app navigation. **Trace:** C4–C5; Vaquill V7/V8.

#### T34 — Test release races and integrity

- [ ] Complete T34 and record its acceptance evidence.

**Status:** TODO. **Depends on:** T31–T33.  
**Build:** Exercise one reviewed plus unreviewed findings under approved policy, duplicate review rows, stale snapshot, revocation, competing release, lost ack, tampered bytes and oversized artifacts.  
**Done when:** One authorized operation; fresh checks and stable reason codes; downloaded bytes match frozen artifact.  
**Touch points:** Export tests and disposable SQL/signed acceptance. **Trace:** C acceptance; UF05.

#### T35 — Preserve historical release access

- [ ] Complete T35 and record its acceptance evidence.

**Status:** VERIFY_EXISTING. **Depends on:** T32–T34.  
**Build:** After changed draft/inventory/source, sign out/restart and reopen authorized old report/source/release. Recheck current grants/retention and history labels.  
**Done when:** Exact historical bytes; no regeneration; revoked actor denied; source links reopen original version.  
**Touch points:** Existing history/release endpoints; ExportsScreen. **Trace:** S11/P08/P09.


### 5.5 Bundle 4 — safe correction and explainable recheck

#### T40 — Measure anchors and decide revision view

- [ ] Complete T40 and record its acceptance evidence.

**Status:** TODO. **Depends on:** D03 decision required before behavior change.  
**Build:** Build isolated single-factor fixtures first, then representative mixed documents. Record attempted/resolved/refused anchors by cause. Specify one revision-view policy across extraction, resolver and writer.  
**Done when:** Baseline measures causes rather than one globally-refused document; revisions inside target remain refused unless separately supported.  
**Touch points:** correction_anchor.py; extraction tests; ADR. **Trace:** D0; StetDoc S2/S3.

#### T41 — Introduce shared bounded locator

- [ ] Complete T41 and record its acceptance evidence.

**Status:** TODO. **Depends on:** T40.  
**Build:** Bind source version/hash, XML part/structural path, declared offset encoding/range, exact literal and edit capability. Update actual preview/commit contracts together; no guessed table paragraph indexes.  
**Done when:** Resolver, preview and writer agree; repeats/cross-boundary/stale offsets refuse; generated types match.  
**Touch points:** Anchor/extraction/writer; correction DTOs. **Trace:** D locator; StetDoc S2/S3.

#### T42 — D1: simple targets amid complex content

- [ ] Complete T42 and record its acceptance evidence.

**Status:** TODO. **Depends on:** T41.  
**Build:** Resolve simple target despite unrelated formatted paragraphs/tables/notes. Scope edit validation to target and required dependencies while preserving actual document coverage.  
**Done when:** Same intended correction succeeds with unrelated complexity; target unsupported structures refuse; namespace/mc:Ignorable preserved.  
**Touch points:** correction_anchor.py; dossier_docx_export.py. **Trace:** D1; StetDoc S2/S10.

#### T43 — D2: supported multiple-run targets

- [ ] Complete T43 and record its acceptance evidence.

**Status:** TODO. **Depends on:** T42.  
**Build:** Define replacement formatting and supported spans, splitting/preserving runs where safe. Do not flatten fields/bookmarks/hyperlinks/revisions or whole paragraphs as fallback.  
**Done when:** Bold/italic and adjacent untouched text survive supported edits; unsupported constructs have stable reasons; originals unchanged.  
**Touch points:** Shared locator/writer; structural fixtures. **Trace:** D2; StetDoc S2/S4/S10.

#### T44 — Contextual correction preview and typed errors

- [ ] Complete T44 and record its acceptance evidence.

**Status:** TODO. **Depends on:** T41–T43.  
**Build:** Show surrounding text, word changes, supported scope/format policy, blockers and lifecycle. Keep diff display-only; review-receipt and hash checks authorize commit. Return typed stale/revision/unsupported reasons.  
**Done when:** Currency/date/negation/accents visible; accessible del/ins; no commit before required saved human review.  
**Touch points:** CorrectionPanel.tsx; correction errors/projection. **Trace:** E before commit; Vaquill V5/V6/V9.

#### T45 — Preserve durable correction lifecycle

- [ ] Complete T45 and record its acceptance evidence.

**Status:** VERIFY_EXISTING. **Depends on:** T41–T44.  
**Build:** Reuse command hash, operation ID, same-actor review, reserve/put-once/hash-readback/activate and authorized recovery. Add actual engine/locator provenance only where needed.  
**Done when:** Lost ack yields one derivative; competing command cannot activate twice; reader lacking correction grants is not wrongly signed out.  
**Touch points:** dossier_journey.py; revisions transport/SQL; CorrectionRecovery. **Trace:** StetDoc S9/S11; Vaquill V8.

#### T46 — Recheck the activated current draft

- [ ] Complete T46 and record its acceptance evidence.

**Status:** VERIFY_EXISTING. **Depends on:** T45.  
**Build:** Recheck actual activated version; disallow superseded draft before and after processing. Produce a fresh snapshot; verify affected evidence dependencies. Old human decisions stay historical.  
**Done when:** Original hashes/history preserved; stale/competing recheck refuses; no stale approval reused.  
**Touch points:** Journey recheck; verification application services. **Trace:** S9; E evidence reevaluation.

#### T47 — Compute backend finding correspondence

- [ ] Complete T47 and record its acceptance evidence.

**Status:** IMPLEMENTED_REVIEW_PENDING. **Depends on:** T46.  
**Evidence (4 Nov 2026, merged PR #185):** Frozen snapshot-bound correspondence, explicit uncertain states and no decision transfer are implemented and regression-tested; [frontend final-head run](https://github.com/haytamAroui/caseproof/actions/runs/41829163384) and [signed F6 final-head run](https://github.com/haytamAroui/caseproof/actions/runs/41829162860) passed. Independent review remains open.  
**Build:** Version explanatory matching across two frozen snapshots, using locator/version lineage and reference/context evidence. Classify unchanged/changed/added/removed/uncertain; handle ties conservatively.  
**Done when:** Repeated/relocated/edited citations do not silently match incorrectly; paragraph hashes alone do not determine correspondence.  
**Touch points:** Application comparison projection; generated schema. **Trace:** E; StetDoc S5/S8.

#### T48 — Show explained old/new reports

- [ ] Complete T48 and record its acceptance evidence.

**Status:** IMPLEMENTED_REVIEW_PENDING. **Depends on:** T47.  
**Evidence (4 Nov 2026, merged PR #185):** Correction workspace exposes explained frozen old/new drift with uncertainty; [frontend final-head run](https://github.com/haytamAroui/caseproof/actions/runs/41829163384) passed. Independent review remains open.  
**Build:** Extend existing comparison UI with correspondence and separate dimension deltas/reasons. Display historical reviews read-only. Open either snapshot with exact source context.  
**Done when:** Reviewer sees why date/currency/page/fidelity changed and what remains unassessed; no correspondence treated as human approval.  
**Touch points:** CorrectionPanel.tsx; app navigation. **Trace:** E; Vaquill V7/V9.

#### T49 — Build actionable coverage navigator

- [ ] Complete T49 and record its acceptance evidence.

**Status:** TODO. **Depends on:** Existing regional inventory; T31 for preflight links.  
**Build:** Expose source/region/state/reason and supported navigation. Separate extraction coverage, visual scope and editability. Missing anchors show notice plus authorized original access.  
**Done when:** Headers/notes/textboxes/revisions, missing mapping and OCR uncertainty retain denominators; stale/cross-matter navigation fails safely.  
**Touch points:** Review/verification/evidence feature public APIs; app orchestration. **Trace:** Plan §21.3; StetDoc inspection; Vaquill V7.


### 5.6 Blueprint and workflow closure across existing screens

#### T50 — Verify matter and check navigation

- [ ] Complete T50 and record its acceptance evidence.

**Status:** VERIFY_EXISTING. **Depends on:** T01.  
**Build:** Audit P01–P07 actual router/backend behavior, organization selection and overview next task. Freeze passive report reads; run checks only through explicit action; distinguish empty/unavailable/denied.  
**Done when:** No seeded IDs or invented tenant/grant picker; safe internal return navigation; correct actual matter/draft/snapshot context.  
**Touch points:** app routes; matters/intake/verification; workspace catalog. **Trace:** S0/S1/S7; blueprint §17–19.

#### T51 — Verify inventory and three page spaces

- [ ] Complete T51 and record its acceptance evidence.

**Status:** VERIFY_EXISTING. **Depends on:** T23 if capacity changed.  
**Build:** Keep confirmed-complete inventory independent of per-entry source and physical/printed/bundle page mappings. Show conflicting/unmapped states and current confirmation revision.  
**Done when:** Printed p4 → physical PDF p6 opens page6; no inferred delta; missing source is not automatically not_in_inventory.  
**Touch points:** InventoryScreen; confirmation models; pageSpaces. **Trace:** S3; FX01/FX22.

#### T52 — Verify viewer and draft context fidelity

- [ ] Complete T52 and record its acceptance evidence.

**Status:** VERIFY_EXISTING. **Depends on:** T26; T42 for extended anchors.  
**Build:** Exercise existing PDF.js/derived DOCX path on rotation, CropBox, mixed sizes, zero origins, scans and repeated text. Bind source/selection/render generations; honor actual scope of DOCX preview.  
**Done when:** Correct target at 200% zoom/reflow and DPR below/above one; no stale-source highlight; unsupported anchor has honest notice.  
**Touch points:** SourceViewer; DraftContext; existing viewer acceptance. **Trace:** Blueprint §7–8; S2/S7.

#### T53 — Verify human inspection and saved decisions

- [ ] Complete T53 and record its acceptance evidence.

**Status:** VERIFY_EXISTING. **Depends on:** Existing review implementation.  
**Build:** Align actual enum/rationale/required-region rules with UI; require server receipt for saved state. Keep deterministic conflict separate from human disposition. Advance only after receipt.  
**Done when:** Saved review survives browser/server restart; revoked/stale/competing save and skipped required region fail correctly.  
**Touch points:** ReviewPanel; existing review endpoints/tests. **Trace:** S8/W05; UF03.

#### T54 — Verify findings queue and inspection modes

- [ ] Complete T54 and record its acceptance evidence.

**Status:** VERIFY_EXISTING. **Depends on:** T49.  
**Build:** Maintain exceptions-first plus show-all, bounded search/filter/paging counts, selected occurrence and source context. Label pixels/OCR/quote diff/translation separately; no global score.  
**Done when:** Filters preserve denominator; no-results and zero detected differ from complete; J/K/Space accessible and scoped; scan stays available.  
**Touch points:** ReportScreen; verification/evidence/review. **Trace:** Blueprint §9/11; S4/S5/S7.

#### T55 — Close shared failure/recovery states

- [ ] Complete T55 and record its acceptance evidence.

**Status:** VERIFY_EXISTING. **Depends on:** Affected bundles.  
**Build:** Cover loading/empty/partial/error/timeout, expiry, stale409, unknown writes, session/matter switches and late status/body/render. Preserve input only under permitted memory lifecycle.  
**Done when:** No private state repopulates after signout; one operation per payload; no raw server errors, optimistic approval or blind retry.  
**Touch points:** shared/api/session; all consequential feature flows. **Trace:** S12; Vaquill V8.

#### T56 — Close workflow fidelity fixture gaps

- [ ] Complete T56 and record its acceptance evidence.

**Status:** VERIFY_EXISTING. **Depends on:** Affected parser/viewer/correction changes.  
**Build:** Run translated FX cases listed in section 7 against actual Python/generated/UI boundaries. Confirm existing fixtures before adding duplicates. Calibrate any guarded-token explanation separately.  
**Done when:** Substantive date/amount/currency/negation changes never become exact matches; uncertainty/unsupported cases remain explicit.  
**Touch points:** Canonical verification tests; frontend contract/UI fixtures. **Trace:** Workflow §6; S4/S5.

#### T57 — Verify frozen reports and review history

- [ ] Complete T57 and record its acceptance evidence.

**Status:** VERIFY_EXISTING. **Depends on:** T46/T48 for new behavior.  
**Build:** Use actual historical listings/read paths; distinguish old source universe and historical reviews from current approval. Restore selected authorized finding after cold reopening.  
**Done when:** Old decisions/report content immutable and attributable; current grants checked; no complete history API assumed where absent.  
**Touch points:** History/report/review APIs; app routes. **Trace:** S11/P08; UF03/UF04.


### 5.7 Bundle 5 — DOCX output and optional structural capabilities

#### T60 — Make appended DOCX report readable

- [ ] Complete T60 and record its acceptance evidence.

**Status:** IMPLEMENTED_REVIEW_PENDING. **Depends on:** T15, D06.  
**Evidence (4 Nov 2026, merged PR #185):** Readable, labeled derivative appendix replaces Python dictionary repr, preserves original ZIP parts and refuses XML-invalid characters. [kernel final-head run](https://github.com/haytamAroui/caseproof/actions/runs/41829163374) and [P6 host/restore/supply-chain acceptance](https://github.com/haytamAroui/caseproof/actions/runs/41829163280) passed on synthetic fixtures; independent code/host review remains open.  
**Build:** Retain existing append model and original body elements. Replace str(dict) output with labeled scope/counts/limitations and per-finding reasons/review identity/time. Include only available bound release metadata.  
**Done when:** NL/FR/EN report readable; valid whitespace/XML; preserves body semantics and untouched ZIP payloads; no certificate wording.  
**Touch points:** dossier_docx_export.py; real-format fixture tests. **Trace:** F1; StetDoc S10.

#### T61 — Verify output in actual document hosts

- [ ] Complete T61 and record its acceptance evidence.

**Status:** PARTIAL_LIBREOFFICE_PASSED_WORD_OPEN. **Depends on:** T60; any adopted writer.  
**Evidence (4 Nov 2026, merged PR #185):** Real LibreOffice Writer 24.2.7.2 synthetic DOCX/PDF/ODT round-trip passed in [P6 host/restore/supply-chain acceptance](https://github.com/haytamAroui/caseproof/actions/runs/41829163280); Microsoft Word desktop and independent visual-format review were not run. Do not check this task off.  
**Build:** Render/reopen representative original/corrected/annotated fixtures in supported desktop Word and LibreOffice. Inspect styles/runs/tables/footnotes/comments/links, package validity and exact historical retrieval.  
**Done when:** Record host/version, observations, failures and limitations. Prior LibreOffice evidence is scoped; do not relabel it Word acceptance.  
**Touch points:** Output fixtures; host verification receipt. **Trace:** F acceptance; UF05.

#### T62 — Experiment with anchored comments/navigation

- [ ] Complete T62 and record its acceptance evidence.

**Status:** CONDITIONAL. **Depends on:** T42; actual feature need and experiment decision.  
**Build:** Compare minimal in-house writer with pinned StetDoc CLI on synthetic references: range comments/bookmarks/internal links. Avoid external PDF/crop link promises unsupported by output host.  
**Done when:** Written adopt/reject/defer recommendation based on fidelity, host behavior, resources, license and usability. No automatic adoption.  
**Touch points:** Isolated experiment; exporter adapter if accepted. **Trace:** F2; StetDoc S1/S9/S10.

#### T63 — Build isolated StetDoc adapter if selected

- [ ] Complete T63 and record its acceptance evidence.

**Status:** CONDITIONAL. **Depends on:** T62 or demonstrated editing need; material ADR.  
**Build:** Allowlist actual documented commands; validate pinned schemas/capabilities; bound process tree/time/memory/output. Enforce filesystem/network isolation separately; no credentials or other matter files available.  
**Done when:** Escape/symlink/timeout/malformed-output tests fail safely; package validated before readback/activation; existing ledger remains authority.  
**Touch points:** Private worker adapter; deployment policy. **Trace:** StetDoc S1/S13; section 8.

#### T64 — Decide and implement native tracked output if needed

- [ ] Complete T64 and record its acceptance evidence.

**Status:** CONDITIONAL. **Depends on:** D04, T61–T63 as applicable.  
**Build:** First record practitioner decision. If activated, specify supported revision constructs and author metadata, exact operations, host support, package validation and receipt binding.  
**Done when:** Word displays intended declared edit; original preserved; authenticated ledger—not author string—proves reviewer; unsupported cases refuse.  
**Touch points:** Writer capability and ADR; Word acceptance. **Trace:** F3; StetDoc S2; Vaquill V10.

#### T65 — D3 bounded table-cell corrections

- [ ] Complete T65 and record its acceptance evidence.

**Status:** CONDITIONAL. **Depends on:** T42–T43 accepted; locator policy extension.  
**Build:** Activate explicit table-cell path after D1/D2 evidence; define supported merged/nested/table structures and style retention. Reuse shared locator and durable lifecycle.  
**Done when:** Target cell only changes; complex unsupported tables refuse; host reopen and fresh evidence recheck pass.  
**Touch points:** Shared locator/writer; table fixtures. **Trace:** D3; StetDoc S2/S4.

#### T66 — Add exhibit-reference drift explanations

- [ ] Complete T66 and record its acceptance evidence.

**Status:** IMPLEMENTED_REVIEW_PENDING. **Depends on:** T47.  
**Evidence (4 Nov 2026, merged PR #185):** Exhibit-reference drift explanations and changed source/page reasoning are implemented with explicit uncertain/unsupported cases; [frontend final-head run](https://github.com/haytamAroui/caseproof/actions/runs/41829163384) passed. No review transfer; independent review still needed.  
**Build:** Compare CaseProof reference identity/source/page changes after correction; keep structural engine warnings separate from domain verification. Classify unsupported/ambiguous drift explicitly.  
**Done when:** Renumbered Stuk/Pièce, changed source and moved references cannot silently retain old approval.  
**Touch points:** Application comparison; explanatory UI. **Trace:** StetDoc S8; E.


### 5.8 Operational and practitioner acceptance — begin alongside engineering

#### T70 — Inspect actual database security configuration

- [ ] Complete T70 and record its acceptance evidence.

**Status:** PARTIAL_DEV_AUDIT_REVIEW_OPEN. **Depends on:** Authorized read access.  
**Evidence (4 Nov 2026, merged PR #185):** Read-only Supabase dev catalog inspection was recorded in [security triage](pilot/P6_SECURITY_DEPENDENCY_PRIVACY_TRIAGE_2026-11-04.md); 15 public privileged RPC warnings, 29 private no-policy notices and leaked-password setting require independent scrutiny and signed-role tests. No grant/auth setting changed.  
**Build:** Check live CaseProof dev function owner/search_path/grants, SECURITY DEFINER boundaries, private tables/RLS, cross-matter and revoked roles; compare migrations and advisor findings. Record actual leaked-password protection availability/state.  
**Done when:** Dated findings and remediation evidence; no blanket change of function mode or claim that advisor warnings prove exploitability.  
**Touch points:** Connected CaseProof dev; SQL catalog; security receipts. **Trace:** G1; S13.

#### T71 — Investigate unexplained signed-browser failure

- [ ] Complete T71 and record its acceptance evidence.

**Status:** TODO. **Depends on:** Existing run diagnostics.  
**Build:** Identify exact F4/F5 run/log/timing, distinguish wrong attribution, session/runner/transient faults and reproducible defect. Fix supported cause; preserve unresolved observation if evidence insufficient.  
**Done when:** Diagnostic evidence or demonstrated fix; no arbitrary retry counted as root-cause resolution.  
**Touch points:** F4/F5 acceptance/workflow logs. **Trace:** G2.

#### T72 — Verify dependency and build hygiene

- [ ] Complete T72 and record its acceptance evidence.

**Status:** PARTIAL_SUPPLY_CHAIN_REVIEW_OPEN. **Depends on:** T06.  
**Evidence (4 Nov 2026, merged PR #185):** The locked npm security audit in [P6 host/restore/supply-chain acceptance](https://github.com/haytamAroui/caseproof/actions/runs/41829163280) found 0 moderate-or-higher production advisories and 11 moderate development-only lint/tooling advisories; remediation or signed exception is still required.  
**Build:** Inspect existing lockfile, dependency/secret scanning and SBOM tools; add missing useful controls. Scope artifacts and logs to synthetic/non-sensitive content.  
**Done when:** Build inputs traceable; no duplicate policy tools or secret leakage; approved headers/assets remain pinned.  
**Touch points:** CI; dependency files; SBOM/notices. **Trace:** G5; Vaquill V15.

#### T73 — Close processing, egress and privacy disclosures

- [ ] Complete T73 and record its acceptance evidence.

**Status:** PARTIAL_INTAKE_DISCLOSURE_ONLY. **Depends on:** Actual deployment mode selected.  
**Evidence (4 Nov 2026, merged PR #185):** Intake now accurately discloses Supabase originals/metadata egress and automated contracts pass in [P6 host/restore/supply-chain acceptance](https://github.com/haytamAroui/caseproof/actions/runs/41829163280); actual deployment regions/processors, capture, retention, legal hold, privacy owner and agreements are not approved.  
**Build:** Map SEC01–16 data flows, browser/backend/OCR/model location, providers/regions, network capture scope and contractual retention. Display accurate P10/session policy before confidential use.  
**Done when:** No unmeasured zero-egress/compliance statement; local/hybrid/hosted boundaries documented with independent acceptance.  
**Touch points:** ADR0025; security evidence; processing disclosure UI. **Trace:** S13/P10; H.

#### T74 — Prove backup restore and retention

- [ ] Complete T74 and record its acceptance evidence.

**Status:** PARTIAL_DISPOSABLE_RESTORE_ONLY. **Depends on:** Operational owner and approved isolated environment.  
**Evidence (4 Nov 2026, merged PR #185):** PostgreSQL 17 pg_dump/pg_restore, four relation checks, synthetic erasure replay and direct-grant denial passed in [P6 host/restore/supply-chain acceptance](https://github.com/haytamAroui/caseproof/actions/runs/41829163280); an authorized actual Supabase operational-backup restore and full retention/legal-hold review remain open.  
**Build:** Test restore, access control and erasure replay against actual retention/legal-hold policy. Include sources, OCR/geometry, snapshots/reviews/releases, scratch and backups.  
**Done when:** No deleted sensitive content reappears after restore; dated actual restore/retention evidence; destructive controls remain authorized.  
**Touch points:** Existing retention/backup services; isolated acceptance. **Trace:** G4; S13.

#### T75 — Manual accessibility and locale acceptance

- [ ] Complete T75 and record its acceptance evidence.

**Status:** PARTIAL_AUTOMATED_A11Y_ONLY. **Depends on:** Affected final UI.  
**Evidence (4 Nov 2026, merged PR #185):** Playwright/axe, keyboard, 320px, zoom simulation, forced colors, reduced motion, multilingual tests passed in [frontend final-head run](https://github.com/haytamAroui/caseproof/actions/runs/41829163384); no manual screen-reader or WCAG 2.2 AA sign-off.  
**Build:** Test keyboard-only and screen reader, zoom/reflow, reduced motion, forced colors, narrow panes, accessible labels/modal/error focus and long NL/FR/EN text. Fix gaps in shared primitives.  
**Done when:** Record browsers/AT/versions and remaining limits; no fully-accessible claim from axe alone.  
**Touch points:** All P01–P10/W surfaces; theme/shared UI. **Trace:** G6; blueprint §10–11.

#### T76 — Build representative rights-cleared corpus

- [ ] Complete T76 and record its acceptance evidence.

**Status:** PARTIAL_SYNTHETIC_CORPUS_ONLY. **Depends on:** Practitioner/data permission.  
**Evidence (4 Nov 2026, merged PR #185):** Authored NL/FR/EN synthetic fixtures validated in [P6 host/restore/supply-chain acceptance](https://github.com/haytamAroui/caseproof/actions/runs/41829163280); real data-owner authorization, representative dossiers and independent gold labels have not been obtained.  
**Build:** Gather representative NL/FR/EN briefs/inventories/text+scans, independent expected labels, repeated citations, formatting/tables/notes and seeded substantive errors. Pin hashes privately where needed.  
**Done when:** Rights and access recorded; expected outcomes independently reviewed; synthetic versus real results distinguishable.  
**Touch points:** Private corpus manifests; synthetic CI generator. **Trace:** H; StetDoc S7.

#### T77 — Run final integrated signed acceptance

- [x] Complete T77 and record its acceptance evidence.

**Status:** PASSED_FINAL_HEAD_SIGNED_ACCEPTANCE. **Depends on:** All required bundle tasks and fixes.  
**Evidence (4 Nov 2026, merged PR #185):** Exact PR head `3c6058a054ffd5172413cba5b90eb9af4bb44586` passed [signed F6 final-head run](https://github.com/haytamAroui/caseproof/actions/runs/41829162860): signed intake through historical release, lost-ack reconciliation, stale/revoked denial and `ZERO_RESIDUAL_VERIFIED`. This checks engineering T77 only, not pilot/production authorization.  
**Build:** Create authorized matter from genuine signed browser, complete intake through historical release after restart. Include stale/revoked/cross-matter, lost ack, competing writes, wrong-source render and tamper.  
**Done when:** Final implementation SHA, relevant CI and zero-residual cleanup recorded; no earlier-run substitution or skipped-gate concealment.  
**Touch points:** Existing protected signed workflows/fixtures; evidence record. **Trace:** G3; UF01–UF05.

#### T78 — Measure practitioner value and readiness

- [ ] Complete T78 and record its acceptance evidence.

**Status:** BLOCKED_REAL_CORPUS_AND_REVIEWERS. **Depends on:** T76 and authorized test/pilot mode.  
**Evidence (4 Nov 2026, merged PR #185):** The [practitioner study protocol](pilot/P6_PRACTITIONER_AND_CORPUS_PROTOCOL.md) exists, but no permissioned representative corpus, real reviewer sessions, denominators, independent outcomes or utility metrics have been recorded.  
**Build:** Interview practitioners, observe timed manual-versus-CaseProof review, record recall/false-verification denominators, uncertainty comprehension, review agreement and paid commitment hypotheses. Define stop criteria and data terms.  
**Done when:** Real owners review outcomes; no zero-risk extrapolation; selected capacity actually fits target dossiers.  
**Touch points:** Pilot protocol; independent results. **Trace:** H/M5.

#### T79 — Make engineering and pilot declarations separately

- [ ] Complete T79 and record its acceptance evidence.

**Status:** BLOCKED_PILOT_APPROVAL. **Depends on:** T77; T70/T73–T78 for pilot.  
**Evidence (4 Nov 2026, merged PR #185):** PR #185 merged as engineering work at `b162a5f7a08975949a32671cbea774b7f0a7bb09`; [signed F6 final-head run](https://github.com/haytamAroui/caseproof/actions/runs/41829162860) and [P6 host/restore/supply-chain acceptance](https://github.com/haytamAroui/caseproof/actions/runs/41829163280) passed. Independent security, privacy/egress, operational restore, Microsoft Word, manual AT, rights and practitioners remain open: **pilot NOT approved**.  
**Build:** Record completed scope, limits, review owners, rollback and release controls. Pilot-ready requires capacity proof, representative data, operational/privacy/security/accessibility/practitioner gates.  
**Done when:** No CI-only product/production approval; no invented acceptance signer. Update backlog and dated status.  
**Touch points:** STATUS; acceptance records; this backlog. **Trace:** Definition of done.


### 5.9 Conditional future features — explicit disposition

#### T80 — Word authentication/read integration maintenance

- [ ] Complete T80 and record its acceptance evidence.

**Status:** CONDITIONAL. **Depends on:** Actual Word channel change.  
**Build:** Preserve existing ephemeral authentication/read-only spike and capture/revalidation behavior. Check PKCE/dialog, expiry and host compatibility when changing it; no separate evidence store.  
**Done when:** Actual supported Word host results; no tokens in localStorage/Office.Settings; web pilot independent.  
**Touch points:** apps/word_addin. **Trace:** Vaquill V1/V5.

#### T81 — Word write anchoring and serialized host safety

- [ ] Complete T81 and record its acceptance evidence.

**Status:** CONDITIONAL. **Depends on:** Approved Word write capability.  
**Build:** If activated, use exact validated head/tail search for Office 255-character limit, capability/protection checks and serialized tracking save/change/restore. Isolate Word.run and host differences.  
**Done when:** Long/repeated/cross-paragraph/protected/tracked/co-author failure cases in real hosts; tracking never accidentally disabled.  
**Touch points:** Optional Word host adapter. **Trace:** Vaquill V2/V3/V4/V11.

#### T82 — Public MCP or editing-tool exposure

- [ ] Complete T82 and record its acceptance evidence.

**Status:** CONDITIONAL. **Depends on:** Separate owner/security scope decision.  
**Build:** Keep currently approved read-only boundaries. Any additional tools require actor/matter authorization, per-operation limits, untrusted-document framing, filesystem/network isolation and OAuth/resource review.  
**Done when:** No unconfined default or --root-as-sandbox claim; revocation and cross-matter denial demonstrated.  
**Touch points:** Existing optional MCP host; private tool adapter. **Trace:** StetDoc S13; S6 nondependency.

#### T83 — Redaction output

- [ ] Complete T83 and record its acceptance evidence.

**Status:** CONDITIONAL. **Depends on:** Practitioner need and explicit product decision.  
**Build:** If activated, define all supported stories and values, physical removal, tracking policy, post-edit validation and explicit accounting of every skipped/unsupported item.  
**Done when:** More-than-255-character values never silently skipped; remaining content detected; source remains immutable.  
**Touch points:** Separate derived-output feature. **Trace:** Vaquill V14.

#### T84 — Optional model notes

- [ ] Complete T84 and record its acceptance evidence.

**Status:** CONDITIONAL. **Depends on:** Policy/provider/data approval.  
**Build:** Separate labeled advisory notes, no write path to findings/review/release authority. Treat document content as untrusted, render inert text and disclose transport/location.  
**Done when:** Deterministic S7–S11 journey works without model; model failure cannot change canonical results.  
**Touch points:** Existing advisory port only after inspection. **Trace:** S6/W08; Vaquill V13.

#### T85 — Progress streaming or alternate export protocols

- [ ] Complete T85 and record its acceptance evidence.

**Status:** CONDITIONAL. **Depends on:** Measured need; separate contract decision.  
**Build:** Use durable-job progress first; add streaming only if necessary and robust to CRLF/chunk boundaries/disconnect. CSV, PDF output, RFC8785/Ed25519 remain separate capabilities.  
**Done when:** No fake/duplicate completion; CSV formula protection only when CSV is actually supported; no unimplemented signing claims.  
**Touch points:** Existing job/report/export contract. **Trace:** Vaquill V12; FX18.


## 6. StetDoc and Vaquill — complete reuse disposition

This table accounts for all 28 source-plan reuse items. Every item has an implementation/verification task or a named conditional decision. A source tool's implementation is a reference, not proof that CaseProof supports its capability.

### StetDoc — structural engineering

Pinned audit source: [`clauseo-ai/stetdoc` at `71c7e3bcedd638638497edd2e31539f07e4780b4`](https://github.com/clauseo-ai/stetdoc/tree/71c7e3bcedd638638497edd2e31539f07e4780b4).

| Item | Useful addition | Tasks | Adoption rule |
|---|---|---|---|
| S1 CLI engine | Bounded optional comments/edit adapter | T62–T64 | Experiment first; no mandatory Rust integration |
| S2 target-scoped multi-run editing | Shared structural locator and staged D1/D2/D3 | T40–T43, T65 | Exact original/version/range; supported format policy; no flattening fallback |
| S3 version-bound refs | Typed stale reasons and internal engine metadata if used | T41, T44–T45 | CaseProof snapshot/hash remains authority; do not reject all older engine tokens indiscriminately |
| S4 origin-aware checks | Separate pre-existing structural issues from edit-induced violations | T43, T46 | Never skip affected evidence recheck or hide inherited uncertainty |
| S5 exact changed spans | Contextual diff and alignment ideas | T44, T47–T48 | Document redline does not establish finding correspondence/legal support |
| S6 hostile-input design | Safe XML, archive/resource controls | T10–T11, T16 | Parsing security and execution isolation are separate controls |
| S7 fuzz/realistic corpus | Reproducible structural and representative fixtures | T16, T20, T76 | Rights, hashes and private data boundaries explicit |
| S8 drift diagnostics | Explain changed exhibit identity/source/page after correction | T47, T66 | Apply CaseProof domain rules; ambiguity stays uncertain |
| S9 rich edit receipts | Operation/locator/engine/input/output provenance | T45, T63–T64 | Author/date strings are not authenticated reviewer proof |
| S10 untouched-part preservation | Byte checks on unchanged members; semantic checks on modified XML | T42–T43, T60–T61 | Distinguish XML semantics, ZIP-member payload and full archive bytes |
| S11 crash-safe local writes | Staged atomic local publication where needed | T24, T45, T63 | Do not replace remote reservation/readback/activation |
| S12 schemas/capabilities | Validate engine JSON against pinned actual schema | T06, T41, T63 | Preserve Pydantic/JSON Schema/AJV/TS as public-contract pipeline |
| S13 confinement/tool safety | Filesystem/network isolation and scoped tool authorization | T63, T82 | --root and per-job directory alone do not sandbox a subprocess |

StetDoc source anchors: [reference model](https://github.com/clauseo-ai/stetdoc/blob/71c7e3bcedd638638497edd2e31539f07e4780b4/crates/stetdoc-core/src/refs/mod.rs), [changed-unit checks](https://github.com/clauseo-ai/stetdoc/blob/71c7e3bcedd638638497edd2e31539f07e4780b4/crates/stetdoc-core/src/check/edit.rs), [revision engine](https://github.com/clauseo-ai/stetdoc/blob/71c7e3bcedd638638497edd2e31539f07e4780b4/crates/stetdoc-core/src/revisions/mod.rs), [working copy](https://github.com/clauseo-ai/stetdoc/blob/71c7e3bcedd638638497edd2e31539f07e4780b4/crates/stetdoc-core/src/api/working_copy.rs).

### Vaquill — workflow and host lessons

Pinned audit source: [`Vaquill-AI/ms-word-addin` at `0740ec39ffd1e1e1ef54088a11d157cf35aa541b`](https://github.com/Vaquill-AI/ms-word-addin/tree/0740ec39ffd1e1e1ef54088a11d157cf35aa541b).

| Item | Useful addition | Tasks | Adoption rule |
|---|---|---|---|
| V1 dialog/PKCE | Preserve ephemeral Word authentication pattern when touched | T80 | Existing web session remains canonical; no browser refresh-token persistence |
| V2 head/tail search | Future Office long-range search with exact assembled-range validation | T81 | 255-character workaround belongs to Office.js, not Python OOXML parsing |
| V3 tracking serialization | Save/edit/restore host mode sequentially | T81 | Required only if Word writes are approved; recover on failure/cancel |
| V4 protection detection | Host capability/protection checks | T81 | Verify actual host APIs, localized cases and unsupported-host behavior |
| V5 fresh baseline timing | Revalidate editable source immediately before commit | T44–T46, T80 | Existing hash/currentness guards enforce web equivalent |
| V6 pending-change guidance | Precise target revision/unsupported reasons | T40, T44 | Never auto accept/reject existing lawyer revisions |
| V7 navigation intent | Deep-link preflight/coverage to existing selected source/finding | T33, T48–T49 | Reuse Router/viewer context; no unnecessary global intent bus |
| V8 explicit error contract | Stale/denied/unavailable/unknown write states | T12–T13, T33, T45, T55 | No blind retries, fake save or raw sensitive error body |
| V9 inline word diff | Accessible contextual change display | T44, T48 | Review library maintenance/license; exact characters remain visible |
| V10 attributed server edits | Optional Word tracked derivative | T64 | Metadata attribution separate from authenticated review ledger |
| V11 Word host reliability | Word.run boundary, API/version/capture/insert tests | T80–T81 | Real supported-host acceptance; no blanket reliability claim |
| V12 stream parsing | Durable progress with robust optional streaming | T85 | Add only for measured need; no SSE-as-evidence authority |
| V13 safe rendering | Inert document/model text display | T54–T55, T84 | Avoid raw HTML; preserve strict CSP |
| V14 redaction accounting | Future physical removal plus per-value verification | T83 | Long values cannot silently skip; outside current pilot scope |
| V15 deployment defense | Relevant headers and bounded local assets | T72–T73 | CaseProof CSP remains strict; Office frame permissions only for approved host path |

Vaquill anchors: [redline](https://github.com/Vaquill-AI/ms-word-addin/blob/0740ec39ffd1e1e1ef54088a11d157cf35aa541b/src/office/redline.ts), [serialized Word operations](https://github.com/Vaquill-AI/ms-word-addin/blob/0740ec39ffd1e1e1ef54088a11d157cf35aa541b/src/office/run.ts), [navigation](https://github.com/Vaquill-AI/ms-word-addin/blob/0740ec39ffd1e1e1ef54088a11d157cf35aa541b/src/app/nav.tsx), [inline diff](https://github.com/Vaquill-AI/ms-word-addin/blob/0740ec39ffd1e1e1ef54088a11d157cf35aa541b/src/features/review/InlineDiff.tsx).

### Never copy these patterns

- Vaquill's tolerant matcher lowercases and removes non-ASCII/alphanumeric characters; it can equate currency differences and discard accents. It cannot authorize a CaseProof edit or fidelity claim.
- Silent long-redaction skips; model errors mapped to default success-like data; provider keys or refresh tokens in persistent storage; unsafe-inline/eval and wildcard remote CSP.
- StetDoc's unconfined defaults or file transaction plan as a replacement for tenant authorization or remote durable state.
- Guessed CLI commands, arbitrary engine adoption thresholds, assumed Word compatibility or complete redline correctness despite comparison exclusions/warnings.
- Duplicated evidence stores, schema authorities, currency tokens, global state buses, cryptographic protocols or automatic human-decision lineage.

### Engine experiment checklist — use within T63

- [ ] Inspect actual selected-version CLI help, capability output and schema output; they are not interchangeable interfaces.
- [ ] Verify pinned binary/source integrity and license/notices, transitive components and packaging provenance.
- [ ] Allowlist operations/arguments; no shell command text from documents. Bound input, stdout/stderr/output artifacts and process descendants.
- [ ] Per-job scratch copy; no vault path, secret or other matter bytes. Enforce filesystem/network restrictions independently, including symlink and timeout behavior.
- [ ] Measured CPU/memory/process/decompression/wall-time bounds; terminate process tree and clean scratch safely.
- [ ] Validate response schema, exact expected edit, package, output digest and readback before activation; recheck evidence afterward.
- [ ] Store supplementary engine/locator provenance without changing CaseProof authority.
- [ ] Compare Python versus engine on same isolated and representative fixtures; document refusals, losses, host behavior, latency and operational cost.
- [ ] Publish explicit adopt/reject/continue-experiment decision. The experiment itself is a task; successful adoption is a later capability gate.

## 7. Complete fixture and adversarial checklist

Translate expectations to canonical states above. Verify existing tests first; missing executable coverage stays open. These identifiers originate in workflow v3.1; no source file says they all pass.

| Fixture | Required behavior | Task |
|---|---|---|
| FX01 | Confirmed printed p4/PDF p6/bundle p37 opens actual PDF p6 | T51–T52 |
| FX02 | Renderer page delta remains metadata, not mapping proof | T51–T52 |
| FX03 | Alternate renderer does not authorize automatic page tolerance | T51–T52 |
| FX04 | Missing/unconfirmed mapping abstains despite apparent layout | T51–T52 |
| FX05 | Renderer-dependent pagination disclosed; no ±2 shortcut | T51–T52 |
| FX06 | Cross-page quote shows both proven regions, or explicit limitation | T52, T56 |
| FX07 | Duplicate quotation gives multiple matches/unresolved target | T41, T56 |
| FX08 | Existing ligature/soft-hyphen/whitespace rules preserve visual gate | T56 |
| FX09 | Altered amount cannot become exact match | T56 |
| FX10 | Altered date cannot become exact match | T56 |
| FX11 | Changed negation cannot become exact match | T56 |
| FX12 | Low-confidence OCR remains ocr_unreliable, with preserved crop | T25, T52, T56 |
| FX13 | Rotation and transform remain correct | T52 |
| FX14 | Paraphrase has no unsupported quote-fidelity claim | T56 |
| FX15 | Revised draft produces new snapshot and historical decisions | T46–T48 |
| FX16 | Unsupported OOXML edit refuses and leaves original unchanged | T42–T43, T65 |
| FX17 | Lost acknowledgment remains unknown until durable reconciliation | T28, T34, T45, T55 |
| FX18 | Spreadsheet formula protection only when CSV becomes supported | T85 CONDITIONAL |
| FX19 | CropBox/zero-origin bounds remain correct | T52 |
| FX20 | Repeated paragraph cannot use silent first match | T41, T47 |
| FX21 | Uncertain lineage never auto-pairs or transfers review | T47–T48 |
| FX22a | Unconfirmed inventory cannot establish not_in_inventory | T51, T56 |
| FX22b | Confirmed entry without authorized source may yield source_missing | T51, T56 |

The original source groups FX02–05 as renderer-delta cases; their rows above are coverage checkpoints, not invented historical fixture specifications. Preserve the actual source fixtures when implementing them.

Additional required cases:

| Boundary | Checklist | Tasks |
|---|---|---|
| XML/archive | UTF8/UTF16 LE/BE with/without BOM, UTF32 policy, entities/DTD, corrupt/encrypted/duplicate/traversal, expansion/node/depth/time | T10–T11, T16 |
| Service | Malformed/invalid/non-dict/oversize HTTP200 JSON, missing/wrong-type report/source/finding fields | T12–T13 |
| Admission | Corrupt last file, exact boundary and one-over each bound, altered bytes, timeout and fresh signed readback | T22–T23, T28 |
| Processing | Worker/process death, lease fence, cancellation, partial OCR, unavailable engine, duplicate referenced pages | T24–T28 |
| Locator | Unrelated table/multiple runs/footnote, target and outside-target revisions, split text, repeated literal, namespaces and mc:Ignorable | T40–T43 |
| Durable writes | Double submit, same-ID changed payload, lost ack, concurrent activation/save/release, stale version, denied grants | T28, T34, T45–T46, T53, T55 |
| Viewer | Scan/text disagreement, three page spaces, missing geometry, mixed page size, rotation/CropBox, DPR<1/>1, 200% zoom and resize | T26, T51–T52 |
| Browser security | Expiry and late status/body/render, matter switch, hostile strings/links, cleanup, content type/size/redirect rejection | T50, T52, T55 |
| Release | Partial/complete/zero-findings policy, unique reviewed counts, HMAC/digest/size, tamper, cold reopen, old-schema compatibility | T30–T35 |
| DOCX | Raw XML-invalid characters, whitespace, formatted paragraphs/tables/notes, active content and external relationships, desktop host reopen | T15, T60–T65 |
| Privacy/ops | Cross-org/matter, revocation mid-operation, real RLS versus privileged catalog checks, backup restore/erasure, zero-residual fixtures | T70–T77 |

Test layers as affected: Python unit/integration, generated schema/AJV/TypeScript checks, frontend unit/architecture negatives, production-build Playwright/axe, disposable PostgreSQL/adversarial tests, genuine signed development journey, manual host/accessibility and independent representative review. Use the appropriate layer; do not substitute a mocked browser fixture for real signed acceptance.

## 8. Commands, evidence and completion

### Command selection

The following commands exist at the source baseline. Confirm scripts and lockfiles at the implementation head. Use the configured runtime and Python environment; do not install unrelated upgrades to obtain green checks.

From repository root:

```bash
uv run --locked python -m scripts.generate_frontend_contract --check
uv run --locked python scripts/check_architecture.py
uv run --locked pytest -q
```

For a narrow code iteration, select meaningful affected tests first. Full relevant CI and required disposable/security checks must pass before merge. Run Ruff/mypy on affected paths using the repository's CI configuration; include imported new helpers and negative controls.

When changing the consumed Python projection intentionally:

```bash
uv run --locked python -m scripts.generate_frontend_contract
```

Then from `frontend`:

```bash
npm ci
npm run contracts:generate
npm run contracts:check
npm run policy:check
npm run typecheck
npm run lint
npm test
npm run build
npx playwright install --with-deps chromium
npm run test:e2e
```

Run generation only for intentional contract changes. A docs-only task needs changed-scope/link/content review; no invented executable-test result. Do not weaken tests/headers/policy or alter expected results merely to pass. A Vite preview server is not the accepted production host.

Existing viewer comparison scripts are `npm run viewer:build`, `viewer:preview` and `viewer:test`; use when renderer behavior changes or adoption evidence must be renewed. Do not rerun a renderer experiment for a documentation-only edit.

Discover the actual protected workflow inputs and fixture-cleanup contract before triggering signed acceptance. No admin DSN, service key in browser, new human messages, production deployment or client files follows from this task list.

### Acceptance-to-layer evidence map

Paths below exist in the inspected workspace; confirm them against the implementation head. These are execution targets, not claims that the proposed regressions already exist or pass. Run commands from repository root unless stated otherwise.

| Acceptance requirement | Proving layer | Existing entry point / command | Evidence limit |
|---|---|---|---|
| Encoded hostile XML refusal and controlled extraction coverage | Python parser unit/regression | `uv run --locked pytest -q tests/test_docx_region_inventory.py tests/test_docx_text_regions_coverage.py` | Add encoding/security cases as needed; prove both extraction paths |
| Malformed RPC JSON and manifest guards | Python transport/application regression | `uv run --locked pytest -q tests/test_dossier_journey.py tests/test_f6_reviewed_exports.py tests/test_f6_trusted_release_transport.py` | Locate/add exact negative cases; file existence is not coverage |
| Historical schema and receipt compatibility | Python integration plus signed cold reopen | T07 identifies existing reader tests; release regressions above; existing protected signed journey | Offline tests cannot prove live authorization or restart behavior |
| XML characters, whitespace and package integrity | Python OOXML regression plus actual document host | `uv run --locked pytest -q tests/test_f6_docx_format_integrity.py`; T61 host receipt | Playwright does not establish desktop Word rendering |
| Error-to-UI state, expiry and unknown outcomes | Frontend unit plus production-host browser integration | In `frontend`: `npm test`, `npm run test:e2e`; T08 selects cases | Genuine signed acceptance remains separate from mocked transport |
| Changed consumed contracts | Generator, AJV and TypeScript | Root generator check and frontend contract/type checks below | Add old-format fixtures where T07 identifies compatibility gaps |

For each selected row record exact final-head command, test names, result and CI link. Determine timeouts from existing workflows and measured workload rather than inventing universal budgets. This documentation update does not execute or close these implementation checks.

### Required PR evidence

- Exact problem and resulting behavior, task IDs, implemented paths and contract/policy versions.
- Actual checks and result URLs at the final code head, skipped gates and reason, synthetic versus representative input.
- Independent review appropriate to tenant/security/evidence changes; real accountable reviewer where required.
- Known limitations, compatibility, migration/rollback and operational cleanup.
- Dated status update and relevant authoritative blueprint/ADR change. Do not force frontend blueprint edits for every pure backend repair.
- Fresh signed integrated evidence after material changes; keep older PR-head receipts historical and post-merge validation separate.

### Closure gates

**A task is DONE** only when its implemented or verified behavior meets its Done-when clause and evidence record is complete. Local work is not merged work. Do not check off a conditional feature merely because an experiment was discussed; record the decision and disposition.

**A bundle is merge-ready** when all required tasks in its agreed scope, meaningful regressions, required cloud checks and reviews pass, and GitHub protections allow merge. Do not bypass a protected branch or invent approval.

**Engineering complete** means the agreed required implementation across bundles is delivered, final signed end-to-end and adverse-case evidence exists, contracts/status are accurate, and remaining optional capabilities are explicitly decided or excluded.

**Pilot ready** additionally requires the supported capacity proved through the signed journey, rights-cleared representative dossiers, actual security/privacy/processing/retention/restore and accessibility evidence, practitioner validation, real owners and approved data terms. CI cannot close those independent gates.

### Resume handoff

At task end, record current branch/head, dirty paths, completed and unresolved task IDs, observed checks, next action and any genuine decision blocker. Do not stop at another plan or capability statement when the user has authorized implementation. If a decision blocks one task, continue other authorized unblocked work.

## 9. Provenance and maintenance

This file consolidates these three sources at CaseProof baseline `2a5420db21c010c39a27fc3d49fd05b2585d0f88`:

1. [Authoritative frontend blueprint](https://github.com/haytamAroui/caseproof/blob/2a5420db21c010c39a27fc3d49fd05b2585d0f88/frontend/BLUEPRINT.md): architecture and UI-01–UI-10 invariants, ownership, contracts, security, geometry, DOCX, review, accessibility/design, commands, F0–F6, P01–P10/W01–W08 and UF01–UF05.
2. [Workflow v3.1](https://github.com/haytamAroui/caseproof/blob/2a5420db21c010c39a27fc3d49fd05b2585d0f88/docs/CASEPROOF_WORKFLOW_BLUEPRINT_V3_1.md): S0–S13, canonical vocabulary, recovery, FX cases and stage acceptance.
3. [Implementation/reuse plan v1.2](https://github.com/haytamAroui/caseproof/blob/2a5420db21c010c39a27fc3d49fd05b2585d0f88/docs/CASEPROOF_HARDENING_PILOT_READINESS_AND_REUSE_PLAN_V1.2.md): workstreams 0/A–H, decisions, five bundles, 13 StetDoc and 15 Vaquill patterns and evidence boundaries.

Constitution/ADRs and applicable AGENTS retain authority. Actual versioned implementation determines installed behavior; if it conflicts with authority, fix the conflict explicitly rather than rewriting policy to excuse drift. This checklist is the operational entry point, not a fourth competing architecture specification.

### Source coverage index

| Source requirement | Included here |
|---|---|
| Blueprint §1–6 authority/stack/dependencies/contracts/privacy | §1–2; T01–T06, T12–T13, T55, T70–T74 |
| Blueprint §7–9 geometry/DOCX/findings/review | T25–T26, T40–T57 |
| Blueprint §10–11 accessibility, design, tokens/locale | §2; T33, T44, T50–T55, T75 |
| Blueprint §12–16 commands/CI/build/rollback/policy | §8; T04, T17, T72, T77, T79 |
| Blueprint §17–19 pages/panels/flows | §4 maps; T22–T57, T73, T75–T77 |
| Blueprint F1–F4 adoption/retrofitting appendices | Preserve existing state in §4; T02, T50–T57 |
| Workflow S0–S13 | Full §4 stage map |
| Workflow canonical enums/strictness | §2 |
| Workflow fixture/migration and recovery | §7; T28, T34, T45, T55–T56 |
| Plan 0 housekeeping | T01–T06 |
| Plan A hardening | T10–T17 |
| Plan B capacity | T20–T29 |
| Plan C preflight | T30–T35 |
| Plan D/E correction/comparison/coverage | T40–T49, T65–T66 |
| Plan F output | T60–T64 |
| Plan G operations | T70–T77, T79 |
| Plan H pilot evidence | T76, T78–T79 |
| Plan 28 repository patterns | Complete §6 mapping |
| Deferred Word/MCP/model/redaction/protocol features | T80–T85; approved native-output experiments T62–T65 |

### Change log

- v1.0 — 3 November 2026: Initial agent task consolidation. 71 task cards, complete S0–S13/P01–P10/W01–W08/FX and 28-pattern mapping. Baseline is merged plan commit; local hardening remains IN_PROGRESS. No implementation or acceptance status is newly claimed by generating this file.

- v1.1 — 3 November 2026: Added T07–T09 for historical-schema, error-contract and test-evidence verification (74 task cards total). Clarified independent bundle dependencies and measurement-first capacity selection. Existing local-work statuses and downstream task dependencies remain intact; no new runtime contract or acceptance is claimed.
