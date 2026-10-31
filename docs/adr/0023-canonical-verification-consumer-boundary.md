# ADR 0023 — Canonical verification consumer boundary

Status: Proposed (implementation gate)

## Context

The signed dossier flow in `apps/api/dossier_journey.py` implements inventory completeness, language declarations, region coverage, OCR ledger, visual assessment, and a frozen report. The separate `apps/api/litigation_headless_verification.py::discover` still computes a headless-v1 result using manifest number matching. The read-only MCP adapter consumes that older snapshot. These paths do not have equivalent semantics.

## Decision

1. The signed dossier frozen report is the authoritative verification artifact. Consumers MUST NOT independently infer identity, fidelity, support, translation, inventory completeness, or page mapping.
2. REST, MCP, web reviewer, and future Word integration must read a shared versioned report projection with the same finding identifiers, snapshot hash, uncertainty, and decision semantics.
3. A projection may omit confidential fields but must never promote an uncertain assessment to a stronger state. Missing fields must be represented as unavailable, not implicitly verified.
4. All document-content release requires an explicit, per-call host authorization distinct from matter-read authorization. MCP tool arguments cannot set identity, grants, or release consent.
5. Review writes remain human-only. The MCP adapter must not expose review mutation tools.
6. A legacy headless-v1 snapshot must be visibly identified as legacy discovery and must not be presented as canonical verification.
7. A failed or incomplete canonical report must fail closed; never silently fall back to legacy discovery.

## Acceptance tests (required before merge of consumer migration)

- Same signed matter and snapshot produce equivalent assessment fields through dossier REST, MCP, and web.
- Incomplete/unconfirmed/unreadable inventory never produces `not_in_inventory` in MCP.
- Translation markers, region coverage, and all three page spaces survive each projection.
- Unauthorized, revoked, cross-matter and content-release-denied callers receive no document text.
- Snapshot hash, engine rules version, and report schema version are preserved.
- No MCP tool accepts user identity, release consent, or human review decisions as model arguments.
- Exports enforce the same matter grant and content-release policy.
- Existing legacy endpoint remains explicitly labelled or is retired with a documented migration.

## Sequencing

First implement the shared projection and tests; then wire the MCP adapter; then make web and export paths consume it. Only then pursue larger page budgets and durable page-processing jobs. Hosted MCP protocol upgrades remain a separate deployment decision.

## Non-goals

This ADR does not authorize hosted MCP, OAuth rollout, changing the evidence assessment taxonomy, or claiming that a passing synthetic test is live practitioner acceptance.
