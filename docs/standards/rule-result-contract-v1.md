# Rule result contract v1 — common per-rule statuses

Contract version: `caseproof-rule-result-contract-v1`
Implementation: `application/litigation/rule_results.py`
Tests: `tests/test_rule_result_contract.py`

## Purpose

One shared vocabulary for the result of any verification rule, across every
existing rule family. Each rule result is one of exactly four statuses:

| Status | Meaning |
| --- | --- |
| `PASS` | The rule ran with sufficient evidence and its condition holds. |
| `FAIL` | The rule ran with sufficient evidence and its condition is violated. |
| `UNDETERMINED` | The machine cannot decide: evidence insufficient or ambiguous, the check not applicable or not run, an input missing or unreadable, or a human review still pending. |
| `UNVERIFIED` | Reserved: a legal article absent from the corpus chosen for the case. No current rule family returns it. |

Every `RuleResult` names: the rule (`rule_id`) and its version (`rule_version`,
the existing engine/contract constant that produced the check), the assessed
reference (`reference`), the bounded `scope` actually checked, the
`preconditions` with their met/unmet outcome, the `input_hashes` of the inputs
that have a digest, the `reason`, and the original granular states as
`subresults`.

## What this contract is not

- A `PASS` names the rule that passed. It never claims the brief is true,
  legally sound, or that a source is authentic.
- A `FAIL` is about the named narrow rule only (for example: the exact
  quotation is absent from the checked page representation). It is never a
  legal conclusion. `legal_conclusion` and `filing_status` stay
  `not_assessed`.
- `UNDETERMINED` and `UNVERIFIED` are never merged into a generic failure, and
  never upgraded silently: a result only moves when the underlying check is
  re-run on new input. `UNVERIFIED` never means that a reference, article or
  source does not exist; it means the chosen corpus cannot verify it.
- `UNVERIFIED` keeps the exact meaning of the product concept: a legal article
  absent from the case's selected corpus. That rule family is wired by a later
  task; until then every existing family resolves to `PASS`, `FAIL` or
  `UNDETERMINED` only, and a missing source, unconfirmed inventory, unmapped
  page, failed extraction or unreadable text stays `UNDETERMINED` with its
  granular reason preserved in the sub-results.
- Human dispositions (confirm, qualify, reject, waive) are separate records in
  the signed review path. The machine finding they refer to is preserved
  unchanged; this contract does not model waivers and does not decide whether
  a waived `FAIL` permits export or a labelled "ready with exceptions" state.
  That product question stays open.
- The paraphrase guard stays advisory: it can require manual review
  (`UNDETERMINED`) but never returns `PASS` or `FAIL`.
- Visual fidelity is uncalibrated: the machine never returns `PASS` or `FAIL`
  for it. Every known visual state is `UNDETERMINED` pending human
  confirmation of the original pixels.

## Adaptation, not replacement

Existing checks, report payloads, snapshot hashes and export formats are
unchanged. This contract is a deterministic projection layer over the existing
outputs; the granular states stay authoritative and are preserved verbatim as
sub-results. Unknown future states fail closed (`RuleContractError`) instead of
being guessed.

## Mapping per rule family

### Citation literal check (`citation.literal`, version `caseproof-disputes-unified-factual-v1`)

Source: `application/litigation/brief_checks.py` (`CitationCheckState`).

| Granular state | Status | Rationale |
| --- | --- | --- |
| `exact_match` | PASS | Exact quotation present in the checked page representation. |
| `quote_not_found` | FAIL | Quotation absent from the checked representation. |
| `multiple_matches` | UNDETERMINED | Quotation location ambiguous. |
| `reference_checked_no_quotation` | UNDETERMINED | No explicit quotation; the literal rule has nothing to check. |
| `ocr_unreliable` | UNDETERMINED | Representation not trustworthy enough to decide. |
| `representation_conflict` | UNDETERMINED | Conflicting representations; cannot decide. |
| `reference_unresolved` | UNDETERMINED | Exhibit identity precondition unmet (granular state preserved). |
| `reference_ambiguous` | UNDETERMINED | Exhibit identity precondition unmet (ambiguous). |
| `page_unmapped` | UNDETERMINED | Page mapping precondition unmet. |
| `source_unavailable` | UNDETERMINED | Source precondition unmet. |
| `incomplete_extraction` | UNDETERMINED | Extraction precondition unmet. |

### Typed factual comparison (`fact.value`, version `caseproof-disputes-unified-factual-v1`)

Source: `application/litigation/factual_values.py` (`FactState`).

| Granular state | Status | Rationale |
| --- | --- | --- |
| `value_match` | PASS | Same-role typed tokens equal. |
| `candidate_difference` | FAIL | Same-role typed tokens differ. Stays a *candidate* difference, not a confirmed contradiction. |
| `needs_context` | UNDETERMINED | Value or role ambiguous; context required. |
| `not_assessed` | UNDETERMINED | Source representation missing or incomplete. |

### Dossier reference findings (versions `caseproof-dossier-v4` / `caseproof-verification-contracts-v1`)

Source: `domains/disputes/dossier_verification.py` and
`application/litigation/dossier_contracts.py`. Each finding projects one rule
result per independent dimension.

`exhibit.identity`:

| Granular state | Status |
| --- | --- |
| `resolved` | PASS |
| `not_in_inventory` | FAIL (reference names an exhibit absent from the confirmed complete inventory) |
| `ambiguous` | UNDETERMINED |
| `source_missing` | UNDETERMINED |
| `not_assessed` (incl. unsupported dialect) | UNDETERMINED |

`exhibit.page_mapping`:

| Granular state | Status |
| --- | --- |
| `mapped` | PASS |
| `conflicting` | UNDETERMINED |
| `unmapped` | UNDETERMINED |

`fidelity.literal`:

| Granular state | Status |
| --- | --- |
| `exact_match` | PASS |
| `quote_not_found` | FAIL |
| `multiple_matches` | UNDETERMINED |
| `translation_review_required` | UNDETERMINED (human translation review pending) |
| `not_applicable` (no explicit quotation) | UNDETERMINED |
| `not_assessed` | UNDETERMINED |

`fidelity.visual`:

| Granular state | Status |
| --- | --- |
| `not_assessed` (including `uncalibrated_agreement` and `visual_not_run`) | UNDETERMINED (pending human confirmation) |
| `ocr_unreliable` | UNDETERMINED |
| `representation_conflict` | UNDETERMINED |

`support.human`: fixed `UNDETERMINED` (`human_only_pending_lawyer_disposition`).
Semantic support is a human decision; the machine never assesses it, and a
pending lawyer disposition is `UNDETERMINED`, never the reserved `UNVERIFIED`.

### Paraphrase guard (`paraphrase.guarded_terms`, version `caseproof-paraphrase-review-guard-v1`)

Source: `application/litigation/paraphrase_guard.py`.

| Granular state | Status |
| --- | --- |
| `needs_manual_review` | UNDETERMINED |
| `not_assessed` | UNDETERMINED (not run: pending) |

Warnings are review priorities, never contradictions: no PASS, no FAIL.

### Coverage issues (`coverage.issue`, version = the coverage manifest version)

Source: `packages/evidence_kernel/domain/coverage.py` (`IssueStatus`). The
declared scope is a recorded claim, not proof of real-world completeness.

| Granular state | Status |
| --- | --- |
| `supported` | PASS |
| `contradicted` | FAIL |
| `qualified` | UNDETERMINED (partial support) |
| `unresolved` | UNDETERMINED |
| `open` | UNDETERMINED (not yet evaluated: pending) |

### Statute parser (syntax only)

`statute_parser.py` validates NL/FR citation syntax only; it does not verify
source, version or entry into force, so it produces no rule results yet. When
legal-source rules are wired to the dossier path (later task), an article
absent from the case's chosen corpus is `UNVERIFIED`, never "nonexistent" —
the original and only meaning of this status in the product concept, which this
contract reserves: the corpus chosen for the case cannot verify the article.

## Scope and input hashes

- `reference` is the assessed object: dossier `reference_id`, citation
  `reference_id`, fact `claim_id`, coverage issue id.
- `scope` restates what was actually checked (never widened by the projection).
  For citations the existing `scope_note` is reused verbatim.
- `input_hashes` contains only digests present on the source record (source
  original sha256; brief original and representation sha256 when the caller
  has them, e.g. from a frozen `VerificationRun`). A missing digest is omitted;
  a digest present but malformed fails closed (`RuleContractError`) instead of
  being silently dropped, because these hashes are integrity evidence. The
  run-level `snapshot_hash` continues to bind the full input set; this
  contract does not replace it.

## Acceptance of this slice

- Written mapping exists for every current rule family (this document).
- Existing checks are adapted through the projection, not replaced: no existing
  payload, snapshot hash, export format or test expectation changes.
- The projection fails closed on unknown states.
