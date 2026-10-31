# ADR 0020 — Bounded representation disagreement gate

Status: bounded v1 merged in PR #142; v2 integration under review, 31 October 2026.

Renumbered from 0019 to reserve that number for the earlier product ADR in PR #141.

Owner requested a semantic/visual fidelity gate. This extends M2/M3 fidelity
review within ADR 0018, without changing market scope or the pure kernel.

`RepresentationComparison` is an adapter-produced observation bound to original
SHA-256, representation ID, physical page and crop SHA-256. Only a matter-authorized
server adapter may supply it. Never accept browser-supplied reliability or edit flags.
A reliable regional text disagreement or meaning-bearing edit candidate produces
`representation_conflict`; missing/unreliable visual text produces `ocr_unreliable`.
Equal strings produce `not_assessed`, never visual agreement or semantic approval.
The existing literal resolver counts blocked pages as unresolved and prevents an
exact match. Dependent factual comparisons already abstain on these states.

A bounded pixel midline heuristic supplies review candidates only. It may mistake
rules/glyphs for edits and may miss diagonal/color edits, insertions and blur. No
claim of general anomaly detection, OCR reliability estimation or automatic redline
interpretation. Fixture labels must never be fed into runtime inference.

## UI contract and remaining integration

Render a red warning icon plus the text “Representation conflict”; color alone
is insufficient. Show escaped extracted/visual text alongside a privately fetched
crop, page and immutable source identity. Human must confirm/qualify/dismiss with
rationale through existing authenticated review. Confirmation does not rewrite
original bytes, erase the detector result or assert authenticity. New source,
parser, crop or review snapshot requires a new assessment. Do not block a scoped
report disclosing unresolved findings; block presentation as an exact supported match.

`caseproof.representation-review.v1` returns the required crop hash and texts,
not signed URLs. Fetch must reauthorize matter membership and verify crop bytes.
The new comparison field on `EvidencePreview` defaults to empty for compatibility;
no observations means not assessed, never silently passed.

Still open: loading comparisons in signed live adapters, immutable private crop
storage/readback, persisted adapter version/geometry bindings, end-to-end export
and web warning rendering. Existing preview codecs must explicitly adopt this
field before live claims. This PR does not close M3 or add a fifth authority axis.

## Evidence and benchmark interpretation

[Document Processing benchmark](https://github.com/openbenchmarks-labs/document-processing)
measures downstream answers from parser Markdown on redlined contracts, with a
fixed reader/judge. Its 61.6% reported arm is not general legal accuracy, proof of
CaseProof detection quality or evidence of willingness to pay. Public reproduction
uses a smaller corpus than the held-out leaderboard. No exclusivity/moat claim.

Acceptance: real generated clean/redlined PDF and strike-marked DOCX plus image-only
scan; positive and negative pixel candidates; equal-text edit conflict; unreliable
abstention; stale-source rejection; literal-match blocking; existing four dimensions
and current literal behavior preserved when no comparison exists. Synthetic only.


V2 supersedes the v1 page-wide comparison design. See [v2 acceptance and data review](../m3/REPRESENTATION_GATE_ACCEPTANCE.md).
## PR #147 correction — 31 October 2026

Regional text overlap is not source geometry. Until adapters supply validated
source-linked bounds, all comparisons on the cited physical page apply; a regional
conflict cannot be dismissed because its words differ from the quote. This may
increase false alerts but avoids claiming disjointness without evidence.

Citation observations serialize derived `visual_comparison_supplied`,
`visual_coverage` (`not_supplied`, `unknown`, `regional`, `whole_page`) and `visual_assessment`.
Supplied does not mean the whole quote is covered; `regional` identifies bounded comparisons, not complete quote coverage. Equal strings
remain `not_assessed` even for whole-page input. Existing asdict API/export/run-hash
consumers receive these additive fields; constructors retain compatibility via
init=False. Run hashes intentionally change; persisted old records are not rewritten.
Engine version is `caseproof-literal-citation-v2`, and observations carry
`representation-gate-v2` so normalization/scoping behavior is distinguishable.
Web rendering and live comparison adapters remain open; no visual verification
or complete crop coverage is asserted by these fields.


## Compatibility with open PR #146

PR #147 is a bounded foundation update against main, not a replacement for #146.
It retains conservative page gating only where no source-linked regional geometry
is available. #146 introduces anchored regional selection and must preserve those
anchors when reconciled with this branch; do not transplant whole-page fallback
over validated regional logic. Merge order requires rerunning the remaining PR.
ADR 0020 matches #146 representation-gate numbering and avoids the merged product
vision ADR 0019. This branch does not establish joint integration acceptance.


## Combined integration acceptance (PR #146 over #147)

Source-bound offsets retain regional independence; missing offsets retain the
conservative page fallback. Ligature/soft-hyphen normalization now shares raw-offset
lineage with region selection. New rules remain uncalibrated and cannot create
positive visual approval. Current-head cloud and signed development receipts must
be refreshed before acceptance; older evidence above remains historical.
