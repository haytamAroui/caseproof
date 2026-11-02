---
name: caseproof-tabular-review
description: Accessible review table and filters.
---

# caseproof-tabular-review

## Authority
Follow `AGENTS.md`, `CONSTITUTION.md`, `frontend/BLUEPRINT.md`, accepted ADRs and generated backend contracts before this skill. Do not invent backend capabilities or legal approvals.

## Procedure
Display finding ID, reference, exhibit, page mapping, source coverage, fidelity, reviewer state and action independently. Sorting/filtering must preserve identity and server authorization. Use keyboard-accessible table patterns and meaningful empty/loading/error states. A filter must not hide unresolved risks from export readiness.

## Acceptance
State exact files changed, tests actually executed, evidence and open gates. Stop when required source authority, permission or data provenance is absent. See [task checklist](references/TASK.md).
