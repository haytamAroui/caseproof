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
| Genuine signed browser on retrofit | Passed on `bbec587a553e505afcd2e2cfd8c860dfde1274b1` | [Protected F2 run 41442263479](https://github.com/haytamAroui/caseproof/actions/runs/41442263479): real source switching, labels, unchanged dimensions, expiry/relogin, denial and zero-residual cleanup |
| Independent security/privacy/manual accessibility/representative corpus/deployment | Separate open gates | No independent approval or legal validity inferred from CI |

## Measured engineering receipts

Executable head `bbec587a553e505afcd2e2cfd8c860dfde1274b1` passed **18/18 workflows**: 17 ordinary PR workflows and protected F2 genuine signed-browser acceptance. [Frontend CI 41442270274](https://github.com/haytamAroui/caseproof/actions/runs/41442270274) passed 68 unit tests, 21 production-build real-worker browser tests including axe, 62 affected Python tests, generated contracts, Ruff/mypy, boundaries, policy, lint and production build. [Renderer comparison 41442270073](https://github.com/haytamAroui/caseproof/actions/runs/41442270073) retained the existing predeclared geometry/hostile/200-page budgets. No new renderer performance or representative-corpus claim is made.

[Protected run 41442263479](https://github.com/haytamAroui/caseproof/actions/runs/41442263479) used actual ephemeral signed accounts, current grants and preserved source bytes in the loopback runtime. It emitted:

- `F2_GENUINE_PAGE_SPACES_AND_UNCERTAINTY_PRESERVED_PASSED`
- `F2_GENUINE_FROZEN_SOURCE_HASH_BOUND_WORKER_RENDER_ZOOM_ROTATE_PASSED`
- `F1_GENUINE_EXPIRED_HISTORY_EXPLICIT_RELOGIN_REOPEN_PASSED`
- `F1_GENUINE_GRANT_REVOCATION_DENIAL_AND_PRIVATE_VIEW_CLEAR_PASSED`
- `M05_STORAGE_EMPTY_VERIFIED`
- `ZERO_RESIDUAL_VERIFIED`
- `DOSSIER_COMPLETE_SIGNED_JOURNEY_AND_TEARDOWN_PASSED`

Signed source switching waits for the selected source's actual binary response before reading its labels; a previous page's rendered notice is not target evidence. The real fixture has PDF p.1 / bundle p.12 for the text source and PDF p.1 / printed p.7 for the scan. The separate synthetic transport test covers printed p.4 → PDF p.6 at 200%. These are different evidence scopes. Earlier failed signed attempts also verified zero-residual teardown; they are not passing receipts. No credential-bearing traces/screenshots, source bodies, private URLs or raw browser assertion errors are logged.

Browser expiry is controlled browser time against a genuine provider expiry, not wall-clock provider expiry. General skipped protected pytest jobs are distinct from this executed F2 workflow. Existing independent security/privacy/manual-screen-reader/representative-source/deployment gates remain open. No human attestation is inferred from a visit or search box.

Local frontend contracts/lint/policy/type/build and 68 unit tests passed; 11 viewer API tests plus affected Ruff/strict mypy passed. Browser evidence above comes from actual GitHub cloud runners. The receipt-only follow-up changes no executable code or configuration; inspect its final cloud status before merge.
