---
name: caseproof-report-export
description: Review record and controlled export.
---

# caseproof-report-export

## Authority
Follow `AGENTS.md`, `CONSTITUTION.md`, `frontend/BLUEPRINT.md`, accepted ADRs and generated backend contracts before this skill. Do not invent backend capabilities or legal approvals.

## Procedure
Export from a canonical immutable snapshot, not a client recomputation. Include version/hash provenance, unresolved items, reviewer decisions, timestamps and explicit limitations. Never describe integrity signatures as qualified lawyer signatures. Require access check at download and confirm cold reopen yields identical authorized artifact.

## Acceptance
State exact files changed, tests actually executed, evidence and open gates. Stop when required source authority, permission or data provenance is absent. See [task checklist](references/TASK.md).
