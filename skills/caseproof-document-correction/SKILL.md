---
name: caseproof-document-correction
description: Safe DOCX correction and recheck.
---

# caseproof-document-correction

## Authority
Follow `AGENTS.md`, `CONSTITUTION.md`, `frontend/BLUEPRINT.md`, accepted ADRs and generated backend contracts before this skill. Do not invent backend capabilities or legal approvals.

## Procedure
Preserve uploaded original and its hash. Apply changes only to a new versioned derived draft, with explicit user approval and source provenance. Prevent overwriting original exhibit bytes. Re-run verification on changed regions and invalidate stale review claims. Never promise Word round-trip fidelity without host testing.

## Acceptance
State exact files changed, tests actually executed, evidence and open gates. Stop when required source authority, permission or data provenance is absent. See [task checklist](references/TASK.md).
