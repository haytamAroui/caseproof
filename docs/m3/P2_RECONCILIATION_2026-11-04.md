# P2 reviewer workspace reconciliation — 4 November 2026

Baseline: `74de01ec20031cc7a99a6f405d5050664764cedc`; this document describes the worktree based on that baseline, not a merged or independently accepted release. The F4 acceptance record and the consolidated task list remain authoritative. Existing test names below identify coverage, not a fresh signed-user run.

| Task | Existing behavior and executable evidence | Outstanding acceptance |
| --- | --- | --- |
| T49 coverage | Source-page coverage can open a preserved PDF even without a matching finding; unanchored DOCX regions offer an authorized original download when the bound source is available. Current reads are bound to snapshot, digest and length; historical reads use the historical path. | Fresh signed acceptance and independent authorization review are required for expanded source navigation. |
| T52 viewers | `viewer.spec.ts` exercises real PDF.js rendering, page spaces, 200% zoom, rotation, fractional DPR, scans, source switch, sign-out, historical read-only reopening, and source-pixel/overlay alignment on two differently sized pages with non-zero CropBoxes; `test_pr174_raster_contract.py` rejects unsupported geometry. Draft context explicitly abstains for unsafe anchors. | Run at the final head in required CI; retain actual supported browser/device and manual accessibility acceptance as separate pilot checks. |
| T53 review | `test_f4_v31_review.py` exercises authorized ledger, stale/revoked paths, replay, changed payload, missing required regions and invented region IDs; `review.spec.ts` exercises region inspection and lost-acknowledgment reconciliation. The API now rejects invented IDs even when the expected set is empty, matching the existing database-side check. | Final-head signed browser run, competing saves and restart/revocation acceptance remain to be reconciled. A mock is not a live authorization proof. |
| T54 queue and modes | Needs-attention/all, scoped J/K/Space, bounded search and pagination; filtered post-receipt navigation; exact-text comparison. Scan-only OCR words with valid source-bound geometry can be displayed as opt-in numbered positions with an accessible word list. | OCR can be wrong; unavailable geometry abstains. Manual accessibility and representative practitioner validation remain open. |
| T55 recovery | Existing browser tests cover loss of acknowledgment and sign-out, changed snapshot, late source response and denied reads; verification API tests prohibit historical fallback on authorization failure. | Final-head signed expiry, competing-write and lifecycle tests remain open. |
| T56 fidelity | `test_verification_contracts.py` covers translation, OCR uncertainty and newly added mutated date/amount/currency/negation and repeated quotation cases; `test_server_quote_resolution.py` tests ambiguity. | Reconcile remaining workflow fixtures and independent representative corpus. Literal match does not prove legal support. |
| T57 history | `verification/api.test.ts`, `review.spec.ts` and `viewer.spec.ts` exercise historical mode, wrong-scope denial and read-only display; `test_f6_reviewed_exports.py` covers restart and historical released artifacts with a test store. | Final-head genuine authorization, immutability and review attribution acceptance remains open. |
| T75 accessibility | Existing automated axe/keyboard/locale and responsive tests. | Manual keyboard, screen-reader, 200% browser reflow and NL/FR/EN review by a real tester remain open. |

## OCR X-ray and legal redline scope

The opt-in OCR view uses scan-only word boxes with matching source provenance; it does not project layer-token geometry as OCR coordinates or assert correctness. The correction preview uses bounded character-level insertion/deletion, not a document-wide tracked-changes editor. The pilot requirement for native Word tracked changes remains the separate D04/T64 decision. Neither an overlay nor a diff changes backend verification or human review authority.

## Validation and closure

Prior PR-head validation is recorded in the PR description. New coverage/OCR/redline changes require their own final-head CI and signed evidence; do not transfer old receipts to the new head. Local tests use synthetic/mocked services and do not establish a live-backend journey. The build emitted a large-chunk warning.

Record exact final commit, CI URLs and protected signed-browser results before claiming acceptance. Local synthetic tests do not establish live RLS, independent review, manual accessibility, representative data, or deployment approval. No historical review is converted into a current approval. This bundle extends an existing authorized read and introduces no new route, database migration or permission.
