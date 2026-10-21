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

## Stage gates — v3 trust-contract amendment (proposed; finance-first remains authoritative)
- **Stage 0 — Foundation:** reference implementation exists, but merge authorization is blocked until a genuine CI run passes, the deliberately forbidden-import negative-control PR fails for the intended reason, and owner-controlled merge protection is enabled (CONSTITUTION C25). Verification debt is not merge permission.
- **Stage 1 — Evidence integrity:** KRN-101 immutable passage/version model; KRN-102 typed anchors; KRN-103 citation resolution vs quote/value fidelity; KRN-104 finding-to-evidence support links; KRN-105 promotion gate; KRN-106 issue/source coverage ledger; KRN-107 provenance integration; KRN-108 adversarial tests; KRN-109 versioned API contracts. Stage 1 reference implementation is in-memory, not durable.
- **Stage 2 — Durable infrastructure:** tenant-scoped persistence, atomic state+audit, object storage, idempotency, crash recovery and authorization.
- **Stage 3 — Sellable invoice/PO exception workflow:** PDF/UBL intake, typed extraction, deterministic Decimal reconciliation, source viewer, contradiction queue, human review and export. Deliver a usable deterministic pilot without agents.
- **Stage 4 — Optional bounded orchestration:** one-level planner/worker execution, explicit coverage, checkpoints, budgets and escalation; only after benchmark evidence of value.
- **Stage 5 — Evaluation and paid pilot:** independent kernel invariant suite, finance golden corpus, agent comparative benchmark if adopted, security and customer outcome gates. Invariant tests begin in Stage 1, not Stage 5.
- **Stage 6 — Conditional expansion:** dispute dossiers and sector packs after validated customer demand; independent kernel packaging after two consumers.

### Updated EXD acceptance
EXD-001 splits sector-neutral kernel tasks from finance reconciliation. EXD-002 requires versioned typed anchors and tenant-scoped citation resolution. EXD-003 checks extracted fields, fidelity, contradiction and source support separately. EXD-004 enforces authorization, promotion policies, idempotent review and immutable audit. EXD-005 requires reproducible dossier evidence manifests and unresolved-coverage disclosure. EXD-006 retains ERP/Peppol/UBL lineage. EXD-007 adds adversarial source, recovery and privacy tests. EXD-008 remains conditional. **EXD-009:** bounded orchestration only if measured benefit. **EXD-010:** independent rubric and deterministic evaluation harness.

### Stage 1 exit criteria
- Invalid/stale/cross-tenant anchors fail closed; matching quote never implies semantic truth.
- No unsupported or unreviewed candidate becomes an approved conclusion; exception disposition cannot change support status.
- Required source/issue coverage and exclusions are explicit; missing coverage blocks ordinary completion.
- Tests for the above must be executed and documented before **Stage 1 implementation PRs** merge. The documentation-only PR #8 defines proposed contracts, not passing implementation or contract tests. It requires independent design review and must separately satisfy C25 before merge; the draft JSON proposal is not covered by C25's Markdown-only commit exception. Stage 2 owns durable transactional guarantees.
