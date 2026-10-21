# Evidence Kernel — mandatory agent rules

This file applies to ALL changes inside `packages/evidence_kernel/`.

1. NEVER import from `domains/`, `apps/`, FastAPI, ORMs, Supabase, Redis, LLM SDKs or any sector-specific module. The kernel must remain independent of finance, disputes and future verticals.
2. Only immutable, source-traceable evidence primitives and sector-neutral ports/use cases belong here. No invoice, VAT, debt, insurance or legal business rules.
3. Source verification, corroboration and human review are separate; no single `verified=true` or mutable reconciliation of source claims.
4. Do not alter public kernel contracts, provenance or authority semantics without an ADR, backward compatibility tests and human review.
5. Tests and `python scripts/check_architecture.py` must pass. Do not suppress, skip, weaken or remove the check.
6. If a feature needs a sector import, STOP and implement the behavior in `domains/<sector>/` or a composition-root adapter.

For feature-branch development while GitHub Actions and uv.lock are deferred, use `python scripts/verify_stage0.py` in an isolated cloud workspace with installed development dependencies. Record exact commands, results and unavailable checks. Unverified changes may be committed to a feature branch but must not be merged or released. Once a lockfile and runner exist, the mandatory locked checks resume. Never weaken architecture tests or bypass protected-branch gates.

## Stage 1 evidence semantics
- Typed source anchors identify immutable document versions and exact locations; source references must fail closed when stale, unresolved or cross-tenant.
- Keep candidate findings distinct from evidence-grounded, reviewed and approved outcomes. Unverified candidates may exist in quarantine; they cannot be promoted.
- Store citation resolution, quote/value fidelity, support/contradiction/qualification and sufficiency as independent dimensions; never use one VERIFIED boolean.
- Track coverage by required issue and source version, with explicit exclusion and unresolved-gap records. No inferred completion from processing alone.
- Domain gate policies reject unauthorized promotion. Human exception dispositions preserve original evidence statuses and require auditable rationale.
- No Pydantic, agent harness or database code inside the pure kernel. See ADRs 0008 and 0009.
