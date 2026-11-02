---
name: caseproof-verification-orchestrator
description: Coordinate source-bound exhibit verification and abstention through existing CaseProof backend contracts; never generate verdicts in a skill.
---
# CaseProof verification orchestration
Read `CONSTITUTION.md`, `frontend/BLUEPRINT.md`, `docs/ROADMAP.md`, `docs/contracts/PRE_M3_VERIFICATION_SPEC.md`, and canonical report/ADR contracts before implementation. Backend is authoritative. This is a development skill, not an alternative verifier or legal-advice engine.

## Activation
Use when building or reviewing intake, reference discovery, source matching, page mapping, quotation fidelity, support display, human decisions, recheck, or export.

## Mandatory gate 0
Require signed authorized matter, preserved version/hash-bound original(s), explicit inventory confirmation and actual canonical snapshot where the operation requires them. Distinguish incomplete inputs from absent references. Never substitute a crop, extracted string, generated model answer, or user-entered filename for authoritative source identity. Do not introduce conflicts-of-interest screening as a CaseProof capability.

## Six stages
1. Discover references from supplied draft, preserving original ranges and extraction uncertainty.
2. Reconcile each reference against confirmed inventory and immutable source originals. Missing/ambiguous remain explicit.
3. Resolve physical PDF page, printed label and bundle page separately; never infer one from another.
4. Compare literal extraction and rendered representation, including strike-through and OCR uncertainty. Reopen same preserved source/version for round-trip; flag mismatch rather than auto-repairing the user's draft.
5. Display backend-provided human-support assessment separately; if absent show NOT_ASSESSED. Matching a quote does not establish semantic support.
6. Require authorized durable human decision receipt before labeling a human decision saved. Recheck changed drafts against a new canonical version; export only a version-bound record with disclosed scope.

## Output contract
Present separate identity, page, fidelity, support, and coverage/processing states. Unknown states fail closed. No universal green check, overall verified label, invented confidence score, or provisional certification. Provide evidence/source anchors and disclose missing or unassessed dimensions. A generated report is a derivative, never the original.

## Acceptance examples
- Missing inventory confirmation: no resolved finding.
- OCR crop without page authority: page remains unmapped.
- Extracted quote agrees but pixels conflict: fidelity not supported.
- Source text matches but support is not evaluated: NOT_ASSESSED visible.
- Revised draft: stale human decisions not silently reused.
- Restart and revocation: saved receipt reopens only for authorized user; denial removes private view.
- Zero references: never claim whole document verified.

## Completion evidence
Report exact contract/schema changes, fixtures, negative tests, CI run, saved/reopened receipts, and limitations. Do not claim independent lawyer review or production acceptance from synthetic fixtures.
