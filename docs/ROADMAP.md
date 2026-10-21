# ExceptionDesk — execution roadmap (finance first)

**Product:** one Belgium-first B2B finance operations platform. **Launch workflow:** supplier invoice versus purchase order mismatch. **Second workflow:** CaseProof dispute dossiers after finance validation. Historical CaseProof-only roadmap is superseded by this file; historical ADRs remain reference.

| ID | Priority | Work | Acceptance |
|---|---|---|---|
| EXD-001 | P0 | Kernel immutable source claims, provenance and finance reconciliation | Pure Python tests pass; no sector imports in kernel; mismatch is a review finding |
| EXD-002 | P0 | Secure tenant-scoped upload, hash, version, source offsets and PDF/UBL intake | Cross-tenant denial; source references resolve; malformed/oversized files fail safely |
| EXD-003 | P0 | Structured invoice/PO extraction and deterministic source-quote verification | Unsupported quotes rejected; field schema and prompt versions stored; AI output cannot approve |
| EXD-004 | P0 | Review UI/API, idempotent audit events, approved resolution and export | User traces findings to sources and approves/rejects; retry does not duplicate decisions |
| EXD-005 | P1 | CaseProof factual dispute dossier module | Reuses original evidence and review history; verified chronology; human-approved export |
| EXD-006 | P1 | ERP/Peppol/UBL import and exception inbox | Pilot integration tested with real-world sanitized formats |
| EXD-007 | P1 | Security/privacy/tenancy hardening and paid pilot | DPA, threat model, retention, tenant tests, measured customer outcome |
| EXD-008 | P2 | Independent kernel packaging and other sector packs | Only after two proven domain consumers and stable contracts |

## Customer validation in parallel
Interview 8–12 Belgian accounts-payable/finance operations buyers. Determine invoice volumes, existing ERP exception workflows, investigation time, repeated cases and actual willingness to pay. Do not assume per-pack price or Gulf expansion.

## Definition of done
Executable tests and reproducible results, source traceability, tenant isolation before production, human decisions audited, no fabricated legal/financial conclusions, no autonomous external actions.

## Proposed Roadmap v3 — trust contracts and stage gates (review required)
Commercial direction remains finance-first: Belgian supplier invoice vs PO mismatch; dispute dossiers only after finance validation. Agent orchestration is optional and must not delay a deterministic paid pilot.

| Stage | Scope | Exit gate |
|---|---|---|
| 0 — Foundation | Hexagonal kernel, reference API and architecture checks | Existing merge; outstanding Stage 0 contract/test verification debt documented |
| 1 — Trustworthy evidence | Typed source anchors, independent verification, finding/support relationships, coverage ledger, promotion gate, provenance interface, adversarial tests | No unsupported promotion in deterministic fixtures; tenant and version checks enforced; domain purity maintained |
| 2 — Durability | Transactional repositories, private storage, atomic audit, tenant authorization, idempotency and restart recovery | Crash/retry/rollback and authorization tests actually pass |
| 3 — First sellable workflow | Invoice/PO/contract intake, deterministic reconciliation, reviewer exception UI, approved export, finance golden fixtures | Realistic pilot tasks and reviewer outcomes measured |
| 4 — Optional bounded execution | One-level root/worker harness, coverage-aware planning, checkpoints, budget limits | Baseline comparison shows value beyond deterministic workflow |
| 5 — Evaluation and pilot hardening | Independent task rubrics, adversarial tests, security/privacy review, integration and buyer metrics | Documented results and pilot readiness review |
| 6 — Expansion | Dispute dossiers, additional sector/jurisdiction packs, kernel packaging | Only after validated demand and stable contracts |

### Stage 1 tasks
- KRN-101 P0: versioned sources, passage IDs and derivation provenance.
- KRN-102 P0: typed anchors (text, PDF region, structured field, spreadsheet range).
- KRN-103 P0: separate citation resolution and quote/value fidelity checks.
- KRN-104 P0: findings and supports/contradicts/qualifies/inconclusive relationships.
- KRN-105 P0: authorization-aware promotion gate and exception disposition.
- KRN-106 P0: versioned coverage manifest with issue-level gaps and audited exclusions.
- KRN-107 P0: integrate provenance with transitions; atomic persistence is Stage 2.
- KRN-108 P0: adversarial kernel fixtures (wrong page, wrong version, misleading quote, contradictions, unauthorized approval, tenancy).
- KRN-109 P1: versioned contract draft and generated OpenAPI compatibility review.

### Additional cross-cutting work
- EXD-009 P1: bounded investigation orchestration (Stage 4, conditional).
- EXD-010 P1: independent evaluation harness with deterministic oracles, rubrics and private holdouts (Stages 3–5).

### Changes to existing EXD tasks
EXD-001 splits evidence kernel trust contracts from finance reconciliation; EXD-002 requires typed locators and tenant-safe resolution; EXD-003 separates fidelity from support; EXD-004 requires audited authorized promotion; EXD-005 requires reproducible manifests; EXD-006 retains integration scope with lineage; EXD-007 adds adversarial/recovery tests; EXD-008 remains conditional.

No implementation, migrations, agent framework or model training is authorized by this roadmap amendment alone. See proposed ADRs 0008–0010 and `contracts/kernel-api.v2.proposal.json`.
