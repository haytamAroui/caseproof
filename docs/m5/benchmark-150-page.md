# M5 stress benchmark — execution record

**Status: NOT RUN.** Do not infer accuracy, performance or scalability from the generator alone.

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
| 150-page source generation | NOT RUN |
| Four-file API execution | NOT RUN |
| Wall time / peak RSS | NOT MEASURED |
| False-positive rate | NOT MEASURED |
| False-negative rate | NOT MEASURED |
| OCR timeout / crop integrity | NOT MEASURED |

**Exit:** attach real CI run URL, raw metrics and reviewer-approved ground truth before claiming scale acceptance.
