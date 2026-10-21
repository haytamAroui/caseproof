# CaseProof — Engineering Foundation

A planning and engineering-governance repository for **CaseProof**, a source-anchored B2B commercial-dispute dossier workflow.

**Status:** architecture and implementation specification only. This branch does not contain a runnable product and makes no production-readiness claim.

## Start here
1. [Engineering constitution](CONSTITUTION.md) — invariant authority.
2. [Agent instructions](AGENTS.md) and [Claude Code instructions](CLAUDE.md).
3. [Implementation roadmap](docs/ROADMAP.md), [coding standards](docs/ENGINEERING_STANDARDS.md), [orchestration](docs/AGENT_ORCHESTRATION.md).
4. [Architecture ADRs](docs/adr/) and [quality gates](docs/quality/).
5. [AZComply reuse and architecture reference summaries](docs/reference/).

The original longer 2026-10-21 design blueprints were supplied as downloadable archives in the planning conversation. The two documents in `docs/reference/` are **condensed repository summaries**, not byte-for-byte copies of the original long reports.

## Technical baseline
Hexagonal DDD-informed modular monolith; FastAPI; dedicated Postgres/Supabase instance; private storage; durable worker; grounded structured extraction; deterministic reconciliation and approved conditional rules; exceptional human review.

## Founder and agent rules
Protect sensitive client evidence, tenant boundaries, source provenance, approval authority and audit completeness. Start with real buyer/pilot validation and a secure end-to-end vertical slice before speculative SaaS features.
