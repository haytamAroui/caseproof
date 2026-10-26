# M1 pragmatic-hexagonal implementation audit — PIV-02–06

**Audit date:** 2026-10-26. **Code reference:** PR #62 `feat/piv-m1-evidence-library`, originally `158891453df5d3bc3f90dbc3c2d2af87ae95a6b0` before this amendment. The M0 baseline merged as PR #61. **Status:** engineering review with targeted corrections; NOT a customer release certificate. CI conclusions must be checked against the actual final PR HEAD.

## Decision

**Pragmatic hexagonal direction: ACCEPTABLE for the internal reference slice; M1 product milestone: NOT COMPLETE.** No need to split this modular monolith into microservices, write domain packs, or add provider-specific abstractions. Keep the existing source-version Kernel sovereign. The code's general dependency direction matches `CONSTITUTION.md` C09/C22 and ADR-0011, but test success on synthetic fixtures is not proof of production authorization, isolation, durable custody, OCR, reviewer decisions or full M1 product acceptance.

## Dependency boundary inspection

| Owner | Source and tested responsibility | Dependency rule / finding |
|---|---|---|
| **Sector-neutral Kernel** | `packages/evidence_kernel/` KRN source versions, representation lineage, anchors | Untouched by M1; never imports dispute, parser, DB, auth or LLM |
| **Dispute domain** | `domains/disputes/exhibits.py` immutable exhibit identity, alias and page map; pure revision CAS proposal | Standard library only; no API/DB/Word/LLM imports, no legal authority policy; matches C22 |
| **Application** | `application/litigation/library.py` document inventory/preview orchestration; `application/documents/catalog.py` stable source reference contract | Uses `DocumentParser` inward-facing port and KRN source contracts; no infrastructure or API import |
| **Inbound/API composition** | `apps/api/authenticated_evidence_library.py` | Calls existing `CaseAccessService`; derives Vault scope from authorized actor/matter; before/after current authorization; depends inward |
| **Outbound adapters** | `infrastructure/parsers/limited.py` + `engines.py`; existing scoped Vault protocol | Implement parsing and custody outside domains/application. New DOCX support is a bounded internal parser, not a production malware sandbox |
| **Tests and architecture** | `scripts/check_architecture.py`, full CI, M1 tests | Static import guard checks Kernel, domains, application; fixtures prove specific contracts only, not actual cloud Auth/DB/Storage |

**Corrected in PR #62 review:** replace sibling API-to-API DTO dependency with a shared application source descriptor; prevent backdating derived representations to ingestion; empty evidence set is not declared fully processed; normalize exhibit labels at lookup; report PDF annotation omissions by physical page and DOCX header/footer/comment/field/textbox omissions explicitly. No external/public APIs, SQL grants, production migrations, provider routes or Kernel primitives were changed.

**Design trade-off:** `EvidenceIndexer` reparses bounded sources per read and returns a fresh text representation, useful for an internal slice but not durable/restartable indexing; optimize only after the persisted representation/worker contracts are installed. The read-side composition uses a trusted in-memory original from the catalog and independent Vault read-back; it is NOT an authenticated durable customer upload implementation.

## All M1 packets against authoritative exit criteria

| Packet | Implemented and observable | Missing mandatory criterion | Assessment |
|---|---|---|---|
| **PIV-02** authenticated matter access | Fail-closed internal bearer action checks (`case:read` + `evidence:read`), post-processing reauthorization, revocation/foreign-case fixtures | Genuine signed-user→least-privilege DB session, matter-create/list route, scoped workers, case-grant policy incl. same-org private matters, mounted secure API, negative tests on live approved dev Auth | **PARTIAL; production blocked** |
| **PIV-03** immutable private evidence | Existing Vault intents/read-back/digests and disposable PostgreSQL tests; internal composer compares bytes and immutable source versions | Production private object store, quarantine/AV, schema migrations, object-backed ingest/restore, audit on writes, retention/deletion, cross-region/worker recovery, signed actor→DB policy | **PARTIAL; production blocked** |
| **PIV-04** deterministic intake/jobs | Internal bounded model-free inventory, normalized original SHA/parser/version, clear ready/partial/failed, tested PDF and DOCX | Real authenticated ingress + durable jobs, per-page persisted failure/retry/recovery and checkpoint/quotas, actual per-dossier cost accounting, independent timeouts/budgets at customer scale | **PARTIAL; production blocked** |
| **PIV-05** PDF/DOCX/OCR fidelity | Internal child-process bounded PDF page text and DOCX paragraph/note extraction, explicit unsupported layout and hidden-content warnings; blank-page status | Actual scanned-image OCR, source-linked coordinates/geometries, verified rendered DOCX/footnotes/tables, complete per-page coverage through recovery, malicious-document isolation beyond Linux resource limit, corpus benchmarks | **PARTIAL; production blocked** |
| **PIV-06** exhibit mapping | Pure versioned `ExhibitRegister`, stable IDs, Stuk/Pièce aliases, independent printed/PDF/bundle pages, duplicate/ambiguous/unknown cases, CAS **proposal** | Authenticated human mapping, persisted confirmed version with atomic CAS+audit, accessible register UI, attachments/annex/bundle mapping and separate communication/filing records, change invalidation | **PARTIAL; production blocked** |

## M0 language scope correction

Product languages: **NL, FR and EN**. Each must be available for UI, evidence workflow/search and supported outputs; choose UI/source/editor/output independently. M0 v1 original fixtures remain preserved. New `evals/litigation/m0_corpus_v2.json` adds English clean, mismatch, ambiguous, scan-incomplete controls and one NL/FR/EN mixed scenario; author-supplied labels are unadjudicated. The validator requires the three individual language cohorts plus mixed. Fixture coverage does **not** demonstrate language-aware retrieval quality or translated released screens.

## Release gates and acceptance sequence

1. **Security decisions:** owner approves same-org restricted matter policy and minimal read/write/confirm actions; verify real Supabase signed-user sessions → least-privilege DB, revocation, isolated case membership and worker delegation. Do not infer release rights from `READ_EVIDENCE`.
2. **Real source custody:** approved private bucket and audited immutable object + SQL schema, ingestion quarantine/malware boundaries, installed RLS/grants, persistence/restart/retention/recovery verification, lost-ACK reconciliation.
3. **Processing fidelity:** genuine independent PDF/DOCX/image-based OCR corpus in NL/FR/EN, failed page states with known denominators, source and representation digests, source-anchored visual/printed/PDF page mappings, throughput/budget accounting.
4. **Exhibit confirmation:** authorized human validates provisional aliases, conflicts and versions; durable transaction and audit; same-source/scope checks, duplicate labels, stale revision/change propagation, separate communication and filing facts.
5. **Reviewer UI journey:** signed-in lawyer on approved infrastructure imports/preserves, opens original/derivative, confirms exhibits, sees partial/fail warnings, resumes after restart, and reopens evidence source in all supported languages. Record actual test and evidence SHA.

No M2 brief-checking or claim of finished M1 until exit tests on actual final product interfaces and dependencies pass. Do not merge high-risk production authorization/storage work without human review and required CI.

## Non-goals and residual risks

- No auto-filing, court-ready badge, legal-authority checking, signoff, internet document retrieval, Requesty inference or source trust inference.
- Parser's Linux subprocess resource limits are NOT a malware isolation boundary; a separate hardened worker/container and security review are required.
- DOCX text order and page layout are NOT equivalent to the rendered document; dynamic fields, headers, comment threads, tracked changes and drawings can affect meaning. Show explicit incomplete scope.
- Exact Vault bytes and SHA do not establish authenticity, complete case record, adjudicated facts or court receipt.
- Metrics comparing CaseProof against competitors remain `unmeasured`. No authenticated live pilot or benchmark is claimed.

**Follow-up:** continue improving PIV-02–06 on the same big M1 engineering PR or an explicitly approved production integration packet; do not inflate fixture assertions into milestone completion.