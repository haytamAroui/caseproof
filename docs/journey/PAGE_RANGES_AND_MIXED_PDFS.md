# Page ranges and mixed PDFs

Two correctness repairs after PR #138. No database migration or production
release. Dossier algorithm version is now `caseproof-dossier-v2`, so old derived
snapshots/decisions are not silently reused under the new assessment rules.

- A recognized page range or numeric page list is **unresolved**, with
  `page_sequence_requires_review`; it is never checked by inspecting its first
  page alone. This is safe abstention, not implementation of full range mapping.
  Covers PDF, printed, bundle and unspecified spaces; `p.`, `pp.`, `page(s)`,
  hyphen/en/em/minus separators, numeric lists and common NL/FR range words.
- Each PDF records its textless physical page numbers. A text page elsewhere in
  the file does not suppress the scanned target page's uncertainty.
- Geometry lookup uses actual resolved physical pages, including explicit PDF
  page references, rather than only confirmed printed/bundle mappings or a
  file-wide image-only flag. Missing geometry remains an explicit OCR/review
  state; neither OCR presence nor absence establishes semantic support.

Offline regressions cover range/list refusal on a one-page source and a physical
reference to scanned page 2 in a mixed PDF, with and without an OCR sidecar.
The protected signed workflow additionally creates a genuine mixed original
(text page 1, image-only page 2), ingests OCR, retrieves the real page-2 crop,
rejects a `PDF p. 1-99` pinpoint, persists/reopens review and exports, checks access
revocation and tears down. Expected mixed-case counts: 9 detected, 3 identity/page
checks, 6 unresolved. The original dossier and unreadable-draft regressions remain.
Exact commit, final workflow and executed outcomes are recorded in the PR.
