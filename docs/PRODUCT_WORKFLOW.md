# CaseProof — Belgian litigation product workflow

**Purpose:** define the complete lawyer-facing workflow that the principal roadmap implements. This is a proposed product contract, not a statement that these screens or capabilities exist in the current application.

**Primary user:** a Belgian lawyer preparing, checking or reviewing a civil/commercial brief and its exhibit bundle. The three product languages are **Dutch (NL), French (FR) and English (EN)** for the UI, searches, evidence workflows and supported outputs. Product UI language, source language, document language and output language are separate settings; they may differ in the same matter. Language support is a product target, not a claim of implemented translations or measured retrieval quality.

## Product outcome

A lawyer can import a brief and its evidence, confirm which files correspond to which Stuk/Pièce references, find and inspect source passages, insert evidence citations while drafting, run a scoped check, resolve or correct findings, hand the exact version to a reviewer, and deliver a navigable brief and exhibit package. When the brief or evidence changes, the product identifies the affected work and requires the appropriate recheck.

The product reports what it checked and what it could not check. “No issue found” means no issue was found within the declared and processed scope; it never means that all facts are true or all evidence was discovered.

## Main navigation

1. **Matters** — create/open, recent activity, access status, archived matters.
2. **Evidence** — upload status, source inventory, exhibit register, page/source viewer.
3. **Drafts** — own brief, opponent brief, response draft, version history.
4. **Search** — search passages across the authorized, indexed matter record.
5. **Review** — issue queue, exact source context, assignment, decisions and corrections.
6. **Outputs** — reports, linked briefs, exhibit indexes/bundles and recipient shares.
7. **Matter settings** — roles, language, citation format, retention and model eligibility.

The Word task pane exposes the contextual subset: selection, evidence suggestions, source inspection, citation insertion, correction preview, recheck status and open-in-web actions. Both clients use the same server-owned matter graph and permissions.

## End-to-end journey

### 0. Sign in and choose a matter

The lawyer signs in, selects an authorized organization and opens or creates a matter. The matter setup captures a title/reference, jurisdiction/court when known, working language and permitted collaborators. It does not require a legal rule profile before evidence work can begin.

**System:** checks current identity and matter access before listing or reading documents. An inaccessible or revoked matter is masked/denied. A new matter starts with no evidence and no inferred legal state.

**States:** loading, signed out, organization selection, empty matter, active matter, archived, access revoked, service unavailable.

**Done when:** the lawyer sees the matter identity, access role, processing status and a clear next action.

### 1. Add the brief and evidence

The lawyer uploads the current draft or opponent brief and the available exhibits. Files are preserved as immutable originals. The upload screen shows per-file progress, duplicate detection, unsupported formats, quarantine/scanning state and whether a prior version already exists. The user can add files incrementally.

**System:** creates stable source identities and resumable jobs; records byte digest, receipt time, uploader and matter scope. It parses supported pages and parts, runs configured OCR where available, and creates derived representations with parser/version lineage. Failed or unprocessed pages remain visible. An upload does not establish that a document was filed or communicated.

**States:** queued, uploading, quarantined, scanning, parsing, OCR pending, ready, partial, failed, duplicate, removed-from-active-scope.

**Done when:** every uploaded file has an explicit status and can be opened as original or as a clearly labelled derivative. The lawyer can continue with available sources while the UI identifies what is missing or failed.

### 2. Confirm the exhibit register

The lawyer imports or creates an exhibit list and maps each displayed identifier (Stuk/Pièce, annex, range, alias) to one or more stable source versions. Printed page numbers, PDF page numbers and bundle page numbers are recorded separately. Duplicate labels, uncertain matches and multi-file exhibits require explicit resolution.

**System:** proposes matches based on supplied metadata, names and extracted references, but never silently treats a filename or numeric similarity as authority. Renumbering a label does not change source identity. Communication, filing and receipt facts remain distinct and require their own records.

**States:** unmatched, suggested, ambiguous, duplicate label, confirmed, revised, stale mapping.

**Done when:** every reference in the selected brief is either resolved to a confirmed exhibit/page map or explicitly left ambiguous/unresolved. The register can include manually selected exhibits that are not cited in the current draft.

### 3. Prepare the brief version

The lawyer chooses a role for each document: own draft, opponent brief, earlier version, response draft, filed copy or other. The system parses paragraphs, tables, footnotes and citations into a versioned draft model while preserving the original bytes and layout. The lawyer can compare parsed text with the original document and correct extraction/mapping errors.

**System:** associates assertions and detected references with this draft revision and parser version. It separates legal references from exhibit references and identifies unsupported/ambiguous references. It does not infer that a changed argument was legally abandoned.

**States:** parsing, ready, needs mapping, unsupported structure, stale, superseded.

**Done when:** the user confirms the draft version and its visible text/reference mapping before checking or editing.

### 4. Write with evidence (Word or web)

The lawyer selects a factual sentence or phrase, opens “Find evidence,” and searches the authorized matter record. Results show source title, exhibit label, page, language, surrounding context and why the passage was returned. The lawyer opens the original or derived source at the exact location, inspects relevant preceding/following context, then inserts a Stuk/Pièce pinpoint.

**System:** records the citation edge from this draft revision/assertion to the resolved exhibit, source version and anchor. Retrieval rank is labelled as relevance ordering, not truth probability. An empty result is a valid outcome with its search scope and unindexed/failed material visible.

**Retrieval promise:** launch with evidence retrieval whose Dutch, French and English keyword and paraphrase-query performance is measured on the rights-cleared corpus. Do not imply proven broad conceptual-search equivalence from a lexical baseline. Broader conceptual-search claims depend on demonstrated retrieval results. Semantic retrieval, if proposed, is a separately evaluated capability; semantic support assessment remains optional under PIV-12 and is not a prerequisite for the deterministic workflow.

**Word safety:** before insertion, the add-in checks that the selected range still matches the captured document revision/context. If the text moved or another editor changed it, the add-in stops and asks the lawyer to reselect or review a refreshed proposal. It preserves formatting, lists, footnotes and tracked changes; the operation is reversible.

**States:** no selection, searching, partial index, results, no matches, source unavailable, citation ready, selection changed, inserted, undone.

**Done when:** the lawyer can reopen the inserted pinpoint and inspect the same source version from Word or web.

### 5. Check own or opponent brief

The lawyer chooses a check profile and explicitly confirms scope: selected draft revision, confirmed exhibit set, excluded documents/pages, and whether to check only cited evidence or also search the wider record for possible counterevidence.

The deterministic pass checks:
- references that cannot be resolved or have ambiguous exhibit/page mappings;
- quotation text against exact source spans, with candidate alignment kept separate from exact fidelity;
- typed date/amount/percentage observations with roles, units, currencies and ambiguity retained;
- defined local citation formatting rules;
- missing or unprocessed material in the declared scope.

A second, optional semantic pass may retrieve supporting, qualifying or contrary context and create model-proposed observations. It records the model/prompt/scope version, can abstain, and never changes an issue into an authorized decision. Legal references are marked “not checked” unless a separately specified legal-authority service and source entitlement are active.

**System:** reports execution status separately from evidence status. A clean result is allowed. If indexing or parsing was incomplete, the report says exactly which pages/files were not checked. It does not infer that an uncited exhibit was uncommunicated, or that the opponent omitted evidence from the world.

**States:** scope confirmation, queued, processing, partial, completed-with-observations, completed-clean, blocked, failed, outcome-unknown, stale.

**Done when:** each observation has a type, severity or uncertainty level, draft/source versions, source location where available, check version and reproducible explanation.

### 6. Review and resolve observations

The lawyer opens a review queue with filters for unresolved reference, literal mismatch, typed value difference, context warning, semantic proposal, missing material and processing issue. Selecting an observation opens the draft beside the source, including enough context to assess it. The reviewer can retain, reject, qualify, correct, or request more evidence, with rationale where required.

A firm can assign a named reviewer to an exact draft/check snapshot, return issues to the author, inspect changes since review and release the exact artifact. A solo practice uses its explicitly configured policy; a solo signoff is identified as such and never represented as independent review.

**System:** appends review events and retains prior assessments. A reviewer disposition does not rewrite source evidence or semantic support. Read permission does not grant edit, publish or filing permission. Concurrency conflicts are explicit; no stale reviewer packet can authorize publication.

**Done when:** every item is resolved, intentionally left open with rationale, or surfaced in the report as unresolved. The reviewer can see scope, exclusions, failed pages and changes since the previous review.

### 7. Correct and recheck

Correction lifecycle: **inspect → propose → preview → revalidate → apply/undo → invalidate → recheck**.

The lawyer previews a text, citation or mapping patch against the current document. The system checks the live range, actor permissions, draft revision and cited source version. If the draft or source changed, it requests a fresh review rather than writing over another editor's work. After application, the change is reversible and recorded.

Only checks/reviews/outputs that depend on changed inputs become stale. History and unrelated issue work remain. Changing the whole-record search universe invalidates that search result even if an individual citation was unchanged. A new check creates a new result version; it does not erase the old one.

For an opponent brief, the original remains untouched. Corrections are annotations, an analysis copy or edits to a separate response draft.

### 8. Generate outputs

The lawyer selects the exact draft revision, exhibit register revision, check run, review state, inclusion policy and output language. Available outputs are separately identified:
- source-linked working brief or correction copy;
- cite-check/review report listing checked and unchecked scope, findings and dispositions;
- exhibit index with stable identifiers and displayed aliases;
- exhibit bundle with bookmarks/hyperlinks where supported;
- offline package or hosted courtesy copy.

The lawyer chooses exhibit order policy (fixed register or first citation) and confirms manually included uncited exhibits. Removing a draft citation never silently removes an exhibit from the register or an already frozen output. The system renders, reopens and validates generated files and links. An earlier output remains immutable and can be marked superseded by a later version.

**States:** dirty draft, stale review, scope confirmation, queued, rendering, validating, ready, failed, superseded.

**Done when:** the output manifest identifies exact input versions, policy/check versions, review events, exclusions and limitations. A hash is an integrity aid, not proof of source authenticity or legal correctness.

### 9. Share or hand off for filing

The lawyer chooses recipients and access scope for a hosted copy, with expiry and revocation settings. Redaction is applied to a derivative and verified in the generated output. Offline downloads cannot be recalled. Filing preparation may produce a court-specific checklist and size/readability preflight, but export is not submission.

Submission and receipt capture are separate actions. A real filing integration requires its own authorization and uncertain-outcome recovery. A receipt is recorded only when an actual external receipt is observed and bound to the submitted artifact.

Court-profile guidance is versioned and shows the court/division/chamber, document type, source and passage, effective date, last verification date, owner, and whether each item is mandatory or recommended. Show scope, expiry and any conflict or unavailable source. A stale or unknown profile is labelled unverified and cannot certify court readiness or impose a national rejection rule. Technical bundle validation and procedural readiness are separate statuses; both remain subject to professional review.

**Done when:** the recipient sees only authorized materials, or the lawyer has downloaded the intended package for the existing filing process. The matter records prepared, shared, submitted and receipt-confirmed as distinct states.

## Cross-cutting failure and recovery behavior

| Failure | Product response |
|---|---|
| Unsupported/corrupt file | Preserve upload record; mark unsupported/failed; continue other files where safe; disclose scope gap |
| OCR failure or low-quality scan | Show original and failed pages; do not fabricate text/geometry or claim complete checking |
| Duplicate/ambiguous Stuk label | Keep all candidates; request user mapping; never first-match silently |
| Partial index | Label search partial; disclose excluded sources/pages; allow retry/reindex |
| Requesty timeout/uncertain dispatch | Preserve outcome-unknown; do not automatically repeat a potentially paid call |
| Save acknowledged but refresh failed | Show saved state separately from refresh failure; reload without claiming save rollback |
| Lost edit/publication acknowledgment | Reconcile by stable operation ID before retry; prevent duplicate mutation/output |
| Source/draft changed during review | Mark dependent checks stale; preserve the review history; block stale release |
| Permission revoked | Deny subsequent reads/search/share; invalidate caches; explain access loss without exposing source metadata |
| Export fails validation | Keep prior output intact; report failed artifact; do not mark ready |
| Court profile is stale, conflicting or unavailable | Mark procedural guidance unverified; explain the profile gap; do not claim court readiness or apply a national rejection rule |
| Clean check | Show checked scope and “no confirmed issue found”; never award an all-record correctness badge |

## Product success measures

Measure task completion on representative NL/FR/EN and mixed-language dossiers through the competitive benchmark and adoption protocol in [ROADMAP.md](ROADMAP.md):
- compare manual Word/PDF with authorized, tested products on fixed tasks; record source/output correctness, total time including setup/review/cleanup, false positives, assistance, errors and breakage;
- first complete task, second task on an actual matter, repeat use within a defined window, false-warning review time and abandonment reasons;
- maintain separate invited/access, registered, trained, active and paying cohorts;
- track cost per completed reviewed dossier, with observed values distinct from estimates and unavailable unit costs left null;
- retain existing measures for reference resolution, labelled-passage recall, correction outcomes, round-trip integrity, partial/failure recovery and access rejection.

Use privacy-safe operational metadata; no customer document content enters telemetry. Each measure names its denominator, corpus/task protocol and version. No metric is advertised as legal accuracy without a validated evaluation design.

## Implementation mapping

This workflow is implemented through the principal PIV backlog in [ROADMAP.md](ROADMAP.md), not a parallel task system:

| Workflow segment | PIV packets |
|---|---|
| Matter setup, access and evidence intake | PIV-02–05 |
| Exhibit register and draft/reference graph | PIV-06–07 |
| Check and review workbench | PIV-08–10 |
| Word evidence-writing loop | PIV-10–11 |
| Semantic/opponent analysis and synthesis | PIV-12–13 |
| Correction, outputs, sharing and release | PIV-08, 11, 14–16 |
| Belgian advisories, filing handoff and connectors | PIV-17–19 |
| Onboarding, operations and release evidence | PIV-20 |

PIV-00/01 establish the scope, owners, claims register, rights-cleared evaluation corpus, fixed competitive task protocol and clean-case controls before integrated delivery. PIV-20 adds cost and repeat-use evidence. No customer document content is collected as telemetry. Customer documents remain gated on the applicable security, custody, persistence and operations evidence in ROADMAP.md.
