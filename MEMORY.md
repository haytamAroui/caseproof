# CaseProof — Project Memory

> **Purpose:** durable, Git-versioned handoff for coding agents after context loss, agent switches, and long pauses. This is a **navigation and verified-state document**, not a substitute for code, tests, Git history, or the Constitution.
>
> **Authority:** `CONSTITUTION.md` > approved ADRs and contracts > verified code/tests > task records > this summary. If these disagree, stop and reconcile; never silently treat memory as truth.

## Read on every new session
1. Read `CONSTITUTION.md`, `AGENTS.md`, `CLAUDE.md`, and `docs/ROADMAP.md`.
2. Read this file, then the most recent `docs/tasks/` entries and relevant ADRs.
3. Check `git status`, current branch, latest commits and open PRs; do not assume this file is current.
4. Verify claimed completion against code, tests, merged commits and CI. Do not rely on an agent's previous statement.
5. Choose the next **unblocked** roadmap item. State its scope, dependencies, acceptance criteria and tests before editing.

## Snapshot (updated 2026-10-21)
- **Product:** CaseProof — source-anchored factual dossiers for Belgian B2B invoice disputes; not autonomous debt collection or legal judgment.
- **Architecture:** hexagonal, DDD-informed modular monolith; FastAPI/Python; dedicated PostgreSQL/Supabase; durable worker; optional retrieval only if benchmarked.
- **AI boundary:** models extract candidates; independent verification anchors quotations; deterministic logic calculates conditional facts; authorized humans approve consequential actions.
- **Repository:** `haytamAroui/caseproof`; default branch `main`.
- **Status:** documentation/governance baseline exists. **Application implementation is not verified as started.**
- **Next candidate:** Phase 1 repository/CI scaffolding, subject to Gate 0 prerequisites and review.
- **Last verified baseline:** `main` commit `9ce0b0ad341f533712cd82e02f20df60cbd8ce48` before this memory-system branch. Refresh after merge.
- **Outstanding external gates:** commercial discovery, legal validation, processor/privacy review and gold-case fixtures; do not falsely mark them complete.
- **Architecture reference:** `docs/adr/`, `docs/reference/`, `docs/ENGINEERING_STANDARDS.md`.
- **No customer evidence** may be pasted into this file.

## Task ledger — newest first
| Task ID | Status | PR / commit | Verified outcome | Next |
|---|---|---|---|---|
| DOC-MEM-001 | In review | Branch `docs/durable-project-memory`; commit pending | Establish persistent handoff protocol | Review and merge only after approval |

**Status vocabulary:** `planned`, `in_progress`, `blocked`, `in_review`, `merged`, `verified`, `reverted`. Never write `verified` without evidence of checks and merged code.

## Current work / blockers
- No implementation task should be assumed active from this file alone.
- For each active task, create `docs/tasks/<TASK-ID>.md` using `templates/TASK.md` and the memory protocol.
- If a task is blocked, record the exact dependency, responsible decision-maker and safe next action.
- For long tasks, record a **checkpoint before context compaction**: branch, HEAD SHA, dirty files, commands/results, failing tests, pending decisions and immediate next step.

## Durable memory protocol (mandatory after each bounded task)
1. Create/update one task record in `docs/tasks/<TASK-ID>.md` with objective, scope, acceptance criteria, implementation, tests, risk and actual commit/PR URLs.
2. Update **only** this short index: snapshot, current blockers, task-ledger entry and next task. Keep the ledger to the latest ~15 items; archive older records in task files.
3. Record **full commit SHA**, branch and PR status; never invent a SHA. Use `pending` before commit and update after the commit exists.
4. Distinguish `implemented`, `tested`, `reviewed`, `merged`, `deployed`; these are not synonyms.
5. Document failed tests and unresolved problems. Do not erase them to make progress look complete.
6. Keep durable architectural decisions in `docs/adr/`, not only in this memory.
7. Update this file in the **same PR** as the task wherever possible. A post-merge bookkeeping PR is acceptable if the final merge SHA was not known beforehand.
8. On conflict, code/tests/CI and the Git commit graph prevail over summaries. Correct stale memory in a separate documented change.
9. Never record secrets, personal data, customer documents, raw prompts, API tokens or privileged URLs.

## Session recovery checklist
- [ ] Confirm repository, branch and working tree.
- [ ] Read Constitution, instructions, roadmap and this memory.
- [ ] Compare latest task record with merged commits and CI.
- [ ] Confirm there are no outstanding high-risk approvals.
- [ ] Identify next eligible task and dependencies.
- [ ] Run relevant baseline tests (or explicitly record why unavailable).
- [ ] Implement and verify one bounded task.
- [ ] Update task record and this index before requesting merge.

## Design constraints worth remembering
- Evidence citation verification is **not** proof of legal truth.
- Preserve conflicting source claims; do not overwrite contradictions.
- No automatic IOS eligibility, court filing or third-party contact.
- Tenant isolation, idempotency, audit and immutable source provenance are correctness requirements.
- Do not extract a shared AZComply package until a second consumer and regression contract exist.
- No unapproved production deployments, paid resources, migrations or autonomous merges.

## How to resume
Say: **“Continue CaseProof. Read CONSTITUTION.md, AGENTS.md, CLAUDE.md, MEMORY.md, ROADMAP.md, the latest task record and Git history; verify status; proceed with the next unblocked task.”**
