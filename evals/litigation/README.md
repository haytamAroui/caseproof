# M0 synthetic litigation evaluation corpus

Current version: `caseproof-litigation-gold-v2` in `m0_corpus_v2.json` (previous v1 retained as immutable historical benchmark input). All cases were freshly invented for this repository. No real court record, confidential file or competitor test data. Original authored text is supplied as CC0-1.0; labels are **author-supplied and not independently adjudicated**.

Run `uv run --locked python -m scripts.validate_litigation_corpus` and `uv run --locked pytest -q tests/test_litigation_m0_corpus.py`. The validator checks duplicate sources, aliases, PDF vs printed-page metadata, quote-resolution controls, OCR-unavailable abstention, retrieval qrel references and known labels. It is **not** a litigation application checker and reports no model quality or lawyer productivity.

Current suite: NL/FR/EN/mixed; clean/mismatch/ambiguous/unresolved/scan-unavailable controls; HTVA/TVAC, dates, source instruction-injection, exhibit revisions, cross-language alias and page-offset fixtures. English clean, quote mismatch, ambiguity and unprocessed-scan controls are included. Scanner flags are synthetic metadata; no real image-backed scanned PDF or OCR ground truth. PIV-01 needs rights-cleared image/DOCX/PDF fixtures and independent Belgian legal review before release benchmarking.

Full task rubric: [Benchmark protocol](../../docs/m0/BENCHMARK_PROTOCOL.md). Product gates: [M0 baseline](../../docs/m0/BASELINE.md).
