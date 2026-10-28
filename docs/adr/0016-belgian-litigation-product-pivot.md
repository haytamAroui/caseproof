# ADR 0016 — Belgian litigation writing and evidence review pivot

**Decision:** ACCEPTED as the product delivery direction on 2026-10-26; **commercial Word-first/broad-scope decision SUPERSEDED on 2026-10-28 by [ADR 0018](0018-pre-submission-verification-freeze.md)**. Retained as historical rationale and for architecture/security continuity. **Implementation:** M0 contracts and synthetic evaluations only; no new production routes, schema, authorizations, or legal-rule approval.

**Historical source of authority:** [ROADMAP.md](../ROADMAP.md) now records the narrower M0–M6 scope; historical PIV-00–20 items do not override it and [PRODUCT_WORKFLOW.md](../PRODUCT_WORKFLOW.md) is the companion full user journey. This ADR records product-level decisions; it does not override [CONSTITUTION.md](../../CONSTITUTION.md) or technical trust gates.

## Decision and intended customer outcome

Focus the next CaseProof product on Belgian lawyers reviewing civil/commercial briefs against an exhibit record. Deliver: authenticate/open matter → preserve and inventory evidence → confirm Stuk/Pièce mappings → write with evidence in Word/web → check own/opponent draft → inspect/resolve/correct → review exact revision → produce linked reports, brief and exhibit bundle → share/human handoff. Dutch (NL), French (FR) and English (EN) are equal product languages for UI, search, evidence workflow and supported outputs. Matter source language, editor language, UI language and output language remain independent; readiness per language must be measured.

The product is **not** currently implemented. The evidence/kernel and finance prototypes are reusable reference components, not proof of end-to-end litigation production readiness. Competitive product evidence supports investigation of a category, **not** a conclusion about Belgian willingness to pay or feature parity.

## Supersession / non-supersession

- **Supersedes:** finance-first *commercial delivery order* in ADR-0011, historical roadmap prose, README/STATUS legacy next-work advice. This is sequencing, not a rewrite of past tests.
- **Retains:** ADR-0011's hexagonal modular monolith, six responsibilities, strict Kernel sovereignty, atomic decision authority, source/version and evidence state separation, API v2 disabled/ungranted actions, auth/tenancy/storage gates and cautious Requesty boundary. Historical finance ADR remains evidence of its period.
- **Compatibility:** `domains/finance/`, `domains/construction/`, existing application/runtime/evals/contracts and all tests stay intact. Do not rename/remove finance internals or upgrade contracts as part of M0.
- **Only disputes authority:** `domains/disputes/`. Litigation orchestration may later use `application/litigation/`; Word client is proposed at `apps/word_addin/`. Do not create `domains/litigation/`.
- **Source identity:** preserve immutable original and versioned representations. Editable Word ranges are ephemeral editor references, never Evidence Kernel anchors.
- **Trust:** exact quote fidelity is not semantic support, source authenticity, completeness, legality or court readiness. Model proposals never approve. Requesty is an optional application provider only; deterministic tasks must run without a model account.

## Role and permission contracts (design decisions; NOT grants)

| Responsibility | Planned system boundary | Present release status |
|---|---|---|
| Authenticated organization/matter access and action scopes | apps/api + application access + Supabase Auth/RLS | Security and true signed-user→DB session gate open |
| Preserved bytes, immutable versions, anchors, provenance | existing kernel contracts + trusted persistence/Storage adapters | Disposable/reference implementations, not customer custody |
| PDF/DOCX/OCR, page completeness, exhibit identity/aliases | infrastructure parsers + application + domains/disputes | DOCX/OCR, exhibit register and complete page coverage pending |
| Factual citation/draft graph and scoped checks | application/litigation + disputes policies + Kernel fidelity | Not implemented for litigation |
| Search/ranking and optional semantic proposals | application retrieval/extraction, Requesty-only for LLM | Retrieval/semantic quality not established |
| Word selection, citations and reversible edits | apps/word_addin through common API | Not implemented |
| Review/release/output/share and filing handoff | authenticated application transaction + rendering adapters | Synthetic recommendations/draft exports only; no legal release |

Existing ADR-0011 *organization membership + action* policy is not same-organization private-matter isolation. PIV-02 must explicitly decide case grants and prove restriction before confidential matters requiring it. A user-provided actor/tenant or signed-in browser alone never approves/reconciles/releases. Never create a legal conclusion or file automatically.

## Change propagation and gates

Correction contract: **inspect → propose → preview → revalidate → apply/undo → invalidate → recheck**. Rechecks are tied to a known source/brief/review/output snapshot. Explicit stale decisions prevent release. PIV-01 supplies initial synthetic CP-01 (changed exhibit; unchanged control) and DE-01 (exhibit order/references) evaluation designs; it does not implement these workflows.

Deployment prerequisites remain: PIV-02 genuine Auth and matter permissions; PIV-03 production custody/recovery; PIV-04 bounded deterministic jobs; PIV-05 safe parsers/OCR; PIV-20 operational controls. Publication, sharing and filing are separate permissions and receipt states. Customer documents are prohibited until relevant gates demonstrate safety and consent. M0 may proceed on synthetic inputs only.

## Implementation order and reversibility

Begin with **PIV-00 status/contract/claims inventory** and **PIV-01 rights-cleared synthetic Dutch/French/English corpus plus fixed competitive manual benchmark**. Then agree PIV-02–04 contracts, build M1–M4 workflow, defer optional semantic breadth (M5) and procedural connectors (M6). No time estimate is an approval.

Rollback: revert M0 docs/corpus/script/tests only. No runtime behavior, SQL, policy, external service, budgets or user data change. A later pilot must use a new reviewed ADR/PR for consequential decisions or installed production migrations.

## Acceptance of M0

- The principal roadmap and this ADR no longer conflict with active README/STATUS instructions; historical records remain historical.
- Code-observed versus design-only capabilities, gates and owners are explicit in [M0 baseline](../m0/BASELINE.md).
- [Claims register](../m0/CLAIMS_REGISTER.md) prevents unsupported external assertions.
- Versioned synthetic [current v2 corpus](../../evals/litigation/m0_corpus_v2.json) (with original v1 retained), [benchmark protocol](../m0/BENCHMARK_PROTOCOL.md), executable validator and adversarial tests are included. Fixture validation is **not** litigation product quality validation.
- Required CI must run on PR HEAD. No automatic merging or release authorization.
