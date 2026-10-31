# M0 NL/FR/EN/mixed — independent adjudication packet

**Candidate corpus:** [v3](../../evals/litigation/m0_corpus_v3.json) (37 fictional cases; 19 legacy v2 unchanged, 18 four-dimension extensions). **Review status: NOT STARTED / NOT SIGNED OFF.** No reviewer, lawyer, organization or adjudicator is claimed by this document. This packet prepares a human review; synthetic author labels are **not independently verified**.

## Qualified review required for formal M0 exit

1. Record the **exact v3 SHA-256**, predecessor v2 SHA-256 and repository commit from `python -m scripts.audit_m0_trilingual`. Only review that pinned text; any correction creates v4 with a visible changelog, never modifies prior gold.
2. Obtain two **independent** label judgments (not supplied to them as the authoritative answer) for NL, FR, EN and mixed-language examples. Reviewers must have the language competence required by [benchmark protocol](BENCHMARK_PROTOCOL.md); at least one qualified Belgian practitioner adjudicates legal/procedural interpretation when implicated.
3. Each person evaluates identity in a **human-confirmed complete/incomplete/unconfirmed** inventory; separately evaluates PDF page, printed label and compiled bundle page; quotation/translation/OCR reliability; and whether semantic support was **assessed by a human** (never automatically affirmed).
4. Record independent decisions, source/quote observations, uncertainties, dissent, evidence and qualifications. Resolve differences with an independent third adjudicator. Preserve the initial labels even when later changed.
5. Inspect at least one actual **rights-cleared DOCX**, **text PDF** and **image-only PDF** in each product language before making real-format/OCR claims. The current 37 cases have inline text and simulated scan metadata; they cannot close this requirement.
6. Owner accepts or rejects M0 with a dated decision only after review receipts and CI. Do not merge a declaration of M0 completion based on mechanical-only passing checks.

## Proposed first-pass author labels (not independently adjudicated)

| Candidate case | Language | Identity / page / fidelity | Author's explanation | Independent reviewer decision |
|---|---|---|---|---|
| `NL_INCOMPLETE_20` | NL | not_assessed / unmapped / not_assessed | Incomplete inventory cannot prove that Stuk 99 is absent. | Pending |
| `NL_OFFSET_21` | NL | resolved / mapped / exact_match | Three distinct numbers: PDF 3, printed 17 and bundle 42. Quotation appears exactly. | Pending |
| `NL_MISMATCH_22` | NL | resolved / mapped / mismatch | Reliable text-layer mismatch between 800 and 900; no numeric coercion. | Pending |
| `NL_SCAN_23` | NL | resolved / mapped / ocr_unreliable | Simulated unavailable OCR is not a quote mismatch. | Pending |
| `FR_DUP_24` | FR | ambiguous / unmapped / not_assessed | Two preserved sources use the same confirmed exhibit label; never first-match. | Pending |
| `FR_CLEAN_25` | FR | resolved / mapped / exact_match | Positive clean control: one source, correct identity/page and exact quote. | Pending |
| `FR_ALIAS_26` | FR | resolved / mapped / exact_match | Declared Stuk/Pièce alias can resolve the same source without inventing provenance. | Pending |
| `FR_NOQUOTE_27` | FR | resolved / mapped / not_applicable | Quote-free reference can establish identity and page, not literal support. | Pending |
| `EN_MISSING_28` | EN | not_in_inventory / unmapped / not_assessed | Only the explicitly complete and human-confirmed inventory supports NOT_IN_INVENTORY. | Pending |
| `EN_OFFSET_29` | EN | resolved / mapped / exact_match | PDF 2, printed 9 and bundle 51 remain separately recorded. | Pending |
| `EN_CLEAN_30` | EN | resolved / mapped / exact_match | English clean control, no human issue labels. | Pending |
| `EN_NOQUOTE_31` | EN | resolved / mapped / not_applicable | Identity/page supported; quoting fidelity is inapplicable. | Pending |
| `MIX_TRANSLATION_32` | MIXED | resolved / mapped / translation_review_required | FR/NL translation cannot count as an exact original-language quote even if semantically plausible. | Pending |
| `MIX_UNCONFIRMED_33` | MIXED | not_assessed / unmapped / not_assessed | A candidate inventory must not confer resolved identity before human confirmation. | Pending |
| `EN_WRONG_PRINTED_34` | EN | resolved / conflicting / not_assessed | Printed-page requirement 12 conflicts with preserved page label 11 even if literal exists. | Pending |
| `FR_SOURCE_MISSING_35` | FR | source_missing / unmapped / not_assessed | A listed exhibit with no source is SOURCE_MISSING, not NOT_IN_INVENTORY. | Pending |
| `FR_MISSING_36` | FR | not_in_inventory / unmapped / not_assessed | Confirmed complete inventory supports a missing-item finding only for this declared scope. | Pending |
| `EN_SCAN_37` | EN | resolved / mapped / ocr_unreliable | Unavailable synthetic scan representation must abstain. | Pending |

The first 19 cases remain in [v2](../../evals/litigation/m0_corpus_v2.json) with author-supplied legacy literal outcomes only. They **also require independent review**: do not treat their absence from the extended-dimension table as implicit approval.

## Reviewer record — deliberately blank

| Role | Name / organization | Qualification, language | Signed review artifact / date | Outcome |
|---|---|---|---|---|
| Independent NL reviewer | *Not assigned* | *Not assessed* | *None* | Open |
| Independent FR reviewer | *Not assigned* | *Not assessed* | *None* | Open |
| Independent EN reviewer | *Not assigned* | *Not assessed* | *None* | Open |
| Mixed-language and Belgian legal reviewer | *Not assigned* | *Not assessed* | *None* | Open |
| Independent disagreement adjudicator | *Not assigned* | *Not assessed* | *None* | Open |
| M0 owner gate | *Not signed* | *Not applicable* | *None* | **Open** |

**What a clean CI result would mean:** synthetic fixtures are structurally self-consistent and the test script refuses label drift; it does **not** mean that a real lawyer agreed, that the parser handled real scans, or that the software is accurate for Belgium.
