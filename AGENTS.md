# CaseProof — universal coding-agent instructions

1. Read `CONSTITUTION.md`, `docs/ROADMAP.md`, `docs/ENGINEERING_STANDARDS.md`, and the nearest directory-level instructions before editing.
2. Read `docs/AGENT_ORCHESTRATION.md`; choose the smallest suitable specialist. Never spawn agents merely to increase agent count.
3. State objective, touched files, acceptance criteria, risks and proposed tests before implementation. For nontrivial work, create/update `docs/tasks/<ID>.md` using `templates/TASK.md`.
4. Inspect existing code and tests; do not invent APIs or assume AZComply paths are generic. Treat `docs/reference/` as reference, not executable code.
5. Make one vertical slice at a time; prefer <400 net changed lines per PR where feasible. If larger, explain why and split by independently testable contract.
6. Tests first for legal rules, money, provenance, auth and state transitions. For UI, test the user journey and accessibility.
7. Do not run migrations or deployment against live systems without explicit human approval. Never change AZComply in the same CaseProof PR.
8. No outbound network or model calls with real customer evidence unless approved processors, routing and retention are documented.
9. Finish with: files changed, exact commands run, pass/fail, security effects, remaining risks, and recommended next PR. Never say 'done' when acceptance criteria are unverified.
10. If task requires a constitutional exception, STOP and write an ADR for human review.

## Repo layout (target)
`backend/src/caseproof/{identity,matters,documents,evidence,reconciliation,finance,legal_rules,review,dossiers,workflow,shared}/` each with `domain/`, `application/`, `adapters/` as needed. `backend/tests/`, `frontend/`, `infra/`, `docs/`, `scripts/`.

## Quick commands (target, create in P0)
`make lint` · `make typecheck` · `make test` · `make test-security` · `make test-contract` · `make check`.
No command is assumed to exist until the scaffold PR implements it.