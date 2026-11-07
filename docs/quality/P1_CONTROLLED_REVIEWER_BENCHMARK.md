# P1 Controlled Reviewer Accuracy Benchmark — study protocol

**Status:** engineering scaffold, 7 November 2026. Parent: P0 PR #205.
**Not a completed reviewer study, legal sign-off, or pilot release approval.**

This is deliberately independent of the Storyteller CSS changes. Existing
read-only source display and the P0 guarded-term panel can be randomized without
creating new evidence verdicts. NLI is expressly out of scope.

## Hypothesis and unit of evaluation

Primary hypothesis: contextual, deterministic guarded-term warnings decrease
false human confirmations of claims that independent Belgian NL/FR legal
adjudicators find unsupported in the **exact preserved source version**.

- **Condition A — standard_interface:** same original PDF, DOCX claim,
  anchored passage and adjacent paragraphs, but no guarded-term warning.
- **Condition B — guarded_term_warnings:** identical source evidence and
  user affordances, with P0 lexical warning(s) and explicit caveat that
  source text absence is not contradiction. No additional AI help.
- **Unit:** a human reviewer decision on one independently adjudicated
  claim and original source version, not a model prediction.
- **Allocation:** reviewer-level, language-competence-stratified, deterministic
  pseudorandom balance. A participant is in only one arm to reduce leakage
  between treatments. Order of claims is pseudorandom per participant.
  Every retained language stratum must have at least two human reviewers
  in each arm before comparative scoring.
- **No bulk approval.** All claims start NOT ASSESSED. Reviewer must open
  the original PDF, consider adjacent context, and enter a rationale.
  The study records self-reported inspection; automation cannot authenticate it.

## Evidence and adjudication prerequisites

The study manager must source **synthetic or explicitly rights-cleared**
PDFs and DOCX claims. Every trial item requires the exact
source_version_id, SHA-256 of preserved **PDF bytes**, physical PDF page,
claim, anchored source passage, surrounding paragraph context, and guarded
warnings. An exact-looking quotation is *not* independently verified
support. The generator opens each original PDF, verifies its digest and real
page count, rejects a path leaving the supplied source root, and refuses
encrypted, missing, oversized or mismatched PDFs.

A separate adjudication file must include two distinct independent
reviewer assessments on each version/page, with reasoned source
observations. Disagreement requires an additional adjudicator. This
validator checks completeness, **not** adjudicators' real credentials,
independence, signatures, legal competence or authenticity. These require
a separately documented human governance process. Gold labels and
author-seeded defect names must never enter participant packets.

P0's author-seeded fixture
[tests/fixtures/p0_review_benchmark_cases.json](../../tests/fixtures/p0_review_benchmark_cases.json)
is *not* independently adjudicated and lacks the required original
PDF bytes. It **cannot** produce real-study results.

## Preparation on rights-cleared local originals

Prepare a private case manifest, using this structure:

    {
      "cases": [{
        "case_id": "opaque-synthetic-001",
        "language": "nl",
        "source_version_id": "version-of-real-original",
        "source_sha256": "<64 lowercase SHA256 of PDF bytes>",
        "physical_pdf_page": 1,
        "source_pdf": "relative/path/original.pdf",
        "draft_claim": "Claim text from the preserved draft",
        "anchored_passage": "Exact or disputed PDF passage",
        "context_before": "Previous original paragraph",
        "context_after": "Following original paragraph",
        "warnings": [{"kind": "negation", "term": "niet"}]
      }]
    }

The local reviewers file must use pseudonyms and declared language
competence:

    {"reviewer_languages": {
      "reviewer-01": ["nl", "fr"],
      "reviewer-02": ["nl", "fr"],
      "reviewer-03": ["nl", "fr"],
      "reviewer-04": ["nl", "fr"]
    }}

Run from repository root using the pinned Python environment:

    uv run --locked python -m scripts.p1_reviewer_benchmark prepare \
      --cases /private/study/cases.json \
      --reviewers /private/study/reviewers.json \
      --source-root /private/rights-cleared-originals \
      --seed fixed-research-randomization-seed \
      --out /private/study/blinded-run-01

The command produces separate, permission-restricted participant packets,
empty submission templates and a **private** allocation manifest. It never
copies original PDF content or gold labels into packets. For an actual A/B trial, an **isolated research frontend** must enforce
the assigned warning visibility while presenting the same actual original
PDF and review tools in both arms. The normal CaseProof UI must not suppress
P0 warnings simply to create a baseline cohort. That isolated study UI is
**not implemented** in this PR. The participant packet is not a signed
review receipt or a replacement for the original source viewer.

For a real trial, put all actual completed decisions in a single private
file with schema caseproof-p1-reviewer-submissions-v1 and the assignment
and source fields copied from the template (one entry per allocation).
Populate decision (SUPPORTED, QUALIFIED, CONTRADICTED, UNASSESSED),
elapsed_ms (actual, not invented), inspected_original, rationale,
confidence 1–5, and optional warning_helpful for condition B.

A **separately held** gold file must use schema
caseproof-p1-independent-labels-v1. Each case must bind the same
case_id/source_version_id/source_sha256/physical_pdf_page and include
independent_labels with at least two distinct adjudicator_pseudonym,
decision and source_rationale values. If labels disagree, add a separate
resolution with its own distinct adjudicator pseudonym, decision and
source_rationale. Adjudicator identities must be verified outside this tool.

Then and only then can the local descriptive scorer run:

    uv run --locked python -m scripts.p1_reviewer_benchmark score \
      --assignments /private/study/blinded-run-01/private_assignments.json \
      --gold /private/study/independent-gold.json \
      --submissions /private/study/completed-human-decisions.json \
      --out /private/study/descriptive-results.json

The scorer rejects incomplete samples, duplicate assignments, wrong
reviewer/arm, mismatched source versions/digests/pages, missing original
inspection attestations, missing rationale and missing independent labels.
No partial-arm selection is allowed.

## Measures and interpretation

Primary denominator: independently gold-UNSUPPORTED claims (qualified,
contradicted or unassessable). A false confirmation is a SUPPORTED human
disposition for those items. Report count and denominator separately by
condition; no claim of reduced risk when no actual reviewer data exist.

Secondary: missed contradictions (including reviewer abstentions),
median seconds per decision, raw pairwise exact reviewer agreement on
the same case, and optional participant-reported warning helpfulness.
Report confidence for false confirmations to study overconfidence.
Do not turn source-text matching into an automatic ground truth.

All outputs include that reviewer identities, self-reported timing,
inspected-source attestations and adjudicator credentials **cannot** be
authenticated by these scripts. Descriptive arm differences alone do not
identify a causal effect or demonstrate generalizable accuracy.
Pre-register analysis, balance expertise, language and document length,
and obtain independent statistical and legal review.

## Current gaps and explicit gates

- No completed independent legal labels for P0's seven seed categories.
- No real human participants or trial submissions.
- No authenticated intervention telemetry in the deployed cockpit.
- No isolated study frontend to enforce blinded warning visibility across
  identical source-inspection controls. **No production warning suppression.**
- No confidential document rights/governance or retention decision for
  practitioner study bytes and logs.
- No durable, signed linkage of every human decision to a specific
  quote hash and source PDF location; existing ledgers remain authoritative.
- NLI remains **P2 / disabled** pending observed benefit.
- PR #205's protected genuine-user and independent security gates remain
  open. This dependent P1 branch is not a workaround for those gates.

Research outputs must never claim "lawyers more accurate" until the
above conditions are actually satisfied and independently assessed.

## Additional P1 increment — source-link projection

This PR adds an **on-demand, read-only correspondence** between each existing
human ledger decision and the frozen signed snapshot's source version, original
PDF SHA-256, physical page and explicit inspected region IDs. This is included
in authorized report projections (JSON and Markdown) with an explicit notice
that it is **NOT** a new durable, jointly signed review receipt. The existing
review RPC and SQL ledger remain unchanged. Missing, ambiguous or mismatched
source versions, source digests and region IDs yield NOT_SOURCE_BOUND. A
uniquely matched derived-text quotation may have a separately labelled
**derived-text quote hash**; this is never a PDF crop or visual proof.

Durable, source-position-signed review receipts with verified reviewer
justification are still a later P1 step and require an independently
reviewed migration, rights checks and genuine signed-user acceptance.
