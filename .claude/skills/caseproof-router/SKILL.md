---
name: caseproof-router
description: Route CaseProof requests to the product-frontend or landing-page workflow.
  Use at the start of any CaseProof design, implementation, correction, animation
  or review task; select only the relevant skills.
metadata:
  version: 2.0.0
  status: draft-for-project-review
---

# CaseProof task router

## Outcome
Choose the workflow before writing code. Product work protects decisions and state; marketing work explains demonstrated value. Neither workflow substitutes for the other.

## Procedure
1. Classify the deliverable: product, landing, or both. For both, create separate acceptance lists.
2. Load caseproof-foundation, then only the task skills required in the reference.
3. Locate the actual project, `frontend/BLUEPRINT.md`, agent instructions, package scripts, generated contracts, design tokens and current feature flags. Record what was actually read.
4. Mark missing sources explicitly. A demo may proceed using labelled fixtures. Production integration may not invent contracts to fill the gap.
5. State implementation scope and acceptance tests. Build one complete thin workflow, including its failure states, before adding unrelated surfaces.
6. Deliver changed files, evidence of tests run, and missing checks. Do not say installed, built, rendered or verified without corresponding evidence.

## Authority
Project-approved blueprint and generated contracts determine implementation. The supplied user-flow document is a design reference, not evidence that every screen exists. External repositories are inspiration only; document their licenses before copying code.

## Stop conditions
Ambiguous tenant or matter, absent write contract, unavailable deployment information or missing legal authority must not be resolved through assumptions.

## Task reference
Read [the task reference](references/TASK.md) before implementation.
