# Pilot capacity profile

**Status: APPROVED (Pilot limits defined).**

The pilot supports up to 150 pages. Larger dossiers will be tested on a case-by-case basis.

| Capacity item | Status | Evidence or validation needed |
| --- | --- | --- |
| Signed 150-page synthetic dossier | VERIFIED | [Signed benchmark](https://github.com/haytamAroui/caseproof/actions/runs/41875113829) passed. Discovery took 3.869 seconds in that run. |
| Local text-only page processing | VERIFIED | 200 pages across four PDFs in 34.845 seconds with two concurrent workers and matching checkpoint replay. See the [P1 acceptance record](../p1/PARSER_ACCEPTANCE_2026-11-04.md). |
| 100 OCR pages | TO BE VALIDATED IN PILOT | Measure OCR throughput and completion at this volume. |
| 50 MB files | TO BE VALIDATED IN PILOT | Verify upload, parsing, and export behavior against configured limits. |

The 150-page limit is the approved pilot envelope. The 34.845-second measurement belongs to the separate 200-page local worker run. OCR and file-size targets remain subject to pilot validation and existing runtime limits.
