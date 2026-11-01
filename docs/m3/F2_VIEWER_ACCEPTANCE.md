# F2 viewer engineering acceptance record

1 November 2026. PR #166, based on merged F1 #165 (`66ca9f0`).
Engineering implementation and automated assessment: Codex. Independent human
review, security/privacy, representative legal-source visual review, manual
screen-reader review and deployment approval remain open. No client documents,
provider requests, new database migration or production installation were used.

## Same-fixture measured renderer decision

The [protocol](F2_VIEWER_COMPARISON_PROTOCOL.md) fixed tolerances and budgets before
execution. [Comparison run 41353141202](https://github.com/haytamAroui/caseproof/actions/runs/41353141202)
passed on code `b560d5cec9e20d07750a1f51f3c8839ee42101a3`. Its [retained JSON receipt](F2_VIEWER_MEASUREMENTS.json) records
all fixture timings and hashes. PDF.js **6.5.438**, exact lockfile/integrity and local
Apache-2.0 license, is selected for the bounded browser adapter. Isolated Poppler
**22.12.0**, image `sha256:b77d705f1ea1fdbaa2392ef323866478e201c16ca4407292600f216f35e39826`,
remains a test-only comparator. There is no added server-image product API.

Actual runner: Linux, AMD EPYC 7763 64-Core Processor; Chromium 156.0.8078.4.
Controlled aggregate Chromium RSS was **435,580,928 bytes** (budget <1 GiB).
This is aggregate measured runner memory, not per-document or peak memory proof.

| Measurement | Actual result | Predeclared budget |
| --- | --- | --- |
| Opening supported synthetic files | 139.6–148.8 ms | <5,000 ms each |
| Browser page rendering | 12.2–47.0 ms | <5,000 ms each |
| Isolated server raster page | 224.1–456.9 ms | <15,000 ms each |
| Four independent painted fiducial edges | Max 2 CSS px on scan; 0 on other initial fixtures | ≤2 CSS px |
| 200-page navigation 1/200/100/1 | 35.7 / 20.6 / 12.7 / 12.2 ms | <5,000 ms each |
| Native/extra rotations, CropBox and DPR | Independent painted-edge assertions passed | ≤2 CSS px |
| Static hostile-file StrikeOut annotation | Painted red pixels preserved | >20 expected red pixels |
| Hostile OpenAction/URI | No script marker or external browser request | No execution/request |
| Corrupt/201-page input | Rejected, document/worker close passed | Bounded failure |

Both engines read the same original SHA-bound fixtures. The mixed file's second
page has UserUnit=1.25: PDF.js produced the expected **2000×1500** backing pixels;
this Poppler build produced **1600×1200**. The browser viewport correctly models
that scale, plus CropBox origin and rotations. This measured difference and the
passed rendering/geometry/cleanup budgets support the engineering choice.
Server timing includes isolated container invocation; browser timing measures
same-origin body reading/opening and rendering separately. These figures are not
a general engine performance ranking or a representative-corpus benchmark.

## Source, session and user-interface evidence

The real frozen source boundary checks current grants, frozen HMAC/source-set,
version/original digest and original bytes. Browser binary transport rechecks
snapshot/length/header digest and computed SHA before parsing. Tests cover altered
same-length bytes, denied reads and late binary responses after session end.
One explicit local worker, one rendered page, resource limits and bounded disposal
avoid an unbounded page stack. Worker isolation is not an OS security boundary.

Production-build browser tests use actual PDF.js workers with synthetic transport,
not a fake renderer. They cover repeated search locations, zoom/rotation/page
navigation, CropBox/UserUnit, responsive layout, keyboard-owned scrolling, axe,
reference switching, tampered bytes and signout canvas/worker disposal. Genuine
signed development acceptance receipts are recorded below only after execution.

Legacy raster boxes without full page-box provenance are deliberately disclosed
and unprojected. Extracted text/boxes are derived navigation aids; no source visit,
box, page load or search changes identity, mapping, fidelity or human support.
Printed/bundle page mapping and manual crop attestation remain backend/F4 scope.

Local full Python suite: **1,930 passed, four general live gates skipped**.
Frontend: **38 unit/architecture tests passed**, lint/type/contract/build checks,
and strict UI audit zero findings. Separate signed workflow evidence must not be
inferred from skipped general live gates. No independent approval is fabricated.

## Passed signed-development and final code receipts

Final code `210326c018d95770fdd9ab632698473e639ff1fa` passed all **17 ordinary
PR workflows**, including [production-build browser tests](https://github.com/haytamAroui/caseproof/actions/runs/41353604598)
and [same-fixture comparison](https://github.com/haytamAroui/caseproof/actions/runs/41353604538).
The retained numerical comparison above is the preceding measured code head;
the final change adds bounded signed-test diagnostics/waits and corrects the
read-only notice, with no renderer/source-contract change.

The protected [genuine signed-development run 41353602246](https://github.com/haytamAroui/caseproof/actions/runs/41353602246)
used that exact final code and emitted:

- `F2_VIEWER_CONTEXT_HTTP_200`
- `F2_VIEWER_ORIGINAL_HTTP_200`
- `F2_GENUINE_FROZEN_SOURCE_HASH_BOUND_WORKER_RENDER_ZOOM_ROTATE_PASSED`
- `F1_GENUINE_SIGNIN_CATALOG_REPORT_COLD_RELOAD_FOREIGN_UNGRANTED_AND_BROWSER_CLOCK_EXPIRY_PASSED`
- `F1_GENUINE_GRANT_REVOCATION_DENIAL_AND_PRIVATE_VIEW_CLEAR_PASSED`
- `ZERO_RESIDUAL_VERIFIED`
- `DOSSIER_COMPLETE_SIGNED_JOURNEY_AND_TEARDOWN_PASSED`

This serves the built React application from the actual loopback Python runtime,
uses real ephemeral provider accounts and signed grants, and reads the actual
registered synthetic original through the frozen-snapshot route. Initial source
reads took about 8.4 seconds across metadata and binary requests, exceeding the
initial test's default five-second assertion wait. The acceptance wait now covers
the existing bounded requests/rendering; no product budget or authorization was
weakened. The first failed attempt also verified zero-residual teardown. Only
fixed stage names/status numbers are logged; no credential-bearing traces,
screenshots, raw exception text or source response bodies are recorded.
Browser-clock expiry checks use the genuine provider expiry with controlled
browser time; they do not establish wall-clock provider expiry.

These receipts close the specified F2 **engineering exits**. The later receipt-only
documentation commit changes no executable code. PR review and the independent
approvals identified above remain separate. F3 intake, F4 review, F5 corrections,
F6 artifacts and full M3 completion remain open.
