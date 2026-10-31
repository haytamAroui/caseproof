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
  selected region IDs in a separate bounded attestation and never erases a machine conflict.
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

## Development installation receipt — 31 October 2026 Brussels

Connected Supabase MCP installed the reviewed function in `caseproof-dev`
`ldwmocpxwskvhoojndrd` as migration `20261030235107_representation_snapshot_read`.
Canonical SQL matches `db/proposals/REPRESENTATION_snapshot_read.sql` exactly.
Read-only catalog inspection verified SECURITY DEFINER, empty search path,
`anon` execute denied, `authenticated` execute granted and direct authenticated
SELECT on private snapshots denied. Both dossier tables retain RLS. Disposable
SQL denial/staleness/retention tests passed in cloud run 41146632949.

Advisors show 27 existing RLS-without-policy informational notices (private RPC
owned tables), 10 authenticated SECURITY DEFINER warnings (9 before this addition),
and existing leaked-password-protection warning. The added warning is intentional
for this guarded read RPC, not a clean-security attestation. See
[function warning guidance](https://supabase.com/docs/guides/database/database-linter?lint=0029_authenticated_security_definer_function_executable)
and [Auth password protection](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).
Independent security/human release review remains a separate gate. No production
project was changed. Signed acceptance evidence is recorded on PR #146 after actual
execution; catalog checks alone are not signed-user acceptance.

## Structured attestation correction after code review

Review found that controller-only validation could be bypassed through the public
RPC and 31+ region IDs exhausted rationale length. The additive attestation
migration adds bounded JSON `reviewed_region_ids` to the existing private
`_phase4_reference_decisions` row. No new table, FK, index or grant is introduced;
existing matter isolation, append-only receipt and retention cascade apply.
The authoritative dossier RPC derives the required IDs from the frozen finding,
requires exact equality, validates bounds and stores IDs independently of rationale.
Replays compare that attestation too. Disposable direct-RPC missing/wrong/partial
IDs and 40-region roundtrip exercise the persistence boundary. Existing decisions
have empty arrays; rollback requires disabling new review routes before restoring
the old function, while preserving recorded attestations. Production is not targeted.

A separate review finding fixed long-page uniqueness: normalization-budget overflow
abstains before anchoring, rather than silently truncating and selecting one crop.

Attestation migration installed through connected MCP in caseproof-dev as
`20261030235456_regional_review_attestation`, after disposable direct-RPC tests
passed in run 41147125040. The JSON column is non-null with an empty-array default;
anon function execution and direct authenticated decision-table SELECT/INSERT
remain denied. No production schema change.

## Server-authenticated provenance for frozen reads

The legacy signed snapshot-write RPC validates matter ownership/shape, not machine
authorship. A reader could write custom findings/crops. Frozen reads therefore
require an HMAC-SHA256 receipt over the entire canonical machine report, including
the exact matter/brief/source set, all regions/crop bytes, processing versions and
coverage. The key is domain-separated from the existing server-only dev processing
credential and never returned to callers. Missing configuration, absent/altered
receipts and substituted source sets fail closed; no public key can mint receipts.
Human decisions remain separately authenticated records appended on export. This
proves origin/integrity relative to that server key, not authenticity or accuracy.
Key rotation invalidates old receipts until a separately designed key-version
recovery policy exists. The legacy RPC may hold untrusted snapshots; these routes
must never use them without receipt validation. Production key custody is not
approved by this development implementation.

## Bounded crop transport

Frozen crop reads use the guarded snapshot RPC and server receipt; original bytes
are verified when the snapshot is created. They do not redownload/reparse originals
per word. The panel requests <=96 selected regions in one authenticated batch per
finding, validates every returned identity/digest and waits for image decoding.
Single-crop lookup remains available. Both retain current database permission,
retention and bundle/confirmation freshness checks. Crop responses explicitly mark
original availability as `verified_at_snapshot_creation`; live original byte
availability is rechecked by review/export reopening, not asserted by a cached PNG.
No shared private cache or additional retention store is introduced.
