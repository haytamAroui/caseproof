# PIV-01/20 fixed litigation task benchmark (v1)

**State (31 October):** protocol and original synthetic inputs only, **no independent human or competitor benchmark executed**, no product accuracy/speed numbers. v3 adds 18 four-dimensional boundary cases to the immutable v2 19-case NL/FR/EN/mixed suite. Mechanical labels remain author supplied, not an externally adjudicated benchmark. [Rights and coverage](TRILINGUAL_RIGHTS_AND_COVERAGE.md) · [Reviewer packet](TRILINGUAL_ADJUDICATION_PACKET.md).

**Historical note:** the older protocol initially referred to v2. Its 19 cases remain unchanged as a regression baseline. Corpus under `evals/litigation/m0_corpus_v2.json` is independently authored fictional material, not real court files and not representative of deployed accuracy. Permission to use a competitor's product is required before testing it. M0 validator checks fixture consistency only.

## Evaluation record

Pin all comparisons to corpus SHA-256; task IDs; evaluator and reviewer; date; reviewer qualification; language and type (NL/FR/EN/mixed); equipment/Word/PDF versions; product/client versions; input order; assistance; setup/cleanup time; errors, missing/failed pages and exclusions; evidence IDs/versions; final artifact SHA and reviewer disposition. Record **not tested** rather than fabricate competitor results. Consent and rights clearing required for any added real cases.

## Fixed tasks (identical inputs, different workflows)

| Task | Input / expected operation | Correctness rubric |
|---|---|---|
| T01 import and map | Confirm exhibit identity, alias and distinct PDF/printed pages; handle duplicate aliases | No silent first-match; all unknown/failed pages disclosed |
| T02 check quote/reference | NL, FR and EN own/opponent draft, matched/mismatched quote, missing and incomplete mappings | Exact quote against versioned page; zero false positive on clean control; never infer truth |
| T03 check role/date/amount | Different dated statements and amount bases with EUR HTVA/TVAC and amendments | Identifies typed ambiguity; does **not** claim legal/tax conclusion |
| T04 source search | NL/FR/EN keyword + paraphrase query with manually judged relevant sources | Query recall@k on adjudicated qrels, returned context correct and correct version; lexical ≠ semantic correctness |
| T05 correct and recheck | Change cited exhibit V1→V2 and selected draft while unrelated control remains | Conflict/revision gate, reversible edit, stale affected result, unchanged control, new checked O2 |
| T06 deliver checked output | Generate report, correctly numbered linked exhibit index/bundle and frozen file | Reopen actual bytes, verify link targets and included/omitted artifacts, disclose missing scope |
| T07 authorize and hand off | Assigned vs solo review, private matter boundary, sharing and filing handoff | No unapproved release, read-only mutation, fabricated filing receipt or access leak |

**Gold rubric:** two reviewers (competent in the assigned Dutch/French/English evaluation language, at least one qualified Belgian legal practitioner for domain/procedural interpretation) independently label literal outcomes, mapping, uncertainty and material issues. Resolve disagreements with a third adjudicator and record original labels, rationale and source revision. Until then, corpus labels are **author-supplied synthetic gold candidates**. Do not advertise evaluator author labels as adjudicated customer-grade truth.

## Measures and denominators

- Literal quote fidelity: TP/FP/FN/TN **only where processing succeeded**; missing/unavailable pages are separate abstention counts. False positive on clean cases is a launch-critical signal, not a score to hide.
- Mapping: resolved/ambiguous/unresolved correct decisions per labeled reference; no first match when duplicates exist.
- Retrieval: relevant documents retrieved / adjudicated relevant documents at k; query language and human qrels pinned; correctness of source relation assessed separately.
- Semantic: proposal precision/recall, supporting vs qualifying vs contradicting vs inconclusive vs not_assessed; separate from quote match and from authorized review.
- Output: valid opened artifacts and links / attempted outputs; changed-input invalidation and unauthorized releases tested as negative cases.
- Human effort: elapsed wall-clock **including setup, help, reviewing false alerts, rework and export**, error count, completion per task, first full task/second actual matter, repeat usage by cohort.
- Economics: per-dossier observed and estimated OCR/index/model/storage/export/support/retry costs, measured at declared scales; missing cost remains `null`, not zero.

## Comparison and publish gate

Run manual Word/PDF as baseline; compare Alice, Nexa, Kleos *only if lawfully available and with product/version parity noted*. Counterbalance task order across evaluators, record dropouts and report unavailable product as untested. Pre-register thresholds **after pilot calibration and before comparative runs**, not post-hoc. Raw human task logs and reviewed outputs must exist before any “faster,” “more accurate,” “court ready,” or market adoption claim. No model credentials, private customer evidence or external filing are used in M0.
