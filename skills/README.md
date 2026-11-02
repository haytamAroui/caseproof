# CaseProof agent-neutral skills

This `skills/` directory is the **canonical** location for reusable CaseProof agent skills. Each complete skill lives at `skills/<name>/SKILL.md`, with optional `references/`, `assets/`, and `scripts/`.

## Discovery
Read `skills/caseproof-router/SKILL.md` to choose between the **product engineering** and **landing-page** workflows. Only load skills relevant to the task. The repository `AGENTS.md`, `CONSTITUTION.md`, generated contracts, and `frontend/BLUEPRINT.md` outrank skills.

Agent-specific adapters such as `.claude/skills/` must be generated from this canonical tree or point to it; never maintain competing copies manually. Not all agents automatically scan `skills/`; configure discovery explicitly.

## Status
This branch is **in progress**. Until all 18 v2.1 skills and their references are committed here, no agent should assume the library is complete. The legacy `.claude/skills/` experiments are not the authoritative v2.1 distribution.

## Security
Never install, execute, or vendor external repositories merely because a skill mentions them. Mike OSS, Anthropic legal plugins, Judicex and safe-docx are research inputs subject to license, provenance, egress and acceptance review. No skill may upgrade an evidence finding or create an authorized human review receipt.
