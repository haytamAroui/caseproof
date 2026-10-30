# CaseProof — pre-submission Belgian exhibit verification roadmap (M0–M6)

**Decision date:** 28 October 2026. **Status:** authoritative **proposed product/acceptance contract**, not an implementation or customer-readiness claim. **Commercial hypothesis frozen until practitioner evidence** under [ADR 0018](adr/0018-pre-submission-verification-freeze.md). See [the actual lawyer journey](PRODUCT_WORKFLOW.md), [implementation evidence](STATUS.md), [historic F01–F42 comparison ledger](FEATURE_DELIVERY_MATRIX.md), [Word channel acceptance](m3/WORD_INTEGRATION_ACCEPTANCE.md), and [M4 output acceptance](m4/DELIVERY_ACCEPTANCE.md).

**One product, one job:** before a Belgian civil/commercial litigator files conclusions, compare **each detected factual Stuk/Pièce reference** with the supplied inventory, the separately preserved originals and the correct page. Produce an inspectable findings list, source crop when needed, reviewer decisions, a revised/annotated DOCX where supported, and a scope-bound verification run record. **The system locates and matches evidence; it never certifies factual truth, admissibility, court compliance or legal correctness.** Unreadable, unavailable and ambiguous materials stay explicitly unresolved.

**Customer-facing promise:** “Before you file, CaseProof checks exhibit references against your actual bundle and shows exactly which it could not substantiate.” Coverage limits must always accompany this promise; uploading a partial bundle cannot yield a whole-dossier pass.

## Decision lock — how to prevent another pivot

- **First buyer hypothesis:** Belgian civil/commercial litigation firms preparing exhibit-heavy conclusions, initially 50–200-page-scale dossiers as a *research assumption*, not a verified market norm. Practitioner interviews must test volume, review cost, frequency, payor and payment intent.
- **First complete user journey:** authenticated **web** workspace: `DOCX + inventory + separately preserved PDF/scanned pieces → map → check → inspect crop → reviewer disposition → safe DOCX/report export → reopen`. DOCX is an input/output format, not a dependency on the Microsoft Word host.
- **Not v1:** legal research/case-law citators or a legal-authority corpus; legal argument drafting; timelines, summaries, Ask My Docs and opponent-wide counterevidence search; court deadline checking; automated Book 8 sufficiency, legal or admissibility conclusions; e-Deposit/DPA filing; e-CODEX; autonomous external communication; “AI Act certified”; paid data reuse without rights.
- **No platform or interface pivot by competitor announcement:** Word add-in is a **deferred optional client**, never the launch gate. MCP **adapter contract** is first-class (same authenticated API) but a deployed MCP server is not a pilot prerequisite. Do not invent a new rich-text editor or replace the preserved DOCX.
- **Engine first:** web and future Word/MCP clients consume one authenticated application/API contract. The engine runs without Word installed and without an MCP client, model provider, vector DB or autonomous agent.
- **No silent scope growth:** new product families, broader casework, new regions, new data/custody architecture, legal reasoning, publishing or filing require (a) direct practitioner evidence, (b) explicit owner decision, (c) updated ADR and acceptance tests. A missed benchmark means **refine/reconsider**, not automatic pivot.
- **Avoid false first-to-market and competitor-exclusivity claims.** Competitor reviews are evidence for tests, not instructions to change the product.

**Priority rule:** complete the smallest safe **end-to-end web product** and the practitioner experiment. Do not spend effort on additional research modules, a Word-first launch, or multi-sector commercialization while M1–M5 remain open. Existing historical PIV/F and Clearbrief benchmark plans are **reference records, not additional mandatory v1 scope**.

## Non-negotiable verification contract

Every observation belongs to exactly one signed matter and a frozen `draft version + source universe + original hashes + representation versions + inventory revision + rule version + processing coverage`.

| Independent dimension | Allowed finding states | Who may establish it | Forbidden inference |
|---|---|---|---|
| **Exhibit identity** | `RESOLVED`, `NOT_IN_INVENTORY`, `SOURCE_MISSING`, `AMBIGUOUS`, `NOT_ASSESSED` | Deterministic resolver on confirmed register and authorized sources | A unique Stuk/Pièce does **not** imply a mapped page |
| **Page location** | `MAPPED`, `UNMAPPED`, `CONFLICTING` | Versioned mapping of physical PDF, printed and bundle pages | Do not guess missing page numbers or collapse page spaces |
| **Text/value fidelity** | `EXACT_MATCH`, `MISMATCH`, `OCR_UNRELIABLE`, `TRANSLATION_REVIEW_REQUIRED`, `NOT_ASSESSED` | Source-anchored literal/same-role deterministic checks; OCR uncertainty must be surfaced | OCR text is a derived representation; an exact OCR match cannot itself establish original-image truth |
| **Semantic support** | `NOT_ASSESSED`, `CONFIRMED_SUPPORTED`, `CONFIRMED_QUALIFIED`, `CONFIRMED_CONTRADICTED` | **Authorized human**, from original page/crop and contextual evidence | No model or literal matcher self-promotes to confirmed factual support |

Keep `communication_proven`, `filing_proven`, `source_in_custody`, `listed_in_inventory`, `reviewer_approved` and `exported` separately. A hash proves byte consistency, not originality/authenticity. No green global “verified” badge. A clean fully assessed scope may have zero findings; an unprocessed page never becomes a clean finding.

**Coverage:** enumerate mandatory DOCX stories/regions and per-region status, including main-body paragraphs, nested tables, footnotes/endnotes, headers/footers, text boxes, revisions and exclusions; show `regions_discovered / scanned / unprocessed / unsupported`, `references_detected / checked / not_assessed`, sources inventoried/preserved, image/text page denominators, missing pages, parser/OCR errors, and unsupported citations. A reference extractor cannot claim “every reference” unless detection coverage has been measured and explicit omissions are shown. Search/recognition proposals are never evidence anchors without source resolution.

**Change:** a corrected draft, changed evidence version, re-ordered inventory, altered page map, revoked actor, changed processing version or changed checked scope invalidates dependent observations/approvals. Corrections create revision lineage; originals and prior exports remain immutable. Review and output decisions revalidate exact inputs; failures and unknown acknowledgements fail closed. Human review is not legal certification.

## Architecture and trust boundaries

- **Kernel:** `packages/evidence_kernel/` stays sector-neutral; immutable evidence identity, anchors, fidelity, explicit coverage and provenance only. No OCR/LLM, authentication, Belgian procedure or infrastructure imports.
- **Domain:** Belgian reference/inventory/page rules go only in `domains/disputes/`; use `application/litigation/` for use cases, existing application ports for signed authorization/review/recovery, `infrastructure/` for parsers/OCR/storage/rendering.
- **Clients:** `apps/web/` is v1 UI; existing `apps/word_addin/` is retained as **optional integration engineering**, not a prerequisite. Both use the same API; no trusted Word editor offset masquerades as an immutable source anchor. Design MCP schemas to map onto these ports; do not require MCP to be running.
- **Custody ≠ processing ≠ provenance:** keep separate ports for original storage, processing location/provider, and evidence/reviewer audit records. Firm-controlled/offline deployment is a research option, **not built or approved**; Supabase dev success does not make customer-confidential processing safe.
- **No mandatory model:** default deterministic; optional model/OCR outputs are untrusted candidates with explicit model/parser/version lineage, human confirmation and permission gating. No confidential uploads to a remote LLM absent independently reviewed safeguards and explicit authorization.
- **Actions:** server-verified signed users, matter grants, least privilege, current-source authorization, idempotency, append-only audit and revocation; preserve installed grants as source of truth. Review ≠ edit ≠ export ≠ share ≠ file. The product never files to a court.
- **Rights/regulation:** professional secrecy/GDPR/security review before live client material. EU AI Act classification is intended-use-specific, not exempt merely because the system is deterministic. Under Regulation (EU) 2026/1744, applicable Annex III high-risk obligations are scheduled **2 December 2027**, not 2 August 2026; applicable transparency obligations must be examined separately. Do not use bBSARD/bLLeQA CC BY-NC-SA datasets commercially without lawful rights. References: [AI amendment](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32026R1744), [Belgian Judicial Code](https://refli.be/fr/lex/1967101055), [OVB guidance](https://www.ordevanvlaamsebalies.be/nl/kennisbank/digitalisering/richtlijnen-voor-advocaten-rond-gebruik-van-artificiele-intelligentie).

## Gates: do not confuse design, code, live development, pilot or release

| Gate | Meaning | Evidence required |
|---|---|---|
| **Designed** | Contract, ADR or issue exists | Approved scope/acceptance, not software |
| **Implemented** | Code merged with CI | Exact SHA, affected tests and limitations |
| **Live development accepted** | Real signed staging journey passed | URLs/runs, genuine Auth/RLS/Storage, restart, negative access and cleanup |
| **Pilot authorized** | Permitted source corpus and confidentiality controls | Security/privacy/bar review where applicable, consent, rights, retention and operator procedures |
| **Commercially validated** | Firms use and are willing to pay | Measured repeatable task results and signed paid/conditional commitment |
| **Released** | Supported customer service | Security, recovery, support, billing, tested artifact correctness and release authority |

**Current verified engineering baseline (28 October 2026; not a release):** protected signed **synthetic TXT** private-matter creation, immutable upload/readback and versioned reviewer correction/recheck/restart passed in [PRs #114–119](https://github.com/haytamAroui/caseproof/pull/119) and [live run #40679567871](https://github.com/haytamAroui/caseproof/actions/runs/40679567871). This does **not** close full PDF/DOCX/scan intake, OCR/crop confirmation, all-reference extraction, identity/pinpoint split, end-to-end web reviewer/export, customer confidentiality or Word host. [Technical receipts](m2/LIVE_SIGNED_CORRECTION_RECHECK_2026-10-28.md) remain the authority for the precise narrow pass. Some earlier narrative status lines are historical; never infer a capability from an older pass.

## M0 — Freeze scope, rights and evaluation baseline

**Outcome:** no two authoritative documents can send agents in opposite product directions.

- **Build/decide:** ADR 0018 records this commercial supersession without changing constitutional/kernel/security boundaries. Align README, AGENTS, roadmap, workflow and feature ledger; identify the explicit v1/non-v1 boundaries, user/buyer and original law sources. Version a rights-cleared NL/FR/mixed **synthetic first** corpus with clean controls, scans, split/duplicate labels, wrong printed/PDF/bundle page, missing piece, contradictory amount, qualifier/negation, OCR ambiguity and unsupported file conditions. State fixture license and no customer data in CI.
- **Contracts:** 4-dimension states; `ReferenceObservation` with source hashes, original page/crop locator, document role, reference detection origin, processing coverage, inventory revision and reviewer decision identity. Source-original hash is separate from parser/representation hash and from DOCX revision fingerprint.
- **Exit:** one reviewed source-of-truth for scope, technical and commercial acceptance; no stale Word-mandatory or finance-first instruction in active documents. The evaluation fixtures are independently checked, include zero-error cases and explicitly mark which tests are synthetic.
- **Not exit:** a draft dataset alone does not demonstrate quality, paid demand or permission to upload legal customer documents.
- **Proof:** scope ADR, changed-file map, linked docs, static consistency checks; all source rights recorded.
- **Status:** documentation alignment proposed here; **validation not yet proven**.

## M1 — Secure matter intake, sources, inventories and scanned pages

**Outcome:** a lawyer can securely supply the *three distinct inputs*: conclusions DOCX, inventory and individual exhibits/bundle scans.

- **Build:** signed private matter and per-matter actions; immutable original byte upload/readback with SHA-256; bounded parser for DOCX and text PDF; **self-hosted OCR in an isolated approved CaseProof processing worker, with no default external OCR API or unauthorized egress** (target design; not currently implemented); safe image-backed PDF OCR with explicit `needs_ocr`, low-confidence and failed-page states; crop coordinates/preview of original image; parsed representation provenance; visible per-page coverage and restart/idempotent worker recovery.
- **Inventory:** extract a *candidate* Stuk/Pièce inventory, bind it only after human confirmation; **no inventory, incomplete/unconfirmed/unparseable inventory → identity `NOT_ASSESSED` with reason**; `NOT_IN_INVENTORY` requires a reviewer-confirmed complete scoped inventory and an absent entry. Stable `exhibit_id` separate from displayed label/aliases; distinguish missing inventory listing, absent original, multiple aliases, separate communication and filing status. Reconcile `pdf_page`, `printed_page`, `bundle_page` with evidence, do not fabricate DOCX physical page numbers.
- **Security:** pilot processing must satisfy the independently signed-off [SEC-01–16 security appendix](security/PILOT_DATA_SECURITY_GATE.md); the checks below are engineering prerequisites rather than live-client approval. Malicious/oversized/corrupt files, decompression bombs, OCR failure, PDF rotation/crop, unsupported format, missing text layer, duplicate originals, cross-matter/cross-tenant and revoked permissions fail safely; enforce budgets and audit. Service-only promotion cannot be self-certified by user.
- **Exit:** real signed staging matter with an authorized synthetic NL/FR sample DOCX + inventory + text PDF + **image-only scan**, preserved originals and reopenable page crops/mappings after process restart; ungranted and revoked access denied; zero false fully-processed flags on an incomplete sample; independent security review for any non-synthetic pilot.
- **Proof:** parser/geometry/crop fixture matrix, signed RLS/Storage results, SHA readbacks, negative/security cases, restart proof. M1-A contracts, M1-B integrated backend and M1-C confidentiality/release approval remain separately tracked.
- **Status:** narrow TXT live path **passed**; full M1 **OPEN**.

## M2 — Whole-draft reference resolution and deterministic evidence checks

**Outcome:** one bounded run inspects **all detected exhibit references** in the supplied draft and says precisely what is located, matched, mismatched or not assessable.

- **Build:** enumerate the explicit DOCX coverage matrix in [pre-M3 contract](contracts/PRE_M3_VERIFICATION_SPEC.md), scan mandatory supported main-body/table/footnote/endnote regions, enumerate header/footer/textbox/revision/excluded regions, and report unsupported parts; parse DOCX references with declared constraints; identify Stuk/Pièce labels/aliases; separately resolve identity and pinpoint (fix existing `ExhibitRegister.resolve()` ambiguity); freeze source/inventory/brief versions; check original page boundaries and exact quotations; compare matched-role amounts/dates/currencies/units (e.g., payment amount to payment amount, not net to gross).
- **Cross-language quotations:** French assertions of Dutch originals (and vice versa) use `TRANSLATION_REVIEW_REQUIRED` unless the original literal text is actually matched; preserve both languages; translation never implies `EXACT_MATCH` or human semantic confirmation. If the original is also unreadable, preserve both OCR and translation review requirements. **Same-role numeric/date normalization must be versioned and fail closed on ambiguous separators, roles and formats** (pre-M5 contract below).
- **OCR boundary:** every uncertainty flows to `OCR_UNRELIABLE` and original-image crop; do not assert `EXACT_MATCH` against an unreviewed low-quality scan. The model cannot confirm `SUPPORTED`, `QUALIFIED` or `CONTRADICTED`. No auto “verified”, no AI confidence presented as truth probability.
- **Coverage:** include zero-quote drafts, quote-heavy, good clean controls, French/Dutch mixed text, contradictory numerals, missing pieces, re-numbered inventory, duplicate citations, unreadable page, empty/no-citation briefs and scoped partial results. Detect and disclose missed-reference limitations, with seeded detection-recall checks.
- **Exit:** real signed staging unified run on the frozen multi-source M1 fixture with per-reference typed outputs and exact crop/source links; re-run determinism, no false location or exact-match on the acceptance corpus, all seeded critical errors found **or marked unresolved**, and unknown scope never reported as fully checked. Do not claim a population zero-error rate.
- **Proof:** pinned results and tests with denominators (`0/N` false matches, not “zero risk”), source/representation/engine versions, checker coverage, changed-revision invalidation and authorized actor audit.
- **Status:** synthetic TXT literal and correction components exist; full M2 **OPEN**.

## Pre-M3 hard prerequisites — explicit contract closure

**M1/M2 engineering can proceed. M3 product-shaped implementation is blocked until four M1/M2 contracts are reviewed and their fixtures/schema accepted.** Do not ask the M3 UI to invent missing states or presentation defaults. Full decisions, test cases and exact status are in [PRE_M3_VERIFICATION_SPEC.md](contracts/PRE_M3_VERIFICATION_SPEC.md).

| Gate | Fixed decision | Proof required before M3 implementation |
|---|---|---|
| **P3-01 Translated claim** | Fidelity adds `TRANSLATION_REVIEW_REQUIRED`; original-language source plus draft-language assertion, human semantic confirmation only | Typed state fixture for FR↔NL translated quote, negation, qualifier and simultaneous OCR uncertainty |
| **P3-02 OCR boundary** | Default self-hosted isolated CaseProof worker in an approved controlled processing environment; **no unapproved third-party OCR egress** | Named runtime/provider/region, data-flow/egress and temp-file test, source/crop lineage, security review |
| **P3-03 DOCX coverage** | Declare and enumerate paragraphs, nested tables, footnotes/endnotes, headers/footers, textboxes/embedded content and tracked revisions; report per-region processed/unprocessed/unsupported denominators | Valid OpenXML fixture and region-by-region count validation, explicit partial-scope UI contract |
| **P3-04 Inventory absence** | Identity adds `NOT_ASSESSED` with missing/unparseable/unconfirmed/incomplete reason. `NOT_IN_INVENTORY` only under a confirmed complete inventory | Absent vs truly missing vs unconfirmed vs missing source vs unique exhibit/unmapped page fixtures |

**Gate status:** these rules are **specified in documentation**, not implemented or independently signed off. Record the exact tests/commit, reviewers and state-schema compatibility before moving M3 to implementation. Synthetic independent UI mockups do not close the gate.

## M3 — Independent web verification and human review (v1 client)

**Outcome:** a lawyer completes the inspect/review/correction journey **without Word installed**.

- **Build:** accessible signed web workspace: upload state, inventory mapping preview/confirmation, list of each detected citation and four distinct statuses; side-by-side assertion + source PDF page/image crop + original context; explicit OCR uncertainty and processing exclusions; human confirm/dismiss/qualify/needs-more-evidence with rationale; version-bound correction preview or annotated DOCX plan; save/reopen after logout or service restart.
- **API:** require the four pre-M3 contracts and signed-off M1/M2 fixtures before product-shaped implementation; all actions through one authenticated, case-scoped application API with typed requests, stable operation IDs, audit, permissions and stale-revision rejection. MCP may later adapt these same ports; **no running MCP server or Word host in the critical path**.
- **Exit:** supported browser end-to-end with a real signed user, synthetic NL/FR dossier, at least one correct, missing, conflicting and unreadable item; safe human disposition and proposed correction; refresh/restart and grants revoked tests; keyboard and screen-reader essentials. Never modify original opponent or source bytes.
- **Proof:** captured browser E2E, persisted review IDs, scope snapshots, denial tests, undo/no-duplicate/lost-ack scenarios and independent data-layer checks.
- **Status:** early web components exist, but full M3 **OPEN**. **Word channel is not M3.** [Word contract](m3/WORD_INTEGRATION_ACCEPTANCE.md) is deferred integration evidence.

## M4 — Reviewed document, provenance report and safe export

**Outcome:** the lawyer gets an artifact usable in their existing workflow, with findings and unresolved items traceable to the frozen source versions.

- **Build:** exact draft version and selected human corrections → non-destructive annotated or corrected DOCX as supported; verification run record in machine-readable and human-readable formats with checked/unprocessed counts, hashes, identity/pinpoint/OCR states, reviewer decisions, times and limitations; page/crop/source hyperlinks; optional derived exhibit index/linked bundle **only if required for validated v1 task**, not a new assembly product.
- **Safety:** hold original unchanged, preserve revision/formatting/footnotes/tables/tracked changes where supported; fail clearly on unsupported structures rather than silently flattening. Freeze manifest once, render outputs from it, reopen actual DOCX/PDF bytes and independently test links/page targets. Final report never says court-filed, legally valid or all claims true.
- **Authority:** reviewer decision, draft edit, export, external share and filing are distinct; only authorized export is in v1. Recipient sharing is an additional separate permission and acceptance, **not required** for the first paid pilot. Court submission remains human/manual and outside CaseProof.
- **Exit:** authenticated web M1→M4 signed end-to-end on real-format synthetic originals; corrected/annotated output and report downloaded and reopened, mapped links actually land on intended preserved pages, changed original/inventory/draft makes stale release impossible, restart and revoked grants denied.
- **Proof:** released artifact hashes and reopen validation, immutable manifest, human reviewer receipt, link-target test, scope denominator, negative/security and interrupted-render recovery tests.
- **Status:** full M4 **OPEN**. [Delivery contract](m4/DELIVERY_ACCEPTANCE.md).

## M5 — Five-week practitioner experiment and conditional commercial pilot

**Outcome:** evidence of whether this specific problem is worth paying for; **not** general Belgian legal-AI market validation. Run discovery in parallel with M1–M4.

- **Before M5 closure:** P5-01..04 in [pre-M5 hard prerequisites](#pre-m5-hard-prerequisites--the-commercial-experiment-must-have-an-exit) are binding; neither a paid letter nor an accurate synthetic demo substitutes for security and representative cohort evidence.
- **Clock starts with the first practitioner conversation**, not this roadmap update. Within five weeks record (1) five disconfirming practitioner interviews; (2) observation of two actual workflows; (3) 3–5 controlled NL/FR dossier tests **only if early evidence justifies them**; (4) one concrete priced scope and signed paid/conditional commitment request. Do not invent a calendar deadline before the start date.
- **Questions:** last material wrong exhibit reference, frequency, severity and cost; who checks, baseline minutes and rework; scanning/page problems; existing tools including Copilot/Hublex; actual purchasing authority, budget, acceptable deployment and review-record needs. Capture rejection and negative evidence, not just testimonials.
- **Quality gates for trial:** `0/N` confidently incorrect mapped/exact matches in measured cohort (a failure triggers RCA and regression; not proof of zero real-world risk); all seeded critical mismatches detected or unresolved; every displayed `MAPPED` actually correct; demonstrable end-to-end total time saving vs manual (20% is a **test target**, not a promise); false-alert review time reported; lawyer-approved report format and safe trust calibration, **not blind cessation of rechecking**.
- **Commercial gate:** at least one written priced paid/conditional commitment with price and conditions recorded; one free reference partner alone is insufficient. Track per-dossier cost/margins and second-use interest. **Proceed** only if repeat pain + technical success + purchase signal; **refine** if problem exists but workflow/security/pricing fails; **reconsider niche** if no credible pain or paid demand. One failure of this niche does not invalidate the kernel.
- **Consent and pilot authorization:** only synthetic or genuinely rights-cleared material until all [SEC-01–16 pilot controls](security/PILOT_DATA_SECURITY_GATE.md) have dated evidence and appropriate professional-secrecy/GDPR/security and firm approval for the exact client environment. A paid commitment alone does not authorize client-source upload.
- **Status:** not run; no paying customer or commercial moat is claimed.

## Pre-M5 hard prerequisites — the commercial experiment must have an exit

**Interviews/observations may start now using appropriate non-confidential methods; before a controlled dossier benchmark is locked, specify P5-02/P5-03, and before any confidential material is processed satisfy P5-04. M5 CANNOT CLOSE without all four P5-01..04 below.** These are acceptance contracts, not new market hypotheses.

### P5-01 — Exact meaning of PROCEED / REFINE / RECONSIDER

- **PROCEED authorizes only the next decision packet:** a **restricted paid design-partner beta proposal** for the validated pre-submission job, with bounded firm/count, price, data class, supported formats/page limits, service levels, support owner, retention period, evaluation plan, controlled deployment cost and signed terms. **It does not authorize public launch, production deployment, broad sales, adding M6, live client uploads, fundraising claims or hiring.** Customer data needs separate SEC-01..16 + operations/rights signoff; releasing the beta needs a separate owner approval with the exact tested version.
- **REFINE:** record the failing metric (time, errors, usability, deployment/privacy, pricing), the minimal M1–M4 repair/contract change, its owner, cost and rerun plan; no new product category or independent roadmap.
- **RECONSIDER:** record the disconfirming evidence, stop new spend on this niche and request a separate owner commercial decision. The evidence kernel remains neutral; no automatic pivot to another vertical.
- **All:** dated, written owner decision with commitments/price and actual denominators; a “positive interest” meeting is not a release gate.

### P5-02 — Locale-aware, same-role money/date normalization

- Preserve **raw source and draft strings**, language/declared locale, extraction coordinates, currency and explicit factual role; derive a versioned canonical value using **Decimal**, not floats. Amount comparisons require exact currency (no implicit FX), unit, tax/VAT basis, and same business/legal role (e.g. payment gross↔payment gross; not claim↔interest, tax base↔total).
- Examples **may** normalize `12 500 EUR`, `12.500,00 €` and `12 500,00 EUR` to `12500.00 EUR` **only when source locale, grouping and separators are established**. The isolated form `€12,500` is ambiguous across locale conventions: **never automatically equate it with 12,500 EUR**; return `NOT_ASSESSED(AMBIGUOUS_NUMBER_FORMAT)` pending contextual/human clarification.
- Dates use a declared **day/month/year** parser for Belgian-locale sources with named months in NL/FR/EN and valid calendar normalization (`14 maart 2026`, `14 mars 2026`, `14/03/2026` → `2026-03-14`). Ambiguous `03/04/2026` without a trusted date convention and other unsupported formats → `NOT_ASSESSED(AMBIGUOUS_DATE_FORMAT)`. Preserve source-local calendar date, do not convert legal dates with implicit timezone shifts.
- The full comparison records `raw_value + normalized_value + locale/rule version + source anchor + comparison role`. Normalization cannot produce semantic `CONFIRMED_*`, source authenticity or a quote-fidelity exact match. Tests must include equivalent formats, wrong role, opposite currency, negative amount, invalid date and ambiguity abstention.

### P5-03 — Fixed dossier scale

- Interviews first determine **real firm size distribution**; 50–200 pages remains an unverified buyer assumption. Before benchmarking, record source-file counts, total source pages and OCR-only pages, number of draft references, document complexity, measured baseline and how each dossier reflects observed work.
- Controlled 3–5 dossiers must include **at least one representative 50–100-page bundle and one 150–200-page bundle if that scale is confirmed in observations**, plus a smaller clean control. Include NL, FR, mixed citations, image-only and text PDFs, inconsistent three-space pagination and seeded critical faults. If lawyers' actual workloads differ, document the revised observed ranges and obtain explicit benchmark-protocol approval **before** testing rather than quietly testing 5-page toy examples.
- Measure total `upload + OCR + inventory confirmation + review + edits + export + setup/retry` time and cost on the same machine/service budget. Record `0/N` false confidently mapped/matched *over actual evaluated references*, recall/unknown, reviewer interventions and timing per dossier/size group. Three small files alone cannot validate a 200-page workflow.

### P5-04 — Pilot security appendix

The [SEC-01–SEC-16 checklist](security/PILOT_DATA_SECURITY_GATE.md) is **OPEN** until evidenced, risk-reviewed and explicitly approved for a concrete environment and data class: threat model, TLS, at-rest/key custody, signed Auth/matter isolation, tamper-evident original/audit, OCR subprocessors and egress, redacted telemetry, retention/deletion/backups, data flows/DPA/transfers, lawful basis and professional secrecy, parser/worker isolation, independent risk-appropriate penetration/security test, incident response, recovery, approval/release control and support runbook. Any missing approval blocks confidential client data; synthetic/appropriately rights-cleared nonconfidential development is separate.

**M5 exit evidence:** signed recorded P5-01 decision, P5-02 normalized/ambiguous fixtures and benchmark, P5-03 actual page/processing distribution and representative tested cohort, P5-04 gate status with no client-source use outside approved scope. “M5 passed” means the commercial experiment reached a decision; it does **not** mean CaseProof is released.

## M6 — Optional channels and expansions (not v1 or pilot blockers)

**Trigger:** after M5 evidence and explicit owner decision for each channel, not after a competitor announcement.

- **Word add-in:** `apps/word_addin/` remains as reusable early spike; enable a real Word client only if a practitioner task demonstrates net value. Word select/inspect/insert/save/undo/reopen has its own supported-host acceptance, but never owns verification truth.
- **MCP server:** design secure tool schemas from shared ports, and add a deployed adapter only for a validated channel need; client cannot provide authoritative tenant, review or evidence claims.
- **Other systems:** a selected document-management connector, optional firm-controlled deployment or approved processing mode only with actual partner need, review of entitlements/security and measured cost.
- **Future legal intelligence:** Book 8 lawyer-guided review, legal-authority retrieval, deadline/court profiles, cross-border provenance, deeper semantic research, opponent review, or new sectors **require a separate approved hypothesis and rights/legal review**. No silent expansion. Dataset licenses and AI Act applicability assessed at that decision.
- **Status:** deferred; **no M6 capability is a v1 acceptance dependency**.

## Delivery order, ownership and scope change control

- **Parallel tracks:** M0 scope/doc freeze; M1 source intake; M2 pure checks against fixtures; M3 web UI against shared API; M4 export against frozen manifests; M5 practitioner interviews. M2 engineering and non-production UI prototypes may use contract-tested stubs during M1; **product-shaped M3 implementation requires the four P3 acceptance contracts to be implemented and reviewed first**, and nothing becomes accepted until the real signed M1→M4 path passes.
- **Technical dependencies:** M1 source identity/page coverage → M2 check; M1/M2 authenticated API → M3 reviewer; M3 human disposition + immutable manifest → M4 output. Pilot-safe materials and permissions precede real-client tests. M5 interview work does not depend on completed software.
- **Acceptance owners:** engineering supplies SHA, tests and actual output proof; security reviewer approves data boundaries; practicing lawyers evaluate task and report; commercial owner records price/commitments. Owner approval of scope ≠ legal/security approval.
- **Milestone evidence format:** `scope; fixed fixture/corpus and rights; exact build SHA; live vs synthetic; tested clients; positive/negative outcomes; partial coverage; remaining blockers; user task outcome; reviewer; linked run/artifacts`. A mock, JSON-only pass, CI-green or launched site cannot close a real-user gate.
- **Change protocol:** record proposed scope change, practitioner evidence, trade-offs, affected M criteria, owner decision and superseding ADR; revise this roadmap and workflow in one PR with consistency checks and exact CI. Keep historic records intact in Git, labelled historical, not authoritative current requirements.

## Historical material — retained as evidence, not alternative delivery plans

- [ADR 0011](adr/0011-architecture-freeze-and-first-finance-slice.md) remains binding architecture, not finance-first commercial order.
- [ADR 0016](adr/0016-belgian-litigation-product-pivot.md) records the previous Clearbrief-class Word-first commercial plan; **ADR 0018 supersedes only that commercial scope and channel gate**, not kernel/security architecture.
- [ADR 0017](adr/0017-default-private-litigation-matters.md) remains applicable to matter confidentiality and grants.
- [F01–F42 matrix](FEATURE_DELIVERY_MATRIX.md), [M0 baseline](m0/BASELINE.md), [PIV issue history](https://github.com/haytamAroui/caseproof/issues), [earlier roadmap at main@486b239](https://github.com/haytamAroui/caseproof/blob/486b239926b681d76e1e3f79d30e3dc7098ab6d8/docs/ROADMAP.md), and [prior workflow](https://github.com/haytamAroui/caseproof/blob/486b239926b681d76e1e3f79d30e3dc7098ab6d8/docs/PRODUCT_WORKFLOW.md) remain inspectable. Historic PIV-00–20 work is retained as compatibility/technical backlog, not automatic v1 authorization.


## M0 — reusable synthetic fixture factory (engineering standard, 30 October 2026)

- **Source of truth:** `tests/fixtures/factory.py` generates synthetic DOCX, TXT inventory, text PDF, and image-only scanned PDF; `tests/test_fixture_factory.py` validates signed registration, SHA-256 binding and fail-closed upload behavior.
- **Provisioning:** `python -m scripts.manage_fixtures create-bundle` uses a signed owner JWT, existing organization grant, CaseProof's authenticated matter API, private Storage upload endpoint and protected bundle-registration RPC. It never directly inserts into application tables or bypasses RLS with a service key.
- **Auth:** `create-users` delegates to the existing protected GoTrue fixture provisioner; no fixed credentials should be embedded in new fixtures. CI development secrets are environment-scoped and never exposed to forked PRs.
- **Lifecycle:** disposable runs need explicit run ownership and a dedicated scoped teardown before automated deletion is enabled. The CLI deliberately rejects `delete-all` rather than risk destroying persistent Phase 3 acceptance evidence.
- **Acceptance:** protected Phase 3 workflow regenerates the synthetic bundle and executes the signed nine-step OCR/crop round-trip; offline tests run first. The persistent acceptance run is **not** a disposable isolated run. Future milestones must introduce separate run-scoped cleanup with auditable ownership and no cross-run deletion.
- **Status:** factory implementation and workflow wiring are engineering work; no claim of all-CI-green or complete zero-manual Auth lifecycle until a run on the committed revision passes.
