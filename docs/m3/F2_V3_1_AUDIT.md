# F2 workflow v3.1 audit — 2 November 2026

Scope: S2 source pixels/OCR provenance, S3 pagination, S5 independent dimensions, S7 source inspection, S12 recovery and S13 private-state lifecycle. [ADR 0030](../adr/0030-f2-workflow-inspection-recovery.md) records compatibility, limits and rollback. C01/C05/C06/C08/C12/C14/C16/C20/C21/C24/C25 apply.

| Guide requirement | Classification | Evidence / action |
| --- | --- | --- |
| Actual viewport/CropBox/rotation/UserUnit/DPR; 200-page navigation; hostile annotations/no script; bounded worker cleanup | Already implemented | [Existing F2 acceptance](F2_VIEWER_ACCEPTANCE.md) and comparison workflow; retained as regressions, no new renderer |
| Printed/PDF/bundle distinction | Confirmed UI gap | Display canonical page_spaces with physical-target agreement; do not infer an offset or label an exploration page with reference labels |
| Mapped physical page required | Confirmed validation gap | Reject missing mapped page at current route and frontend parser; no page-1 fallback under mapped certainty |
| Deadline/selection fencing | Confirmed lifecycle gap | boundedInspection rejects deadline/cancellation; late result cannot publish derived text; existing pixel/worker teardown retained |
| Source error recovery | Confirmed UI gap | Explicit Reopen source remounts all inspection state, fetches context and digest-bound original anew; no writes or automatic retry |
| OCR/source representation uncertainty | Confirmed explanation gap | Specific canonical OCR/conflict notices; scan pixels and absent selectable text remain independent of assessment |
| Reference navigation and private-source switching | Added regression coverage | Physical p.6 vs printed p.4; 200% zoom; keyboard return; old bytes delivered after selection; denied switch clears canvases/workers |
| Full raster crop overlays with missing transform metadata; human crop attestation | Deferred by existing ADR 0028 / F4 | Disclose unsupported geometry; preserve existing crop APIs, no invented projections or reviewer receipts |
| Genuine signed browser on retrofit | Pending execution | Existing protected F2 workflow and M0.5 scoped fixtures/teardown; ordinary mocks are not live-RLS proof |
| Independent security/privacy/manual accessibility/representative corpus/deployment | Separate open gates | No independent approval or legal validity inferred from CI |

Execution receipts will be added after actual cloud runs. This table is an audit and implementation scope, not a passing claim.
