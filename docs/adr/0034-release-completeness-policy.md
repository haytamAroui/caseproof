# ADR 0034 — Review completeness and explicitly partial reviewed releases

**Status:** engineering implementation merged in [PR #197](https://github.com/haytamAroui/caseproof/pull/197) on 5 November 2026, with [dedicated F6 CI](https://github.com/haytamAroui/caseproof/actions/runs/42081353655) and [final signed F3–F6 development acceptance](https://github.com/haytamAroui/caseproof/actions/runs/42082133289) green. Independent security and practitioner approval remain OPEN. Supplements [ADR 0032](0032-reviewed-release-and-historical-artifact-boundary.md), does not replace the SQL release ledger or historical receipt schema.

## Context and scope

The original F6 preview/commit gate required only one saved human decision. A dossier containing 60 detected findings with one reviewed finding could therefore be described as release-ready. A count of database review rows is also insufficient where rows duplicate one reference or refer to no finding in the frozen report.

CaseProof must distinguish **review completeness of detected findings** from **completeness of document/reference coverage**. Neither status is certification of legal correctness, source authenticity or court filing.

## Deterministic decision table

| Detected findings | Unique valid persisted dispositions | Requested release | Result |
| --- | --- | --- | --- |
| 0 | 0 | Complete or partial | Block: no detected findings, no review; do not infer clean dossier |
| N > 0 | 0 | Complete or partial | Block: no saved decisions |
| N > 1 | 0 < K < N | Complete | Block: unreviewed findings |
| N > 1 | 0 < K < N | Partial, without explicit acknowledgement | Block |
| N > 1 | 0 < K < N | Partial, with explicit acknowledgement | Permit if all existing currentness, permissions, integrity and output checks pass |
| N > 0 | K = N | Complete | Permit if all existing currentness, permissions, integrity and output checks pass |
| N > 0 | K = N | Partial | Block: partial is not the true scope |
| Any | Duplicate finding ID, duplicated decision/reference/request ID, orphan decision or unsupported decision | Any | Integrity fault; fail closed before writing |

A **valid disposition** is any persisted human CONFIRMED_SUPPORTED, CONFIRMED_QUALIFIED or CONFIRMED_CONTRADICTED decision attached to exactly one finding from the frozen report. A contradictory or qualified disposition counts as *reviewed*, never as evidence that the claim is legally supported.

The request must explicitly specify partial mode and a true acknowledgement; a stale preview or front-end checkbox is **not** authority to write. The server recomputes the identical pure policy after fresh signed report/decision reads during commit. The existing PostgreSQL release RPC additionally verifies current grants, source bundle, active draft, confirmation, and byte-for-byte matching of the persisted decision ledger in the transaction.

## Policy and artifacts

- Shared policy version: `caseproof-release-completeness-v1`.
- Count unique findings/receipts; expose total, required, reviewed, unreviewed, review_complete, reason codes and pending reference IDs.
- Release modes: `complete_review` and `partial_review`. They describe **detected-finding human review**, not the document's coverage or accuracy.
- Keep `text_coverage_complete` and `reference_recall_measured` separate in the preview, frozen manifest and source coverage. Their false/unknown values remain conspicuous limitations even when all detected findings were reviewed.
- Existing `caseproof-reviewed-release-v1` manifests gain an optional, HMAC/digest-covered `review_completeness` extension. No new table or SQL schema required. Older signed manifests without this field reopen unchanged, but must be labeled **legacy: completeness unclassified**. Never retrofit or re-sign them.
- All newly generated JSON, Markdown and DOCX outputs carry the selected review scope; the manifest carries its signed counts and exact SHA-256 bytes.
- A partial release never changes the review ledger, verification dimensions or historical source bytes.

## Security and regression requirements

Tests cover: one of multiple findings; explicit partial acknowledgement; no review; zero findings; qualified and contradicted dispositions; duplicate/orphan receipts; stale preview, changed findings, revocation and historical restart; manifest tampering and output hashes; browser checklist/accessibility; legacy manifest reads.

Limitations: The policy cannot prove complete reference discovery or legal correctness. The existing signed release function is a trusted service-role endpoint, not a public approval action. Genuine signed browser and SQL acceptance, live loss/restart/revocation tests, independent security and practitioner approvals remain outside this ADR's automated unit evidence.

## Rollback

Reverting the new writer must not erase or modify prior artifacts. Historical signed records must continue to verify under their original schema, hash, receipt and actor authorization. Do not promote to production or claim practitioner approval solely because automated CI passes.
