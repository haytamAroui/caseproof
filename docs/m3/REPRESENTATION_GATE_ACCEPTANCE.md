# Representation fidelity gate v2 — implementation and acceptance

Owner authorized combined implementation on 31 October 2026. Extends ADR 0020;
issues #143–145. Kernel public contracts and market scope remain unchanged.

## Data/access review

| Existing relationship | Behavior |
|---|---|
| org → private matter → source versions | Current signed membership, matter grant and original SHA checks |
| matter → dossier snapshot (immutable hash) | Existing private JSON snapshot holds bounded region metadata and PNG bytes |
| snapshot → reference → human decision | Existing append-only reviewer/rationale transaction, idempotent request ID |
| reference → region → crop | Exact snapshot hash, regional bounds, source SHA, raster SHA, crop SHA and algorithm versions |

No new tables or indexes. Added read-only `caseproof_dossier_snapshot_read`
delegates authorization/freshness/retention denial to the installed dossier RPC,
then reads the same locked case's snapshot. Only authenticated execute is granted;
no direct table privileges. SECURITY DEFINER is needed for existing private tables,
not a bypass of failed access. Rollback: drop this function and disable v2 frozen
read/crop UI; preserved source and old snapshots remain readable through old tools.
The migration requires cloud disposable SQL/adversarial tests and review before
caseproof-dev installation; production is outside this work.

Snapshot payload <=1.9 MB, <=4 referenced pages, <=96 word regions/page and 200 KB
crop bytes/page. Budgets are explicit partial coverage, not complete parsing. No
sensitive source text or PNG in telemetry. Existing matter retention cascades
snapshot rows/crops; backups remain subject to the existing retention limitations.

## Semantics

- Exact quotation fidelity stays lexical. Visual state and coverage are explicit.
- Every assessed PDF page, including PDFs with text layers, is independently
  rendered and OCRed with the existing no-network bounded binary runner.
- Poppler word boxes align layer and OCR; painted vector strokes and pixel
  midlines produce candidates. Complicated transforms/clipping/forms/annotations,
  scan-only sources, handwriting, insertion-only edits and blur can remain unknown.
- NFC/whitespace normalization retains originals and offset ranges. No edit-distance
  threshold, number/sign/punctuation rewriting, NFKC or speculative dehyphenation.
- Only an immediately delimited quotation after an explicit page reference gets a
  regional assessment. No quote means page candidates are context only. An unrelated
  same-page candidate cannot become a conflict for the reference.
- No calibrated artifact ships. Raw OCR scores are not probabilities. Agreement
  remains not_assessed/uncalibrated; a finite-threshold, document-level held-out
  risk-bound utility is available, with adjudication/split/shift constraints.
- Findings and crop bytes persist in the immutable private snapshot. Reopen,
  review, export and crop lookup can use its hash without rerunning OCR. Changed
  bundle/confirmation or revoked grants reject replay. A human review records exact
  selected region IDs in its rationale and never erases a machine conflict.
- The UI shows warning text plus icon, escaped layer/OCR text and signed PNG crops;
  loads compare returned crop/source/snapshot hashes, and no automatic support.

## Evidence required before closure

Actual generated document → sandbox raster + OCR + vector/pixel candidate → signed
API → private persisted snapshot → source-linked PNG readback → explicit review →
process restart → identical reopen → JSON/Markdown/DOCX export. Include clean same-page
control, hidden/white/clipped/overlaid layer, text-only/image-only/dual-view ablation,
blur/diagonal/coloured edits and unsupported abstention. Freeze fixture rights/hashes,
labels and denominators; measure detection and review workload, not legal accuracy.
Only record real run links/results. Synthetic corpus is not commercial calibration.
