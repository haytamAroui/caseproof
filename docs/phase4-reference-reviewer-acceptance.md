# Phase 4 — DOCX references to reviewed source (M2/M3)

Status: **implementation started; no live UI acceptance yet**. Base: merged M0.5.

## First end-to-end acceptance journey

An authorized signed development user opens an existing private matter and uploads a synthetic DOCX draft, a separate inventory, a text PDF, and an image-only scanned PDF. The user can:

1. See every detected `Stuk X, p. Y` and `Pièce X, p. Y` reference, with location in the DOCX and any adjacent literal quote or numeric claim. Incomplete DOCX coverage must be visibly marked, never silently treated as complete.
2. See the original reference literal and distinct exhibit identity, printed page, PDF page, and bundle page. Missing inventory, source, or mapping remain separate unresolved states; no inferred mapping may be reported as confirmed.
3. Resolve an exhibit against the actual matter inventory and versioned source identity. A successful identity match is **not** a successful pinpoint match.
4. Compare the exact quoted/numeric assertion to the located source, showing a bounded source crop and OCR uncertainty. `EXACT_MATCH` is allowed only with exact normalized text and verified source location; scanned or low-confidence material remains human-confirmation-required.
5. Open a split web reviewer: draft and highlighted references on the left; original crop, provenance and identity/page/support states on the right; persisted human decision below.
6. Record `CONFIRMED_SUPPORTED`, `CONFIRMED_QUALIFIED`, or `CONFIRMED_CONTRADICTED` with rationale, actor, timestamp, version/hash and idempotent request ID. These are **human decisions**, not automatic AI conclusions.
7. Cold restart, reopen the same matter, and see the same evidence, review and version/hash; ungranted and revoked users cannot access originals, decisions or exports.
8. Download a scoped JSON and Markdown report plus a **reviewed DOCX**. Export must preserve the original draft and distinguish annotations from source edits; unresolved references and OCR uncertainty remain explicit.
9. Verify no production access, no confidential fixtures, no background migration of source files, and zero residual resources for synthetic test runs.

## Architectural rules

- Reuse `infrastructure/parsers/docx_reference_discovery.py` and the existing region coverage model; do not create a second DOCX parser.
- Reuse signed source and review services in `apps/api`, and the existing Phase 3 bounded source/crop endpoints.
- Use a new CaseProof litigation review route; **do not** repurpose the ExceptionDesk invoice demo.
- Treat `RESOLVED`, `MAPPED`, and `EXACT_MATCH` as three independently evidenced conditions, not a single status.
- Preserve `resolved / not_in_inventory / source_missing / page_unmapped` and `supported / qualified / contradicted / not_assessed` as distinct dimensions.
- Reject or qualify unknown DOCX parts, OCR ambiguity, ambiguous exhibit numbering, and cross-matter source identities. No invented source crops.
- No legal authority research, procedural deadlines, or Book 8 sufficiency automation.
- No auto-merge. Stop before first end-to-end UI test and request approval.

## Acceptance gates

Designed → Implemented → offline regression green → protected dev live API green → **UI test authorized by user** → live UI accepted → pilot authorized.

A spec and draft PR are **not** evidence that the UI, extraction or export have been implemented.
