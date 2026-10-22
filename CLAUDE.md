# CaseProof / ExceptionDesk — Claude Code operating guide

Read `CONSTITUTION.md`, `AGENTS.md`, `MEMORY.md`, `docs/STATUS.md` and relevant domain standards/ADRs first. Code, merged commits and actual GitHub CI outrank textual summaries.

## Current environment, not historical assumptions

- GitHub Actions **works** on `main` as of 2026-10-22. Verify required checks on the **exact new SHA**; do not repeat the old claim that GitHub runners cannot start.
- Positive architecture/pytest/PostgreSQL CI has passed, and deliberate forbidden-import PR #4 failed for the intended architecture reason. **PR #4 must never merge.**
- No branch rulesets appeared through GitHub integration; main branch protection is **not verified** (read was 403). `CONSTITUTION.md` C13/C25 applies: issue #5 remains a human-owner-controlled merge protection gate, not a reason to disable tests.
- Developer default for code: `uv run --locked pytest -q`, `uv run --locked python scripts/check_architecture.py`, relevant Ruff/mypy; run real cloud CI and affected Postgres security jobs before any merge.
- Stage 2 `db/proposals` are disposable SQL fixtures, not production migrations. `/v1` is caller-tenant development API; `/v2` and true Auth-authorized approval remain unmounted. Never use synthetic credentials, manually set JWT claims, or elevated database roles as customer authentication.

## Implementation routine

Plan risk and bounded user outcome; review source, tests and closest `AGENTS.md`; implement tests and minimal code; run locked checks; obtain independent security review for tenant, evidence and payment/financial correctness; reconcile reviewer findings; record exact run IDs and unresolved gates in `docs/STATUS.md`. Avoid unnecessary agent delegation, invented installed tools, automatic law interpretation or autonomous legal action.

## Stop conditions

Missing trusted membership, uncertain object write, absent byte verification, unsigned identity, unverifiable parser citation, audit transaction failure, unreviewed schema/RLS alteration, unprotected merge or unavailable CI: do not expose a customer workflow, claim release approval or silently bypass a gate.

## Completion report

`Implemented` / `Not implemented` / `Tests executed and SHA` / `Security/data handling` / `Unmerged and owner gates` / `Next bounded, customer-facing milestone`.
