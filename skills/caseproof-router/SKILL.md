---
name: caseproof-router
description: Select CaseProof product-engineering or landing-page workflows and load only necessary skills.
---
# CaseProof skill router

Read `AGENTS.md`, `CONSTITUTION.md`, and `frontend/BLUEPRINT.md` before touching frontend code. The blueprint, generated contracts and backend application services outrank this skill.

## Route
- **Product engineering:** intake, source viewer, verification, table, correction, review, export, session recovery. Start with `skills/workflows/product.md`.
- **Landing page:** positioning, synthetic demonstration, accessible animation, multilingual copy, responsive QA. Start with `skills/workflows/landing.md`.
- **Both:** maintain separate implementation and acceptance evidence; never let marketing components mutate review state.

Use only the specific supporting skills needed for the requested task. Missing or ambiguous contracts are a stop condition for production writes, not permission to invent an API.

## Output
Identify exact code changes, affected contracts, checks executed, test receipts, failures, and open acceptance gates. Never claim a skill was installed or tested without evidence.
