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
