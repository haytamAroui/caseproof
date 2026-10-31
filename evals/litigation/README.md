# M0 synthetic litigation evaluation corpus — NL / FR / EN / mixed

**Current candidate:** `caseproof-litigation-gold-v3` in [m0_corpus_v3.json](m0_corpus_v3.json): 37 author-supplied fictional cases (19 preserved verbatim from v2 + 18 newly authored four-dimensional scenarios). Historical [v2](m0_corpus_v2.json) and [v1](m0_corpus_v1.json) remain unchanged. No customer, court, published vendor content or third-party production data is used. Original authored corpus text is declared **CC0-1.0**; legal/domain labels are **author-supplied and not independently adjudicated**.

**Mechanical evaluation:**
```bash
uv run --locked python -m scripts.validate_litigation_corpus  # frozen historical v2
uv run --locked python -m scripts.audit_m0_trilingual          # new v3 + immutable v2
uv run --locked pytest -q tests/test_litigation_m0_corpus.py tests/test_m0_trilingual_acceptance.py
```

The v3 audit checks source rights declarations, immutable v2 prefix, case/label integrity, independent page spaces (PDF/printed/bundle), unconfirmed/incomplete/complete inventory boundaries, missing source versus missing inventory, no-quote cases, translation, simulated scans and four non-collapsed dimensions. It **does not** run CaseProof's deployed verifier, use a PDF/OCR model, validate actual DOCX structures, measure accuracy/recall against real data or adjudicate legal meaning. An oracle written by the project is **not an independent human reviewer**.

**Language policy:** NL/FR are the first product and legal-domain target; EN is an explicit synthetic evaluation/reference cohort, not a promise of equivalent commercial Belgian-law feature coverage. Mixed cases intentionally contain NL/FR/EN. No German launch obligation.

**Next formal M0 gate:** the [independent adjudication packet](../../docs/m0/TRILINGUAL_ADJUDICATION_PACKET.md) must be reviewed by qualified Dutch, French and English language reviewers with Belgian legal competence for procedural judgments; original decisions, disagreements, sources, date and any corrected gold version must be recorded. Do not silently relabel v2/v3 or claim independent review while those fields are blank. See [rights declaration](../../docs/m0/TRILINGUAL_RIGHTS_AND_COVERAGE.md) and [benchmark protocol](../../docs/m0/BENCHMARK_PROTOCOL.md). M0 engineering fixture gate may pass while the **formal M0 acceptance remains OPEN**.
