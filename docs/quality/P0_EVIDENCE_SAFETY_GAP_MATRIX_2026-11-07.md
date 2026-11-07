# CaseProof P0 evidence-safety gap matrix — 7 November 2026

**Audit base:** main at dc848806 (merged Storyteller PR #196), followed by feature branch
feat/p0-evidence-falsification-paraphrase-guard. **No approval to merge or deploy**
is implied. This is an evidence-first gap matrix, not a legal assessment.

The repository has **no canonical check_engine.py** at this revision. The
production dossier path is
[domains/disputes/dossier_verification.py](../../domains/disputes/dossier_verification.py),
[apps/api/dossier_journey.py](../../apps/api/dossier_journey.py),
[application/litigation/dossier_contracts.py](../../application/litigation/dossier_contracts.py);
the distinct reference checker lives in
[application/litigation/brief_checks.py](../../application/litigation/brief_checks.py).
The reusable kernel has an independent
[exact-fidelity evaluator](../../packages/evidence_kernel/domain/fidelity.py)
and [prospective grounding eligibility gate](../../packages/evidence_kernel/domain/grounding.py).
Neither a source-text match nor a grounding-eligible candidate is a legal verdict.

## Code-grounded status (not aspirational)

| Safeguard | Status | Verified code basis and what remains |
|---|---|---|
| P0 Pinpoint falsification | **PARTIAL** | Physical-versus-printed mapping requires confirmation; a quote on a different page is not matched; multiple matches, changed version and unreliable OCR abstain in brief_checks.py, dossier_verification.py and dossier_contracts.py. Controlled labels and independent full PDF/polygon version-falsification acceptance are still needed. |
| P0 Paraphrase Review Guard | **PARTIAL** | New paraphrase_guard.py compares limited guarded terms only around a unique quote in derived text, and otherwise abstains. It warns about amounts, dates, numbers, party names, articles, NL/FR negation/qualifiers. Added to frozen signed dossier report and reviewer screen. No NLP semantic conclusion or validated precision/recall. |
| P0 Safe review defaults | **PARTIAL** | Dossier findings support begins not_assessed; ReviewPanel now requires explicit radio selection, rationale and actual source inspection before a browser save; no bulk approval in the workflow. Server rejects CONFIRMED_SUPPORTED on unresolved identity/pinpoint; explicit source-inspection receipt semantics and genuine-signed acceptance are not yet independently validated for this change. |
| P0 Coverage visibility | **PARTIAL** | Dossier records scanned regions, source page processing, unprocessed sources, unsupported dialect, unknown page counts, OCR/visual uncertainty; release policy distinguishes detected-finding reviews from whole-document recall. Missing oracle entries do not automatically mean fabricated. Independent reference-recall/coverage experiment remains open. |
| P0 Export safety | **PARTIAL** | release_completeness.py verifies all detected findings reviewed before a complete_review release; dossier_export_release.py checks actor, snapshot, authenticated release intent and applicable rights. Complete review explicitly does not mean complete source coverage. Dev migration deployment and genuine-signed rollout remain separate. |
| P1 Reviewer accuracy benchmark | **MISSING** | Seeded NL/FR cases and 2-arm assignment protocol exist in this PR, but no independent labels, randomized real reviewers, adjudicated error rates, timings or inter-reviewer agreement have been measured. Never claim human accuracy from unit tests. |
| P1 Context-aware evidence display | **PARTIAL** | Existing original PDF/crop plus source text; new guard presents up to 760 characters surrounding unique exact quote in derived page text. Nonquote paraphrases, OCR scan pixels and ambiguous anchors always require original-PDF review. It is NOT a validated source polygon or complete paragraph chain. |
| P1 Source-linked review receipts | **PARTIAL** | Signed frozen snapshot contains source version/sha/page; the review ledger stores reviewer identity, rationale, region IDs and snapshot. Durable receipts do not yet independently serialize an exact source quote hash + text locator + reviewed guard warning IDs for every judgment. |
| P2 Advisory NLI experiment | **MISSING** | No production NLI added; keep off until randomized human comparison supports a benefit and no unsafe confidence gain. |

## Deterministic guard contract

- The **only** anchor eligible for lexical comparison is a *unique verbatim*
  occurrence in the exact frozen, version-pinned derived page text. This is
  navigational, **not** verified source pixels.
- Missing source/version/pinpoint, duplicate quotation, absent quotation,
  partial/truncated extracted text, unreliable OCR, translation/cross-language
  uncertainty and oversized paragraphs **abstain** rather than generating
  contradiction or verification outcomes.
- Numbers, dates, EUR amounts, article numbers, conservative party names,
  negations and qualifiers are **priority warnings**, never a decision. A
  missing term in a text window does not mean it is missing from adjacent
  sources. False positives are expected until independent legal review.
- The guard's semantic_support is **always** not_assessed, even when no
  warning is emitted. No model call or external provider egress occurs.
- Every new report is bound to source version, original digest, mapped
  physical page and frozen snapshot. Older historical reports with no guard
  remain readable with an explicit no-guard notice.

## Reproducible synthetic falsification

From repo root, using the locked Python environment:

    uv run --locked pytest -q tests/test_paraphrase_guard.py tests/test_p0_review_benchmark_manifest.py tests/test_dossier_journey.py
    uv run --locked pytest -q tests/test_citation_fidelity.py tests/test_exhibit_identity_pinpoint_split.py tests/test_litigation_m1_pdf_ocr.py
    uv run --locked ruff check application/litigation/paraphrase_guard.py tests/test_paraphrase_guard.py
    uv run --locked mypy --explicit-package-bases application/litigation/paraphrase_guard.py

From frontend/, Node 24 and pinned npm dependencies:

    npm ci
    npm run contracts:check
    npm run policy:check
    npm run lint
    npm test
    npm run build
    npm run test:e2e

The seeded packet is
[tests/fixtures/p0_review_benchmark_cases.json](../../tests/fixtures/p0_review_benchmark_cases.json).
All fixture labels are **synthetic author seeds, NOT independently adjudicated**;
there are no human submissions or published confidence intervals.

## Controlled human reviewer experiment (P1, not yet performed)

1. Obtain independent two-lawyer NL/FR adjudication of each example, source
   version, mapping, quote, omitted qualifier, amounts, and reviewer interpretation.
2. Randomize reviewers and case order, balancing NL/FR, OCR, paper length,
   error type and reviewer seniority. Compare standard cockpit vs identical
   cockpit plus guarded-term warning. Capture blinded task assignments;
   do not display seeded truth.
3. Record disposition (including abstention), wrong confirmations, missed
   contradictions, time per decision, and inter-reviewer agreement by source
   version. Pre-register analysis and statistical uncertainty; measure warning
   fatigue and false confidence. Never derive human performance from model scores.
4. Only after the above and owner approval, evaluate advisory NLI as a third
   condition. It cannot replace human inspection or reassign legal authority.

## Research rationale and limits

[Ovcharov, *Citation Grounding Measures the Oracle*,
arXiv:2606.00898](https://arxiv.org/abs/2606.00898) evaluates **400
responses** (100 Ukrainian legal queries × four LLMs) against two snapshots
of a national citation graph. The same outputs appear less grounded when
the oracle is sparse; the dense snapshot substantially reduces apparent
hallucinations. Independent legislation adjudication showed that citations
flagged by the sparse snapshot were real. This is **not** a benchmark of
Belgian scanned PDFs, lawyer paragraph judgments, or CaseProof; it motivates
showing unavailable coverage explicitly instead of calling missing index
entries fabrications. Do not cite this as evidence of CaseProof accuracy.

## Merge/pilot gate

Synthetic CI on the exact PR head, standalone security review, current
session/tenant/right fences, and no regression in signed-user flow are
necessary. **A green CI result is not independent NL/FR legal adjudication,
real reviewer behavior, or permission to export a pilot dossier.**
