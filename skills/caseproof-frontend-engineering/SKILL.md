---
name: caseproof-frontend-engineering
description: React frontend engineering under the authoritative blueprint.
---

# caseproof-frontend-engineering

## Authority
Follow `AGENTS.md`, `CONSTITUTION.md`, `frontend/BLUEPRINT.md`, accepted ADRs and generated backend contracts before this skill. Do not invent backend capabilities or legal approvals.

## Procedure
Read frontend/BLUEPRINT.md first. Use the repository's Vite, React, TypeScript, router and query versions rather than inventing a Next.js stack. Bind views to generated APIs, stable operation IDs and explicit pending/unknown states. Handle 401/403 with cache and object-URL purge. Use typed adapters, loading/error/denied/expired states and tests.

## Acceptance
State exact files changed, tests actually executed, evidence and open gates. Stop when required source authority, permission or data provenance is absent. See [task checklist](references/TASK.md).
