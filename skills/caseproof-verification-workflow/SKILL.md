---
name: caseproof-verification-workflow
description: End-to-end verification orchestration.
---

# caseproof-verification-workflow

## Authority
Follow `AGENTS.md`, `CONSTITUTION.md`, `frontend/BLUEPRINT.md`, accepted ADRs and generated backend contracts before this skill. Do not invent backend capabilities or legal approvals.

## Procedure
Map signed matter intake, upload, confirm, verify, inspect, decide, save receipt, reopen and export. Use the canonical application ports; no client-side verification authority. Include source_missing, not_in_inventory, page_unmapped, representation_conflict and ocr_unreliable paths. Prove denial, stale state and restart behavior.

## Acceptance
State exact files changed, tests actually executed, evidence and open gates. Stop when required source authority, permission or data provenance is absent. See [task checklist](references/TASK.md).
