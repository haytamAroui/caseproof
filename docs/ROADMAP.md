# ExceptionDesk — execution roadmap (finance first)

**Current status:** Stage 1 reference kernel merged; Stage 2 disposable integration proofs merged through PR #35, but no production-ready customer workflow. Consult [verified status](STATUS.md) before using this roadmap. **Product:** one Belgium-first B2B finance operations platform. **Launch workflow:** supplier invoice versus purchase order mismatch. **Second workflow:** CaseProof dispute dossiers after finance validation. Historical CaseProof-only roadmap is superseded by this file; historical ADRs remain reference.

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

## Stage gates — v3 trust-contract amendment (proposed; finance-first remains authoritative)
- **Stage 0 — Foundation:** Python modular reference and CI exist. Positive runs on `main` and forbidden-import negative control PR #4 were **actually verified** by 2026-10-22. Owner-controlled branch protection remains **unverified** (issue #5); CI passing is not permission to bypass CONSTITUTION C13/C25.
- **Stage 1 — Evidence integrity:** KRN-101 immutable passage/version model; KRN-102 typed anchors; KRN-103 citation resolution vs quote/value fidelity; KRN-104 finding-to-evidence support links; KRN-105 promotion gate; KRN-106 issue/source coverage ledger; KRN-107 provenance integration; KRN-108 adversarial tests; KRN-109 versioned API contracts. Stage 1 reference implementation is in-memory, not durable.
- **Stage 2 — Durable infrastructure:** tenant-scoped persistence, atomic state+audit, object storage, idempotency, crash recovery and authorization.
- **Stage 3 — Sellable invoice/PO exception workflow:** PDF/UBL intake, typed extraction, deterministic Decimal reconciliation, source viewer, contradiction queue, human review and export. Deliver a usable deterministic pilot without agents.
- **Stage 4 — Optional bounded orchestration:** one-level planner/worker execution, explicit coverage, checkpoints, budgets and escalation; only after benchmark evidence of value.
- **Stage 5 — Evaluation and paid pilot:** independent kernel invariant suite, finance golden corpus, agent comparative benchmark if adopted, security and customer outcome gates. Invariant tests begin in Stage 1, not Stage 5.
- **Stage 6 — Conditional expansion:** dispute dossiers and sector packs after validated customer demand; independent kernel packaging after two consumers.

### Stage 2 — merged reference slices and remaining integration (verified 2026-10-22)

**Design reference:** [ADR 0010](adr/0010-stage2-native-durability.md). The purpose is to preserve KRN-101–109's trust contracts in a **new, independent CaseProof implementation**, learning from earlier engineering experience without copying external product code, database schemas, roles or runtime dependencies.

| Slice | Verified state on `main` | Production exit / remaining gate |
|---|---|---|
| S2-001 identity/case access | Merged deny-by-default boundary | No spoofable client tenant header as authority |
| S2-002/002A foundational migration | Canonical seven-table `caseproof` development Supabase schema installed; disposable PG17 RLS/CAS/rollback CI | Genuine tenant identity and least-privilege deployed roles |
| S2-003 Auth verifier | Merged independently checked Supabase `/user` verifier | Real signed-user and session-revocation proof; not automatically human approval |
| S2-005 case reader | Merged read-only repository adapter, unwired to live pool | Authorized real DB connection, tenant and same-org case isolation |
| S2-006 signed Auth probe | Merged manual-only authentic session verification tool | Two genuine development accounts, protected environment secrets and successful run |
| S2-004 / PR #28 | **Merged disposable PostgreSQL** atomic observation/audit/idempotency proof | Real review-command writer, case/evidence heads and human authorization, `/v2` routes |
| S2-007 / PR #29 | **Merged** synthetic PostgreSQL tenant-denial suite and protected manual genuine-Auth workflow | Real signed Auth→least-privilege runtime DB identity; A/B and revocation/pool proof |
| S2-008 / PRs #30–33 | **Merged** graph design, **disposable** representation/anchor SQL, typed codec, read-only scoped JSONB reconstruction | Canonical graph migration; finding/link/assessment/coverage persistence, real object provenance and current-head gate |
| S2-009a / PR #34 | **Merged** in-memory private Vault protocol: stable intents, put-once, SHA readback and unknown-commit reconciliation | Actual object store/scan/version identity and deployed authorized ledger |
| S2-009b / PR #35 | **Merged disposable PostgreSQL** audited staged/verified/unavailable ledger with atomic CAS, idempotency and concurrent replay | Install reviewed migration, real Supabase private Storage, trusted byte proof and availability-head invalidation |
| S2-010 | **Not implemented** | Persistent lease/worker restart, outbox replay, crash/timeout negatives and safe unknown outcomes |

S2-004 **has been implemented as a production-disabled reference** with disposable DB tests. S2-007/008/009 references have also been implemented in development form; they are not a connected, authenticated customer workflow. A **real authorized promotion/approval API** depends on their integration plus trusted human attestation, aligned action permissions and effective-policy resolution. No `/v2` customer route is authorized by a green unit test or by creation of these docs.


**Open repository administration gate:** [issue #5](https://github.com/haytamAroui/caseproof/issues/5). As of this audit, actual main-branch CI green, intentional architecture negative-control fail demonstrated, but owner-controlled merge protections **not verified**. Never merge negative-control PR #4. [`docs/STATUS.md`](STATUS.md) tracks actual evidence and release blockers.

**Priority before more kernel prototypes:** [real signed Auth→tenant DB least privilege](https://github.com/haytamAroui/caseproof/issues/37); [real private stored source bytes and reviewed ledger](https://github.com/haytamAroui/caseproof/issues/38); [persisted evidence/coverage and human decisions](https://github.com/haytamAroui/caseproof/issues/39); then [a working invoice/PO discrepancy user journey](https://github.com/haytamAroui/caseproof/issues/40), not open-ended agent framework construction.

**Stage 2 release gate:** real cryptographic Auth and runtime DB isolation; fine-grained kernel evidence persisted without lossy flattening; verified private original bytes and immutable parser lineage; authorization, snapshot and state+audit+receipt committed atomically; revocation, concurrent retries, audit-failure rollback, signed URL attacks and crash/restart demonstrated using appropriate real integrations. Unknowns remain blockers.

**Stage 3 first outcome:** one finance reviewer can upload invoice+PO, inspect exact source evidence and incomplete/contradictory issues, record an action-scoped review and export a reproducible resolution package. Do not add general agents, new sectors or public legal-action endpoints to bypass the pilot outcome.

### Updated EXD acceptance
EXD-001 splits sector-neutral kernel tasks from finance reconciliation. EXD-002 requires versioned typed anchors and tenant-scoped citation resolution. EXD-003 checks extracted fields, fidelity, contradiction and source support separately. EXD-004 enforces authorization, promotion policies, idempotent review and immutable audit. EXD-005 requires reproducible dossier evidence manifests and unresolved-coverage disclosure. EXD-006 retains ERP/Peppol/UBL lineage. EXD-007 adds adversarial source, recovery and privacy tests. EXD-008 remains conditional. **EXD-009:** bounded orchestration only if measured benefit. **EXD-010:** independent rubric and deterministic evaluation harness.

### Stage 1 exit criteria
- Invalid/stale/cross-tenant anchors fail closed; matching quote never implies semantic truth.
- No unsupported or unreviewed candidate becomes an approved conclusion; exception disposition cannot change support status.
- Required source/issue coverage and exclusions are explicit; missing coverage blocks ordinary completion.
- Tests for the above must be executed and documented before **Stage 1 implementation PRs** merge. PR #8 originated as a design-only contract proposal; subsequent KRN-101–109 implementation PRs are merged. That history does not authorize live v2 routes or durable approvals. Cloud CI evidence and owner-controlled release gates remain required by C13/C16/C25. Stage 2 owns durable transactional guarantees.
