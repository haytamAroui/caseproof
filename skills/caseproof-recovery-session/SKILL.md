---
name: caseproof-recovery-session
description: Session recovery and ambiguous writes.
---

# caseproof-recovery-session

## Authority
Follow `AGENTS.md`, `CONSTITUTION.md`, `frontend/BLUEPRINT.md`, accepted ADRs and generated backend contracts before this skill. Do not invent backend capabilities or legal approvals.

## Procedure
Treat network timeout after a write as unknown, not failed or successful. Use idempotent operation IDs and authoritative readback. After 401/403, cancel requests and clear private caches, object URLs and sensitive in-memory state. On reopen, restore only server-authorized matter/version/receipt state.

## Acceptance
State exact files changed, tests actually executed, evidence and open gates. Stop when required source authority, permission or data provenance is absent. See [task checklist](references/TASK.md).
