# CaseProof — Architecture Decisions v2 Reference

**Condensed repository reference.** Full earlier blueprint is preserved in the previously delivered architecture ZIP.

## Architecture decision
Hexagonal DDD-inspired modular monolith. Separate FastAPI HTTP process and durable background worker on one codebase, PostgreSQL database and private object storage. No microservices, vector service or free-running agent framework for the first paid pilot.

## Domains
`tenancy`, `intake`, `documents`, `evidence`, `reconciliation`, `finance`, `rules`, `workflow`, `reviews`, `dossiers`, `audit`.

### Dependency rule
`delivery(adapter) → application → domain`; outbound ports expose interfaces for database, storage, OCR, model provider and PDF rendering. Domain has zero imports from SDKs, frameworks or concrete adapters.

## Factual and legal separation
Citation verification checks literal source match; factual reconciliation compares documentary assertions; legal assessment requires dated, applicable authority and professional review. Never infer acceptance from silence or IOS eligibility from a high confidence score.

## Evidence model
Immutable document version with content SHA-256; parse/OCR derivation and source offsets; candidate assertion; verified quote status; support/contradict/qualify links; separate factual status; exception record; immutable reviewer decision; dossier snapshot with complete source manifests and reproducible version hashes.

## Durable workflow
`INTAKE → QUARANTINE → PARSED → EXTRACTED → QUOTES_VERIFIED → RECONCILED → RULES_EVALUATED → READY_FOR_REVIEW → DOSSIER_PREPARED → APPROVED`. Nonhappy paths: rejected upload, extraction failure, retryable error, poison file, needs evidence, cancelled and stale snapshot. Job acquisition uses SQL transaction/lease + retry idempotency. External model calls run outside open SQL transactions.

## Rules and model routing
Use versioned conditional `RulePack(jurisdiction, effective_range, source_manifest, predicate, effects)`. Finance uses Decimal and explicit rounding. LLM extraction uses typed strict schemas and grounding checks. Compare full-context and segmented extraction empirically; RAG/embedding is postponed until benchmark suggests it improves recall without losing auditability.

## Data isolation and security
Dedicated CaseProof environment. Tenant membership and case containment independently checked even with service-role credentials. RLS on exposed Supabase tables, private buckets, expiring signed URLs, upload quarantine, malware/content checks, retention controls, threat model and least-privilege capabilities.

## User interface
Initial secure internal intake + reviewer exceptions; later premium accountant/lawyer dashboard. Every claim connects to exact source context, with explicit statuses and provenance. Never make green citation badges imply verified legal entitlement.

## Pilot gates
Measurable objection false negatives, unsupported citations, reviewer minutes, model and worker costs, price willingness, repeated buyer workflows and legal sign-off. No fabricated 95% confidence claim, blanket interest rate or payment-period rule.

## Future expansion
Separate jurisdictions as approved versioned rule packs. Add document types and integrators through ports. Dedicated services only when throughput or ownership warrants it. Publish a shared evidence kernel once stable, tested seams exist.
