# CaseProof — End-to-End Evidence Workflow Blueprint v3.1

**Status:** Reconciled implementation proposal, **not** a replacement for repository authority or evidence of delivery.  
**Prepared:** 2 November 2026  
**Product:** Evidence-first verification of Belgian litigation DOCX briefs against inventories and text/scanned PDF exhibits; NL/FR/EN.  
**Target:** Existing Python/FastAPI backend and React/TypeScript frontend.  
**Source proposal:** `CaseProof_Workflow_Blueprint_v3.md` (v3.0).  
**Repository:** https://github.com/haytamAroui/caseproof

> **Authority rule:** `CONSTITUTION.md`, applicable ADRs, `docs/ROADMAP.md`, generated backend contracts and `frontend/BLUEPRINT.md` govern implementation. This document supplies a reconciled *workflow proposal*. Where a detail is unverified, it is explicitly `VERIFY` or `PROPOSED`. Do not silently create replacement APIs, statuses, databases, or milestone definitions.

## 1. Executive decision

Adopt v3.0's **S0–S13 journey, provenance, failure recovery, exceptions-first review and adversarial test ideas**. Reject wholesale adoption of its invented API surface, duplicate state machine, speculative `CitationPayload`, blanket page-tolerance rule, and unimplemented DOCX/manifest/signing architecture. Extend existing contracts through explicit ADR and regression tests only.

**Product promise:** CaseProof checks references against the bundle as filed, explains uncertainty, provides source crops for inspection, records human decisions durably and exports a reproducible review record. It does **not** certify legal correctness, semantic support, authenticity or filing compliance.

**Non-negotiable boundaries:**

1. Python application services own authorization, evidence resolution, verification and release; the browser does not compute or upgrade findings.
2. Identity, page mapping, fidelity, coverage and human review are distinct. Never display one global green/red or blanket “verified” result.
3. An extracted quote match does not establish semantic support; a crop locator does not establish mapping; no references detected does not prove complete review.
4. Originals are immutable; corrections are derivatives/new versions; prior receipts remain historically bound.
5. Every sensitive operation is authorized against current signed-user grants, matter, source version and snapshot. UI affordances are not permission checks.
6. Partial, unavailable, ambiguous, OCR-unreliable, representation-conflicted and not-assessed states remain visible. Abstain rather than guess.
7. A reviewer decision is saved only after durable server acknowledgment; unknown write outcomes must be reconciled, never optimistically marked saved.
8. Do not log document text, quoted passages, tokens or signed URLs; source identifiers and hashes may also be sensitive.
9. Model-generated notes, if ever enabled, are advisory and cannot mutate deterministic findings or human receipts.
10. Local deployment, synthetic browser tests or a signature alone do not prove zero egress, professional secrecy compliance or legal validity.

## 2. Architecture and compatibility decisions

| Topic | Actual CaseProof contract / direction | v3.1 decision | Classification |
|---|---|---|---|
| Backend authority | Python/FastAPI application and domain services | Preserve existing services; avoid parallel verification engines | KEEP |
| Frontend authority | `frontend/BLUEPRINT.md` v1.1 (2 Nov 2026), plus root constitution/ADRs/roadmap | Update that file only by explicit accepted change | KEEP |
| Frontend stack | Vite, React, strict TypeScript, React Router, TanStack Query, CSS tokens | Follow installed compatible versions and existing boundaries | KEEP |
| Contract pipeline | Pydantic → JSON Schema → generated TypeScript + AJV; PR #169 | No Zod, Orval or new OpenAPI generation stack | KEEP |
| Dossier output | `DossierView`, `FindingView` in `application/litigation/frontend_contract.py` | Preserve versioned `caseproof-dossier-v1` and `extra='allow'` extension semantics | KEEP |
| Identity | `not_assessed`, `not_in_inventory`, `source_missing`, `ambiguous`, `resolved` | No invented uppercase status layer | KEEP |
| Page mapping | `mapped`, `unmapped`, `conflicting` | Keep canonical enum; add explainable metadata only after contract review | KEEP |
| Fidelity | `not_assessed`, `ocr_unreliable`, `representation_conflict`, `translation_review_required`, `multiple_matches`, `exact_match`, `quote_not_found` | Preserve visual/literal gate and abstention | KEEP |
| Support | `not_assessed`, `supported`, `qualified`, `contradicted` | Distinguish mechanical report field from durable human review decision | KEEP |
| Viewer context | `ViewerContext` with bounded page/region metadata | Use existing version/hash-bound viewer and crop API | KEEP |
| Inventory confirmation | `InventoryConfirmation` with bundle signature, entries and completeness | Reuse strict request boundary, confirm actual endpoint behavior | KEEP |
| Intake | `IntakeCommand`, `IntakeFile` and existing workspace intake | Preserve current four-original development contract; broader intake requires separate design | KEEP / EXTEND |
| Session | `LoginBody`, `SessionView`, signed workspace auth | Preserve server-side checks, fail closed and avoid token persistence | KEEP |
| HTTP surface | Existing `/v2/...` workspace/dossier routes | Map screens to existing routes; do **not** implement proposed `/api/v1/...` API | REJECT REPLACEMENT |
| `CitationPayload` | No established canonical model in inspected frontend contract | Do not introduce as a prerequisite | DEFER |
| DOCX tracked-change writer | Existing bounded correction preview/commit and derived export | Do not promise native OOXML tracked-change editing without host tests | DEFER |
| RFC 8785 / Ed25519 | Not established as canonical manifest format in inspected contracts | Do not migrate export or claim signatures without independent review | DEFER |
| Optional model notes | Not required for evidence-first M3 | Explicitly optional, isolated, policy-controlled | DEFER |

**Verified repository pointers (at document drafting):**

- [Frontend blueprint](https://github.com/haytamAroui/caseproof/blob/main/frontend/BLUEPRINT.md)
- [Dossier projection](https://github.com/haytamAroui/caseproof/blob/main/application/litigation/frontend_contract.py)
- [Viewer contract](https://github.com/haytamAroui/caseproof/blob/main/application/litigation/viewer_contract.py)
- [Workspace intake](https://github.com/haytamAroui/caseproof/blob/main/apps/api/workspace_intake.py)
- [Workspace auth](https://github.com/haytamAroui/caseproof/blob/main/apps/api/workspace_auth.py)
- [Dossier journey](https://github.com/haytamAroui/caseproof/blob/main/apps/api/dossier_journey.py)
- [Merged contract hardening PR #169](https://github.com/haytamAroui/caseproof/pull/169)

## 3. User journey and stage-to-system map

```text
S0 Signed access + matter selection
  → S1 Original intake and durable readback
  → S2 Extraction / OCR / provenance
  → S3 Inventory + page-map confirmation
  → S4 Draft reference discovery
  → S5 Canonical verification snapshot
  → S7 Findings and source inspection
  → S8 Human review and durable decision
  → S9 Optional correction → new draft version → recheck
  → S10 Export reviewed results
  → S11 Reopen exact historical snapshot

S6 Optional AI notes: OUT OF CRITICAL PATH
S12 Failure/retry/reconciliation: CROSS-CUTTING
S13 Authorization/privacy/retention: CROSS-CUTTING
```

The workflow diagram describes user outcomes, **not** new route definitions. Stage completion is not implied by existence of a Python class.

### S0 — Access, organization and matter

**UI:** Signed-user entry, permitted matter list, matter creation where authorized, session expiry and re-authentication. **Backend:** Existing workspace auth/catalog and matter authorization. **Safety:** On matter switch or revocation, cancel reads, clear in-memory scoped caches, discard late responses and reauthorize; never show matter A bytes in matter B. **Acceptance:** Delayed-response, cross-matter and revoked-user browser tests. **Status:** Existing building blocks; complete signed-user journey acceptance must be demonstrated.

### S1 — Intake and original preservation

**UI:** Four-file intake for current development contract (DOCX draft, UTF-8 inventory, two PDFs), progress, digest/readback outcome and retry instructions. **Backend:** `IntakeCommand`, `IntakeFile`, `WorkspaceIntake`, strict file/container preflight, immutable private Storage and signed readback. **Safety:** Registration is not proof of upload; unknown write outcome reconciles via existing durable state. No blind replay. **Acceptance:** Corrupt final file causes no writes; changed bytes fail digest; lost ack requires fresh readback; unauthorized write denied. **Future:** Arbitrary-N exhibits is a separately versioned contract, not an implicit v3.1 requirement.

### S2 — OCR, source extraction and geometry

**UI:** Processing status, partial/unreadable page notice, image crop and original-source link. **Backend:** Existing PDF OCR geometry sidecars and crop retrieval, PDF visual fidelity and DOCX region extraction. **Safety:** Preserve original SHA-256, source version, coordinate space, parser provenance and OCR uncertainty. Zero coordinates are valid. **Acceptance:** Rotated/CropBox pages, zero-origin bounding box, scan/text disagreement, incomplete OCR, cold restart and crop-to-original match. **Proposed enhancement:** Persist additional transform metadata only where current geometry contract lacks it; do not replace proven crop handling.

### S3 — Inventory and pagination confirmation

**UI:** Explicit inventory-complete toggle and per-exhibit confirmation; distinguish printed page, exhibit PDF page and bundle page. **Backend:** Existing `InventoryConfirmation`, `IdentityConfirmation`, `PageConfirmation` and snapshot/bundle signature. **Safety:** An unconfirmed inventory cannot justify `not_in_inventory`; an absent authorized original can yield `source_missing` when otherwise established. **Acceptance:** Confirmed printed p.4 → PDF p.6 mapping opens page 6 without inventing a page delta. **Proposed enhancement:** Rich mapping visualization, not a new state vocabulary.

### S4 — Draft reference discovery and coverage

**UI:** Found references with context; visible unsupported/unparsed regions and detection limitations. **Backend:** Existing DOCX reference discovery and regional text extraction. **Safety:** Never equate “zero references detected” with “all claims checked.” **Acceptance:** NL/FR/EN references, repeated labels, missing inventory references and unsupported notation. **Proposed:** Distinguish quotation/paraphrase/uncited assertion in a versioned extension only after parser evidence and schema review; do not add speculative `CitationPayload`.

### S5 — Verification and frozen report

**UI:** Per-finding identity, page mapping, fidelity and coverage with reasons and source links. **Backend:** Existing canonical dossier verification and `DossierView`/`FindingView`. **Safety:** `exact_match` is not legal support; `representation_conflict` and `ocr_unreliable` block unsupported certainty; no automatic ±2-page tolerance. **Acceptance:** Stable snapshot for identical inputs, stale version denial, changed numbers/dates/negation, ligature/soft-hyphen handling, scanned split-view conflicts, multiple candidate matches and page unmapped abstention. **Proposed:** Guarded-token diff metadata as a non-authoritative detail field after calibration.

### S6 — Optional model notes (non-blocking)

**UI:** Only if policy enables, clearly labeled as unverified suggestions. **Backend:** Separate advisory channel without write access to canonical finding states, reviewer decisions or exports. **Safety:** Untrusted document text must never become instructions; data location and model transport need explicit approval. **Status:** DEFER; no dependency from S7–S11.

### S7 — Signed-user reviewer workspace (M3 priority)

**UI:** Exceptions-first findings list with show-all, keyboard navigation, source/crop viewer, selected reference details, printed/PDF/bundle page labels and explicit uncertainty explanations. **Backend:** Existing signed dossier report and viewer context; no client-side verdict computation. **Safety:** Bind every view to matter, reference, source version and snapshot; discard stale responses. Unresolved anchors show notice, not fake highlight. **Acceptance:** Correct crop at 200% zoom, no cross-matter leaks, text-vs-image conflict visible, screen-reader semantics and mobile/narrow-width graceful fallback. **Implementation rule:** Use existing frontend feature boundaries and PDF.js viewer adapter; no parallel viewer stack.

### S8 — Human decision and durable review

**UI:** Confirm supported, qualify or contradict, with appropriate rationale, clear pending/unknown/saved states and Save & Next. **Backend:** Existing signed review/decision endpoints and durable receipts. **Safety:** Only server-confirmed decision is saved; recheck snapshot currency; unknown write outcomes reconcile before retry. **Acceptance:** Double-submit, lost ack, stale snapshot, revocation during write, reload and cold restart preserve exactly one authorized decision. **VERIFY:** Align UI labels and rationale requirements with actual `DecisionBody` and persisted decision enum; do not assume the v3.0 uppercase receipt schema exists.

### S9 — Correction and recheck

**UI:** Bounded edit preview, original vs derivative, blockers, explicit commit and mandatory recheck. **Backend:** Existing `CorrectionPreviewBody`, `CorrectionCommitBody`, draft revision service and corrected DOCX derivative. **Safety:** Original untouched; new version and snapshot; old human decision never silently applies to changed content. **Acceptance:** Supported single-paragraph correction, stale hash, unsupported OOXML structures, retry/reconciliation, prior receipt remains historical. **DEFER:** Full Word tracked changes, universal paragraph locator and automatic lineage matching.

### S10 — Scoped reviewed export (M4)

**UI:** Export preview showing checked/unchecked findings, version IDs, coverage limitations, review decisions and output type. **Backend:** Existing canonical report projection, signed receipt/attestation where actually implemented, JSON/Markdown and supported DOCX exports. **Safety:** Verify stored bytes, snapshot/hash, actor grants and reopening; never call a machine result “certified.” **Acceptance:** Tampered bytes fail, stale export denied or explicitly historical, cold re-download equals frozen artifact. **DEFER:** New JCS/Ed25519 protocol and CSV unless separately approved.

### S11 — Reopen and audit

**UI:** Historical/current snapshot distinction, exact prior source version, review record and export retrieval. **Backend:** Persisted signed review and snapshot readback. **Acceptance:** Sign out, restart worker/browser, sign back in, reauthorize and compare report/receipt/export bytes; revoked actor cannot reopen.

### S12 — Recovery and unknown outcomes (cross-cutting)

| Failure | UI behavior | Backend requirement | Regression |
|---|---|---|---|
| Expired/revoked session | Clear scoped state, stop requests, reauthenticate | Recheck current grant | Cross-matter late-response denial |
| Lost upload acknowledgement | Show **unknown outcome**, not success | Reconcile durable registration + exact signed readback | No duplicate originals |
| Lost review acknowledgement | Keep unsaved local input; show unknown | Query durable receipt/idempotency result | One decision only |
| Stale snapshot/version | Block consequential action; refresh and compare | Reject stale commit | No silent rebase |
| Partial OCR/geometry | Mark unassessed regions; allow inspection | Resume safely from durable stage | No fabricated crop |
| Interrupted source read | Discard partial bytes | Reauthorize and retry read | No partial display |
| Worker crash | Show resumable state | Durable lease/recovery | No duplicated result |

**Do not prescribe new header names or HTTP codes unless current endpoint contracts require them.**

### S13 — Privacy, retention and deployment boundary (cross-cutting)

Private Storage, row-level authorization, signed-user access, source revocation, retention/purge and operator separation are backend responsibilities. Do not store bearer tokens or sensitive quotes in persistent browser storage. Operator, data-residency, no-network, legal-professional secrecy and external security-review gates remain separate from functional CI. Clearly disclose OCR/model processing locations and limits before pilot use.

## 4. Canonical contract vocabulary

Use these exact `FindingView` states unless a separately reviewed versioned contract supersedes them:

```text
identity:     not_assessed | not_in_inventory | source_missing | ambiguous | resolved
page_mapping: mapped | unmapped | conflicting
fidelity:     not_assessed | ocr_unreliable | representation_conflict |
              translation_review_required | multiple_matches | exact_match | quote_not_found
support:      not_assessed | supported | qualified | contradicted
```

Do **not** convert v3.0's `PAGE_CONSISTENT`, `TEXT_EQUIVALENT`, `QUOTE_AMBIGUOUS`, `NOT_APPLICABLE`, `PAGE_RENDERER_DEPENDENT` or `TEXT_DIFFERS` into new public enum values by default. They are **candidate explanatory concepts**, not the canonical contract. Add non-authoritative detail metadata only with a proven use case, documented semantics, generator output and positive/negative cross-language tests.

**Request DTO strictness:** `extra='forbid'` at appropriate strict API boundaries. **Response compatibility:** preserve intentional `extra='allow'` on `DossierView` and `FindingView`. **Generation:** Pydantic → JSON Schema → TypeScript/AJV; generated artifacts are not manually edited.

## 5. Screen and component plan (M3/M4)

| Screen | Core UI | Existing owner | Gate |
|---|---|---|---|
| Session / organization | Sign-in, session expiry, permitted organizations | `src/app` + shared auth | S0 |
| Matter catalog | Matter list/create/select | `src/features/matters` | S0 |
| Intake | Four-original upload, validation, readback, confirmation | `src/features/intake` | S1–S3 |
| Findings workspace | Exceptions-first list, dimensions, coverage, snapshot | `src/features/verification` | S4–S5, S7 |
| Evidence viewer | PDF/crop, page map, selected source region | `src/features/evidence` | S2, S7 |
| Review panel | Decision, rationale, durable receipt, retry state | Existing feature boundary; verify directory | S8 |
| Correction preview | Bounded edit and recheck | Existing feature boundary; verify directory | S9 |
| Export / history | Reviewed export, integrity, cold reopen | Existing feature boundary; verify directory | S10–S11 |

**Navigation:** Session → Matter → Intake/confirmation → Findings → Evidence + review → optional correction/recheck → Export → History. Every screen must support loading, empty, partial, error, stale and revoked states. Keep a single selected finding/source context. Do not introduce a heavy grid or new component library without measured need.

## 6. Test and fixture migration from v3.0

The original 22 cases are **candidate coverage**, not 22 passing tests. Translate expected outcomes to canonical CaseProof states, and split ambiguous expectations. Prioritize:

| Candidate fixture | v3.1 expectation | Priority |
|---|---|---|
| FX-01 printed p4/PDF p6/bundle p37 | Confirmed mapping → `mapped`, viewer opens PDF p6 | P0 |
| FX-02–05 renderer page deltas | Record renderer metadata; **no automatic ±2 tolerance**; abstain if mapping unconfirmed | P2 |
| FX-06 cross-page quote | Both page regions shown if proven; no fabricated geometry | P1 |
| FX-07 duplicate quote | `multiple_matches` / unresolved pinpoint; no silent first match | P0 |
| FX-08 ligatures/hyphens/quotes | Apply existing fidelity normalization policy; preserve visual conflict gate | P0 |
| FX-09–11 amount/date/negation changes | Never `exact_match` after substantive alteration; preserve conflicting evidence | P0 |
| FX-12 low-confidence OCR | `ocr_unreliable`; retain raw crop and uncertainty | P0 |
| FX-13,19 rotation/CropBox/zero | Correct normalized crop and bounds at x=0 | P0 |
| FX-14 paraphrase | No quote-fidelity claim without quotation evidence; coverage limitation explicit | P1 |
| FX-15,21 revised draft / lineage | New snapshot, old decisions historical; ambiguous pairing not automatic | P1 |
| FX-16 unsupported OOXML edit | Safe rejection; original unchanged | P0 |
| FX-17 lost acknowledgement | Unknown outcome + durable reconciliation; no blind replay | P0 |
| FX-18 spreadsheet formula injection | Only required if CSV export becomes supported | DEFER |
| FX-20 duplicate paragraph | No silent first-match locator | P1 |
| FX-22 incomplete inventory | **Split into two fixtures:** (a) inventory unconfirmed → cannot conclude `not_in_inventory`; (b) confirmed item with missing authorized source → `source_missing` where established. Do not assert both for same unresolved input | P0 |

**Required test layers:** Python unit/integration, live signed-user/RLS denial, generated schema drift, AJV runtime, TS compile-time narrowing, Vitest UI state tests, Playwright keyboard/accessibility and cold restart. CI green is not a substitute for real-file legal review or independent security assessment.

## 7. Delivery sequence and acceptance evidence

### PR-A — Blueprint reconciliation (documentation only)

- Map each S0–S13 stage to actual route, model, frontend feature, test and owner.
- Mark `EXISTS`, `EXTEND`, `NEW`, `DEFER` or `REJECT` with file references.
- Resolve discrepancies in `frontend/BLUEPRINT.md` through an approved change, without changing constitutional/ADR authority.
- **Done when:** every claimed implementation has a link and a passing test; missing capabilities remain explicitly OPEN.

### PR-B — M3 reviewer closure

- Signed matter selection → intake confirmation → canonical findings → source crop → human decision → cold reopen.
- Handle stale snapshot, revocation, slow fetch, unknown write outcome and OCR uncertainty.
- **Done when:** signed-user end-to-end acceptance runs on real-format NL/FR/EN fixtures and no unsupported verdict upgrades occur.

### PR-C — Adversarial fidelity and recovery suite

- Implement highest-value P0 fixture gaps using existing engines, no new public state vocabulary.
- Verify source-image disagreement, page mapping, OCR abstention, wrong amount/negation, unknown writes and rotated crops.
- **Done when:** deterministic regression and honest-abstention assertions pass; calibration claims are evidenced.

### PR-D — M4 reviewed export and cold reopen

- Recheck frozen snapshot, authorization, review receipt and export bytes across restart.
- **Done when:** a signed user can reopen the exact historical reviewed artifact; tampering and revocation fail closed.

### Later research / separate approvals

- General-purpose DOCX structural indexing and tracked changes.
- Automatic finding-lineage matching and multi-renderer page calibration.
- RFC 8785 manifest migration, Ed25519 registry/rotation and CSV output.
- AI notes, Word host integration, packaged offline engine, legal/ethics/security opinions and paid practitioner pilot.

**Milestone discipline:** Keep repository M0–M5/M3–M4 definitions; do not rename them from the proposal. Pilot acceptance requires actual lawyer review, measured false-verification rate, data-handling terms and independent legal/security gates—not just synthetic tests.

## 8. Architecture decision and change-control template

For any proposed contract or workflow change, record:

```text
Decision ID / accountable owner:
Existing code + generated schema + route:
Problem observed in real fixture or user workflow:
Proposed change and why existing behavior is insufficient:
Security / compatibility / privacy impact:
Migration and rollback:
Python, AJV, TypeScript and browser tests:
Human acceptance and remaining limitations:
```

No change to canonical enum vocabulary, public route shape, retention semantics, review receipt or export digest should be merged without that record and tests. Preserve the contract validation decision merged in PR #169.

## 9. Outstanding verification before repository adoption

- Inventory every actual `/v2/...` route and compare it to S0–S13. This document intentionally does not invent an endpoint table.
- Check frontend feature directories and screens on current `main` before marking them implemented.
- Confirm persisted review enum, receipt, rationale and idempotency behavior from current code and live acceptance.
- Confirm export formats and signature semantics; never infer them from a proposed manifest.
- Confirm which 22 fixture scenarios already have equivalent tests; avoid duplicating coverage.
- Reconcile the proposed changes with `frontend/BLUEPRINT.md` and `docs/ROADMAP.md` in a dedicated reviewed PR.

## 10. Sources and provenance

- User-supplied *CaseProof — End-to-End Document Evidence Workflow, Builder’s Blueprint v3.0*, used as the source of the S0–S13 flow and FX-01–FX-22 candidate tests.
- CaseProof repository and contracts linked in §2, including authoritative frontend blueprint and merged PR #169.
- External commercial/open-source references in v3.0 are **design inspiration only**, not proof of CaseProof functionality, benchmark performance, legal compliance or code-license permission. Re-verify sources and licenses before implementation.

**Bottom line:** Build the lawyer's evidence-first journey on CaseProof's existing engine and contracts. Treat every proposed extension as an explicit, testable gap—not a reason to rewrite working infrastructure.