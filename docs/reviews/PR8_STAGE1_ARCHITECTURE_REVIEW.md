# PR #8 — Stage 1 trust contracts: review and verification record

Date: 2026-10-21
PR: https://github.com/haytamAroui/caseproof/pull/8
Head branch: `docs/stage1-trust-contracts`
Target: `feature/stage1-evidence-provenance`
Disposition: **revised design proposal; merge blocked pending C25 gates**

## Scope, reviewed changes and invariants

Documentation and illustrative contract only; no Python implementation, executable endpoints, database tables or migrations. The amendments clarify five requested changes:

1. Promotion requests no longer accept a client-supplied `actor_id` or `tenant_id`; authorization and effective policy come from trusted application context, with explicit preconditions and idempotency.
2. Evidence anchors bind immutable source **and derived representation** identities; typed locators have explicit coordinate conventions and cannot silently re-resolve against new OCR/parser output.
3. Link-level assessments and policy-level aggregate sufficiency are separate; contradictions and qualifications cannot be voted away; operational `BUSINESS_EXCEPTION_ACCEPTED` is a separate audited outcome, not `approved_conclusion`.
4. Issue-to-source mapping and missing, failed, processed or excluded source statuses determine coverage under a frozen scope/policy. A processed flag alone never closes an investigation.
5. Stage 1 implementation exit testing is distinguished from this proposed documentation amendment. The v2 JSON is labeled an informative proposal, not formal JSON Schema/OpenAPI. C25's **Markdown-only** exemption does not cover this PR.

C01, C03, C05, C07–C09-A, C12–C13, C16, C20–C25 are affected design/integrity constraints. Existing `contracts/kernel-api.v1.json` remains untouched.

## Verification record (not a claim of merge readiness)

- Fetched and inspected PR #8 changed files, Constitution and existing v1 contract through the GitHub connection.
- Parsed the v2 proposal via JavaScript `JSON.parse` in the tool runtime; syntax passed at the time of editing. This is **not** a complete schema validator or Python/API contract test.
- The pre-amendment pull-request workflow run `39626680686` (`Kernel boundary`) concluded **failure**. GitHub job `119313628960` had `runner_id: 0`, an empty runner name and zero recorded job steps. It did **not** execute architecture or unit tests; the precise scheduling/failure cause is not established. Job logs returned BlobNotFound.
- The underlying workflow calls `uv run --locked python scripts/check_architecture.py` and `uv run --locked pytest -q`. `uv.lock` was not present when inspected. Do not weaken `--locked` to obtain a green check.
- GitHub branch-protection inspection returned HTTP 403 (`Resource not accessible by integration`); the rulesets endpoint returned HTTP 403 requesting GitHub Pro or public visibility. This does not establish that C25 merge protection is configured.
- No Python tests, locked uv verification, architecture negative-control validation or independent reviewer approval were executed/observed by this amendment review.

## Remaining explicit blockers before merge

1. A legitimate cloud runner must run the required **locked** checks, with successful logs/checks on the final PR head.
2. Verify a negative-control architecture sabotage PR fails **because of a forbidden import**, not runner setup, and record its link.
3. Repo owner must configure and verify effective merge protection on the target branch; private-repository plan/permissions may require owner action or plan change.
4. Independent human read-only reviewer must sign off on the final ADR/API design and C25/C16 controls.
5. KRN-109 implementation will later require enforceable field-typed OpenAPI/JSON Schemas, compatibility tests and HTTP error examples. Do not treat this draft contract as implemented.

Do not merge on absent evidence, and do not bypass or weaken CI. Recheck current GitHub status after any new pushes. All Stage 1 implementation and durability claims remain out of scope for this PR.
