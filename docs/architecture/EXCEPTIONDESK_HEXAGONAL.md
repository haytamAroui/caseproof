# ADR 0006 — ExceptionDesk finance-first hexagonal architecture

**Status:** proposed implementation baseline, 2026-10-21.

## Product and boundaries
One product, one repository, one eventual API, one tenant-isolated persistence boundary. Finance resolves document mismatches; disputes later turns an unresolved case into a reviewed factual dossier without copying evidence. **Do not build both workflows simultaneously.**

## Dependency direction
```text
apps/api, apps/web, infrastructure adapters
               |
        application use cases
          /           \
  domains/finance   domains/disputes (future)
          \           /
      packages/evidence_kernel
```
The evidence kernel contains source identity, exact quote provenance, immutable assertions, source-verification outcome and review/audit contracts. It does **not** own finance calculations, sector schemas, legal decisions or model-specific prompts.

Source quote verification != factual truth. Corroboration and human decisions are orthogonal and cannot silently change immutable assertions. Hashes prove integrity relative to captured bytes, not authenticity.

## Ports and adapters
Future ports: document repository, evidence repository, extraction provider, audit event store, review repository, report renderer and clock. Adapters: private storage, Postgres/Supabase, parser/OCR, model provider, PDF, HTTP and durable worker. Composition root wires adapters; neither kernel nor finance imports their SDKs.

## Finance v1
Invoice and PO identifiers, currency, net amounts and optional line items; decimal arithmetic, source refs and explicit unknowns. A total mismatch creates a `requires_review` finding, not `contradicted` or `fraud`. VAT, credits, partial delivery, freight, rounding and amendments must be explicitly accounted for before conclusions. Mixed currencies are not compared without an approved conversion basis.

## Disputes v2
Chronology, correspondence, unresolved assertions, human-reviewed factual dossier. No autonomous legal advice, recovery notices, procedural eligibility or court filing.

## Rollout
1. Immutable evidence models and finance comparison with tests (EXD-001).
2. Source-anchored extraction + document intake + review persistence (EXD-002/003).
3. End-to-end upload-to-reviewed-report workflow and pilot validation (EXD-004).
4. CaseProof disputes as a second consumer (EXD-005).
5. Independently versioned kernel only if two consumers demonstrate a need.

## Guardrails
No direct AZComply runtime/database dependency. No universal plugin framework or microservices. Privacy, authorization, idempotency, review audit and test evidence are mandatory before customer data.
