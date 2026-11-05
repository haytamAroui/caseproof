# ADR 0033 — DOCX-rich editing as a separate optional capability (PROPOSED)

**Date:** 4 November 2026. **Status:** PROPOSED — not an accepted release, change of product positioning, or authorization to deploy. **Decision owner:** unassigned. This proposal responds to the owner's request to extend supported corrections to ordinary paragraphs, tables, textboxes, native Word tracked changes and a Word-style editing interface.

## Context and boundary

CaseProof is an independent source verifier, not Microsoft Word. Existing F5 actions require an exact detected finding, source version, saved review receipt and canonical recheck. A general editor cannot borrow finding-specific authorization for unrelated text or modify frozen exhibits. Changing a DOCX does not approve its citations. Preserve the immutable source, separate derivative version, original/derivative SHA-256, actor/organization/matter, current snapshot and review provenance.

## Split the deliverables instead of claiming parity

1. **DOCX-native engine (this PR, experimental):** an offline/infrastructure kernel that identifies plain paragraphs in main document, top-level and nested table cells, supported textbox stories, headers/footers and note stories. It can replace the *complete plain-text content of an editable paragraph*, emit true OOXML `w:ins`/`w:del` revisions, and accept/reject supported textual revision IDs. It does not collapse or delete unknown structural descendants to create a false 'successful edit'. Other package members remain unchanged.
2. **Signed candidate API and structured editing workspace (this PR, experimental):** `/dossier/editor/blocks`, `/revisions`, `/preview`, and `/candidate` reopen the exact authenticated current source, require a current snapshot, derive the tracked-revision author from server-verified identity, refuse stale selectors, and return bounded preview receipts or downloadable SHA-256-verifiable DOCX candidate bytes. The React workspace offers paragraph/table/textbox text editing and textual native revision decisions. Candidate preview/download never mutates the source. Additional review/status/commit routes and a dedicated document-wide SQL proposal are implemented but **not installed**; in live environments those consequential writes fail closed. This is **not** a pixel-faithful Word interface.
3. **Existing verified F5 (unchanged):** finding-bound citation edits, durable signed activation and recheck; the OOXML engine is **not** wired as an alternate route to bypass actor-scoped, reference-scoped PostgreSQL reservation.
4. **Full browser Word-style UI (NOT IMPLEMENTED):** requires a supported embedded editor with source input/output, faithful rendering, capability isolation, accessibility and safety. A visual imitation made from `contentEditable` is insufficient.
5. **Office host (available external workflow, NOT integrated):** Microsoft Word can author paragraph/table/textbox edits and revisions but CaseProof still requires a separate reviewed derivative import/activation bridge. A downloaded copy is not an accepted CaseProof version.

## Engine correctness contract

- All edits bind to an expected SHA-256 of *the exact complete source DOCX* and expected SHA-256 + exact text of each selected paragraph. Duplicate, invalid, stale or unsupported targets refuse.
- Plain text paragraph replacements preserve source document paragraph properties and first-run style, not every old mixed-run style. Explicitly report that limitation.
- Suggesting mode generates actual `w:del` with `w:delText` and `w:ins` with author/UTC timestamp; unsupported existing revision structures are not silently normalized. Accept/reject operates on exact part/revision IDs and refuses nested/complex revisions.
- Original input bytes never mutate; output is a separate ZIP archive; all unaffected package-part *uncompressed bytes* remain equal. Package must re-pass existing security preflight and XML safety limits.
- A signed **structured text editing UI** and preview/download API now exist. They return uncommitted local candidates. A separate persisted actor-scoped review + reserve + trusted readback/activation path is implemented in source and proposed SQL, but the proposal is not installed and cannot yet activate a real user draft. The new `draft:edit` permission is required for review/reserve and checked again at trusted activation; existing F5 citation privileges cannot substitute. Word rendering/page-layout parity remains unimplemented.
- Host-generated timestamps in signed persisted edits must be bound to the durable operation fingerprint, never regenerated on a blind retry.

## Editor engine options and licensing (4 November 2026)

- **SuperDoc v2:** DOCX-native browser editor, tracked changes/comments; public AGPLv3 or a separate commercial license. No AGPL dependency may be merged under current CaseProof distribution rules without an owner/legal choice. [Editor documentation](https://docs.superdoc.dev/editor/) · [License](https://docs.superdoc.dev/resources/license/).
- **OpenDoc / CasualOffice:** Apache-2.0, supports Word-style toolbar, tables, textboxes and revision modes, but the public embedded host contract still lacks `open(bytes)` and host-visible DOCX export. Published SDK is pre-release; a host cannot supply the authenticated preserved CaseProof draft. It must not be marketed as a fully integrated CaseProof editor yet. [Project](https://github.com/CasualOffice/opendoc) · [Embedding contract](https://opendoc.casualoffice.org/embedding.html).
- **Native Office host:** desktop Word provides its own license, UI and revision mode. CaseProof does not assert host custody or Office Word file compatibility without actual tests.

## Required work before general editing can be activated

- Owner must approve product expansion relative to ADR 0018/0019 and the frontend blueprint; record choice of editor engine, licence, ongoing security owner, accessibility and 3–5 practitioner observations.
- **Review and approve, then install** the new document-scoped signed approval contract in [review-only SQL](../security/DOCX_EDITOR_DOCUMENT_SCOPE_SQL_PROPOSAL.sql). It uses an explicit `draft:edit` grant, separately persisted exact command digest, audit-atomic reserve and fresh trusted activation check. No fake finding is used. Its disposable SQL script and API integration tests are candidates for CI; deployment, real signed activation/cold reopen, independent security review and release approval remain OPEN.
- Add loss-aware host import/export with canonical DOCX re-validation, compatibility/omission reports, styling/regression corpus, backed-up source and derived hashes. Verify authored tracked revisions in desktop Microsoft Word and LibreOffice. All uncovered structures explicitly abstain.
- The candidate request contract is Pydantic strict and the browser checks response fields, byte lengths and SHA-256; **generated JSON Schema → TypeScript/AJV** contracts for this new editor contract remain required before independent release approval. The React editor wipes working state on version/actor route remount. A truly embedded Word-fidelity engine still requires an approved host with source input/output. No browser document text in URLs/logs/persistent storage.
- Genuine signed full-document editing → source-bound preview → reviewed activation → mandatory recheck → history and revoked denial; zero residual fixtures and manual WCAG 2.2 AA testing.

**Rollback:** remove experimental module/CLI and tests; existing F5 remains unchanged. Never migrate or deploy new document-editing privileges merely to satisfy a demo.
