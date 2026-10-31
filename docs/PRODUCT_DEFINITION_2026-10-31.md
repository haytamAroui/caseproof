# Product definition and prioritized delivery — 31 October 2026

**31 October owner refinement (superseding PR #141's planning snapshot).** This document refines the existing
[M0–M6 roadmap](ROADMAP.md), [workflow](PRODUCT_WORKFLOW.md) and
[ADR 0019](adr/0019-evidence-engine-and-first-market.md). It does not reset milestones,
certify a legal position, authorize client data or replace existing security gates.
CaseProof remains the repository name; the future public name is undecided.
The supplied Product Definition and Roadmap PDF is planning input, not proof of
implementation, competitor limitations, bar approval or commercial demand.

## Vision and differentiated position

**Long-term purpose:** make source-referenced professional work inspectable, uncertainty explicit, and accountable human review reproducible. **First commercial hypothesis:** independent pre-submission verification of Belgian FR/NL civil/commercial litigation conclusions—not general legal research, a bundle assembly tool, an AI law firm or a legal judgment engine.

**Position in existing workflow:** after a lawyer uses their own Word, DMS or exhibit-assembly tool to prepare a draft and inventory, CaseProof independently checks detected Stuk/Pièce references against the **supplied and separately preserved original exhibits**: inventory identity, physical PDF/printed/bundle page space, literal/visual/value fidelity, then human-only semantic review. Show an actual source page/crop and exact version-bound review; never claim to prove the original is authentic or that the bundle was filed.

**Working differentiation, not exclusivity:** source-linked post-assembly checking of a Belgian inventory and three page spaces, explicit OCR abstention and a durable review trail at lower measured total lawyer effort. Compare real capabilities of Jimini, Doctrine Flow Litigate, Clearbrief and QiXCite before claiming they do not verify; vendor marketing and funding do not prove market gaps. See [Jimini litigation help](https://intercom.help/odysai/fr/articles/15073060-jimini-contentieux), [Doctrine Flow Litigate](https://www.doctrine.fr/flow-litigate) and [QiXCite](https://marketplace.microsoft.com/en-us/product/WA200010493).

**Customer copy:** “Before filing, CaseProof checks detected exhibit references against the bundle you supply, shows which could not be substantiated within disclosed coverage, and records your review.” Do not say “only”, “as filed”, “every reference”, “100% accurate” or a global verified result. The public CaseProof name is provisional pending EUIPO/BOIP trademark clearance; a pre-existing software business using Caseproof is a search lead, not an infringement conclusion.

## Product and buyer

**Promise:** check detected exhibit references against the supplied litigation bundle,
inspect the source beside each finding, and record human review against exact document
versions. Belgian FR/NL civil/commercial litigators are the first buyer hypothesis.
A reusable evidence engine is the longer-term ambition, not a second current market.

The first task is pre-submission reference verification. Partner, associate and risk/
knowledge-management roles must be interviewed separately: user, purchasing authority
and budget owner may differ. Opponent-side reference audit is an adjacent hypothesis,
not a new argument-generation, discovery or counterevidence-search product.
No authority research, legal drafting, automated legal support judgments or court filing.

Say **supplied bundle snapshot**, not **as filed**, unless separate filing evidence is
captured. Say **detected references within disclosed coverage**, not **every reference**.
An authenticated processing receipt is not a qualified lawyer signature; a signed review
record is not proof of careful supervision, factual truth, authenticity or admissibility.

## Verification and report contract

| Dimension | Required presentation | Abstention or limitation |
|---|---|---|
| Exhibit identity | Confirmed inventory revision, stable exhibit/source IDs and alias | Missing/unconfirmed/incomplete inventory is not assessed; absence requires confirmed complete scope |
| Page location | Physical PDF page, printed label and bundle position as separate values | Not applicable differs from unmapped; printed labels may be Roman, duplicated or absent |
| Literal/visual fidelity | Raw quote, source span, match/diff, extraction and visual-assessment provenance | Exact text alone is not visual agreement; absent visual comparison remains not assessed |
| Human semantic support | Authorized supported/qualified/contradicted/not-assessed decision with rationale | Human decision cannot erase the machine finding or establish authenticity |

No worst-colour overall verdict or global VERIFIED badge. A separate action queue may
say needs review, blocked or review recorded; it cannot collapse four evidence dimensions.
Colour must always accompany text. No quotation means identity/page checks only, with
literal comparison not applicable. A conflict is a review trigger, not automatic legal
interpretation of a deletion. A crop may be unavailable: disclose the reason and provide
authorized original-page access where possible rather than promise a crop for every error.

`quote_not_found` means not located in the checked representation/scope. A claim that a
quote is absent from the source requires reliable complete extraction and established
page mapping. Unreliable scans, partial extraction and ambiguous anchors abstain.
Reference-resolution failure alone does not prove an exhibit was never communicated.

Report outputs must include:

1. Matter and run identity, draft/source/inventory snapshot hashes, parser/OCR/engine/
   rule versions, processing boundary, operator and run timestamp.
2. Coverage: discovered/processed/unsupported DOCX regions; detected/checked/unassessed
   references; source files/pages and OCR denominators; excluded inputs and failures.
3. Per-reference four dimensions, raw reference and sentence, resolved exhibit,
   independently labelled page spaces, reason, deciding layer and source/crop link.
4. Explicit visual coverage: no comparison, unknown/partial regional coverage, or
   validated coverage; supplied comparison never implies the entire quote was checked.
5. Visible abstentions and next action. Uncited inventory items are informational only;
   they do not prove an omission or legal irrelevance.
6. Human dispositions, stale status, immutable source lineage and method/limits appendix.

Render every export from one frozen manifest. Add PDF/CSV after the report schema is
stable; retain existing scoped JSON/Markdown/DOCX artifacts. CSV must resist spreadsheet
formula injection. Reopen exported bytes and check source/page links, Unicode FR/NL,
row counts, dispositions and identical scope/version identities across formats.

## Delivery order and acceptance gates

Calendar dates below are planning windows, not commitments. Move dates, not gates.

| Order / milestone | Bounded work | Exit evidence |
|---|---|---|
| Completed M1/M2 engineering baseline | PRs #146/#147, #149 and #150 merged fidelity/translation/coverage/canonical-report work; #152–154 merged recovery and CI coverage | Exact PR/check receipts. [Main commit d3374b8f](https://github.com/haytamAroui/caseproof/commit/d3374b8f78599b33bff7ce098a746b70af29b094) passed 17 automated checks, with four intentionally skipped manual live gates: no customer release |
| **Priority 1 — M1–M4 browser** | Signed user-created matter → DOCX/inventory/PDF/scan upload → confirmed identity → separate evidence dimensions and original crop → review/correction/recheck → canonical report/DOCX download → cold reopen | Browser E2E with real-format synthetic originals; current grants, hash-bound source links and actual reopened artifacts; stale/revoked/interrupt/duplicate denial |
| Following core journey — M1/M2 intake | Consolidated bookmarked PDF and locale/role-aware money/date normalization, without silently mixing source/page spaces | Confirmed exhibit-to-range mapping, overlap/alias/insert/rename cases; unambiguous Decimal/locale match or typed abstention |
| Following stable manifest — M4 formats | Optional PDF/CSV and portable review record derived from one frozen report | Independent actual byte/Unicode/link reopening; CSV formula-injection protection; no qualified-signature claim |
| **Parallel — M5 practitioner discovery** | Five disconfirming FR/NL interviews and two observed workflows, extend toward 8–10 litigators and 2–3 risk/ethics contacts if evidence supports | Actual post-assembly errors, time, competitors, confidence, confidentiality needs, buyer/budget and concrete price reaction |
| Conditional — M5 controlled pilot | Priced design-partner offer and only approved representative dossier trials | P5-01–04, SEC-01–16, rights and professional-secrecy approvals, independent ground truth and measured whole-task effort |
| **Parallel assessment — deployment/security** | Data-flow and network-capture comparison of hosted, hybrid and firm-controlled modes; packaging only if buyer requires it | Documented processing environment, egress, retention/backups, vendor confidentiality, independent security/legal signoff |
| Deferred — M6 channels | Word add-in, deployed public MCP, local installer, qualified signatures, German and authority research only on separately approved evidence | Separate owner scope decision and acceptance. MCP **code** merged in #153; production/OAuth and host-client consent unaccepted |

The PDF's November groundwork, December–February report, March–May pilot and June–
September channels are provisional planning windows only. Do not postpone existing
review integrity or security controls to match those dates, or claim already-built
capabilities must be rebuilt in a later phase.

### Consolidated bundle acceptance

Preserve the original consolidated PDF and its hash. One file may contain many exhibits;
one exhibit can comprise multiple authorized source parts. Do not enforce one inventory
entry equals exactly one file. Keep stable exhibit identity separate from bookmark title,
physical range, printed labels and global bundle pagination. Reject ambiguous overlapping
assignments; cover coversheets, unnumbered pages, annexes, nested bookmarks and 12bis/I.A
aliases. Confirm supported bookmarks/ranges explicitly. Never rewrite an opponent original.

### Deployment decision, not an automatic pivot

**Do now:** map field-level flows, network egress, processing provider and region, source originals, crops, derived texts, hashes, IDs, report exports, logs, support access, subprocessors, backups, retention and deletion for all candidate modes. A browser UI can be served within a firm; web-first is **not** hosted-first. Hashes, reference strings and timing may still be confidential or personal. Deterministic computation and an isolated worker do not independently satisfy Belgian professional secrecy. Assess vendor confidentiality after contract termination, not only GDPR DPA paperwork. No zero-retention or no-egress promise without evidence.

The independent web report remains the first experience; web does not imply hosted
processing. Current Supabase development infrastructure is not a packaged local product.
Validate firms' actual requirements before choosing which customer deployment to build.

| Candidate mode | Contract to establish before delivery |
|---|---|
| Firm-controlled/local | OCR, rendering, storage, review and keys within approved boundary; inspect dependencies, telemetry, licence checks, updates, backups and support access; prove runtime egress behaviour |
| Hybrid | Documents and crops stay in approved boundary; whitelist every outbound field; assess hashes, IDs, verdicts and timing as potentially sensitive metadata; test network capture |
| Hosted | Approved providers/regions, access controls, processing agreement, transfers and explicit retention/deletion across originals, caches, temp files, logs and backups |

Do not promise nothing leaves or zero retention without measured and contractual evidence.
OCR/ML processing must be disclosed separately from an optional generative layer. Generative
notes are off by default and cannot promote an uncertain/conflicting finding to passed.
A local installation alone does not establish bar approval or security compliance.

### Review record and signatures

**No evidence transparency paywall:** a sample/free trial must show the same four independent states, abstentions, provenance and coverage as a paid report; enterprise administration may be priced separately. Cryptographic integrity receipts are not qualified human signatures or proof of careful legal supervision.

Keep version-bound durable review, actor authorization, rationale, source/crop hashes and
stale detection in M2–M4 now. Add cryptographic verification only with an explicit threat
model: who signs, who holds keys, whether the signature attests system origin or reviewer
identity, verifier portability, timestamp source, key rotation/revocation and recovery.
Changed draft, inventory, source, mapping or relevant rules makes dependent review stale;
prior records remain immutable. Do not make every unrelated confirmation stale without
recording dependency scope. Qualified signatures/trusted timestamps are later options;
provider support and legal effect require specialist confirmation. No Book 8 automation.

### Commercial and benchmark decision

Measure reference-detection recall against independently annotated ground truth, false
acceptance over evaluated references, false-alert workload, useful assessed coverage,
abstention by reason, reviewer disagreement, total setup/upload/OCR/review/export time
and cost at observed dossier sizes. Report numerator/denominator, corpus composition,
versions and synthetic versus representative rights-cleared results. A system that checks
only easy references cannot claim success because it accepts none incorrectly.

Seek a paid or priced conditional pilot early; the existing five-week M5 decision process
starts at the first practitioner conversation. A roughly 60-day no-paid-demand checkpoint
may inform refine/reconsider, but does not automatically authorize a new market. Record
outreach quality, buyer fit and objections before requesting an owner decision. Paid
interest is not permission to upload client documents or release software.

## Competitive, name and practitioner research queue

- Conduct permissioned direct workflow comparisons of actual post-assembly reference verification, original crop/three-page mapping and review reports in Belgian, French and neighboring markets; do not assume existing assembly systems cannot also check.
- Perform EUIPO/BOIP name clearance before public branding. A naming overlap is not an established legal conflict.
- Interview actual litigators, risk reviewers and purchasers about total checking time, missed Stuk/Pièce references, OCR, wrong page spaces, deployment restrictions, buyer budget and priced commitment.
- Get security, privacy, confidentiality/vendor-terms and intended-use AI Act analysis for the exact proposed processing environment before any non-synthetic customer data.

## External validation and deferred claims

Name clearance: check exact/phonetic trademark conflicts, domains and relevant registries
before public branding; no confirmed infringement is asserted. Read primary Belgian bar
and filing guidance; obtain specialist AI Act applicability advice and assess processing
components/intended purpose separately. Do not confuse outside Annex III with an Article
6(3) exemption. Track regulatory dates against current official texts before external use.
Competitor capability gaps, sanctions counts, academic percentages, insurer effects and
court weight of a signature remain unverified unless backed by reviewed primary evidence.

Sources: owner-supplied Product Definition and Roadmap PDF (31 October 2026), critically
adapted here; [OVB guidance](https://www.ordevanvlaamsebalies.be/nl/kennisbank/digitalisering/richtlijnen-voor-advocaten-rond-gebruik-van-artificiele-intelligentie),
[consolidated AI Act](https://eur-lex.europa.eu/eli/reg/2024/1689),
[existing pilot controls](security/PILOT_DATA_SECURITY_GATE.md).
