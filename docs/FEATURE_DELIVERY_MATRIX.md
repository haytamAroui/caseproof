# Historical Clearbrief feature crosswalk — F01–F42 (not a v1 product roadmap)

**Scope reconciliation date: 28 October 2026.** The original rows represent a **dated feature comparison**, not customer-accepted functionality. [ADR 0018](adr/0018-pre-submission-verification-freeze.md), [ROADMAP.md](ROADMAP.md) and [PRODUCT_WORKFLOW.md](PRODUCT_WORKFLOW.md) supersede the former Word-first commercial feature plan. Column 3 now maps each feature to the **current v1 applicability or explicit deferral/exclusion**. Remaining evidence/status/acceptance descriptions are historical comparison notes and may mention outdated Word/launch expectations; they do **not** silently reinstate those as acceptance gates.

**Current product:** web-first `DOCX + inventory + preserved exhibits → source/page/fidelity checks → human crop review → reviewed DOCX/report`. No broad Clearbrief parity, legal research, deadlines, automatic Book 8, mandatory Word host or active MCP server. Older source states must be re-audited against exact commits before any implementation claim. **No F01–F42 row implies a sellable or released capability.**

**Authoritative implementation status:** see [STATUS.md](STATUS.md) and the explicit M0–M6 statuses in [ROADMAP.md](ROADMAP.md); the dated matrix does not establish new accomplishments.

## Status vocabulary

- **Not built:** the lawyer-facing capability or entire specified output does not exist; related primitives may exist elsewhere.
- **Reference only:** parsers, fixture UI, data models or adapters exist, but no integrated live/user acceptance.
- **M2 engineering:** deterministic/disposable implementation and recorded CI, not a mounted production/legal customer workflow.
- **Deferred:** expressly staged later than initial M4 release; not a launch blocker unless a paid user's validated task depends on it.
- **Unresolved:** license/rights/quality/market policy must be decided; never implied in sales.
- **Excluded:** an explicit out-of-scope decision, not a dropped undocumented capability.

**Zero** F01–F42 rows are marked **customer accepted**, **launched**, or **commercially proven** as of the pinned audit. No score or percentage of feature completeness may be extrapolated from these categorical states.

## All 42 capabilities: disposition vs observed code vs proof still needed

| ID | Clearbrief reference feature | Current v1 applicability (ADR 0018) | Engineering state (audit) | Evidence / limitation | Required acceptance evidence |
|---|---|---|---|---|---|
| F01 | Word task pane | M6 optional Word; not v1 | **Not built** | No `apps/word_addin/` | Real task pane in a supported Word host; authentication/host matrix |
| F02 | Install/signup | M6 optional Word setup; web sign-in in M1 | **Not built** | No Word install/signup product | Supported user install and first-use setup; denied/expired token |
| F03 | Enterprise deployment | Deferred; firm-controlled deployment only with demand | **Deferred** | Enterprise integration undecided | Enterprise threat model and supported host/deployment matrix |
| F04 | Subscription/seat activation | M5 commercial operations if paid pilot; not v1 technical gate | **Not built** | No commercial seat lifecycle | Assisted/supported activation, consent, billing/cancellation evidence |
| F05 | Practice-system PDF import | M6 connector by paid evidence | **Deferred** | No customer-selected practice-system connector | Rights, API entitlements, tenant-scope source readback |
| F06 | OCR/searchable scans | M1 v1 bounded OCR/crops | **Reference only** | Optional Poppler/Tesseract PDF OCR; synthetic path | Pinned real image-backed NL/FR/EN OCR, page coords and sandbox |
| F07 | Sentence-to-source suggestions | M6 optional Word reference insertion | **Not built** | Evidence search concept/contracts, no Word feature | Select factual text → inspect authorized source → suggest citation |
| F08 | Insert factual citation | M6 optional Word citation edit | **Not built** | No Word insertion/undo | Stable source/version pinpoint inserted and reopened in DOCX |
| F09 | Factual citation analysis | M2 v1 factual reference verification | **M2 engineering** | Merged #71 unified checker; #82–85 disposable persistence | Actual signed-user PDF/DOCX/Word check against private sources |
| F10 | Legal citation analysis | Excluded v1: case-law/authority verification | **Unresolved** | No Belgian legal-authority entitlement | Licensed/versioned case-law validation or explicitly unchecked |
| F11 | Opponent filing review | Deferred: opponent-wide review is not v1 | **M2 engineering** | Opponent typed role and factual-check flow (no full Word review) | Opponent original preserved; permission/scoped report; source-linked findings |
| F12 | Judicial filing review | Excluded v1: judicial filing review | **Excluded** | Judicial-document review not selected for launch | Separate scope, authority and user need before addition |
| F13 | Relevance/support scoring | M2 v1 only deterministic/anchored ranking; no truth score | **Reference only** | Limited retrieval/candidate ranking; not calibrated correctness | Precision, recall and reviewer value; never truth probability |
| F14 | Formatting/substance flags | M2 v1 only exhibit/quote/value checks | **Reference only** | Deterministic literal checks and profiles contemplated | Versioned NL/FR citation styles; formatting vs factual checks distinct |
| F15 | Concept search | M1/M2 v1 bounded source lookup, not open-ended concept research | **Reference only** | Limited matter library/search path; no measured NL/FR/EN quality | Indexed keyword/paraphrase retrieval benchmark with scope gaps |
| F16 | Timelines | Excluded v1: timeline | **Deferred** | No legal timeline product | Source-linked chronology roundtrip, conflicts and date roles |
| F17 | Timeline-to-facts narrative | Excluded v1: generated narratives | **Deferred** | No narrative fact-section product | Sentence-level source links with unsupported-statement marking |
| F18 | Medical timelines | Excluded v1 | **Excluded** | Medical timeline not in Belgian first product scope | Explicit later decision, not inferred from generic timeline |
| F19 | Timeline theme sorting | Excluded v1 | **Deferred** | No chronology/theme controls | Auditable grouping, sorting and edit recovery |
| F20 | Timeline filters | Excluded v1 | **Deferred** | No timeline filters | Language/date/source filter and completeness tests |
| F21 | Varied document formats | M1 v1 DOCX + text PDF + image PDF; limited support matrix | **Reference only** | Bounded PDF/DOCX/MIME parser components | Rights-cleared real file/support matrix, adversarial corruption |
| F22 | Large-source timeline processing | Deferred | **Deferred** | No large-scale timeline workload evidence | Large dossier performance, quotas, time/cost and resume |
| F23 | Deposition summaries | Excluded v1 | **Deferred** | No Belgian witness/expert summaries | Witness/expert provenance and role-specific controls |
| F24 | Summary depth/keywords | Excluded v1 | **Deferred** | No summaries in product UX | Adjustable, source-linked summary with abstention, quality tests |
| F25 | Table Builder | Excluded v1 | **Deferred** | No Table Builder | Cell-level anchors, bounded export and editing |
| F26 | Ask My Docs | Excluded v1: Ask My Docs | **Deferred** | No Ask My Docs interface | Grounded answers, safe abstention and corpus scope |
| F27 | HR investigation reports | Excluded v1 | **Excluded** | HR investigation deliverable outside litigation scope | Only with separate product decision |
| F28 | Leadership/legal handoff | M3 v1 authorized reviewer actions (not leadership reporting) | **Reference only** | Durable synthetic reviewer ledger (#82–85), no legal release | Assigned reviewer action, audit, stale version and handoff UI |
| F29 | Table of Authorities | Excluded v1: Table of Authorities | **Unresolved** | No Belgian Table of Authorities or legal source license | Authority format/source policy and generated TOA byte verification |
| F30 | Exhibit generation | M4 optional index only if pilot requires; not mandatory bundle assembler | **Not built** | Typed exhibit register; no production bundle renderer | Live graph→generated index/bundle and reopened bytes |
| F31 | Dynamic exhibits after edits | M4 dependent link/revision integrity; no mandatory dynamic bundle | **Not built** | DE-01 change contract only; no Word dynamic bundle | Renumber/reorder/retain uncited exhibits across DOCX/PDF |
| F32 | Hyperlinked briefs/letters/motions | M4 v1 safe annotated/corrected DOCX and source links | **Not built** | No Belgian linked filing artifacts | Reopen actual DOCX/PDF and validate every pinpoint and hyperlink |
| F33 | Secure courtesy copies | Deferred external sharing; M4 authorized download only | **Not built** | No secure released courtesy-copy service | Recipient-scoped share, expiry/revoke/redaction audit |
| F34 | Interactive examples | M0/M5 safe synthetic demonstration | **Reference only** | Synthetic NL/FR/EN demos, no lawyer UI onboarding | Repeatable installable user walkthrough and accurate disclaimers |
| F35 | Cite Check Report | M4 v1 report with four-state and coverage manifest | **M2 engineering** | Machine-readable scoped run record; no released legal report | Human-reviewed report + manifest + generated document bytes |
| F36 | Opponent PDF-to-Word conversion | Excluded v1 | **Unresolved** | No high-fidelity opponent PDF→Word converter | Reversible mapping on scanned/rotated/footnote-heavy inputs |
| F37 | Retrieve uncited counterevidence | Excluded v1: opponent-wide uncited discovery | **Not built** | Limited text search; no validated uncited counterevidence | Explicit source universe, separate search vs opponent-wide recall |
| F38 | Cross-examination outline | Excluded v1 | **Deferred** | No cross-examination workflow | Human-controlled source-linked outline and event integrity |
| F39 | Generative/non-generative choice | M1–M4 v1 deterministic core, no model credential | **Reference only** | Deterministic engine, optional Requesty adapter; no choice UI | Matter-specific model consent; no-model complete core journey |
| F40 | Local citation style/linking | M1/M4 v1 stable Stuk/Pièce labels; Word insertion deferred | **Not built** | Typed alias/page representation, no shared Word/export profile | NL/FR Stuk/Pièce generated consistently in Word/PDF/index |
| F41 | Lexis source access | Excluded v1: licensed Lexis data | **Unresolved** | No Lexis licence/integration | Territory, entitlement and independently validated legal sources |
| F42 | Fastcase/vLex access | Excluded v1: licensed case-law source | **Unresolved** | No vLex/Fastcase territory entitlement | Licensed Belgian coverage and testable authority source integrity |

## Current integration gates (supersede historical Clearbrief sequencing)

1. **M0:** one consistent product freeze and rights-cleared synthetic test baseline.
2. **M1:** signed confidential boundary, real DOCX/inventory/text-and-scanned PDFs, original hash/OCR/crops, three independent page spaces and crop coverage.
3. **M2:** all detected factual references resolved in four independent states; no false authoritative source/page/text matches, human-only semantic support, unknown denominators.
4. **M3:** real signed independent browser review/correction with exact source crop, grant/stale/restart/security tests; no Word host.
5. **M4:** actual independently reopened annotated/corrected DOCX, reviewer report/manifest and correct links; authorized download, not court filing.
6. **M5:** five conversations, two observations, controlled dossier pilot if warranted, measured time and priced written commitment.
7. **M6:** only partner-justified Word/MCP/connector work; no v1 blockers.

**Commercial truth:** old features tagged “Not built” remain historical audits. This file does not upgrade any result to live/pilot/released. A green synthetic CI is not customer acceptance.

## Update discipline

- Maintain F01–F42 as **exactly 42 unique historical comparison identifiers** in this matrix. They are not a second feature backlog or required rows in the new ROADMAP. Do not silently remove or add a new Clearbrief feature: propose a new tracked `F43+` only when there is a genuinely distinct capability and an owner decision.
- A row can progress to **integrated staging** only with actual signed users, approved private matter grants and source bytes where applicable; **customer accepted** additionally needs protected operations and a reproducible lawyer task receipt. Link the exact PR, commit, workflow run and fixture/test in the changed row.
- Never mark F35 `released` based on a machine-readable Python JSON run, F31 `complete` based on an exhibit-register data model, F08 `complete` based on a mock Word range, or F39 `complete` based solely on an available LLM API.
- This dated comparison records historical source observations; current acceptance and delivery priority are solely in ROADMAP.md and PRODUCT_WORKFLOW.md. Legacy finance adapters are compatibility code and do not count as completed Belgian legal features.
