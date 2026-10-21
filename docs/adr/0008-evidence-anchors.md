# ADR 0008 — Versioned typed evidence anchors and finding semantics

Status: Proposed — human review required
Date: 2026-10-21

## Context

A source citation, a faithful quotation, the semantic relationship of evidence to a claim, and the claim's sufficiency are separate questions. Existing exact-substring checks prove at most the presence of text in one registered representation; they cannot prove authenticity, factual truth, or legal effect.

## Decision: immutable source and representation identity

- Identify source bytes with server-trusted tenant scope, `document_id`, immutable `version_id`, `sha256_hex`, and ingestion metadata. A content hash proves integrity of captured bytes, not authorship or authenticity.
- Every parsed text, OCR result, spreadsheet normalization, or other derived representation has its own immutable `representation_id`, digest, parent source-version reference, parser/OCR implementation + version, configuration identity, and coordinate convention. Never silently overwrite a representation when reprocessing a source; generate a new identity.
- An `EvidenceAnchor` refers to an immutable document version **and**, when applicable, the specific representation against which the locator was recorded. The resolver must validate both identities, current tenant authorization, locator bounds, and type. Never resolve by searching for a similar quote in a different representation or version as an implicit fallback.
- Text-span locations use **zero-based, half-open [start, end) Unicode code-point offsets** into the exact stored, normalized representation; record that normalization and encoding. For PDF regions use **zero-based physical page index** (not display page label) and an explicit bounding box with coordinate system, units, page width/height and rotation convention. For spreadsheets use stable sheet identifier, A1 range, workbook representation, and any applicable table/field key. Structured fields use representation-local schema identifier and a typed field path. Out-of-bounds, ambiguous, missing or stale locations do not resolve.
- Re-OCR/reparse is a new immutable representation. An old anchor may still resolve against its preserved original representation, but is never automatically remapped. A requested remap creates a new anchored link with recorded provenance and requires reassessment; if the original representation is unavailable or no longer permitted, fail closed.
- An unanchored finding is only a `candidate` in quarantine. Moving to an evidence-grounded state requires at least one resolvable anchor and explicit assessments. All source and link revisions remain observable; do not mutate history to make a finding appear verified.

## Decision: independent evidence dimensions

For each finding-to-anchor link, record an assessment revision, assessor kind/identity, basis and provenance for:

1. **Citation resolution:** `resolved`, `unresolved`, `stale`, `invalid`.
2. **Content fidelity:** `matched`, `mismatched`, `indeterminate`. It compares an asserted quote or typed value with the correct immutable representation. It does not establish what happened in the real world.
3. **Semantic relation:** `supports`, `contradicts`, `qualifies`, `inconclusive`, `not_assessed`. The assessment must be relative to the **exact finding statement and version**; changes to wording require reassessment.
4. **Sufficiency:** `sufficient`, `insufficient`, `not_assessed`. Link-local sufficiency is not automatically overall sufficiency; aggregation uses a separate versioned policy in ADR 0009.

A perfect quotation can contradict the claim it accompanies. Model confidence is optional diagnostic metadata, never approval authority. Evaluator output is a proposal subject to review, not a factual oracle. Sector-specific reconciliation, financial calculations and legal assessments remain outside the evidence kernel. Keep the domain pure Python; Pydantic belongs at external I/O boundaries.

## Negative and compatibility cases

Test wrong offset, wrong PDF page, OCR offset drift, stale document/representation, changed statement, unrecognized spreadsheet sheet, true quote with false claim, conflicting source, and cross-tenant attempts. Cross-tenant access is denied by the application using trusted context; in-memory unit tests model denial but cannot prove database isolation.

Stage 1 uses deterministic in-memory reference contracts; Stage 2 owns durable storage, authorization enforcement, and transformation history persistence. The existing v1 reference API is unchanged. The v2 proposal is illustrative until implementation and contract tests establish a formal API.
