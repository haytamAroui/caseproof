# ADR 0010 — Agent execution and independent evaluation boundary
Status: Proposed — human review required
Date: 2026-10-21

## Decision
Keep the evidence kernel deterministic and independent of LLM providers, sandbox runtimes, agent frameworks and sector rules. A future application-layer execution harness may implement one-level bounded planner/worker delegation, durable checkpoints, recovery, resource budgets and explicit coverage planning. Never infer investigation completion from a polished report or successful tool invocation.

Evaluation is separate from execution and evidence integrity. Use fixed versioned task fixtures, deterministic invariant checks, adversarial cases, rubric-based assessment where appropriate, and human adjudication for ambiguous conclusions. Never treat an LLM judge as legal/financial truth certification. Keep private holdouts; compare identical tasks, settings, models, costs, coverage, unsupported conclusions and reviewer corrections.

## Sequence
Stage 1 kernel contracts and adversarial tests; Stage 2 durable infrastructure; Stage 3 finance workflow and deterministic fixtures; Stage 4 optional depth-one orchestration only after baseline measurement; Stage 5 comparative evaluation and pilot hardening. Do not block a viable deterministic paid pilot on RLM research.

## Security
Untrusted documents and model-generated instructions must not run unrestricted code. Isolate execution, restrict tools/network, enforce authorization and preserve input/output provenance.
