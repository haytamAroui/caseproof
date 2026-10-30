# M5 stress benchmark — execution record

**Status: FIRST SIGNED LIVE RUN PASSED (partial metrics only).** Do not infer accuracy, performance or scalability from the generator alone.

## Synthetic input
Run `python -m scripts.m5_generate_stress_docx --output /tmp/m5-150.docx --truth /tmp/m5-truth.json`. This produces 150 explicit DOCX page breaks and 60 NL/FR reference candidates, including mismatched identifiers and impossible page numbers. A DOCX renderer may paginate differently. A full benchmark additionally requires a separate inventory, text PDF and image-only scanned PDF with labeled expected source locations.

## Reproducible acceptance protocol
1. Pin commit, environment, worker CPU/RAM, OCR version and source SHA-256.
2. Provision isolated signed matter, upload all four sources, ingest and capture timing at each stage.
3. Call discovery; match each reference to independent human-annotated identity/page/crop/fidelity truth.
4. Measure end-to-end p50/p95 time over repeated runs, peak memory, OCR timeouts and denial handling.
5. Count TP/FP/FN/TN **separately** for identity, physical-page mapping, fidelity and semantic-support claims. No global VERIFIED state.
6. Zero falsely verified claims is a hard safety gate. Unknown/refused results are not silently converted to matches.
7. Record confidence intervals and adjudicate disagreements. Clean up all ephemeral records.

## Results
| Metric | Result |
|---|---|
| 150-page source generation | PASSED: 150 intended pages, 60 references |
| Four-file API execution | PASSED: signed caseproof-dev, run 41081792051 |
| Discovery wall time | 2,470.271 ms (one run) |
| Client Python peak allocation | 129,215 bytes (not API RSS) |
| API process peak RSS | NOT MEASURED in first run; instrumentation added |
| Extraction TP / FP / FN | 60 / 0 / 0 |
| Extraction precision / recall / FNR | 100% / 100% / 0% |
| Statistical FPR | NOT MEASURED: TN candidate universe undefined |
| Legal identity / fidelity / semantic-support error | NOT MEASURED |
| OCR crop integrity | Signed SHA-verified Phase 3 crop passed |

**Exit:** attach real CI run URL, raw metrics and reviewer-approved ground truth before claiming scale acceptance.

First run evidence: https://github.com/haytamAroui/caseproof/actions/runs/41081792051 . Reference detection counts are not evidentiary correctness; server RSS and security follow-up run remain pending.
