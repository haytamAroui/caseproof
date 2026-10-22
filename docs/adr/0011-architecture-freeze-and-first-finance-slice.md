# ADR 0011 — Freeze CaseProof architecture and unblock the first ExceptionDesk workflow

**Decision:** ACCEPTED as product/architecture target on 2026-10-22 by explicit project-owner instruction. **Not** a production security approval, schema migration approval, proof of live Auth, authorization attestation, paid pilot certificate or license to override `CONSTITUTION.md`.

**Supersedes:** only contradictory future implementation-order interpretations and vocabulary in earlier proposals. ADRs 0001/0004/0007–0010 continue to provide trusted design constraints. `contracts/architecture_baseline_v1.json` and `contracts/action_catalog.v1.json` are machine-checked freeze inventories; real code and installed migrations remain authoritative for their own behavior. `/v1` is legacy development-only.

## Five fixed architectural decisions

1. **One hexagonal modular monolith.** Pure Python `packages/evidence_kernel` owns sector-independent source/representation lineage, typed anchors, exact citation/fidelity verification, immutable candidate finding/link revisions, coverage manifests, provenance and **pure** promotion-policy evaluation. It does NOT call OCR, Auth, LLMs, PostgreSQL, queues or customer workflows.
2. **Three distinct authorities.** Document intelligence parses bytes and produces *candidates*. A finance domain service applies deterministic `Decimal`, comparable currency/VAT-basis, partial-delivery, freight, credit and amendment policies. The authenticated application service applies an effective policy and atomic audit/review/exception action. Exact quotes are neither factual truth nor permission.
3. **Single evidence lifecycle.** KRN-101 `SourceVersion`/`DerivedRepresentation` plus typed KRN-102 `EvidenceAnchor` is the authoritative new `/v2` identity lineage. Legacy `workflow.DocumentVersion` and `/v1` in-memory models remain compatibility-only, never second source of truth. A changed parser/normalization creates a new representation and new assessed links.
4. **Independent execution and evidence state.** `pending/verified/unavailable` source storage, source verification, coverage inventory, finding lifecycle, review decision and worker step outcome are distinct state dimensions. `OUTCOME_UNKNOWN` is for uncertain external effects, not approval or source truth. A worker succeeded ≠ evidence supported; a human accepted a business exception ≠ the factual mismatch disappeared.
5. **No generic framework before customer validation.** Do not invent `DomainPack`, a universal `EvidenceState`, pluggable jurisdiction platform, recursive agent graph, independent kernel package or shared AZComply runtime now. Copy only lessons; CaseProof code/data/projects remain independent.

## Six areas and ownership

| Responsibility | Target owner | Immediate boundary |
|---|---|---|
| Evidence integrity | `packages/evidence_kernel` | Domain types/policies only; pure Python |
| Document intelligence | `application/documents` and `application/extraction` | Parsers/OCR/LLMs behind application ports; candidate trace, no classification authority |
| Deterministic business reasoning | `domains/finance` | Explicit money basis, tax/currency/amendments and rule versions |
| Execution and recovery | `application/runtime` + `infrastructure/execution` | Real leases, checkpoints, durable artifacts, outbox; external calls outside SQL transactions |
| Review and decision governance | `application/review` + `application/decisions` | Trusted current actor, policy, frozen snapshot, atomic state+audit+receipt |
| Evaluation and observability | `evals` + infrastructure telemetry | Synthetic golden finance cases now; optional agent benchmark only with baseline |

No folders need to be created merely to match this conceptual diagram. The first real use case should create only the smallest necessary modules; adapters currently in `apps/api` can migrate behind use-case ports when wiring begins. HTTP routing never becomes the workflow engine.

## v2 API and persistence contract freeze — resolved

- **Locator wire identity:** canonical kinds `text_span`, `pdf_region`, `sheet_range`, `structured_field`. Text spans carry *explicit* `encoding` and `normalization`. Sheets carry optional `table_id`. PDF positions are **bounded, canonical decimal strings** with exact KRN-102 `Decimal` conversion: JSON number/float coordinates and lossy coercion are rejected. Current v2 draft changes are safe only while `/v2` is **disabled**; they are not a silently backward-compatible public API upgrade. Explicit `to_kernel_locator` + storage codec tests enforce exact round trips. Coordinate conventions remain fixed to versioned layouts.
- **Authoritative access catalog:** installed `caseproof` schema and `CaseAction` declare only `case:read`, `coverage:read`, `evidence:read`, `finding:write`, `review:request`, `conclusion:request_approval` and `exception:request`. The future `evidence:write`, `finding:promote`, `conclusion:approve` and `exception:accept` are **NOT INSTALLED**. Request permission is never approval. `contracts/v2_operation_matrix.json` flags each not-yet-granted action as *blocked* and all v2 routes as *disabled*. A future reviewed action-grant/RLS migration and human attestation policy must precede every consequential operation.
- **MVP organization access policy:** signed, current active organization membership **plus specific granted action** gives org-wide access to cases in that organization. This is a **product scope decision**, not a claim that the whole org has equal action rights. Same-org case assignment is **not** a current restriction. If private assignment is required for a pilot, add explicit case grants in a separate, reviewed data-model decision with real same-org cases tested before any customer deployment. Never assert assignment isolation from composite FKs alone.
- **No actor masquerading:** review approval requires a second, explicitly authenticated, action-specific human attestation and independently derived server actor/org/case; a user-supplied `actor_id`, `human_authenticated` flag or UUID simulation does not confer approval authority. Current `/v1` caller-controlled tenant header is development only.
- **No duplicate stored source models:** new data paths use KRN-101 lineage and verified immutable bytes; `caseproof.document_versions` foundational table is a physical source-version reference and must be mapped precisely to kernel identity. Do not create a third parallel truth ledger.
- **Trusted persistence:** S2-004/008/009 disposable PostgreSQL proposals and in-memory mock ledgers are *test references*, not installed schema or real source availability proof. No real storage/RLS change is granted by this ADR.

## Canonical product execution flow (logical gates)

1. **Trusted Auth and immutable source intake.** Accept bounded PDF/UBL bytes into a private quarantine; validate content, scope, digest, object storage, version identity; no external client-supplied tenant as authority.
2. **Parser-specific faithful representations.** Deterministic UBL/XML parser first where applicable; PDF text/OCR as separately derived, versioned representations. Preserve coordinates and parser/config identity. A parser does not assert a legal or financial conclusion.
3. **Inventory and finance scope.** Required source/issue inventory, missing PO, VAT basis, amendments, credits, currency and uncertainty.
4. **Parallel candidate finance and evidence work.** Deterministic comparison may detect a proposed €100 discrepancy immediately after a reliable parse, while exact typed anchor resolution, readback, fidelity and semantic relation checks run. Neither branch alone grants final disposition.
5. **Coverage, conflicts and frozen review packet.** Relate candidates to current source/finding/scope versions, retain unresolved issues and contradictory evidence visibly.
6. **Authorized human disposition and reproducible export.** Independently verify reviewer + permissions + current snapshot; one transactional state+audit+idempotency transition. Business acceptance may close workflow but NEVER converts unsupported evidence to verified truth. Export original anchors, manifest, unresolved exceptions and review provenance.

Do not impose expensive AI semantic assessment on a deterministic amount candidate before it can be shown as **unreviewed**; do require every applicable evidence/coverage/reviewer gate before consequential approval/export.

## Revised delivery order — two tracks

**Track A, secure foundation:** verify owner-controlled branch protection [#5](https://github.com/haytamAroui/caseproof/issues/5), genuine signed Auth and least-privilege database tenancy [#37](https://github.com/haytamAroui/caseproof/issues/37), private verified immutable source bytes [#38](https://github.com/haytamAroui/caseproof/issues/38), a persisted assessment/coverage graph and transactionally authorized reviews [#39](https://github.com/haytamAroui/caseproof/issues/39), then durable leased worker/recovery before remote callbacks matter. A green disposable SQL test does not release any step.

**Track B, synthetic-only finance outcome:** while foundation is reviewed, develop one real-format but **synthetic/sanitized** UBL invoice + PO parser, deterministic finance policy/golden corpus, source-linked candidate discrepancy, reviewer workbench/prototype and report layout [#40](https://github.com/haytamAroui/caseproof/issues/40). No production customer uploads, exposure or approved decision through mocks.

**Join gate:** a genuine logged-in reviewer completes one invoice/PO case end to end: private immutable source bytes → validated typed fields → source-resolved discrepancy → explicit signed human disposition → atomic audit and frozen evidence snapshot → reproducible export. Show real cross-tenant, session revocation, stale snapshot and crash/retry behavior before first paid pilot.

**Later:** adaptive multi-pass extraction only after measured improvement vs deterministic baseline; bounded investigator delegation only after rubric/golden-set evidence. Buyer interviews and observed finance work happen alongside product engineering.

## Change control

The five decisions and action/locator catalog are **frozen target contracts**, not immutable dogma: revisiting them requires evidence of a business, security or quality requirement, a new ADR with explicit migration/compatibility strategy and updated cross-layer tests. Changes to installed grants, schema, a real private bucket or production approval still require separate review and owner control under C13/C16/C25. PR #36 is documentation cleanup; this ADR is intentionally stacked on it to avoid merging contradictory records.
