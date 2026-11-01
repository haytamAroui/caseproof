# F2 viewer comparison protocol — budgets fixed before measurement

Candidate protocol, 1 November 2026. No viewer adoption or completed measurement
is claimed until the actual comparison artifact passes. This file is a measurement
record/protocol; frontend/BLUEPRINT.md remains the sole frontend specification.

Compare isolated Poppler server images with PDF.js 6.5.438 (exact npm pin,
Apache-2.0; LICENSE included in local assets). Both use the same SHA-bound
synthetic originals: clean text, scan, native 90/180/270 rotations, nonzero CropBox,
mixed page sizes/UserUnit, repeated text, hostile OpenAction/URI annotations,
200 pages, overflow 201 pages and corrupt bytes. No client documents or external
viewer service. Server candidate rasterization uses the existing network-disabled,
CPU/memory/time/output-limited OCR container; no server page-image product endpoint
is invented. Browser candidate uses an explicit same-origin worker with no fake
worker, active annotation DOM, scripting integration, external document URL,
WASM, font loading or persistent cache. Static painted annotations remain visible.

Before execution the budgets are:

| Measurement | Budget / evidence |
| --- | --- |
| Fixture fiducial geometry | Four independently specified edges within 2 CSS px at the comparison scale; compare actual painted pixels, not reported target metadata |
| Document opening | Under 5,000 ms for each supported synthetic file |
| Individual browser render | Under 5,000 ms, including page 1/200/100/1 navigation in the 200-page file |
| Server raster page | Under 15,000 ms, per isolated invocation |
| Controlled Chromium aggregate RSS | Under 1 GiB, measured from browser-reported process IDs in the isolated Linux runner; not document-exclusive memory |
| Production safety bounds | 20 MB original, 200 pages, 16 million backing pixels per canvas, 20,000 text items / 200,000 extracted characters per page; 15-second opening/render deadline; bounded disposal then worker termination |
| Source/session integrity | Exact digest, case/brief/reference/source/snapshot; stale, denied, replaced, cancelled and late responses never become current pixels |

Server and browser timings cover different deployment boundaries: server includes
container startup/rasterization; browser records local same-origin fixture body
reading/opening and rendering separately. This is a constrained engineering
comparison, not a general performance ranking. Record PDF.js/package lock, actual
Poppler/image version, Chromium version, runner CPU/OS, timings, memory scope,
geometry results, unsupported cases and cleanup. UserUnit discrepancies remain
measured differences; do not force the server candidate to claim agreement.

PDF.js is a candidate because its native viewport models CropBox origin, rotation
and UserUnit, while one-page rendering keeps long-file rendering bounded. Adoption
requires executed evidence, not this rationale. Worker isolation is not an OS
security boundary; independent hostile-content/deployment review remains open.
Browser-only request capture does not establish whole-machine zero egress.

Legacy frozen raster boxes omit full page-box geometry. They are disclosed and
not guessed onto a viewport. PDF-derived text search boxes are separately labelled
navigation aids; all supported repeated occurrences stay visible, unsupported
glyph transforms stay without boxes, and no engine verdict or human decision is
changed. Pixel inspection never certifies that a reviewer inspected a crop.

Primary references: [Mozilla API](https://mozilla.github.io/pdf.js/api/draft/api.js.html),
[Mozilla PDF.js security advisory](https://github.com/mozilla/pdf.js/security/advisories/GHSA-wgrm-67xf-hhpq),
[pinned package](https://www.npmjs.com/package/pdfjs-dist/v/6.5.438).
The pinned v6 API no longer exposes `isEvalSupported`; use its actual typed API,
CSP and built-source inspection rather than passing an obsolete flag.
