# ADR 0028 — replaceable evidence viewer and explicit geometry boundary

1 November 2026. Status: F2 implementation/comparison candidate. Engine adoption
requires the executed [comparison protocol](../m3/F2_VIEWER_COMPARISON_PROTOCOL.md)
and exact-head browser/source-scope evidence. No independent reviewer is invented.

F1 is merged (#165, main 66ca9f0). F2 adds a frozen-reference inspection adapter
through the existing receipt/grant/source-set boundary. Metadata and actual bytes
bind case, brief, snapshot, reference, source version and original SHA-256. The
browser checks actual size, response snapshot/digest and computed SHA before parsing.
Every sensitive read is reauthorized; no Storage URL, service key, browser database
access, report creation or verdict mutation is introduced. No migration needed.

The candidate PDF.js adapter is pinned to 6.5.438, loaded lazily with an explicit
same-origin worker, no fake worker, WASM/font asset loads or annotation DOM. Static
painted annotations remain visible; actions/links/scripts are never exposed as
interactive content. Current typed v6 no longer exposes `isEvalSupported`; old
examples are not configuration authority. Source scripts, package integrity and
CSP are checked along with actual hostile fixture behavior. The local Apache-2.0
LICENSE is shipped. Worker isolation does not establish OS-level resource safety.

One page is rendered at a time. Original, page, text-item, text-character, pixel,
open/render and disposal budgets are specified before comparison. Cancellation,
selection generations, key-bound components, zeroing old canvases and worker/task
teardown prevent old-source pixels or text becoming the new selection. Zoom has
real CSS reading size, bounded backing pixels and independent DPR. The source panel
owns its scrolling and resize observer; the application keeps document scrolling.

The actual native viewport supplies CropBox origin, rotation and UserUnit. Canonical
PDF user-space boxes are transformed through all four corners, then backing pixels
and CSS scaling. Nonfinite/singular geometry is rejected. Repeated derived text
locations are all retained; search never establishes identity/fidelity/support.
Legacy frozen raster regions lack complete MediaBox/CropBox/rotation provenance:
the new viewer discloses them and does not guess a projection. Existing crop APIs
and downstream F4 human-inspection contracts remain authoritative and unchanged.
No visit, page load or text box automatically certifies human inspection.

The isolated server-image candidate uses the same originals and expected painted
fiducials. It remains test-only: no invented page-image production endpoint and
no second production renderer. Record actual geometry, version/hardware, timing,
RSS scope, 200-page navigation, hostile/corrupt/overflow failures and cleanup before
adoption. A measured engine comparison is not a representative legal-corpus or
independent security/visual/manual-screen-reader acceptance.

Rollback removes the new viewer routes, projection, UI/engine dependency and
comparison fixtures/workflows. Existing snapshots, original bytes, grants,
verification/review/export services and older clients remain unchanged. F3 intake,
F4 review writes, F5 corrections and F6 artifacts remain separately open.
