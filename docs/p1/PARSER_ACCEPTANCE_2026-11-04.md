# P1 DOCX parser acceptance — 4 November 2026

Scope: synthetic DOCX region inventory and text discovery. Both call the shared defused XML parser. UTF-8 and UTF-16 LE/BE with and without BOM, hostile DTD/entity declarations, ordinary text, and explicit UTF-32 rejection are exercised in `tests/test_p1_xml_encoding_acceptance.py`. The initial PR head `9ec14381e6477121e00c2aa000131d4245ceb1ea` passed the [kernel workflow](https://github.com/haytamAroui/caseproof/actions/runs/41851128432); later changes require final-head CI.

The hostile-package tests cover damaged ZIP data, unsupported compression, duplicate names, traversal and a reduced per-part expansion limit. The discovery adapter reports unknown coverage for decompression failures. The synthetic mutation smoke uses a fixed seed, 256 archive mutations and 768 structured XML part mutations; its CI process has a 30-second wall timeout and a 512 MiB virtual-memory limit. It is a narrow mutation smoke, not coverage-guided fuzzing, an OS sandbox for production, or proof of a production processing deadline. The isolated parser applies shared XML bounds to relationships, content types, the document body and notes. Structured mutations exercise the parser with valid ZIP envelopes. Content-type semantics remain outside the scope of XML parsing. No private documents are used.

The parser hardening and bounded mutation checks landed in [PR #187](https://github.com/haytamAroui/caseproof/pull/187). The final PR head passed [kernel checks](https://github.com/haytamAroui/caseproof/actions/runs/41875123217), the [signed benchmark](https://github.com/haytamAroui/caseproof/actions/runs/41875113829), and [signed browser acceptance](https://github.com/haytamAroui/caseproof/actions/runs/41875122925).

| Acceptance item | Status | Record |
| --- | --- | --- |
| Capacity Profile | APPROVED (Pilot limits defined) | [Pilot capacity profile](../pilot/PILOT_CAPACITY_PROFILE.md) |
| Independent Security Review | READY FOR SIGN-OFF (Documentation generated) | [Parser security review](../security/PARSER_SECURITY_REVIEW.md) |

P1 engineering closeout leaves independent sign-off and pilot validation of the OCR and file-size targets pending.

## Existing candidate-capacity evidence

At PR head `bef3c4f4a152e485a0eed5d26f1db04fe1a9176f`, the [disposable dossier CI job](https://github.com/haytamAroui/caseproof/actions/runs/41855260931/job/126662033897) ran `scripts.benchmark_page_processing`: four synthetic text-only PDFs, 200 pages total, two concurrent workers, 200 completed and zero failed in 21.894 seconds; checkpoint replay matched. The log reports parent peak RSS 33,884 KiB and child peak RSS 39,788 KiB. This is one CI measurement of the local page coordinator, not a sum of memory across processes. It is not a signed journey and includes no OCR, browser, export, representative scans or practitioner evaluation. It cannot establish a supported dossier capacity or close T20.

The isolated-worker hostile relationship tests exercise the existing subprocess with its current resource limits and reject external targets, DTD/entity declarations and malformed XML. Content-type semantics are not validated by the discovery adapter or these tests. Independent review remains pending.

Local batch evidence: 95 focused regressions passed with locked dependencies, Ruff and diff checks passed, and the seed 20261104 completed all 1,024 mutations. The local worker benchmark processed 200 text-only pages across four PDFs with two concurrent workers in 34.845 seconds. All pages completed and checkpoint replay matched. Parent peak RSS was 27,468 KiB and child peak RSS was 27,340 KiB. This run covered the local coordinator only. The separate signed benchmark and approved pilot limit are recorded above.
