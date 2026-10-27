# Clearbrief-to-Belgium feature delivery matrix (F01–F42)

**Audit date:** 27 October 2026; **observed repository:** `main@eb289e867c18c8c1cf8b645a809ce56dd7f5bc61`. This is **not another roadmap**: IDs and intended dispositions are reproduced directly from the authoritative [ROADMAP.md](ROADMAP.md) and must stay aligned with it. A feature being planned for launch does not mean it exists; even a working synthetic feature is not a usable law-office product. Re-audit against current code and test receipts before changing the implementation column.

**North star:** Clearbrief-class **end-to-end Word → evidence → check/review → dynamic exhibit → linked outputs** for Belgian lawyers, with NL/FR/EN and Stuk/Pièce localization. A standalone M2 checker is a **technical validation slice**, not commercial completion. We do **not** assert feature parity with US legal research databases or professional legal validation.

## Status vocabulary

- **Not built:** the lawyer-facing capability or entire specified output does not exist; related primitives may exist elsewhere.
- **Reference only:** parsers, fixture UI, data models or adapters exist, but no integrated live/user acceptance.
- **M2 engineering:** deterministic/disposable implementation and recorded CI, not a mounted production/legal customer workflow.
- **Deferred:** expressly staged later than initial M4 release; not a launch blocker unless a paid user's validated task depends on it.
- **Unresolved:** license/rights/quality/market policy must be decided; never implied in sales.
- **Excluded:** an explicit out-of-scope decision, not a dropped undocumented capability.

**Zero** F01–F42 rows are marked **customer accepted**, **launched**, or **commercially proven** as of the pinned audit. No score or percentage of feature completeness may be extrapolated from these categorical states.

## All 42 capabilities: disposition vs observed code vs proof still needed

| ID | Clearbrief reference feature | Planned CaseProof disposition | Engineering state (audit) | Evidence / limitation | Required acceptance evidence |
|---|---|---|---|---|---|
| F01 | Word task pane | Launch M3 | **Not built** | No `apps/word_addin/` | Real task pane in a supported Word host; authentication/host matrix |
| F02 | Install/signup | Launch M3–M4 | **Not built** | No Word install/signup product | Supported user install and first-use setup; denied/expired token |
| F03 | Enterprise deployment | Later M6 | **Deferred** | Enterprise integration undecided | Enterprise threat model and supported host/deployment matrix |
| F04 | Subscription/seat activation | Launch M4; assisted operations allowed initially | **Not built** | No commercial seat lifecycle | Assisted/supported activation, consent, billing/cancellation evidence |
| F05 | Practice-system PDF import | Later M6; choose one customer-used connector | **Deferred** | No customer-selected practice-system connector | Rights, API entitlements, tenant-scope source readback |
| F06 | OCR/searchable scans | Launch M1, bounded and lineage-preserving | **Reference only** | Optional Poppler/Tesseract PDF OCR; synthetic path | Pinned real image-backed NL/FR/EN OCR, page coords and sandbox |
| F07 | Sentence-to-source suggestions | Launch M3 | **Not built** | Evidence search concept/contracts, no Word feature | Select factual text → inspect authorized source → suggest citation |
| F08 | Insert factual citation | Launch M3 | **Not built** | No Word insertion/undo | Stable source/version pinpoint inserted and reopened in DOCX |
| F09 | Factual citation analysis | Launch M2; deterministic first | **M2 engineering** | Merged #71 unified checker; #82–85 disposable persistence | Actual signed-user PDF/DOCX/Word check against private sources |
| F10 | Legal citation analysis | Unresolved/later; detect and label unchecked, define authority levels separately | **Unresolved** | No Belgian legal-authority entitlement | Licensed/versioned case-law validation or explicitly unchecked |
| F11 | Opponent filing review | Launch M2 factual workflow; semantic extensions later | **M2 engineering** | Opponent typed role and factual-check flow (no full Word review) | Opponent original preserved; permission/scoped report; source-linked findings |
| F12 | Judicial filing review | Out of scope for initial product | **Excluded** | Judicial-document review not selected for launch | Separate scope, authority and user need before addition |
| F13 | Relevance/support scoring | Launch retrieval ranking; never present as correctness probability; semantic assessment later | **Reference only** | Limited retrieval/candidate ranking; not calibrated correctness | Precision, recall and reviewer value; never truth probability |
| F14 | Formatting/substance flags | Launch defined citation-style and deterministic checks; semantic flags later | **Reference only** | Deterministic literal checks and profiles contemplated | Versioned NL/FR citation styles; formatting vs factual checks distinct |
| F15 | Concept search | Launch evidence retrieval with measured NL/FR keyword and paraphrase-query performance; broader conceptual-search claims depend on demonstrated retrieval results | **Reference only** | Limited matter library/search path; no measured NL/FR/EN quality | Indexed keyword/paraphrase retrieval benchmark with scope gaps |
| F16 | Timelines | Later M5 | **Deferred** | No legal timeline product | Source-linked chronology roundtrip, conflicts and date roles |
| F17 | Timeline-to-facts narrative | Later M5, source-linked and editable | **Deferred** | No narrative fact-section product | Sentence-level source links with unsupported-statement marking |
| F18 | Medical timelines | Out of scope for initial product | **Excluded** | Medical timeline not in Belgian first product scope | Explicit later decision, not inferred from generic timeline |
| F19 | Timeline theme sorting | Later M5 | **Deferred** | No chronology/theme controls | Auditable grouping, sorting and edit recovery |
| F20 | Timeline filters | Later M5 | **Deferred** | No timeline filters | Language/date/source filter and completeness tests |
| F21 | Varied document formats | Launch bounded formats; publish support matrix, extensions later | **Reference only** | Bounded PDF/DOCX/MIME parser components | Rights-cleared real file/support matrix, adversarial corruption |
| F22 | Large-source timeline processing | Later M5 with measured resource limits | **Deferred** | No large-scale timeline workload evidence | Large dossier performance, quotas, time/cost and resume |
| F23 | Deposition summaries | Later adapted to witness/expert material; no US-specific parity promise | **Deferred** | No Belgian witness/expert summaries | Witness/expert provenance and role-specific controls |
| F24 | Summary depth/keywords | Later M5 | **Deferred** | No summaries in product UX | Adjustable, source-linked summary with abstention, quality tests |
| F25 | Table Builder | Later M5, cell-level evidence links | **Deferred** | No Table Builder | Cell-level anchors, bounded export and editing |
| F26 | Ask My Docs | Later M5, scoped/cited answers and abstention | **Deferred** | No Ask My Docs interface | Grounded answers, safe abstention and corpus scope |
| F27 | HR investigation reports | Out of scope; distinct from litigation review report | **Excluded** | HR investigation deliverable outside litigation scope | Only with separate product decision |
| F28 | Leadership/legal handoff | Launch litigation reviewer handoff; HR workflow out of scope | **Reference only** | Durable synthetic reviewer ledger (#82–85), no legal release | Assigned reviewer action, audit, stale version and handoff UI |
| F29 | Table of Authorities | Later/unresolved; separate from exhibit index | **Unresolved** | No Belgian Table of Authorities or legal source license | Authority format/source policy and generated TOA byte verification |
| F30 | Exhibit generation | Launch M4 | **Not built** | Typed exhibit register; no production bundle renderer | Live graph→generated index/bundle and reopened bytes |
| F31 | Dynamic exhibits after edits | Launch M4; deletion, reordering and frozen prior exports tested | **Not built** | DE-01 change contract only; no Word dynamic bundle | Renumber/reorder/retain uncited exhibits across DOCX/PDF |
| F32 | Hyperlinked briefs/letters/motions | Launch supported brief outputs; other templates separately scoped | **Not built** | No Belgian linked filing artifacts | Reopen actual DOCX/PDF and validate every pinpoint and hyperlink |
| F33 | Secure courtesy copies | Launch M4 with recipient controls | **Not built** | No secure released courtesy-copy service | Recipient-scoped share, expiry/revoke/redaction audit |
| F34 | Interactive examples | Launch synthetic NL/FR/EN demo | **Reference only** | Synthetic NL/FR/EN demos, no lawyer UI onboarding | Repeatable installable user walkthrough and accurate disclaimers |
| F35 | Cite Check Report | Launch M2 draft, M4 release; scope/version/dispositions explicit | **M2 engineering** | Machine-readable scoped run record; no released legal report | Human-reviewed report + manifest + generated document bytes |
| F36 | Opponent PDF-to-Word conversion | Later/unresolved fidelity work; original-PDF review does not depend on conversion | **Unresolved** | No high-fidelity opponent PDF→Word converter | Reversible mapping on scanned/rotated/footnote-heavy inputs |
| F37 | Retrieve uncited counterevidence | Launch scoped search M3; no exhaustive discovery claim | **Not built** | Limited text search; no validated uncited counterevidence | Explicit source universe, separate search vs opponent-wide recall |
| F38 | Cross-examination outline | Later M5 as source-linked hearing prep | **Deferred** | No cross-examination workflow | Human-controlled source-linked outline and event integrity |
| F39 | Generative/non-generative choice | Launch; deterministic workflow works without model credentials | **Reference only** | Deterministic engine, optional Requesty adapter; no choice UI | Matter-specific model consent; no-model complete core journey |
| F40 | Local citation style/linking | Launch shared versioned profile across Word and outputs | **Not built** | Typed alias/page representation, no shared Word/export profile | NL/FR Stuk/Pièce generated consistently in Word/PDF/index |
| F41 | Lexis source access | Unresolved, excluded from launch pending license/territory decision | **Unresolved** | No Lexis licence/integration | Territory, entitlement and independently validated legal sources |
| F42 | Fastcase/vLex access | Unresolved, excluded from launch pending license/territory decision | **Unresolved** | No vLex/Fastcase territory entitlement | Licensed Belgian coverage and testable authority source integrity |

## Cross-feature integration gates

1. **M1:** genuinely signed, private matter; persisted original bytes and representation/page validity; actual PDF/DOCX/OCR readback, human-confirmed exhibit register, restart/recovery and security signoff. Isolated tests alone are not enough. [M1 backend exit](m1/BACKEND_EXIT_CONTRACT.md).
2. **M2:** a single source-bound scope/check/review/correction/recheck process with approved live permissions, clean controls, zero-quote NL/FR/EN, same-role amounts/dates and clear incomplete/unknown states. [M2 acceptance](m2/ENGINEERING_ACCEPTANCE.md).
3. **M3:** actual supported Office client, selected passage, ranked source lookup, original preview, citation insert/undo, Word safe mutation, recheck and cross-process identity security. Start an early synthetic Word integration spike while M1/M2 progress. [M3 acceptance](m3/WORD_INTEGRATION_ACCEPTANCE.md).
4. **M4:** real reviewed Word/PDF/index/bundle artifact bytes, dynamic exhibits, opened-and-validated hyperlinks, immutable release, authorized share and complete legal user journey. [M4 acceptance](m4/DELIVERY_ACCEPTANCE.md).
5. **Market:** authorized, rights-cleared task benchmark vs manual Word/PDF, Belgian Hublex/Alice and directly comparable accessible Prudai/Clearbrief capabilities, with observed review time, false alarms and fees. Price is an experiment, not evidence of demand.

## Update discipline

- Maintain F01–F42 as **exactly 42 unique identifiers** in this matrix and ROADMAP. Do not silently remove or add a new Clearbrief feature: propose a new tracked `F43+` only when there is a genuinely distinct capability and an owner decision.
- A row can progress to **integrated staging** only with actual signed users, approved private matter grants and source bytes where applicable; **customer accepted** additionally needs protected operations and a reproducible lawyer task receipt. Link the exact PR, commit, workflow run and fixture/test in the changed row.
- Never mark F35 `released` based on a machine-readable Python JSON run, F31 `complete` based on an exhibit-register data model, F08 `complete` based on a mock Word range, or F39 `complete` based solely on an available LLM API.
- This document records code/acceptance truth; the **product scope and delivery priority remain solely in ROADMAP.md**. Legacy finance adapters are compatibility code and do not count as completed Belgian legal features.
