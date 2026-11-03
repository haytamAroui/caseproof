# CaseProof — Complete Hardening, Pilot Readiness and Repository Reuse Plan v1.2

**Date:** 3 November 2026
**Baseline:** `main` at `43550e9` (PR #178, F6 merged). F1 to F6 are on `main`.
**Status:** Proposed engineering plan. Consolidates the post-F6 audit, blueprint v1.0, reviewed plan v1.1 and StetDoc/Vaquill reuse analysis. Consolidation does not mean implemented, merged into the repository or accepted for a pilot.
**Authority:** `CONSTITUTION.md`, ADRs, `docs/ROADMAP.md`, `frontend/BLUEPRINT.md` and workflow v3.1 govern. This plan proposes work and creates no new milestone, state value or public route by itself. Material architectural, policy and public-contract changes require the applicable ADR or documented amendment (section 13); routine compatible fixes do not automatically require a new ADR.

## 0. How to read this plan

| Tag | Meaning |
|---|---|
| **[V]** | I read the source or repo document myself. |
| **[C]** | Reported by the ChatGPT audit at `43550e9`; I did not verify it. |
| **[D]** | Stated in a repo acceptance document; not independently re-run. |
| **[NEW]** | An improvement I add beyond the three source plans. |
| **[OPEN]** | Needs inspection or an owner decision before it is a requirement. |

The source plan author ran no tests or live configuration checks. This consolidation incorporates additional targeted CaseProof source inspection and GitHub metadata verification. No new tests, Word-host execution or live Supabase inspection were performed to generate this document. See sections 19 and 24 for evidence boundaries.

## 1. Goal and non-goals

**Goal:** a complete pilot journey: intake a realistic dossier, review evidence with explicit coverage, safely correct supported text, recheck, release clearly scoped results and reopen the exact historical artifacts, all in the genuine signed web journey.

**Non-goals (deferred by workflow v3.1):** Word add-in write path, hosted MCP exposure, RFC 8785 or Ed25519 signing, AI notes, CSV export, general DOCX structural indexing, native tracked changes without a separate capability decision.

**Retain unchanged:** Python services as verification and authorization authority; separate identity, page mapping, fidelity, coverage and human-decision dimensions; immutable originals; version-bound findings; durable correction reservation, verified readback and activation; explicit unknown outcomes; server-authorized release with artifact hashes; existing frontend feature boundaries and the Pydantic to JSON Schema to TypeScript/AJV pipeline.

## 2. Verified starting point

| Area | State at `43550e9` | Evidence |
|---|---|---|
| Delivery | F1 to F6 merged; F6 merged 3 Nov 2026 at 11:06 UTC | [V] commit history |
| Docs | `docs/STATUS.md` newest entries stop at F1 to F3 | [V] |
| Intake | One DOCX, one UTF-8 text inventory, two PDFs; 5 MiB per file; 12 MB aggregate; 64 pages per PDF | [D] STATUS; [C] `workspace_intake.py` |
| Visual assessment | Budget of four distinct source-version/page pairs, not every uploaded page | [C] `dossier_journey.py`; [D] STATUS |
| Discovery XML | Byte search for `<!DOCTYPE` then stdlib `ET.fromstring` in text extraction (and region inventory per [C]) | [V] `docx_text_regions.py` |
| Export XML | Derivative package validated with `defusedxml` on every `word/*.xml`, `.rels` and content-types part | [V] `dossier_docx_export.py` |
| Correction | Resolver globally rejects unsupported body structure and multiple runs; writer separately restricts the target to a direct-body paragraph with one run and one `w:t`. Both must agree on expanded support. | [V] targeted code inspection |
| Corrected output | In-text replacement in the derivative; no tracked changes | [V] |
| Annotated DOCX | Original preserved; appended paragraphs with `str()` of dicts for coverage, abstentions, verification contract | [V] |
| Release | `release_ready = len(human_decisions) > 0`; receipts rechecked on replay, list, status and bytes; idempotent | [V] `dossier_export_release.py` |
| Release manifest | Direct dict indexing without a guard | [V] |
| `rpc()` | `json.loads(raw)` without error handling (unlike `export_rpc`) | [V] `dossier_journey.py` |
| Supabase | Receipts note SECURITY DEFINER advisor warnings and disabled leaked-password protection on dev | [D]; live state [OPEN] |
| F5 history | A protected run failed shortly after sign-in; cause not established | [D] |
| F6 browser tests | Mocked production-build tests plus genuine signed acceptance. Later run `41623751514` succeeded at PR head `c0e7d44b42b137c80b568e44ccbce28acad3ee97`; distinguish this from older receipts at `deceb69` and post-merge evidence. | GitHub metadata rechecked; see section 24 |

## 3. Workstream map

| ID | Workstream | Workflow stages | Required outcome |
|---|---|---|---|
| 0 | Housekeeping and process | cross-cutting | Records match reality; CI churn reduced |
| A | Parser and service hardening | S2 to S5 | Hostile XML and malformed responses fail predictably |
| B | Pilot capacity contract | S1 to S5, S12 | One documented envelope works end to end |
| C | Release preflight | S7 to S11 | Eligibility, completeness and coverage visible independently |
| D | Correction usability | S9 | Supported targets editable despite unrelated complex content |
| E | Explainable preview and recheck | S7 to S9 | Reviewers understand changes between snapshots |
| F | Useful DOCX output | S10 to S11 | Readable, accurately scoped output that opens in Word |
| G | Operational acceptance | cross-cutting | Security configuration and end-to-end evidence recorded |
| H | Pilot evidence (non-code) | M5 | Representative validation, practitioner results, approvals |

## 4. Workstream 0: Housekeeping and process

| Item | Work | Done when |
|---|---|---|
| 0.1 | Add F4, F5 and F6 entries to `docs/STATUS.md`, each with PR, final SHA, run links and remaining gates. | STATUS matches the commit history |
| 0.2 | PR-A from workflow v3.1: map S0 to S13 to actual route, model, frontend feature, test and owner; mark `EXISTS`, `EXTEND`, `NEW`, `DEFER`. Inventory every `/v2/...` route. | Table committed; no invented endpoints |
| 0.3 | Existing pre-commit/pre-push hooks run architecture checks and pytest. Add documented formatter/linter commands and enable hooks explicitly in developer setup. Keep CI authoritative. | Relevant local checks run before push; reduced churn is a process metric, not a correctness gate |
| 0.4 | Recheck the ADR index before allocating numbers; 0033–0037 below are provisional. | No number collisions; material decisions linked |
| 0.5 | Add a "final-SHA evidence" line to each acceptance doc: exact SHA, workflow links, what the evidence does not cover. [NEW] F6's own doc says earlier green commits do not prove later changes. | Template in use |
| 0.6 | Keep a single decision log (section 12). [NEW] | Owner decisions recorded with date |

## 5. Workstream A: Parser and service hardening

### Implementation

| ID | Change | Notes |
|---|---|---|
| A1 | One shared safe XML parsing boundary for inventory and extraction: `defusedxml` with `forbid_dtd`, `forbid_entities`, `forbid_external`. | The anchor module and export validator already use it. Replace stdlib `ET` in discovery. |
| A2 | Keep the raw byte search only as a cheap pre-check, never as the control. | UTF-16 and UTF-32 store `<!DOCTYPE` as multi-byte characters |
| A3 | Let the safe parser handle supported XML declarations/BOMs, including UTF-16 LE/BE with and without BOM where supported. Explicitly reject unsupported encodings; never decode lossily. UTF-32 may be rejected. | Define controlled package-level versus part-level outcomes |
| A4 | Preserve existing package, part-count, part-size and total-expanded-byte limits. Inspect actual decompression enforcement. Add measured XML depth/node limits and execution bounds where absent. | Depth/node bounds are proposed protections, not verified existing controls |
| A5 | `DossierStore.rpc()`: handle JSON decoding errors with a controlled service failure. Preserve the existing non-dict rejection and bounded response read. Compare all RPC adapters for consistency. | Non-dict checking already exists |
| A6 | `release_manifest` and related release code: validate required keys and types of the frozen report once at the boundary; malformed internal data gives a controlled service failure. | Malformed backend data is a server-side fault, not a client 422 |
| A7 | Check `reserved.get("original_sha256") != digest` against the SQL and rename if it is only a naming issue. | |
| A8 | Preserve significant whitespace. For XML-invalid OCR characters, refuse with a stable reason or use a visible substitution plus an explicit transformation record. Never silently strip evidence text or alter originals. | Validate emitted XML and reopen the derivative |
| A9 | Fuzz targets for DOCX entry points (package, `document.xml`, `.rels`, content types), seeded with real OOXML fragments, run in CI for a bounded time. [NEW] | Pattern from StetDoc's four targets |
| A10 | Error responses carry stable codes and no document text, quotes, hashes of sensitive identifiers or signed URLs. | Constitution rule |

### Tests

- UTF-8 hostile XML with DOCTYPE and internal entity: refused or unscanned; text never expands.
- UTF-16 LE and BE, with and without BOM, same payload: same result.
- UTF-32: matches the decision in A3.
- Corrupt ZIP/XML: controlled package rejection or scoped unscanned outcome. Part-level salvage is allowed only when region identity, coverage denominator and provenance remain trustworthy; never promise it for every corruption.
- Malformed HTTP-200 JSON; non-dict JSON; oversize body (`rpc()` and release paths).
- Frozen report missing each required key; wrong types.
- Normal extraction and export regressions pass.

**Sizing:** separate small fixes from the larger fuzz/resource-limit work. **ADR:** routine hardening normally needs no new ADR; new externally visible coverage or encoding behavior needs documented contract review. Record actual validation in STATUS.

## 6. Workstream B: Pilot capacity contract

### The problem

"Supports 200 pages" means different things in each layer. The earlier 200-page worker acceptance is worker-only and does not prove the authenticated end-to-end application. Raising one constant is insufficient and can replace an explicit refusal with unreliable processing.

### Capacity layers

| Layer | Today | Decision required |
|---|---|---|
| Upload transport | 4 files; 5 MiB each; 12 MB total | Max files, per-file and total bytes, timeouts, interrupted-upload behaviour |
| Parsing and OCR | 64 pages per PDF | Page caps, OCR time and memory per page, concurrency |
| Page mapping | Per-exhibit confirmation | Usability and validation at N exhibits |
| Visual assessment | 4 distinct source-version/page pairs | Budget as a function of dossier size, scheduling policy, time and memory bounds |
| Durable progress | Worker recovery proven separately | Same guarantees on the signed path |
| Report and manifest | Export caps: JSON 2 MB, Markdown 2 MB, DOCX 5 MiB [V] | Growth with finding count |
| Browser | Findings list and viewer | Large lists, narrow width, keyboard use |

### Candidate envelope (hypothesis for the owner, not a requirement)

The roadmap's 50 to 200 page range is a research assumption. A staged approach lets you learn before committing:

| Tier | Purpose | Candidate shape (placeholders to measure and set) |
|---|---|---|
| Current | Installed limits, not proof of every boundary combination | 1 DOCX, 1 inventory, 2 PDFs, 64 pages each, 12 MB total; four distinct visually assessed page pairs |
| Pilot-1 | First practitioner trials | Small multi-exhibit dossier |
| Pilot-2 | Roadmap target | Roadmap-scale dossier (50 to 200 pages total) |

The actual numbers are decision 1 in section 12.

### Implementation

| ID | Change |
|---|---|
| B1 | ADR 0033 "Pilot envelope and capacity contract": one limit per layer, a stable refusal reason per limit, and the rule that anything beyond the envelope is refused explicitly and early, never degraded silently. |
| B2 | Centralize policy in one versioned capacity profile in the application layer; expose the applicable limits through the API so the UI and generated contracts read the same values. |
| B3 | Extend existing whole-intake preflight rather than rebuilding it: validate complete counts, sizes, page counts and types against the selected capacity profile before any original is written. Refusals name the limit. |
| B4 | Measure first: time and peak memory for intake, parsing, OCR, visual assessment, report generation and export at the envelope, through the authenticated path. Extend the existing benchmark harness to the signed application path. |
| B5 | Replace oversized synchronous work with bounded durable processing: queue, concurrency limit, per-job timeout and cancellation, checkpoint and resume. |
| B6 | Decide whether budget exhaustion rejects the check or yields an explicitly partial snapshot. This changes current refusal behavior and belongs in the capacity ADR. If partial snapshots are adopted, define a versioned stable scheduling order, assessed/eligible-page and assessed/finding denominators, unassessed reasons, resumption and export semantics. No finding disappears. |
| B7 | Page-mapping validators, frontend forms and generated contracts aligned with the new limits (including `pdf_page` bounds now fixed at 64 in confirmation models [V]). |
| B8 | Privacy-safe operational metrics [NEW]: durations, counts and memory only; no document text, quotes or signed URLs. |
| B9 | Synthetic dossier generator [NEW] producing envelope-size NL/FR/EN dossiers (clean text PDFs, scans, repeated source pages, rotations) with fixed seeds and recorded hashes. |

### Acceptance

- One dossier at the chosen boundary passes the full genuine signed browser journey: sign-in, intake, confirmation, check, review, correction, recheck, release, cold reopen, teardown with zero residual.
- Cases at the boundary: scans, repeated source pages, interrupted upload, lost acknowledgement, worker restart, revoked actor mid-run.
- A dossier one step over each limit is refused with its stable reason at the earliest layer.
- No unreliable partial processing; partial results are labelled.
- Out of scope here: customer OCR location, egress and retention approval (separate gate).

**Size:** L. **Needs ADR:** yes (0033). **Depends on:** owner decision 1.

## 7. Workstream C: Release preflight

### Three independent concepts

| Concept | Meaning |
|---|---|
| Release eligibility | Actor, current draft and snapshot, sources and artifact requirements pass |
| Review completeness | Every finding that requires review has an applicable human decision |
| Coverage | Inspected and uninspected scope, with reasons |

### Server projection (server-computed policy result; preview is point-in-time)

- `can_release` plus blocking reason codes.
- Findings total, requiring review, reviewed, unreviewed.
- `review_complete` and `incompleteness_reasons`.
- Coverage limitations (regions unprocessed, OCR-unreliable, unmapped pages, sources not assessed).
- Current or historical snapshot status.
- Authorized remediation targets: finding, source or coverage region links.
- The server recomputes eligibility when releasing; the preview is advisory. [V] today `release()` rechecks draft currency and decision presence but not completeness.

### Implementation

| ID | Change |
|---|---|
| C1 | ADR "Release eligibility and review completeness" including decision 2 (does incomplete review block any release type). |
| C2 | Add the fields above to the preview; compute them in one shared function used by preview and release. [NEW] |
| C3 | Manifest records the same counts, completeness flag and reasons, so a historical release states what it covered. |
| C4 | Release scope label: "Partial reviewed report" versus "Complete reviewed report". Never imply completeness from one decision. [NEW] |
| C5 | Exports screen checklist: each unresolved item links to its finding, source or coverage region using the existing viewer path and snapshot. |
| C6 | Preserve exact-byte historical release behaviour and receipt rechecks. |

### Acceptance

If the approved policy permits partial reviewed release: one decision with other required findings unreviewed gives eligible true, complete false and a partial label. If a release type requires complete review: the same case blocks with a reason. Define eligibility for zero findings, zero decisions, qualified/contradicted decisions and unsupported scope. Count applicable unique finding decisions, not raw ledger rows. Stale or revoked requests block. Lost acknowledgement reconciles. Tampering refuses. Preview and release use the same policy but release recomputes it against fresh state. Historical artifact retrieval is a separate authorization path.

**Size:** M. **Needs ADR:** yes. **Depends on:** owner decision 2.

## 8. Workstream D: Bounded correction support

### Shared locator contract

Resolution, preview and writing change together. Each target binds to:

- Preserved source version and SHA-256.
- XML part and structural location.
- Declared text-offset encoding and range.
- Exact expected text.
- Supported editing capabilities.

Capabilities and refusals use stable reason codes so the UI can explain them. [NEW]

### Delivery sequence

| Step | Supported case | Notes |
|---|---|---|
| D0 | Baseline measurement | First run one-factor fixtures, each isolating an unrelated table, formatting, footnote or revision. Then measure a representative cohort. Report attempted/supported/refused counts and causes. A mixed document alone confounds the global-refusal baseline. |
| D1 | Simple target paragraph surrounded by unrelated tables or formatted paragraphs | Scope edit validation to the target and required dependencies. Mark unrelated content outside edit-validation scope; do not overwrite extraction/verification coverage. |
| D2 | Selected multi-run targets with an explicit formatting policy | Which run's formatting does replacement text take |
| D3 | Bounded table-cell targets | Only after D1 and D2 have fixtures in CI |

Revisions, fields, bookmarks, hyperlinks and other structures need explicit support or a precise refusal. Native Word tracked changes need a separate capability decision and host acceptance (workstream F).

### Rules that must survive the widening

- `region[start:end] == literal`; uniqueness within the target; expected-SHA check; derivative only.
- Tracked changes inside the target refuse. Tracked changes elsewhere follow the revision policy (decision 3), applied to extraction, anchor resolution and writing consistently.
- FX-16 unsupported-structure refusal inside the target leaves the original unchanged.
- Recheck remains mandatory. Prior human decisions never transfer silently.

### Fixtures

Simple paragraph; unrelated multi-run text; unrelated table; footnote present elsewhere; tracked change inside target (refused); tracked change elsewhere (policy case); duplicate literal in paragraph (refused); stale snapshot (409); competing commands (one activation); unsupported structure inside target (refused, original unchanged); `mc:Ignorable` namespace preservation.

**Sizing:** estimate after isolated fixtures. **Needs ADR:** locator and revision contract. **Depends on:** D0 evidence and decision 3; no arbitrary refusal threshold determines engine adoption.

## 9. Workstream E: Explainable preview and recheck

### Before commit

Show surrounding text, changed words, target scope, unsupported structures and lifecycle: commit creates/activates a derivative draft; mandatory recheck then creates the new report snapshot. No prior decision automatically applies to that new snapshot. Preserve historical records. A read-only word-level presentation diff may be computed in the web UI; it never authorizes the write.

### After recheck: finding correspondence

Classify each old finding against the new snapshot as **unchanged, changed, added, removed or uncertain**, and explain dimension changes separately (for example corrected quotation text with page mapping still unresolved).

| Rule [NEW] | Detail |
|---|---|
| Deterministic matching | Application-layer correspondence uses preserved version/locator lineage where available and explicit evidence such as reference identity, literal, occurrence and context. Paragraph hashes alone cannot match edited paragraphs. Ties, repeated citations and unsupported relocation remain uncertain. Record algorithm version and rationale; UI renders the result. |
| Dimension view | Identity, page mapping, fidelity, support and coverage each show before and after |
| Historical decisions | Prior decisions appear read-only as historical; never applied to the new snapshot |
| No new enum values | Correspondence is a non-authoritative detail field, not a change to the canonical finding vocabulary |
| Evidence re-evaluation | Structural validation may focus on changed units; evidence verification re-evaluates all affected dependencies |

### Acceptance

Repeated citations, moved text, changed dates and currencies, removed findings and uncertain correspondence are each understandable and correctly scoped. Existing F5 report comparison is read first so work is not duplicated. [OPEN]

**Size:** M. **Needs ADR:** yes (the correspondence field).

## 10. Workstream F: Useful DOCX output

### F1. Improve the appended report (no new capability)

- Readable sections: header (derivative, snapshot, release id, date), scope and limitations, summary counts, then one block per finding.
- Replace Python dict representations with labelled fields; stable finding identifiers; reasons, decisions with reviewer and timestamp, abstentions and coverage in plain language.
- Valid XML characters and whitespace preservation (A8).
- Preserve original body elements semantically and retain the append model and derivative validator. Do not claim byte-identical `word/document.xml`: serialization can change it. Assert untouched ZIP member payload bytes separately.
- Keep wording neutral: no certificate, no "verified" badge.

### F2. Bounded spike: anchored comments and internal navigation [NEW]

- Prototype Word comments at Stuk/Pièce references and bookmarks or internal links from the report to findings, on synthetic NL/FR documents.
- Try two candidate writers: an in-house minimal writer and StetDoc through its CLI. The choice follows the results.
- Any StetDoc use: pin the version; validate its JSON output; restrict filesystem and network separately (a scratch directory is not a sandbox); check licence notices; run CaseProof's derivative validator on the output; treat the comment author as metadata only.

### F3. Tracked changes decision

Decision 4 (does the pilot need visible tracked changes in the corrected DOCX) is taken with the first practitioners, then, if yes, a separate ADR and a Word-tested experiment.

### Acceptance

Representative outputs reopen in desktop Word and LibreOffice; formatting, annotations, source identity and exact historical download bytes verified; existing external-relationship, macro and active-field refusals remain.

**Size:** M for F1, M for F2 spike.

## 11. Workstream G: Operational acceptance

| Item | Work |
|---|---|
| G1 | Inspect live SQL and configuration before closing recorded warnings: SECURITY DEFINER function ownership, `search_path`, grants and execution boundaries; RLS posture; revocation; cross-matter denial; authentication protection settings including leaked-password protection. Record evidence with dates. |
| G2 | Investigate the unexplained signed-browser failure observed in F5, or record it as an open observation with its diagnostics. |
| G3 | Genuine signed correction-to-release acceptance on the final implementation. |
| G4 | Restore and retention gate [NEW]: a documented, tested backup restore and erasure replay (the roadmap lists it as open). |
| G5 | Dependency hygiene [NEW]: pinned dependencies, a lockfile check and a software bill of materials for the Python and frontend builds; secret scanning in CI. |
| G6 | Manual accessibility assessment (keyboard, screen reader, narrow width). |
| G7 | Assign actual accountable owners for each gate. Do not invent sign-offs. |

## 12. Owner decisions

| # | Decision | Needed by | Notes |
|---|---|---|---|
| 1 | Pilot envelope numbers per capacity layer | Start of B | Use measurements from B4 |
| 2 | Does incomplete review block any release type | Start of C | Preserve current scoped-release policy until explicitly amended; new completeness labels and gates need defined semantics |
| 3 | Revision policy for tracked changes outside the target | Start of D | One rule for extraction, anchor and writing |
| 4 | Visible tracked changes in corrected DOCX for the pilot | Before F3 | Ask practitioners |
| 5 | UTF-32 handling: parse safely or reject | Start of A | Either is acceptable if tested |
| 6 | Handling of XML-invalid OCR characters in annotations | Start of A8/F1 | Visible substitution with disclosure, or controlled refusal; no silent stripping |

## 13. ADRs and change control

Use the workflow v3.1 template for each: decision id and accountable owner; existing code, generated schema and route; problem seen in a real fixture; why existing behaviour is insufficient; security, compatibility and privacy impact; migration and rollback; Python, AJV, TypeScript and browser tests; human acceptance and remaining limitations.

| ADR | Topic |
|---|---|
| 0033 | Pilot envelope and capacity contract |
| 0034 | Release eligibility, review completeness and scope label |
| 0035 | Target-scoped correction, locator contract and revision policy |
| 0036 | Finding correspondence on recheck |
| 0037 | Anchored DOCX annotations and tracked-change capability (only if the spike supports it) |

Routine compatible hardening in A needs no automatic ADR. Document material behavior changes explicitly. Do not blanket-exempt new resource/encoding/coverage policies from review.

## 14. Implementation bundles and likely touch points

Use complete, reviewable changes across backend and frontend. The five bundles below replace the earlier prescribed eighteen-PR sequence. Split only when ownership, risk or independent rollout warrants it. Complete meaningful local work before pushing; avoid formatter-only churn.

| Bundle | Scope | Likely touch points | Exit |
|---|---|---|---|
| 1 — Hardening and factual records | A, STATUS/evidence corrections, explicit hook improvements | Parser modules, `dossier_journey.py`, `dossier_export_release.py`, tests, docs, hooks | Encoding/error regressions and relevant ordinary checks pass |
| 2 — Pilot capacity | Candidate measurements, capacity ADR, admission, transport, durable jobs, visual scheduling and UI limits | Intake, verification application services, existing page jobs, SQL if required, generated contracts, frontend | Agreed envelope passes the complete signed journey and boundary failures |
| 3 — Release preflight | Policy, shared server computation, immutable manifest detail, actionable UI | Release service, generated projection, exports feature | Partial/complete semantics, races, denial, historical compatibility proven |
| 4 — Correction and explainability | Isolated baseline, locator/writer D1–D2, preview, backend correspondence, coverage navigation | Anchor/extraction/writer, journey commands, corrections/review/viewer features | Safe supported edits and explained recheck pass signed acceptance |
| 5 — DOCX presentation | Readable appendix and host acceptance; optional annotation experiment kept separate | Exporter, fixtures, rendering/Word acceptance | Valid, usable, truthful derivatives and exact historical retrieval |

D3 table-cell editing is a separately gated extension after D1/D2, not implicitly delivered by bundle 4. F2 anchored-comments and tracked-change experiments are evaluated separately before production-path adoption. G starts immediately and continues through all bundles; H runs alongside engineering.

Every implementation bundle records affected contracts, relevant tests, limitations and rollback. Add regression tests for security and behavior changes; do not demand meaningless failing-first tests for documentation or trivial formatting. Update frontend/BLUEPRINT.md when a durable UI/architecture decision changes, and update status/evidence when delivery status changes. Regenerate consumed contracts rather than hand-editing generated types.

## 15. Build order and dependencies

| Phase | Work | Dependency / gate |
|---|---|---|
| Immediate | Parser/RPC fixes, factual status, live security inspection, failure diagnostics | Existing authorization; no pilot-envelope decision required |
| Discovery | Benchmark candidate envelope shapes; isolated correction fixtures; practitioner output questions | Synthetic data first; no new capacity promise |
| Capacity decision | Select supported envelope using measurements | Actual owner decision, including refusal vs partial visual assessment |
| Capacity build | Implement complete vertical slice and signed recovery acceptance | Approved capacity ADR |
| Release build | Shared policy, preflight, frozen completeness record and UI | Explicit release policy |
| Correction build | D1, then D2, preview and correspondence | Locator/revision policy and isolated fixtures |
| Output build | Readable appendix, host verification | Character-handling decision; experiments remain optional |
| Final acceptance | Cross-feature signed journey, resource limits, revocation, restart, history, accessibility | Exact final implementation; independent pilot gates stay separate |

Security inspection, restore planning, corpus work and practitioner interviews do not wait for the final phase. No workstream depends on adopting StetDoc. Do not introduce a mandatory model, Word host or public MCP endpoint.

## 16. Workstream H: Pilot evidence (non-code)

- Representative NL/FR/EN corpus with independent legal review and rights recorded.
- Detection recall and false-verification rate with denominators (for example 0 of N), not "zero risk".
- Practitioner interviews and timed comparison with the manual workflow; price and commitment evidence.
- SEC-01 to SEC-16 and independent security, privacy and professional-secrecy review.
- Deployment egress, data residency and OCR-location assessment.
- Pilot protocol [NEW]: scope, data-handling terms, success metrics (time saved, review agreement, false-verification count), stop criteria, and an explicit statement that human review is not legal certification.

## 17. Definition of done

**Engineering complete:** applicable final-commit CI green; genuine signed end-to-end acceptance on the final implementation; meaningful regression coverage for changed behavior and security boundaries; relevant status/contract/blueprint records updated; limitations and rollback documented. Any skipped gate is named and justified. Human/production approval is not inferred from CI.

**Pilot ready:** engineering complete, plus the agreed capacity envelope proven, representative dossiers run, security configuration inspected, accessibility assessed, and independent acceptance recorded with real owners.

## 18. Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| Raising the visual budget without memory and time bounds | Explicit refusal becomes unreliable processing | B4 measurements, B5 bounds, B6 scheduler, explicit `not assessed` |
| Capacity fixed in one layer only | Journey fails at the next layer | ADR 0033 covers all layers; full-envelope signed acceptance |
| Widening correction increases corruption surface | Bad derivative activated | D1 to D3 staging, fixture per construct, derivative validator, mandatory recheck |
| Completeness wording misread as certification | Over-reliance | C4 labels, neutral wording, limitations in manifest |
| Synthetic dossiers misrepresent real firm files | False confidence | Workstream H; recall and false-verification with denominators |
| Mocked-backend tests mistaken for live acceptance | Overclaimed status | Keep mocked and genuine runs labelled separately in acceptance docs |
| Spike tool (StetDoc) escapes its directory | Filesystem or network exposure | Separate restrictions; validator; pinned version; not a prerequisite |
| CI churn slows delivery | Slow merges | 0.3 hooks, final-SHA evidence template |
| Unknown Supabase configuration | Hidden exposure | G1 inspection before any claim |

## 19. Verification limits

This is a proposed plan, not a new full-codebase audit. Its source author did not read F1–F3 implementation, frontend features or SQL, and did not run tests. Additional consolidation checks covered selected intake, journey, correction, export and parser code, hooks, ADRs and GitHub run metadata. Earlier repository audits and test results are historical evidence, not tests rerun for this document. Live Supabase settings, native Word behavior, practitioner acceptance and performance at proposed limits remain unverified. No capacity number is newly approved here.

## 20. Reuse policy and source baseline

The two reference repositories contribute specific patterns, not a replacement architecture.

| Repository | Pinned audit baseline | Primary value | Adoption boundary |
|---|---|---|---|
| [StetDoc](https://github.com/clauseo-ai/stetdoc/tree/71c7e3bcedd638638497edd2e31539f07e4780b4) | `71c7e3bcedd638638497edd2e31539f07e4780b4` | Structural DOCX editing, reference staleness, edit validation, comparison and package-preservation practices | Python-first CaseProof improvements; optional isolated CLI experiment |
| [Vaquill Word add-in](https://github.com/Vaquill-AI/ms-word-addin/tree/0740ec39ffd1e1e1ef54088a11d157cf35aa541b) | `0740ec39ffd1e1e1ef54088a11d157cf35aa541b` | Contextual redline UX, navigation intent, Word-host edge cases and serialized host operations | Web UX patterns now; Office-writing patterns only if a separate Word capability is approved |

Pinned revisions are audit references, not recommendations to ship an old dependency without review. At implementation, inspect the intended version, license and compatibility. Use current compatible stable dependencies and the repository's lockfile workflow; do not upgrade the stack merely to implement this plan. Source reading does not establish host correctness, security or performance.

### 20.1 What to add from StetDoc

All entries below are proposals. Status describes disposition, not completed implementation.

| ID | Pattern / capability | CaseProof addition and boundary | Priority / bundle | Acceptance |
|---|---|---|---|---|
| S1 | Optional engine adapter | A bounded CLI adapter behind existing correction/export services only if experiments justify it. Never expose a raw arbitrary-command API. | Experiment after bundles 1–4 | Pinned schemas, explicit supported operations, controlled failure, validated derivative and host reopening |
| S2 | Structural, target-scoped text mapping | Shared extraction/locator/writer representation for supported paragraph spans; staged D1, D2, then optional D3. | Required; bundle 4 | Unrelated tables/formatting do not block a simple target; unsupported target constructs still refuse |
| S3 | Version-bound references / base tokens | Improve typed stale-state diagnostics around CaseProof source versions, hashes and snapshots. If an engine is adopted, store its token privately as adapter metadata. Do not create a second canonical currency check. | Required diagnostics; bundle 4 | Changed source/snapshot refuses; unchanged engine references follow the engine's actual documented token semantics |
| S4 | Origin-aware edit validation | Distinguish pre-existing structural violations from edit-induced ones. Validate affected structures and all required dependencies. Evidence recheck remains mandatory. | Required principle; bundle 4 | No new edit-induced corruption; prior evidence problems remain visible; optimized checks match full validation on the cohort |
| S5 | Structural comparison and changed spans | Borrow alignment concepts for contextual preview and explained reports. Engine document redlines are optional; they do not establish finding correspondence or evidence support. | Required UX; bundle 4 | Repeated/moved citations are uncertain where necessary; dates, currency and negation remain distinct |
| S6 | Hostile-input boundaries | Shared safe XML parsing, package validation and measured processing bounds. | Required; bundle 1 | Encoding/entity, archive, path, resource and malformed-part regressions |
| S7 | Corpus and fuzz practices | Pinned, rights-cleared structural fixtures plus representative conclusions files; bounded fuzz entry points. | Required staged testing; bundles 1–5 | Reproducible seeds/hashes; failures minimized; corpus permissions recorded; no private documents in public CI |
| S8 | Reference drift diagnostics | Compare CaseProof exhibit references before/after correction. Explain identity, source or page-space changes with CaseProof rules. StetDoc cross-reference checks are not exhibit verification. | Extension after correspondence | Seeded exhibit renumbering and source/page changes detected or explicitly unresolved |
| S9 | Detailed edit receipts | Record operation identity, input/output hashes, locator policy version, engine/version when applicable, supported scope and limitations. Human attribution stays in CaseProof ledger. | Bundle 4/5 as needed | Receipt binds actual derivative bytes and operation; author strings cannot establish authenticated review |
| S10 | Untouched-part preservation | Assert byte equality of untouched ZIP member payloads and structural fidelity of modified parts. Do not promise unchanged archive compression or whole-package bytes after an edit. | Required; bundles 4–5 | Non-target parts unchanged unless a declared necessary package edit; modified XML remains valid |
| S11 | Crash-safe local write plan | Where local persisted outputs are authoritative, use staged writes and atomic publication appropriate to the filesystem. Ephemeral scratch needs cleanup. Remote truth remains reservation/readback/activation. | Conditional | Crash injection cannot expose a completed partial artifact; restart reconciles remote state |
| S12 | Capability/schema generation | Retain Pydantic → JSON Schema → AJV/TypeScript. Validate optional engine JSON against its actual pinned schema. Do not introduce another public schema authority. | Existing pattern; extend only as needed | Drift checks fail on incompatible changes; generated clients validate real responses |
| S13 | Explicit tool confinement | If any future MCP/agent exposure is approved, authorize each action, minimize roots and isolate execution. A CLI `--root` is not an OS sandbox. | Deferred | Matter isolation, symlink/path escapes, network denial and revocation tested |

Useful source anchors: [reference model](https://github.com/clauseo-ai/stetdoc/blob/71c7e3bcedd638638497edd2e31539f07e4780b4/crates/stetdoc-core/src/refs/mod.rs), [edit checks](https://github.com/clauseo-ai/stetdoc/blob/71c7e3bcedd638638497edd2e31539f07e4780b4/crates/stetdoc-core/src/check/edit.rs), [revision engine](https://github.com/clauseo-ai/stetdoc/blob/71c7e3bcedd638638497edd2e31539f07e4780b4/crates/stetdoc-core/src/revisions/mod.rs), [working copy](https://github.com/clauseo-ai/stetdoc/blob/71c7e3bcedd638638497edd2e31539f07e4780b4/crates/stetdoc-core/src/api/working_copy.rs).

### 20.2 What to add from Vaquill

| ID | Pattern / capability | CaseProof addition and boundary | Priority / bundle | Acceptance |
|---|---|---|---|---|
| V1 | Office dialog / PKCE workflow | Preserve existing read-only add-in's ephemeral authentication if retained. Reuse no browser token persistence. Web signed authentication stays canonical. | Existing/conditional; no new pilot dependency | Host/session and expiry tests if add-in changes; no credentials in persistent browser/Office storage |
| V2 | Long-selection head/tail anchoring | Office.js search workaround only. It does not solve server OOXML location. Any future assembled Word range must pass exact text and unique-target validation. | Deferred to Word writing | More-than-255-character, repeated-prefix and paragraph-boundary cases in real Word |
| V3 | Serialized track-change toggling | Save/flip/edit/restore host state in a serialized lifecycle, including exceptions and cancellation, if host writes are approved. | Deferred | Failure does not leave tracking disabled or apply concurrent edits out of order |
| V4 | Protection detection | Host capability and protection checks before any approved Word write; verify API availability and behavior across supported hosts. | Deferred | Protected/unsupported host refuses clearly in tested languages |
| V5 | Fresh baseline timing | Re-read the actual editable baseline immediately before commit and reject drift. On web this means backend freshness and existing hash checks. | Required principle; bundle 4 | Concurrent source/version changes prevent stale commits |
| V6 | Actionable pending-change guidance | Explain unresolved revisions and unsupported constructs with stable codes and supported remediation. Never automatically accept/reject a lawyer's revisions. | Required; bundle 4 | Target revision refusal has clear scope; outside-target revision policy consistent |
| V7 | Typed navigation intent | Use existing route and selected-finding context for preflight/coverage links. Carry source/snapshot scope and discard stale requests. No new global intent bus without demonstrated need. | Required; bundles 3–4 | Exact finding/source opens; stale/cross-matter targets masked or refused |
| V8 | Explicit UI error states | Distinguish stale conflict, masked/denied resource, unavailable service and unknown write outcome. Reconciliation preserves operation identity. | Required; bundles 1–4 | HTTP/network failures never become saved/released success; no blind retry |
| V9 | Inline word-level contextual preview | Accessible semantic del/ins, surrounding text and clear target scope. Select a maintained compatible dependency only if necessary. Do not pull an unreviewed git+ssh package into builds. | Required; bundle 4 | Currency, accents, whitespace and negation remain visible; screen reader and keyboard usable |
| V10 | Server-generated attributed edits | If tracked output is approved, generate it server-side and bind it to CaseProof operation/receipt. DOCX author/date is descriptive metadata. | Optional; bundle 5 experiment | Real Word displays intended tracked edit; ledger proves actor, package metadata does not |
| V11 | Office host reliability lessons | Encapsulate Word.run; support host/API differences; avoid long UI blocking; validate file capture and OOXML insertion behavior. | Deferred | Host/version matrix and cancellation/recovery measured; no universal Word claim |
| V12 | Robust streaming protocol | Use only if an existing progress transport cannot meet requirements. Progress must come from durable jobs; model SSE is not verification authority. | Conditional, not mandatory | Split chunks/CRLF/disconnect/cancel tests; no duplicated events or fake completion |
| V13 | Safe text rendering | Render untrusted document/model output as text; avoid HTML injection. Optional model notes remain isolated and deferred. | Required principle | Markup-like source content inert; CSP preserved |
| V14 | Explicit redaction accounting | Redaction is outside pilot scope. Any future feature must count every candidate, report unsupported values, physically remove intended content and validate the output. | Deferred | Long strings, headers, tables and notes cannot be silently skipped |
| V15 | Deployment defense | Preserve CaseProof's strict same-origin headers and CSP; adapt only relevant header patterns. Office frame allowances are conditional, not a web default. | Existing/ongoing; G | Static host headers verified; no wildcard source or unsafe-inline/eval introduced |

Useful source anchors: [redline handling](https://github.com/Vaquill-AI/ms-word-addin/blob/0740ec39ffd1e1e1ef54088a11d157cf35aa541b/src/office/redline.ts), [host operations](https://github.com/Vaquill-AI/ms-word-addin/blob/0740ec39ffd1e1e1ef54088a11d157cf35aa541b/src/office/run.ts), [navigation](https://github.com/Vaquill-AI/ms-word-addin/blob/0740ec39ffd1e1e1ef54088a11d157cf35aa541b/src/app/nav.tsx), [inline diff](https://github.com/Vaquill-AI/ms-word-addin/blob/0740ec39ffd1e1e1ef54088a11d157cf35aa541b/src/features/review/InlineDiff.tsx).

### 20.3 Explicitly excluded transfers

- Vaquill's tolerant matcher: lowercasing and stripping non-ASCII/alphanumeric characters can equate currency changes and discard accents. Navigation heuristics must never authorize CaseProof edits or fidelity decisions.
- Silent long-value redaction skips, model failures converted to default success-like objects, provider keys/refresh tokens in localStorage, permissive CSP and wildcard remote connectivity.
- StetDoc's default unconfined tool registrations, agent/plugin setup, or filesystem transactions as replacements for database/storage authorization and recovery.
- New base tokens as a second source of authority; a new global state bus or schema generator duplicating existing infrastructure.
- New cryptographic manifest protocol, public MCP, native tracked changes or mandatory Word integration as unapproved pilot prerequisites.
- Auto-transferred human decisions, skipped dependent evidence checks, or machine author metadata presented as lawyer approval.

### 20.4 Optional StetDoc adapter experiment

**Entry:** D1/D2 Python approach and representative failure data exist, or a separately approved anchored-comments experiment has a specific need. No arbitrary refusal-percentage threshold triggers adoption.

**Experiment requirements:**

1. Pin binary release/source revision, verify integrity and record build/OS provenance. Inspect actual CLI help and capabilities; this document does not prescribe guessed commands or flags. In particular, capability output and schema output are distinct interfaces.
2. Allowlist operations and arguments. Never invoke a shell with document-controlled command text. Bound input, output, stdout/stderr and process descendants.
3. Use per-job scratch copies; enforce filesystem permissions/isolation and network policy separately. Do not expose original store paths, service credentials or other matters to the process. A timeout or a root directory alone is insufficient.
4. Set measured CPU, memory, process, decompression and wall-time bounds. Kill the process tree on timeout; safely remove scratch after reconciliation.
5. Validate the pinned JSON schema, exit status and artifact. Apply CaseProof's package validator, exact edit checks, hash readback and mandatory recheck before activation.
6. Store operation/engine provenance as supplementary derivative metadata. Existing source/snapshot and human ledger remain authoritative.
7. Test clean/simple, mixed runs, tables, notes, revisions, fields, repeated text, hostile packages and unsupported comparisons. A comparison warning is a limitation, not exact complete redline proof.
8. Reopen in supported Word hosts and verify declared changes. Compare benefit, corruption/refusal behavior, latency, packaging and operational cost against Python.

**Exit:** written recommendation: reject, retain as experiment, or adopt a bounded capability through its ADR. Production acceptance is separate. Do not expose the engine through MCP merely to run this experiment.

### 20.5 Licensing and dependency record

- StetDoc is audited as MIT OR Apache-2.0; choose and comply with the applicable license. Invoking a binary does not erase distribution notice obligations. Review the chosen release's license and transitive components.
- Vaquill is audited as Apache-2.0 with NOTICE. Preserve applicable notices for copied/adapted material, identify origin revision and changed files, and update CaseProof's third-party notices.
- Review any diff dependency's exact provenance, license, integrity and maintenance. No unreviewed git+ssh dependency.
- Record the CaseProof owner's intended license position without inventing or assigning one. Public visibility alone is not reuse permission.
- Maintain lockfiles, an appropriate SBOM and secret/dependency checks. Inspect what already exists before adding duplicate tooling.

## 21. Integration design and contract compatibility

### 21.1 Use the existing application path

| Concern | Integration point | Authority |
|---|---|---|
| Capacity admission | Existing workspace intake/application validation | Backend capacity profile |
| Parsing and region coverage | Existing parser adapters and inventory | Preserved bytes and explicit extraction provenance |
| Durable work | Existing signed page-job / worker boundary, extended after inspection | Durable job record and authorized readback |
| Corrections | Existing preview/commit and reserve/readback/activation | Exact current source and review receipt |
| Correspondence | Application-layer comparison projection | Non-authoritative explanation tied to two snapshots |
| UI navigation | Existing React Router and selected finding/viewer context | Server-scoped identifiers and access checks |
| Release | Existing release preview, commit, history and binary endpoints | Server policy, frozen manifest and verified artifact bytes |
| Optional engine | Private worker adapter | Never an independent evidence or authorization service |

No route names in this plan authorize inventing an endpoint. Inventory real routes first. Add a public route only when required, documented and reviewed through existing architecture controls.

### 21.2 Contract checklist

- Define who owns new fields, valid types, offset encoding, units, optionality and unknown-state handling.
- Version meaningful policy changes: capacity profile, visual scheduling, correspondence and locator support.
- Generate frontend validators/types from Python projections; do not hand-edit generated files.
- Preserve old immutable release manifests and receipt verification. A new manifest version must remain distinguishable and readable under its original schema; never backfill signed historical content in place.
- If introducing preview digest/engine version binding, specify expiry, stale rejection and replay behavior without weakening the existing command hash/operation identity.
- Extend storage/SQL only when needed. Forward migrations and authorization/retention compatibility require exact review and adversarial verification before installation.
- Preserve historical original/version retrieval and existing release grants. New preflight remediation links do not grant access by themselves.
- Avoid input/output circularity: an artifact cannot contain its own final hash. Distinguish preview DOCX from frozen release artifact and decide release-id/time injection before final serialization.

### 21.3 Coverage navigator — explicit deliverable

Build a keyboard-accessible list over existing region inventory and unprocessed scope. Each item shows source/version, region type, processing state, reason and supported action. Link to the exact source/region where possible. If no reliable anchor exists, show an honest notice and original-source action rather than a fabricated highlight.

Keep three concepts separate: extraction coverage, visual assessment coverage and editability. A region can be extracted but not editable, or mapped but not visually assessed. The navigator must not collapse these into one badge. Preserve denominator identity across recheck; changed scope produces a new snapshot.

Acceptance includes footnotes, headers, text boxes, revision-unresolved regions, OCR-unreliable pages, missing mappings, stale snapshots, revocation and regions with no browser-renderable anchor.

## 22. Consolidated acceptance matrix

The matrix defines required evidence; it does not claim these checks have run for the proposed implementation.

| Area | Positive case | Failure / boundary case | Required evidence |
|---|---|---|---|
| XML safety | Ordinary UTF-8/UTF-16 extraction | DTD/entity, corrupt part, unsupported encoding, depth/node excess | Parser unit/regression tests; controlled outward outcome |
| Archive boundary | Valid bounded package | Duplicate/path traversal, encryption, size/expansion limits | Existing controls retained and measured missing controls added |
| Service boundary | Valid bounded JSON | Malformed/non-dict/oversized response; missing manifest keys | Stable failure; no private content leakage |
| Intake | Whole envelope admitted | Last source invalid; over each bound; uncertain upload | No premature originals written; readback-based recovery |
| Durable processing | Full signed job completes | Worker dies; stale lease; cancel; revoked user | Fresh-process resume; fenced stale writes; explicit unknown/partial |
| Visual assessment | Selected page pairs assessed | Budget exhausted, OCR unavailable, representation conflict | Correct counts, state and policy; no false success |
| Correction D1 | Simple target amid unrelated complexity | Ambiguity, stale bytes, target revisions | Exact edit; clear refusal; immutable originals |
| Correction D2 | Supported formatted span | Field/bookmark/hyperlink or unsupported run boundary | Explicit formatting policy; no flattening |
| Correction D3 | Bounded table cell, if approved | Merged/nested/unsupported table structures | Dedicated fixtures and host acceptance; never implied by D1 |
| Recheck | Current derivative produces fresh report | Superseded draft, competing activation, changed references | Dependent evidence recomputed; no decision transfer |
| Comparison | Explained matching changes | Repeated/moved/deleted references; currency/negation | Backend correspondence with uncertainty; accessible presentation |
| Coverage navigation | Real region/source jump | Missing anchor, stale/cross-matter link | Honest notice and server-scoped access |
| Release policy | Policy-eligible current scope | Incomplete review under strict type; no decisions; stale preview | Shared policy, fresh commit checks and truthful labels |
| Release integrity | Frozen artifacts reopen exactly | Tamper, oversized output, lost acknowledgment | Digest/size/HMAC validation and operation reconciliation |
| Historical compatibility | Old manifest/artifact readable | New profile/schema; changed source; revocation; retention | No regeneration/mutation of historical bytes; current access checks |
| DOCX output | Readable appendix and preserved body | Invalid characters, active content, unsupported relationships | Package validation, renderer inspection, real Word acceptance |
| Optional engine | Declared supported operation | Timeout, malformed output, escape, child process, unsupported edit | Isolation and bounded failure; no activation before verification |
| UI | Keyboard/screen reader/narrow layout | Expiry, stale request, duplicate submission | Accessible states; cleared sensitive memory; no success on uncertainty |
| Pilot evidence | Rights-cleared representative dossiers | Seeded misses, scans, languages, unsupported cases | Independent labels; denominators; measured practitioner results |

### Evidence record template

For each gate record: exact commit, policy/schema versions, environment and configuration scope, synthetic versus representative data, commands/workflows, result and artifacts, accountable reviewer, limitations, unresolved observations and rollback. Do not log content or unnecessary sensitive identifiers. Retain private hashes only in authorized evidence records.

Use final-head checks for affected paths, then complete integrated signed acceptance at the final implementation. Rerun after material changes. Prior green PR heads are historical evidence; record post-merge validation separately rather than relabelling an older run. Explain expected skips.

## 23. Decisions, ownership and handoff checklist

Names are intentionally unassigned until real owners accept responsibility.

| Responsibility | Deliverable | Required before |
|---|---|---|
| Product owner | Capacity envelope and partial-release semantics | Bundles 2–3 behavior changes |
| Backend owner | Parser, limits, durable processing, locator, correspondence and release policy | Relevant implementation review |
| Frontend owner | Limits display, coverage navigation, preview, preflight and accessibility | Relevant UI acceptance |
| Database/security reviewer | Exact SQL/grants, secrets, RLS, revocation and configuration | Related DB installation or security closure |
| Operational owner | Backup/restore, retention, cleanup and supported deployment mode | Pilot approval |
| Practitioner / independent reviewer | Corpus labels, Word output usefulness, track-change need and pilot metrics | Pilot-ready declaration |

Engineering can proceed on compatible hardening and measurements while decisions are pending. Do not delay routine reversible work for optional policy questions. Do not silently choose a material release or revision policy merely to satisfy a test.

Before implementation:

- [ ] Confirm branch/main baseline, applicable AGENTS and current ADR numbers.
- [ ] Inventory existing capacity, job, release, correspondence and security tooling before adding replacements.
- [ ] Preserve this document as a proposal; create repository decisions/evidence at the actual changed contracts.
- [ ] Record the six owner decisions in section 12 and amend them using measured evidence.

Before engineering completion:

- [ ] All committed behavior in the agreed scope implemented; optional experiments explicitly excluded or accepted.
- [ ] Relevant Python, contract, frontend, SQL, build and browser checks pass at the final implementation.
- [ ] Full signed envelope/correction/release/reopen journey and adverse cases recorded.
- [ ] No unsupported architecture, editing, coverage or cryptographic claims.
- [ ] Current status and applicable blueprint/ADRs match implementation; historical evidence remains dated.

Before pilot readiness:

- [ ] Representative NL/FR/EN expectations independently reviewed; unsupported language behavior explicit.
- [ ] Capacity boundary, usability, time savings and false-verification denominators recorded.
- [ ] Security/privacy/professional-secrecy, OCR location, egress, retention/restore and accessibility gates have real owners and evidence.
- [ ] Data-handling terms and stop criteria accepted; production/customer-data approval explicit.

## 24. Sources and evidence provenance

### CaseProof — pinned primary sources

1. [Baseline commit / PR #178 merge](https://github.com/haytamAroui/caseproof/commit/43550e971ad194d1515296962430ad997a4155bb).
2. [Frontend architecture and acceptance blueprint](https://github.com/haytamAroui/caseproof/blob/43550e971ad194d1515296962430ad997a4155bb/frontend/BLUEPRINT.md).
3. [Workflow v3.1](https://github.com/haytamAroui/caseproof/blob/43550e971ad194d1515296962430ad997a4155bb/docs/CASEPROOF_WORKFLOW_BLUEPRINT_V3_1.md).
4. [Signed intake and installed limits](https://github.com/haytamAroui/caseproof/blob/43550e971ad194d1515296962430ad997a4155bb/apps/api/workspace_intake.py).
5. [Journey, RPC, visual budget and correction lifecycle](https://github.com/haytamAroui/caseproof/blob/43550e971ad194d1515296962430ad997a4155bb/apps/api/dossier_journey.py).
6. [Release preview, manifest and artifact boundary](https://github.com/haytamAroui/caseproof/blob/43550e971ad194d1515296962430ad997a4155bb/apps/api/dossier_export_release.py).
7. [Correction anchor](https://github.com/haytamAroui/caseproof/blob/43550e971ad194d1515296962430ad997a4155bb/infrastructure/parsers/docx_correction_anchor.py).
8. [Correction and annotated DOCX writer](https://github.com/haytamAroui/caseproof/blob/43550e971ad194d1515296962430ad997a4155bb/infrastructure/parsers/dossier_docx_export.py).
9. [Region inventory](https://github.com/haytamAroui/caseproof/blob/43550e971ad194d1515296962430ad997a4155bb/infrastructure/parsers/docx_region_inventory.py) and [text extraction](https://github.com/haytamAroui/caseproof/blob/43550e971ad194d1515296962430ad997a4155bb/infrastructure/parsers/docx_text_regions.py).
10. [Correction UI and current comparison](https://github.com/haytamAroui/caseproof/blob/43550e971ad194d1515296962430ad997a4155bb/frontend/src/features/corrections/CorrectionPanel.tsx).
11. [Existing release ADR 0032](https://github.com/haytamAroui/caseproof/blob/43550e971ad194d1515296962430ad997a4155bb/docs/adr/0032-reviewed-release-and-historical-artifact-boundary.md).
12. [Existing hooks](https://github.com/haytamAroui/caseproof/tree/43550e971ad194d1515296962430ad997a4155bb/.githooks).
13. [Later genuine signed F6 acceptance run](https://github.com/haytamAroui/caseproof/actions/runs/41623751514): GitHub metadata checked, completed/success at `c0e7d44b42b137c80b568e44ccbce28acad3ee97`. This is PR-head evidence; it is not a rerun of proposed v1.2 changes or proof of pilot readiness.

### Consolidated input documents

- [Reviewed plan v1.1](https://chatgpt.com/library?file_id=libfile_5c5701f4b2dc8191bc0abd564dd2c2f6&account_id=personal).
- [Repository reuse feature proposal](https://chatgpt.com/library?file_id=libfile_8a04dbd6e0248191bec3288b1f172eb7&account_id=personal).
- [Three-repository code audit](https://chatgpt.com/library?file_id=libfile_38ab52bba8c88191b3653532f2ebb4fd&account_id=personal).
- [Four-file strategic synthesis](https://chatgpt.com/library?file_id=libfile_917b6391b24c819198b5f8364e70e31d&account_id=personal).

The repository maps in section 20 distinguish patterns recommended for CaseProof from conditional features. Earlier tests/builds and source audits are historical, scoped evidence. No StetDoc Rust test execution, Word-host result, live security acceptance or new implementation is claimed by generating this plan.
