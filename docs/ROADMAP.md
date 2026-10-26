# CaseProof — Belgian litigation writing and review roadmap

**Status:** proposed product roadmap; supersedes the finance-first delivery order in this file and all older competing roadmaps. It does not change historical ADRs, claim implementation, or authorize production routes, migrations, customer uploads, approvals, publication or filing.

**Product objective:** build a Belgian evidence-linked workspace for lawyers to organize a matter, write with evidence, check their own or an opponent's brief against exhibits, review and correct findings, and deliver source-linked documents. Clearbrief establishes a product category and workflow reference; it does not prove Belgian demand or CaseProof feature parity.

**Current baseline:** the code audit this plan derives from inspected main at `7c27e4ffcb5d512a55f88aca48423adb1d923861`. Audit observations are pinned to that commit and are not fresh verification. Existing evidence-kernel, finance, extraction, UI, persistence and security behavior must be checked against the implementation branch before each packet starts. Proposed work below is not implemented.


**M0 implementation packet:** See [ADR 0016](adr/0016-belgian-litigation-product-pivot.md), [pinned capability/gate matrix](m0/BASELINE.md), [external claims register](m0/CLAIMS_REGISTER.md), [fixed manual task benchmark](m0/BENCHMARK_PROTOCOL.md), and [original synthetic evaluation corpus](../evals/litigation/README.md). These are M0 evidence artifacts, **not** claims of approved legal gold labels, benchmarked accuracy, complete PIV-01 real-format coverage or production readiness.

**M1 integrated development slice:** [Implementation evidence and remaining gates](m1/IMPLEMENTATION.md) for PIV-02–06 (PR #62). Until production custody, genuine signed identity/permissions and audited exhibit confirmation exist, this is a tested internal reference, **not a complete or customer-usable M1 milestone**.

## Product workflow

1. **Set up and access a matter.** Authenticate the user, enforce organization and matter permissions, and create a case workspace.
2. **Import and preserve the record.** Store immutable originals; parse supported PDFs, DOCX and other declared formats; show per-file and per-page processing, OCR and failures.
3. **Confirm the exhibit register.** Map stable internal exhibit identities to Stuk/Pièce labels, aliases, annexes, versions and printed/PDF/bundle page numbers. Keep communication and filing records distinct from inventory.
4. **Write with evidence.** In Word, select an assertion, search the authorized record, inspect exact source context, and insert a citation. A web workspace uses the same application contracts and graph.
5. **Check a draft.** Resolve citations, flag exact quote/value discrepancies and ambiguous references, retrieve possible counterevidence, and present semantic/context observations as proposals. A clean case may produce zero confirmed problems.
6. **Review and correct.** Assign a reviewer or apply the configured solo-practice policy. Preview version-bound corrections, revalidate the live document, apply reversibly, then recheck affected assertions.
7. **Deliver.** Freeze the checked scope and exact artifact version; generate a review report, linked brief, exhibit index and bundle; share with selected recipients under explicit access rules. Filing remains a separate human handoff unless an authorized integration is implemented.

## Architecture and boundaries

- Keep the sector-neutral kernel in `packages/evidence_kernel/`: immutable source identity, typed anchors, exact fidelity, assessments, declared-scope coverage and provenance. It does not parse/OCR, call models, interpret Belgian procedure, authenticate reviewers or transact production storage.
- Use **only `domains/disputes/`** for Belgian litigation models and rules. Do not create a parallel `domains/litigation/` authority.
- Put use cases in the existing application contexts, with litigation orchestration under `application/litigation/` where needed. Keep storage, OCR, retrieval, identity and rendering in infrastructure.
- Use **`apps/word_addin/`** as the sole proposed Word-client path. `apps/web/` and Word call the same authenticated application API. Mutable Word ranges are editor references, not source evidence anchors.
- Keep finance modules and tests as a compatibility consumer. Do not mass-rename them or weaken kernel/security contracts.
- Inference is optional and Requesty-only under the existing provider boundary. Deterministic intake, literal checking and search must work without model credentials. Model output proposes; application rules evaluate; authorized humans make consequential decisions.
- Keep execution completion, source fidelity, semantic support, reviewer disposition, publication and external filing as separate states.

## Dependency order and implementation milestones

`PIV-00 → PIV-01 → agreed PIV-02–04 foundations → integrated litigation workflow`. Independent security, persistence and intake tracks may proceed in parallel after contracts are agreed. Synthetic work can use agreed interfaces while foundations mature. Confidential customer data must wait until applicable identity, matter isolation, source custody, persistence, recovery and operations gates are demonstrated.

| Milestone | User outcome | Packets and exit evidence |
|---|---|---|
| **M0 — Product and quality baseline** | One authoritative scope, contracts, owners and NL/FR clean/adversarial corpus | PIV-00–01; clean cases can return no findings; capability dispositions and limitations recorded |
| **M1 — Evidence library** | Import, preserve, inspect and organize a dossier without an LLM | PIV-02–06; real auth/matter policy, immutable bytes, parser lineage, page status and confirmed exhibit mappings |
| **M2 — Check and correct** | Check a supplied brief, inspect source context, correct a draft and produce a review report | PIV-07–09 plus correction/minimum output slice; deterministic path works; unresolved scope is visible |
| **M3 — Write with evidence** | Complete Word selection → retrieve → inspect → cite → edit/undo → recheck loop | PIV-10–11; supported-host and document-integrity tests; no semantic-model prerequisite |
| **M4 — Review and deliver** | Partner or policy-compliant solo review of an exact version, linked outputs and controlled recipient copy | PIV-14–16 and operational gates from PIV-20; dynamic exhibit and change propagation pass |
| **M5 — Deeper analysis** | Optional counterevidence semantics, chronology, tables, summaries and document questions | PIV-12–13; separately measured retrieval and model quality, abstention and costs |
| **M6 — Belgian operations** | Reviewed procedural profiles, filing preparation/receipt capture and one justified connector | PIV-17–19; verified authorities, local profiles, actual integration entitlements and recovery |

Milestones are acceptance outcomes, not calendar estimates. The “1–3 person-weeks” estimate is withdrawn.

## PIV-00–20 authoritative backlog

- **PIV-00:** superseding product ADR, active instructions, current status matrix and compatibility plan. Preserve ADR-0011's architecture decisions; supersede finance-first sequencing.
- **PIV-01:** rights-cleared NL/FR and mixed-language litigation corpus with clean controls, quote/context variants, dates/amounts, aliases, scans, page offsets and gold labels; fixed, versioned competitive task benchmarks against manual Word/PDF, with authorized competitor comparisons only.
- **PIV-02:** authenticated production API, explicit matter access (including same-organization restricted matters if required), scoped jobs and legacy/demo isolation.
- **PIV-03:** reviewed production persistence and source custody: immutable bytes, graph/review/job records, audit, recovery and retention.
- **PIV-04:** provider-independent deterministic intake/index/check jobs; page-level completeness and typed warnings; reconcile all file, job, checkpoint and export budgets; capture dossier dimensions and observed/estimated unit economics.
- **PIV-05:** bounded PDF geometry, OCR and DOCX representations with exact transformation lineage, resource limits and visible failure states.
- **PIV-06:** confirmed exhibit registry with stable IDs, Stuk/Pièce aliases, annexes, page maps, ambiguity and separate communication records.
- **PIV-07:** versioned briefs, assertions and citation graph connecting draft references to resolved exhibits, source versions and locations.
- **PIV-08:** accessible source/reviewer workbench; fix dirty-export, contradiction-filter and save-versus-refresh defects; show partial and failed scope.
- **PIV-09:** deterministic quote, reference, date/amount and citation-format observations. Keep exact fidelity separate from candidate alignment and legal conclusions.
- **PIV-10:** matter-scoped lexical evidence retrieval with measured NL/FR keyword and paraphrase-query performance; evaluate recall/coverage separately from relation correctness. Broader conceptual-search claims require demonstrated retrieval results. Assess optional semantic support separately under PIV-12.
- **PIV-11:** Word add-in citation loop with safe range revalidation, formatting/footnote/tracked-change handling, undo and host capability checks.
- **PIV-12:** separately evaluated optional semantic support/opponent assessment (including Requesty proposals) with counterevidence scope, abstention, model/prompt lineage, evaluation and unknown-outcome recovery. Semantic retrieval, if proposed, requires its own evaluation and decision record. Not a prerequisite for M3.
- **PIV-13:** later evidence-linked timelines, tables, narrative drafting, summaries, question answering and hearing preparation; every material generated statement remains linked or marked unsupported.
- **PIV-14:** versioned DOCX/PDF/report/index/bundle outputs, dynamic exhibits, frozen manifests and reopen/link validation.
- **PIV-15:** published review copy and recipient access, redaction, expiry/revocation and immutable output versions.
- **PIV-16:** authenticated review/release transactions with assignment, return-for-correction, change review, policy-specific solo/independent review, atomic audit and stale-snapshot rejection.
- **PIV-17:** maintained, conditional Belgian court profiles and procedural advisories with court/division/chamber, document type, official authority/passage, publication/effective/verification dates, owner, mandatory-versus-recommended status, scope, expiry and conflict/unavailable behavior. No legal conclusion from missing inventory alone.
- **PIV-18:** technical filing preflight, distinct from procedural readiness, plus receipt capture. Stale/unknown profiles cannot support court-ready claims or national rejection rules. Export is not submission; unknown external outcomes require reconciliation.
- **PIV-19:** one selected document-system connector after customer usage, permissions and API access are verified.
- **PIV-20:** ongoing deployment/operations, onboarding, monitoring, quotas, deletion/retention, backup/recovery, support, cancellation/export, competitive task benchmarks, dossier economics, adoption/repeat-use measurement and release readiness.

## Clearbrief feature dispositions

This inventory records scope decisions for all 42 capabilities in the product research. Disposition describes planned CaseProof scope, not current implementation. “Later” means staged after the core M4 workflow; “unresolved” requires an explicit decision before implementation.

| ID | Capability | CaseProof disposition |
|---|---|---|
| F01 | Word task pane | Launch M3 |
| F02 | Install/signup | Launch M3–M4 |
| F03 | Enterprise deployment | Later M6 |
| F04 | Subscription/seat activation | Launch M4; assisted operations allowed initially |
| F05 | Practice-system PDF import | Later M6; choose one customer-used connector |
| F06 | OCR/searchable scans | Launch M1, bounded and lineage-preserving |
| F07 | Sentence-to-source suggestions | Launch M3 |
| F08 | Insert factual citation | Launch M3 |
| F09 | Factual citation analysis | Launch M2; deterministic first |
| F10 | Legal citation analysis | Unresolved/later; detect and label unchecked, define authority levels separately |
| F11 | Opponent filing review | Launch M2 factual workflow; semantic extensions later |
| F12 | Judicial filing review | Out of scope for initial product |
| F13 | Relevance/support scoring | Launch retrieval ranking; never present as correctness probability; semantic assessment later |
| F14 | Formatting/substance flags | Launch defined citation-style and deterministic checks; semantic flags later |
| F15 | Concept search | Launch evidence retrieval with measured NL/FR keyword and paraphrase-query performance; broader conceptual-search claims depend on demonstrated retrieval results |
| F16 | Timelines | Later M5 |
| F17 | Timeline-to-facts narrative | Later M5, source-linked and editable |
| F18 | Medical timelines | Out of scope for initial product |
| F19 | Timeline theme sorting | Later M5 |
| F20 | Timeline filters | Later M5 |
| F21 | Varied document formats | Launch bounded formats; publish support matrix, extensions later |
| F22 | Large-source timeline processing | Later M5 with measured resource limits |
| F23 | Deposition summaries | Later adapted to witness/expert material; no US-specific parity promise |
| F24 | Summary depth/keywords | Later M5 |
| F25 | Table Builder | Later M5, cell-level evidence links |
| F26 | Ask My Docs | Later M5, scoped/cited answers and abstention |
| F27 | HR investigation reports | Out of scope; distinct from litigation review report |
| F28 | Leadership/legal handoff | Launch litigation reviewer handoff; HR workflow out of scope |
| F29 | Table of Authorities | Later/unresolved; separate from exhibit index |
| F30 | Exhibit generation | Launch M4 |
| F31 | Dynamic exhibits after edits | Launch M4; deletion, reordering and frozen prior exports tested |
| F32 | Hyperlinked briefs/letters/motions | Launch supported brief outputs; other templates separately scoped |
| F33 | Secure courtesy copies | Launch M4 with recipient controls |
| F34 | Interactive examples | Launch synthetic NL/FR demo |
| F35 | Cite Check Report | Launch M2 draft, M4 release; scope/version/dispositions explicit |
| F36 | Opponent PDF-to-Word conversion | Later/unresolved fidelity work; original-PDF review does not depend on conversion |
| F37 | Retrieve uncited counterevidence | Launch scoped search M3; no exhaustive discovery claim |
| F38 | Cross-examination outline | Later M5 as source-linked hearing prep |
| F39 | Generative/non-generative choice | Launch; deterministic workflow works without model credentials |
| F40 | Local citation style/linking | Launch shared versioned profile across Word and outputs |
| F41 | Lexis source access | Unresolved, excluded from launch pending license/territory decision |
| F42 | Fastcase/vLex access | Unresolved, excluded from launch pending license/territory decision |

## Correction and change-propagation contract

Every correction binds to the current brief revision, assertion, editor range/context fingerprint, source representation, check version and actor permissions.

**Inspect → propose → preview → revalidate → apply/undo → invalidate → recheck.** Preview never mutates. Before applying, the client verifies the live range and server checks current source/draft/review versions. Stale selections and coauthor edits produce a conflict, not a blind overwrite. Apply is reversible and acknowledged; unknown acknowledgment is reconciled without duplicate edits. Only dependent checks/reviews/releases/outputs become stale; history and unaffected work remain available. Recheck produces a new recorded result and output version. Opponent originals remain untouched; edits go to an annotation, derivative or separate response draft.

**CP-01 acceptance scenario:** review assertion A against exhibit E version V1 and freeze output O1. Replace E with V2 and edit A while a reviewer has the old packet open; retain unrelated exhibit U as a control. V1/anchors/O1 remain immutable; A's affected checks and review become stale; stale publication is rejected; unaffected U remains valid when out of scope; whole-record search becomes stale if its declared source universe changes. Reviewer sees the conflict. Recheck produces O2; O1 is marked superseded, never overwritten. Restart/lost acknowledgment does not duplicate edits or publication. Revoked access blocks new retrieval and hosted access; prior downloads cannot be remotely recalled.

**DE-01 dynamic exhibits:** define register order versus first-citation order. Test repeated references, citation removal, body/table/footnote references, manually included uncited exhibits, annexes, alias renumbering and oversized single exhibits. Removing a citation never silently deletes manually included material. Word numbering, index, PDF bookmarks and page maps derive from one frozen graph revision. Reopen generated bytes and validate every link; prior exports remain frozen.

## Review, legal scope and release gates

Professional workflow: request review of a named version → assign reviewer or apply the configured solo policy → inspect → return specific issues → correct → inspect changes → release the exact artifact. A solo signoff must be labelled as solo policy, not independent review. Read-only access never grants mutation/publication authority. Reports disclose checked scope, exclusions, failed pages, unresolved items, dispositions, versions and reviewer identity.

Legal-authority work has distinct levels: resolve a statute/decision; compare quotation to an identified version; propose relevance; verify later treatment/current status. The initial factual-evidence product does not promise these automatically. Legal references are marked unchecked when detected. PIV-17/19 must define licensed authoritative sources, jurisdiction, update/version policy, evaluation and professional oversight before expanding the promise. Procedural advisories and an authority list alone do not constitute legal citation verification.

| Use level | Release condition |
|---|---|
| Synthetic development | PIV-00/01 contracts and fixtures; no customer documents; demo is labelled |
| Confidential customer use | Relevant PIV-02–05 identity, matter isolation, private custody, persistent recovery, parser containment, retention/provider policy and PIV-20 evidence |
| Recommendation review | Revision-bound issues, visible scope, history/CAS/idempotency; no implied legal approval |
| Artifact publication | Exact current snapshot; action-specific authorization; atomic audit/receipt; validated links/redaction; recipient policy for hosted share |
| External filing | Separate authorized integration or human handoff; receipt bound to artifact; unknown outcomes reconciled; export never means submitted |

Quality thresholds are provisional until measured on PIV-01. Record denominators; separate reference resolution, retrieval recall, literal false positives, semantic quality, output round-trip integrity, reviewer effort, latency/resource use and permission/recovery failures. A clean case returning zero confirmed findings is a success condition.

## Evidence, maintenance and commercial validation

PIV-00 owns a claims register for material external claims in product, sales and roadmap material. Each entry records the claim, source and exact passage, publication/access dates, evidence type, supported scope, limitations, requirement, owner and status (**pending**, **approved**, **qualified** or **withdrawn**). Material claims may be used externally only when supported by approved entries. Keep withdrawn entries and their rationale as history; do not erase them.

Seed these disputed statements as **pending source review**, not established facts: that the DPA native splitter destroys bookmarks; that Belgium has a universal 200-page filing limit; that existing products lack bundle creation (scope must account for products such as Kleos and e-Deposit); that EU hosting establishes professional-secrecy compliance; and that a reported Nexa firm count means paying active customers. Separate access, registration, training, activity, payment and retention metrics. Reject national inferences from local handling advice and unsupported compliance conclusions unless an approved source supports the exact scope.

### Competitive task benchmark (PIV-01, PIV-20)

Compare against a documented manual Word/PDF baseline using a fixed task protocol and versioned, rights-cleared representative dossiers: Dutch, French and mixed-language; clean controls and known issues; scans and clean PDFs; varied dossier sizes. Tasks cover date and email acceptance, a cited amount with VAT and role basis, reference repair after exhibit replacement, and production of a reviewed linked output. Record correctness of sources and outputs, total elapsed time including setup/review/cleanup, false positives, assistance, errors and breakage. Compare Alice, Nexa and Kleos only with authorized access; mark unavailable or untested products as untested. Never invent benchmark results.

### Maintained court profiles (PIV-17, PIV-18)

Each court profile records court/division/chamber, document type, official source and passage, publication and effective dates, last verification date and owner, whether an item is mandatory or recommended, scope, expiry and conflict/source-unavailable behavior. A stale or unknown profile cannot support a court-ready claim or a national rejection rule. Technical bundle validation is distinct from procedural readiness; neither alone asserts legal compliance. Do not populate a profile with unverified legal requirements.

### Dossier economics and repeat use (PIV-04, PIV-05, PIV-10, PIV-12, PIV-20)

Track dossier size/pages/languages and versioned observed or estimated costs for OCR, indexing, inference, export, storage, delivery, retries and human support; record cache/reuse. Define cost per completed, reviewed dossier as processing + indexing + inference + storage + export/delivery + retries + human support. Keep one-time setup separate from recurring cost. Represent unavailable unit costs as null, not zero, and label estimates as estimates.

Measure first complete task, a second task on an actual matter, repeat use within a defined window, time spent reviewing false warnings and reasons for abandoned tasks. Keep invited/access, registered, trained, active and paying adoption cohorts distinct. Use privacy-safe operational metadata only; do not collect customer document content as telemetry. The release question is whether lawyers complete work more reliably with less total effort than their current workflow and return for another matter. Synthetic development and benchmark work can proceed before release gates; confidential customer benchmarks require the applicable release gates.

## Historical and competing plans

This roadmap supersedes finance-first sequencing in prior roadmap prose, including the old active text formerly in this file. Preserve historical ADRs and code audit records as dated evidence; update their status by reference, never rewrite old verification as current. The former standalone `CaseProof_Belgium_Code_Audit_and_Roadmap.md` is supporting pinned code-audit evidence, not a competing roadmap authority. Companion CORE/LIT/AP packet names map to PIV-00–20 and do not create a second backlog. The separate owner decision already adopted is authoritative: use `domains/disputes/`, sequence PIV-00 → PIV-01 → foundation contracts/intake, and do not revive the withdrawn estimate.

**First build outcome:** one lawyer can import evidence, map exhibits, find and insert source support, check/correct a brief, review the changes and deliver a correctly linked artifact; after evidence or draft changes, the product identifies stale work and safely rechecks it.
