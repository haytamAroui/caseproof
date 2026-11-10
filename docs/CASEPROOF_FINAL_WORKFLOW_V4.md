# CaseProof — Final Workflow and Engineering Acceptance Plan (v4.1)

**Version:** 4.1 (v4 update) · **Updated:** 10 November 2026 · **Status:** **PROPOSED TECHNICAL CONTRACT — NOT FULLY IMPLEMENTED OR PILOT-APPROVED**  
**Base specification:** `caseproof-final-workflow (3).md` (v3), with corrections from the 8 November code-level review and the independent DeepSeek commentary.  
**Code snapshot:** `haytamAroui/caseproof`, `main` including merged PR #209 (squash commit `af438c3771add91f3b4b83409d464a0c05031670`, verified 10 November 2026). The original v4 audit was performed 8 November; later acceptance claims must be supported by separate evidence.  
**Change control:** This revision records that PR #209 was merged; it does **not** authorize production, real client-data processing, court filing, or silently supersede accepted [ADR 0018](https://github.com/haytamAroui/caseproof/blob/main/docs/adr/0018-pre-submission-verification-freeze.md). Adopting a broader mandatory commercial scope, or making Word mandatory for launch, requires an explicit owner decision and a reviewed superseding ADR.

> **Core rule:** The **LLM proposes**; the **deterministic kernel verifies only bounded, technically checkable properties**; the **authorized lawyer decides semantic support**; and **the complete baseline review/export journey works with the LLM off**.

## 0. Product, outcome, and scope

**Product hypothesis:** CaseProof is a **Belgian NL/FR pre-filing factual-evidence workspace**. A lawyer uploads an existing DOCX brief, its Stuk/Pièce inventory, and preserved original exhibits. CaseProof discovers *candidate* factual propositions, locates *candidate* relevant passages, checks the technical integrity and page/fidelity of explicit claim–source relationships, enables human assessment, and produces carefully scoped, reviewable work product and a verifiable audit record. **No system can promise to detect or verify every factual claim without measured recall and explicit coverage limits.**

**Customer outcome to test:** Find evidence and check factual propositions faster than manual review, discover meaningful missed errors, and produce source-linked corrections without introducing new filing errors. The product is not validated merely because it detects citation typos or its CI passes.

**Initial supported journey:** Existing draft → preserved sources/inventory → claim candidates and reference checks → evidence discovery → human-reviewed source links → correction/Add Fact Cite → recheck → scoped signed output. **When the product presents a particular PDF as ready to file, a separate final-artifact parity check and explicit approval of that PDF's exact bytes are required.** This does not claim to observe court submission. A lawyer can inspect, accept, qualify, or reject every proposed source relationship. Manual evidence selection remains possible when search fails.

**Near-term deliverables:** Claim-level finding/coverage view, cited original-page navigation, a reviewed DOCX and findings report, Stuk/Pièce index, scope-/rights-bound verification receipts, and a **separate final-PDF preflight contract** for any later ready-to-file feature. A functioning Word task pane is a **separate optional channel milestone**, not a synonym for DOCX import/export.

**Explicit non-goals in the initial controlled pilot:** Legal research, authoritative *good-law* certification, generative legal arguments, Ask My Docs chat, autonomous agents, settlement predictions, e-filing, case outcome predictions, a new rich-text editor, mandatory cloud LLM use, broad Clearbrief parity, or general Netherlands/France integrations. Opponent mode is **not** presumed safe or free to launch just because it can reuse processing functions.

**Definition of success:** An authorized lawyer finishes a complete scoped review of known inputs, can navigate each relied-upon original, receives intelligible coverage/uncertainty, saves a correct reviewed artifact, and a third party with proper access can validate the export's technical provenance. The lawyer's legal conclusions remain the lawyer's responsibility.

---

## 1. Non-negotiable principles

1. **Preserved originals are authoritative** for what was received: hashes protect byte integrity relative to intake, **not third-party authenticity or correct exhibit identification**. OCR and PDF text layers are derived and can be wrong.
2. **No AI authority promotion.** A model response, similarity score or semantic reranker must never assign technical success, human confirmation, legal sufficiency or release permission.
3. **Independent findings:** source-byte integrity, confirmed exhibit identity, physical-page mapping, literal quotation/value fidelity, semantic support, coverage, authorization/currentness and release status are distinct.
4. **Human semantic judgments only.** `SUPPORTED`, `QUALIFIED`, `CONTRADICTED`, `INCONCLUSIVE` and `NOT_ASSESSED` are recorded as authenticated, source- and snapshot-bound reviewer decisions. A model can suggest these only in a separate, clearly untrusted proposal field.
5. **Literal matching is not semantic proof.** Cross-language paraphrase can be human-supported even when literal fidelity is `NOT_APPLICABLE`; do not weaken the existing exact-quote verification contract to permit paraphrases.
6. **Search misses are not factual disprovals:** use *“no supporting evidence located within the searched scope”*. Always describe excluded, unprocessed and inaccessible material.
7. **Unknown is not clean.** Unreadable OCR, unscanned DOCX regions, uncertain page mappings and truncated retrieval produce `PARTIAL`, `UNKNOWN` or `NOT_ASSESSED`, never a green aggregate.
8. **Version everything that changes decisions:** preserved bytes, document versions, inventory confirmation, parser/representation/OCR outputs, index snapshots, source anchors, algorithm/ruleset digest, proposal outputs and reviewer receipts.
9. **No hidden re-generation.** Rechecks of frozen inputs replay deterministic logic and previously stored proposals without calling the model; changed dependencies invalidate only the affected objects, with an explicit new evaluation for affected proposals.
10. **Untrusted documents are data, not commands.** Enforce permissioned retrieval, bounded context, no model tools by default, structured response validation, prompt-injection tests and safe rendering.
11. **LLM-off parity:** intake, lexical search, original inspection, manual source selection, technical verification, review, correction/recheck, and scoped release are usable without an LLM.
12. **A signed receipt is technical evidence, not a legal certificate.** Signing and verification live in an authorized application/service boundary; the reusable kernel may define hash/provenance/receipt data types but never owns secrets, tenant grants or external signing keys.
13. **Do not expand the kernel with providers.** Requesty, OCR executables, prompts, Word SDKs, Supabase clients, Stuk/Pièce-specific law and UI concerns stay in adapters/domain/application services.
14. **No false print guarantees.** A QR/verification code is optional until a protected verifier, key lifecycle, access checks, retention semantics and actual print/scan verification are proven.
15. **Safety gates cannot be traded for schedule.** No confidential matter ingestion without documented rights, a deployment-specific data-flow review, security approval and legally appropriate processing arrangements.
16. **Existing working code is reused.** An audit must mark `exists`, `connected to the signed path`, `tested`, and `independently accepted` separately; a demo endpoint is not the entire product.
17. **The initial hypothesis is falsifiable.** Pilot results may lead to **proceed**, **refine**, or **reconsider**; competitor marketing is not evidence of Belgian customer demand.
18. **The reviewed draft is not automatically the final filing artifact.** A corrected DOCX, its exported PDF, and the exact PDF eventually submitted are three distinct byte identities. Never infer cross-format parity from matching file names, dates or SHA-256 digests of different formats.
19. **Approval attaches to exact final bytes.** A `READY_TO_FILE` claim requires a successful scoped DOCX→PDF content/visual comparison **and** an authenticated lawyer's review and approval of the exact final PDF hash. Any byte change invalidates that approval. No such label is permitted if the preflight feature has not been accepted.
20. **Approval is not filing proof.** A final-PDF receipt proves only what was inspected and approved; actual submission requires separate uploaded-byte confirmation or trustworthy external filing evidence. CaseProof has no e-filing integration in initial scope.

---

## 2. Findings, claim and evidence-link contracts

### 2.1 Do not collapse different questions into a single `verified` field

| Dimension | Allowed illustrative states | Authority | Interpretation |
|---|---|---|---|
| Original-byte integrity | `INTACT`, `MISMATCH`, `UNKNOWN` | Kernel plus trusted readback | Does the retrieved object match the preserved hash? **Not authenticity**. |
| Exhibit identity | `CONFIRMED`, `AMBIGUOUS`, `UNRESOLVED`, `NOT_ASSESSED` | Inventory mapping + authorized confirmation | Is this the *right* Stuk/Pièce item, independent of byte integrity? |
| Page mapping | `MAPPED`, `CONFLICT`, `UNMAPPED`, `NOT_ASSESSED` | Deterministic mapping | Physical PDF page, printed page and bundle page are separate spaces. |
| Representation quality | `TEXT_LAYER`, `OCR_REVIEW_REQUIRED`, `REPRESENTATION_CONFLICT`, `UNAVAILABLE` | Parser/OCR + comparison | Derived text must identify its method, scope and uncertainty. |
| Literal fidelity | `EXACT`, `MISMATCH`, `NOT_APPLICABLE`, `INDETERMINATE` | Kernel | `NOT_APPLICABLE` is permitted for a **paraphrase**, not for a requested exact quote. |
| Search state | `NOT_SEARCHED`, `CANDIDATES_FOUND`, `NO_HIT_WITHIN_SCOPE`, `PARTIAL`, `STALE` | Retrieval application | Candidate availability, not semantic truth. |
| Human semantic support | `SUPPORTED`, `QUALIFIED`, `CONTRADICTED`, `INCONCLUSIVE`, `NOT_ASSESSED` | Authenticated authorized reviewer only | Actual review of the claim **against a particular original passage**. |
| Review state | `PENDING`, `DECIDED`, `STALE`, `SUPERSEDED` | Review application | Neither a decision nor a previous signature transfers automatically to changed inputs. |
| Release | `REFERENCE_REVIEW_COMPLETE`, `CLAIM_REVIEW_COMPLETE_WITHIN_SCOPE`, `PARTIAL_REVIEW`, `NOT_ELIGIBLE` | Authorized release service | Always scoped; **not** “all factual statements true.” |
| Final-PDF parity (separate) | `NOT_ASSESSED`, `MATCH_WITHIN_DECLARED_SCOPE`, `DIFFERENCES_FOUND`, `INDETERMINATE`, `STALE` | Deterministic cross-format preflight | A similarity or text match does not certify visual and legal equivalence. |
| Final-PDF human approval (separate) | `NOT_APPROVED`, `APPROVED_EXACT_HASH`, `REVOKED`, `STALE` | Authenticated lawyer + signed application | Only approval for the exact compared PDF and stated scope; **not evidence that it was filed**. |

**Important:** These are target contract semantics, not a claim that identical enum names already exist. Map to existing public APIs carefully and version any migration.

### 2.2 Identity objects and provenance

| Object | Required minimum fields | Rules |
|---|---|---|
| `PreservedSourceVersion` | `matter_id`, `document_id`, `version_id`, `sha256`, `size`, MIME, custody/rights identity | Byte hash checked on readback; no cross-matter sharing by assumed equivalence. |
| `DerivedRepresentation` | Parent version+hash; parser/OCR name/version/config digest; representation hash; page/coordinate convention; omissions | Never imply OCR text is original content; keep page/word confidence when available. |
| `ClaimUnit` | `claim_id`, draft version/hash, DOCX story/part, bounded text offset, quote/text digest, segmenter version, classification state | ID deterministic for **identical input bytes and algorithm**; edited documents get a new identity and optional explicit lineage mapping. |
| `EvidenceCandidate` | `candidate_id`, source version/hash, representation hash, physical page, locator/offsets, extracted passage digest, retrieval algorithm/index version, source quality | A search result is a candidate; duplicate passages and ambiguous mapping remain explicit. |
| `ClaimEvidenceLink` | Claim identity + selected evidence anchor + evidence expectation type + technical findings + coverage/snapshot IDs | Multi-source and multi-claim links allowed; do not silently force a one-to-one relation. |
| `ModelProposal` | Proposal ID, exact authorized input/candidate-set hash, provider/model/version, prompt template digest, parameters, invocation ID, bounded raw/parsed output, timestamps/outcome | Separate from findings. Encrypt, scope, minimize, and delete according to approved policy. Missing/uncertain dispatch must not silently retry. |
| `HumanReviewReceipt` | Actor and authorization provenance, claim/link ID, evidence snapshot, semantic decision, rationale, timestamp, reviewed original-page IDs, idempotency key | Only signed application authority may attribute decisions; never trust a model or browser-supplied `human=true`. |
| `ExportManifest` | Original/derived hashes, scope, selected source anchors, review and coverage summaries, rule/index/model provenance, rights disposition, signing-key identity | External verification validates integrity and lineage, not correctness of a lawyer's conclusion. |
| `FinalPDFCandidate` | Final PDF SHA-256/size/version, approved DOCX hash/version, transformation provenance, content/visual comparison version, coverage and unresolved differences | Separate immutable derivative; neither a DOCX digest nor an automatically generated PDF proves parity. |
| `FinalArtifactApprovalReceipt` | Actor/grant, reviewed exact PDF SHA-256, DOCX/review snapshot, signed comparison digest, inspected pages, exceptions, time, idempotency key and approval state | Created only after verified actor action; a modified PDF or changed review snapshot makes the receipt stale. Filing confirmation is a separate record. |

**No unbounded text replication:** Original bytes and confidential quotes should not be copied into logs, tracing or public receipts. Store exact content only in approved restricted storage; a digest plus authorized private lookup may be sufficient for the public-facing verifier.

### 2.3 Claim identity and DOCX semantics

- **Two notions of identity:** (a) immutable **snapshot claim ID** based on draft SHA-256, story/part, text offsets and statement digest; (b) **cross-revision correspondence** established by a separate, conservative resolver. Do **not** claim the same ID survives arbitrary DOCX edits.
- Enumerate main document, headers, footers, footnotes/endnotes, tables, tracked revisions, comments, textboxes, fields, hyperlinks and unsupported parts. For any unsupported/ambiguous content, record omitted or `NOT_ASSESSED`, not `COMPLETE`.
- Segmentation is a **candidate inventory**, not proven factual classification. Handle NL/FR abbreviations (`art.`, `M.`, `Mme`, `Dr.`, `nr.`, numbered articles), decimal punctuation, dates, citations, mixed-language clauses and multi-proposition sentences. Uncertain boundaries are reviewable or explicitly ambiguous.
- A factual proposition may span multiple sentences; a sentence may contain multiple independently checkable propositions. Support splitting/merging claim units with versioned user action and recalculated coverage.
- Keep a human-readable excerpt and neighboring context for review, but bind acceptance to original DOCX and its version rather than merely normalized text.

### 2.4 Coverage is multidimensional and denominators must be honest

| Measure | Denominator or scope | Required labels |
|---|---|---|
| DOCX story coverage | Discovered regions/parts with known scan outcomes | Scanned; unsupported; unscanned; unknown; parser version. |
| Claim discovery | Candidate units, human-excluded/added units and independently labeled actual claims where available | **Factual claim recall is `UNMEASURED`** until a gold denominator exists. |
| Exhibit corpus | Authorized declared source versions/pages | Included; excluded; unreadable; unavailable; partial; unknown. |
| Retrieval execution | Accepted claim units requested for search | Searched/no hit/not searched/error/truncated/stale. **Search execution coverage ≠ relevant-passage recall.** |
| Source-anchor quality | Candidate links | Provenance intact; page ambiguous; fidelity determined/indeterminate; OCR conflict. |
| Human review | Eligible finding/link IDs | Pending/decided/stale/superseded; explicitly excluded items. |
| Export scope | Frozen reviewed items and permitted original/derived versions | Reference-review and claim-review scope separate, with unresolved counts. |

For measured gold-set retrieval, separately report `Recall@k`, precision at *k*, source/version/page correctness and abstentions. A corpus can be fully indexed while retrieval still misses the correct passage.

### 2.5 Release semantics: the P0 integration risk

Existing `application/litigation/release_completeness.py` counts decisions over **detected reference findings**. It explicitly says this is not proof that all legal claims were discovered. V4 must **preserve that distinction** when claim candidates are introduced.

1. Keep existing reference-review completeness intact; never silently re-label it full factual-claim completeness.
2. Add a separate **claim-review ledger** and coverage denominator for the claim set accepted within the frozen snapshot. Unassessed or stale links cannot silently become confirmed.
3. When both reviews are present, exports show both counts, their scopes and exclusions. `COMPLETE` must be qualified (*“complete review of detected references”* versus *“complete review of accepted claim units within declared scope”*).
4. Failing corpus permissions, unresolved originals, incorrect source IDs or stale selections block any release that would represent those links as confirmed.
5. Preserve `PARTIAL` exports only where a human explicitly acknowledges their limits and rights allow export. A reviewer decision is not a filing authorization.
6. A nonliteral supported paraphrase can carry a human semantic receipt plus technically sound source/page/representation details; never counterfeit `EXACT` literal fidelity.

### 2.6 Final Artifact Verification contract — new conditional P0

**Why it exists:** In *Farhat v. Cutera, Inc.* (N.D. Cal., No. 3:26-cv-05674-TSH, ECF No. 27, 28 October 2026), counsel reported correcting citations after checking authorities, but an earlier, uncorrected draft was inadvertently converted and filed. The court discharged its show-cause order without sanctions at that time, yet emphasized counsel's duty to inspect the **final** document. This is an illustrative U.S. workflow failure, **not** a Belgian court rule and **not** proof that a particular AI system generated each error. The two-page order alone does not provide the filed motion, corrected draft or redline needed for a reproducible test.

**When it is required:** This is **P0 for any CaseProof output or UI state claiming a named PDF is ready to file**. A strictly **non-filing exploratory pilot** may omit the capability only if it clearly labels the output `FINAL_PDF_NOT_CHECKED` and never presents it as filing-ready. The requirement does not make Word or e-filing mandatory, and does not expand the initial legal-authority scope.

**Frozen input identity:** `approved_docx_version_id`, original DOCX SHA-256, current review snapshot/receipts, permitted source bundle, generated or user-supplied PDF SHA-256 and byte length, PDF parser/raster/normalizer versions, comparison ruleset digest, conversion provenance and independent review scope. Different formats are compared by **meaningful content and rendering**, not by comparing their file hashes to one another.

**Deterministic preflight:** Extract and align statements and citations across DOCX/PDF with stable context and explicit ambiguous mappings; check names, amounts, dates, numbers, negations/qualifiers, legal and Stuk/Pièce citations **as text**, quotations, page references, tables, footnotes, headers/footers, field results, tracked-revision state and missing/added content. Distinguish harmless pagination/fonts from substantive changes. Rasterize and compare when a text-layer-only result could miss visually material edits or omissions. Identify inserted/deleted/reordered material, low-quality OCR, partial pages, annotation/hidden-layer risks and unrendered parts. An empty or incomplete comparator result is `INDETERMINATE`, never `MATCH`.

**Human last-mile decision:** The lawyer opens the **exact final PDF bytes** in an approved viewer, inspects all material differences and uncovered regions, and explicitly approves the reviewed PDF hash via a fresh identity/rights/snapshot check. No automatically checked checkbox, implicit export approval or delegation to an AI is sufficient. Approval after a scoped human exception is only allowed under documented policy and must not be displayed as an unqualified match.

**Status and refusal:** `NOT_ASSESSED`, `MATCH_WITHIN_DECLARED_SCOPE`, `DIFFERENCES_FOUND`, `INDETERMINATE` and `STALE` remain separate from `APPROVED_EXACT_HASH`. If the final PDF changes **by any byte** after approval, or if its governing DOCX/review snapshot changes, approval is invalid for the new candidate. Exports can still be labeled `REVIEWED_DOCX` where applicable; they cannot receive `READY_TO_FILE` from incomplete or stale parity.

**Filing boundary:** The record proves **approval of bytes**, not court upload. If a later workflow receives the actual submitted PDF or trustworthy filing evidence, compare that submitted **PDF's exact hash** against the approved PDF hash and record the limits of verification. No claim about successful submission is made solely from a receipt or the lawyer's intention to file.

**Safeguards:** No unapproved external PDF conversion/OCR/LLM egress; run PDF parsing and rasterization within the approved sandbox/capacity envelope, inherit source rights and retention, protect diff excerpts, record file bombs/timeouts and avoid public QR/access links. Keep a separate immutable audit record for each attempted PDF and its disposition.

**Acceptance examples:** (1) Correct approved DOCX → substantively corresponding PDF: eligible for explicit lawyer approval; (2) corrected DOCX → older uncorrected PDF: **not ready**; (3) same PDF with a changed citation, number or negation: **not ready**; (4) unreadable/partial PDF or unverified DOCX story: `INDETERMINATE`; (5) approval then modified PDF: `STALE`; (6) authorized approved PDF differs from later submitted bytes: flag mismatch, do not claim a safe filing. Use seeded, rights-cleared versions until actual case artifacts and labels are independently obtained.

---

## 3. Phase 0 — Code-evidence audit (8 November baseline; 10 November PR-status correction)

**Methodology:** The original audit checked actual modules on `main`, PR #209 before merge, and GitHub Actions status; the PR merge was separately verified on 10 November 2026. It did **not** run a confidential dossier, a real Word desktop host, an independent penetration test, or an external reviewer study. “Present” does not mean production-approved.

| Capability | Exists in code | Connected to signed litigation journey | Evidence and remaining work |
|---|---|---|---|
| Secure signed intake, original hashes | **Yes** | **Yes, development-signed** | `apps/api/workspace_intake.py`, `signed_supabase_originals.py`; client-data permission remains gated. |
| Signed bearer and matter authorization | **Yes** | **Yes, relevant signed routes** | `apps/api/supabase_auth_verifier.py`, `dossier_journey.py`; not an independently approved production deployment. |
| Database/private Storage | **Yes** | **Yes, selected signed paths** | `postgres_case_repository.py`, signed Supabase adapters and RPCs; review full operational posture. |
| DOCX/PDF/OCR extraction, source geometry | **Yes** | **Yes, with limits** | `pdf_ocr.py`, `signed_document_parse.py`; real-source OCR acceptance open. |
| Stuk/Pièce inventory and explicit references | **Yes** | **Yes** | `reference_detection.py`, `docx_reference_discovery.py`; explicit reference recall limits. |
| General claim segmentation | **Bounded parser merged in PR #209** | **Signed frozen-snapshot candidate read exists** | `docx_claim_discovery.py`; heuristic claim recall, complex DOCX stories, real-world adjudication and claim-link integration remain open. |
| Claim-level evidence coverage/ledger | **Partial** | **No full signed claim-review path** | Reference review ledger exists; separate claim review not wired into release. |
| Authorized lexical evidence search | **Yes** | **Legacy development adapter; not full new rights-gated claim route** | `litigation_evidence_search.py`; preserve authorizations and current snapshots. |
| Multilingual semantic candidate retrieval | **Not established** | **No** | Cross-language lexical miss cannot be repaired by reranking an empty set. |
| Requesty model transport/proposals | **Yes** | **No accepted signed litigation LLM path** | `requesty_extraction.py`, `application/extraction/`; old manual live smoke had an uncertain failed attempt. |
| Deterministic reference/page/fidelity checks | **Yes** | **Yes** | `domains/disputes/dossier_verification.py` plus `dossier_journey.py`; independent NL/FR falsification still open. |
| Human review, correction, recheck | **Yes** | **Yes, signed development** | `dossier_journey.py`, review/correction layers; no externally observed lawyer acceptance. |
| Add Fact Cite | **Synthetic/partial** | **No accepted live insertion** | `apps/word_addin/`; original-page link/citation save-reopen acceptance open. |
| Microsoft Word add-in | **Prototype** | **Read-only signed dev plus synthetic editing** | Real host, versioned range insertion, coauthoring and undo tests open. |
| Stuk/Pièce renumbering, complete exhibit assembly | **Partial** | **Not complete end-to-end** | Confirmed mappings and reviewed exports exist; dynamic reassembly requires test evidence. |
| Signed export and rights enforcement | **Yes** | **Yes, scoped development** | `dossier_export_release.py`, `export_rights_manifest.py`; external verification and lawyer acceptance open. |
| Final reviewed DOCX → exact final-PDF parity/approval | **No accepted end-to-end preflight established** | **No signed final-PDF approval gate** | New v4.1 requirement; actual uploaded/generated PDF, cross-format comparison, human exact-byte approval and later filing-byte matching need implementation and independent tests. |
| Decision-affecting ruleset registry/replay | **Partial** | **Partial** | Multiple versioned rules; unified digest and exact dependency manifest not established. |
| Independently labeled, rights-cleared NL/FR corpus | **Protocols/synthetic** | **No actual study** | Recruitment, permissions, adjudicated labels and signed evaluation evidence open. |

### 3.1 What the DeepSeek review got right—and wrong

- **Right:** modular/hexagonal boundary, typed source anchors, hash-validated source objects, separation of fidelity and semantic truth; `apps/api/main.py` is a **development-only demonstration** with caller-controlled `X-Tenant-Id`.
- **Not representative of current code:** claims that **no** signed bearer adapter, PostgreSQL adapter, private object storage, OCR pipeline or actual disputes verification exists. The repo contains `supabase_auth_verifier.py`, `postgres_case_repository.py`, `signed_supabase_originals.py`, `pdf_ocr.py`, and `domains/disputes/dossier_verification.py`.
- **Still true:** none of those code files alone certifies secure production deployment, licensed client-data use or real user accuracy. Do not infer the entire product from one tiny policy module or from `apps/api/main.py`.
- **Do not rebuild:** a duplicate JWT verifier, duplicate storage, new generic OCR pipeline or a second verification engine. Reuse and independently test existing signed pathways.

### 3.2 PR #209 — merged code and still-open acceptance

[PR #209](https://github.com/haytamAroui/caseproof/pull/209) was **squash-merged** into `main` at `af438c3771add91f3b4b83409d464a0c05031670` on 9 November 2026 Brussels time (GitHub timestamp: 8 November 2026, 23:59 UTC). Its final pre-merge GitHub Actions results were **26 passed, 9 skipped, 0 failed**; this is synthetic engineering evidence, not independent lawyer/security or client-data approval.

Its signed claim endpoint now binds to a named frozen snapshot instead of invoking snapshot-writing `DossierStore.load()`. It has additional rights/currentness tests and more conservative NL/FR abbreviations, but it remains **candidate discovery**, not independently measured claim recall. A fully reviewed explicit-reference ledger is not a fully reviewed claim ledger.

**After-merge gates still open:** independent review of real signed-actor permissions/revocation and snapshot races, complex DOCX story-region coverage and human claim adjudication, no-evidence/partial labeling, claim-to-evidence integration, and representative NL/FR testing. Merge is **not** pilot or production approval. This document does not retroactively treat those gates as closed.

---
## 4. Per-matter workflow — nine stages, with stage gates

Every stage is a **versioned operation** on a signed, currently authorized matter. Failure/unknown results must remain visible in later stages. A draft can contain uncited factual claims, and a cited reference may not relate to a factual claim; the two discovery streams are complementary.

### Stage 1 — Secure intake and scope declaration (deterministic)

**Input:** Existing conclusions/brief DOCX, separate Stuk/Pièce inventory, original PDFs/scans and optional approved translations. **Owner:** secure intake application.

**Actions:** Authenticate actor and matter; check current rights **per action**; apply file/bundle limits, content inspection and allowed MIME; preserve original bytes and SHA-256; record source role/version/size; read back and validate before a source is accepted; require explicit inventory confirmation and unresolved-exception handling; determine permitted processing, sharing and export rights for each source version.

**Output:** An immutable signed *matter input snapshot* with declared and excluded source versions, original hashes, inventory revision, permitted actions and outstanding exceptions. Intake success does not imply correct evidentiary identity.

**Acceptance:** Corruption, duplicate labels/ambiguous inventory, wrong org, revoked permission, storage write outcome unknown and oversized files cannot produce an accepted source or an unjustified complete inventory. Original source versions survive correction unchanged; derivative rights inherit applicable restrictions.

### Stage 2 — Parse, OCR and preserve representations (deterministic)

**Actions:** Process supported DOCX stories and original PDF pages under bounded isolated worker execution. Preserve PDF **physical page number** separately from printed labels and compiled-bundle pages. Record transformation/geometry version, exact source hash, parser/OCR engine/version, original-page positions, image/text-layer provenance, OCR word confidence where available, warnings and skipped content. Corrupt, encrypted, truncated and unsupported content fails closed or is explicitly excluded.

**Output:** Versioned representations plus a page/story coverage ledger; original view remains available to the authorized reviewer. Store sensitive OCR text and derived geometry only in approved custody with retention/deletion rules.

**Acceptance:** Synthetic and rights-cleared PDFs with mixed text/scans, rotated/cropped pages, page labels, OCR failures and scanned legal documents preserve original visual correspondence; a string found only in OCR never becomes verified solely on text match. A per-finding confidence/uncertainty projection must be demonstrably linked to the affected passage, not merely stored in an unused OCR sidecar.

### Stage 3 — Reference and claim candidate discovery (deterministic first)

**Actions:** Reuse `docx_reference_discovery.py` for Stuk/Pièce references. Separately segment bounded DOCX story regions into **candidate** propositions. Extract dates, amounts, parties/name candidates, article references, qualifiers, explicit citations and negations as advisory lexical attributes; do not label these statements true or legally relevant. Allocate snapshot IDs, stable identical-input locators and uncertain-boundary flags. Provide lawyer split/merge/exclude controls under versioned receipts later, not a silent automatic merge. Index authorized exhibit passages with source version, page/representation geometry, offsets and extraction limitations.

**Output:** Frozen claim-candidate inventory, detected references and a separate honest coverage ledger.

**Acceptance:** NL/FR abbreviations, multi-clause propositions, decimal/percentage formatting, table cells, footnotes, tracked revisions, duplicate passages, unsupported stories and long/partially omitted DOCX demonstrate stable same-input IDs, explicit omissions and no false completeness. `claim_classification` defaults to `NOT_ASSESSED`; independently measured recall is still **unmeasured** unless a labeled set exists.

### Stage 4 — Evidence discovery and optional model suggestions

**LLM-off baseline:** Given a claim and *explicit authorized matter scope*, retrieve bounded lexical candidate passages from a frozen index. Every hit includes original document ID/version/hash, representation, physical page, locator, passage digest and source quality. Return no-hits, omissions, truncation and inaccessible sources explicitly. Provide manual source/page selection for cases lexical search misses.

**Candidate selection:** Cross-language search **cannot be solved merely by LLM reranking** when relevant French passages never enter the Dutch query candidate set. If approved and evaluated, add a separately versioned multilingual retrieval method (e.g., local or contracted multilingual embeddings/query expansion), combine lexical and semantic candidates, deduplicate and then rerank. **An embedding index is an independent processing/data-rights decision**, not automatically permitted because an LLM feature is enabled.

**Optional model:** Only after per-matter policy/processor approval, send **bounded, authorized, frozen candidate passages**, not all exhibits or unapproved documents. Requesty or another explicitly approved adapter may propose relevance ordering, paraphrase correspondence, qualifiers, negations or contradictions. No external tools, unrestricted retrieval, automatic evidence writes or implicit fallback. Validate response structure, source IDs, source version hashes, and output limits; disregard invented anchors. Store minimal encrypted/protected model provenance, including exact candidate-set digest and uncertain request outcomes.

**Output:** Candidate list and separate model suggestions, **never verified evidence**.

**Acceptance:** Wrong-matter, revoked actor, substituted source, staleness between authorization and response, prompt-injection text, unknown model outcome and empty/partial retrieval cannot disclose data or upgrade status. Log no raw confidential passages in generic telemetry. Evaluate top-*k* recall against independently anchored NL/FR passages.

### Stage 5 — Deterministic kernel checks

**Actions:** On a *selected claim–source link*, evaluate byte-hash and source-version integrity, confirmed exhibit identity, independent physical page mapping, representation/geometry lineage, exact quotation/value match **only when applicable**, and OCR/visual uncertainty. Duplicate quotations and conflicting source versions must not resolve to an unjustified pinpoint. Never decide semantic entailment or legal sufficiency.

**Output:** Independent typed technical observations, `NOT_ASSESSED` and conflict reasons, frozen source anchors, and an explicit applicable/non-applicable policy for literal matching.

**Acceptance:** Wrong source, moved page, duplicate quote, missing printed-page mapping, OCR-only match, edited source and cross-language paraphrase cannot yield an unjustified technical `EXACT`. A human-supported paraphrase must be possible **without** asserting literal equality.

### Stage 6 — Reconciliation and claim-level coverage

**Actions:** Join the claim inventory, reference observations, candidate sets, selected source links, technical findings and model proposals **by exact snapshot identities**. Deterministically flag missing/extra amounts, numbers, dates, named entities, article citations, negations and qualifiers as **review warnings**, not fabricated contradictions or machine-certified legal outcomes. Handle multiple sources per claim and contradictory sources. Keep “not searched”, “searched/no hit”, “source unavailable”, “partial scope”, “candidate rejected” and “human decided” distinct.

**Output:** Two honest review views: (a) reference review and (b) claim review, with separate coverage denominators, stale counts and exclusions. A projected evidence table may be produced from these already-grounded links; do not imply this adds a chronology-generation engine.

**Acceptance:** No-hit cannot become “false”; candidate truncation cannot be reported as exhaustive retrieval; an unlinked claim stays pending/not located, and a fully reviewed set of explicit exhibit citations does not automatically mark all factual claims reviewed.

### Stage 7 — Reviewer workspace, Add Fact Cite and Word channel (human)

**Evidence-first UI:** Show preserved original source/page or authenticated source representation, page labels and affected OCR uncertainties **before** model suggestions. Display claim/context and separate technical badges; no preselected confirm or bulk semantic confirmation. Offer `Support`, `Qualify`, `Contradict`, `Inconclusive`, `Reject candidate` and `Defer` according to a reviewed state model. Store rationale, reviewer identity and version-bound reviewed source regions. Explain ambiguous source matching and omitted evidence.

**Add Fact Cite:** Only an **explicitly chosen, authorized and current** candidate link may produce a reference (Stuk/Pièce) to the exact original page. The insertion should support a format-aware DOCX round trip, preserve existing content/OOXML, and return a new draft version requiring appropriate recheck. Do **not** require semantic `SUPPORTED` for exploratory insertion unless the actual UI explains its pending nature; where a citation is presented as reviewer-confirmed, human confirmation is mandatory.

**Two Word milestones:**

- **A. DOCX round trip:** import or export corrected/annotated DOCX; preserved structure/relationships and working original-page hyperlinks; verified save/reopen in actual compatible document editors.
- **B. Native Word task pane (separate):** signed auth and permissions, stable selection/range mapping, safe user-triggered insert, concurrency/coauthoring behavior, undo, save/reopen, logout/revocation, desktop Word host/version evidence and fail-closed ambiguous edits. Synthetic Office API tests are necessary but insufficient.

**Acceptance:** A reviewer can locate actual original evidence from the claim, reject every proposal, add a permitted source, record an attributable review, edit the DOCX and recheck the new version. No link or human attribution is silently carried to an unmatched version.

### Stage 8 — Recheck and deterministic replay

**Actions:** Recheck every affected claim/link against current preserved originals, inventory mapping, source and draft versions, derived representation/index snapshots, rule registry and stored proposal set. For an **unchanged fully frozen input**, deterministic calculations must reproduce their observations without a model call. Changed dependencies are recorded as `STALE`/`SUPERSEDED`, with an auditable diff and a new explicit evaluation for affected proposals or links. Recheck never silently transfers prior human confirmation to a different claim or source passage.

**Acceptance:** Re-running an identical pinned snapshot is stable; changing a source, draft, page mapping, inventory confirmation or ruleset invalidates the relevant receipts/links; two concurrent reviewers or a lost acknowledgment cannot accidentally confirm stale evidence. Idempotency keys and snapshot preconditions are enforced.

### Stage 9 — Signed export, final-artifact preflight and external verification

**Artifacts:** Scoped reviewed DOCX (and optional linked PDF), reference findings report, **separate** claim review/coverage annex, Stuk/Pièce inventory/index, selected original-page links, reviewer receipts, decision-affecting ruleset digest and exact versioned source/representation manifest. Model-suggested and human-confirmed states are plainly labeled.

**Release:** Apply fresh source-version rights, current grants, approved action, complete/partial release policy and visible exclusions. A partial report may be exported **only** with explicit partial acknowledgment where policy permits; never label its review complete. Preserve issued artifacts/release manifests as versioned outputs.

**Verifiability:** Specify a verifiable signing envelope, canonical serialization, key ID/rotation/revocation, timestamp, manifest hash, scope and authorized historic record retrieval. Validate actual downloaded/printed links on real DOCX/PDF viewers. QR verification is **deferred** until the verifier safely enforces access and records retention/expiry; no public enumeration of matters or sources.

**Acceptance:** Signed artifact and source hashes round-trip, wrong-version links fail, unauthorized source access is denied, stale/partial review cannot masquerade as complete, and an authorized independent verifier can reproduce the technical integrity check. An audit signature is not proof of legal truth, evidentiary admissibility or actual filing.

**Stage 9A — Reviewed export:** Issues a scoped, rights-gated reviewed DOCX/report with its original/source/review/manifest digests. This alone is **not a filing-ready PDF approval**.

**Stage 9B — Final Artifact Verification (conditional P0):** Where CaseProof labels an exact PDF `READY_TO_FILE`, compare it against the approved DOCX and frozen reviewed snapshot under Section 2.6; show the exact rendered PDF to the authorized lawyer; refuse approval on material discrepancy or incomplete coverage; and bind an explicit approval receipt to the exact PDF SHA-256. Recheck current permissions and version bindings. Any subsequent byte change revokes the applicability of that approval. Non-filing pilots must state `FINAL_PDF_NOT_CHECKED` rather than implying safe filing.

**Stage 9C — Filing acknowledgment (not part of initial pilot):** If separately authorized evidence of actual submitted bytes later exists, check the **submitted PDF hash** against the approved PDF hash; otherwise report `ACTUAL_FILING_NOT_VERIFIED`. CaseProof does not file court documents or guarantee what a clerk received.

### Opponent-brief mode — shared machinery, separate acceptance

Opponent mode **reuses** intake, claim detection, search, technical checks and reviewer UI, but it is **not zero additional architecture or risk**. Require an expressly authorized opponent filing and permitted reference corpus, distinct matter/source scopes, correct attribution (“opponent asserted”), separate search-coverage limits, counter-evidence handling and safe output wording. No implication that undiscovered evidence proves fabrication. Deploy only after separate policy, privacy and reviewer-evaluation acceptance.

---

## 5. Retrieval, authority and optional LLM boundaries

### 5.1 Two execution profiles

| Capability | LLM OFF — required baseline | LLM ON — optional, gated |
|---|---|---|
| Intake, original hashing, rights | Full | Same, no elevated permissions |
| Parser/OCR, physical-page mapping | Full where local worker is available | Same |
| Explicit Stuk/Pièce detection | Full | Same |
| Deterministic claim candidates and manual correction | Full | Same plus untrusted model classification proposals if approved |
| Source search | Authorized bounded lexical/manual selection | Lexical plus **separately approved/evaluated** cross-language retrieval and reranking |
| NL/FR paraphrase support | Manual human examination; no model suggestion | Suggestions only; originals shown |
| Qualifier/contradiction suggestions | Deterministic warning terms; human decision | Extra model proposals, never authoritative |
| Source/page/literal checks | Same deterministic kernel | Same deterministic kernel |
| Human review, DOCX Add Fact Cite, recheck, signed output | Full, where each feature is actually implemented/accepted | Same; no new approval shortcuts |

**Note:** “LLM off” means **no external language-model calls**. Local OCR remains an independent deterministic/document-processing capability, subject to its own sandbox/egress rules. “LLM on” is not blanket authorization to upload sensitive data or create embeddings at an external provider.

### 5.2 Requesty implementation rules

1. Reuse `apps/api/requesty_extraction.py` and proposal-only contracts; never introduce a parallel unmanaged provider client.
2. Diagnose the documented `OUTCOME_UNKNOWN` manual live request using provider-side usage/billing and sanitized telemetry; **do not blindly retry**.
3. Require a named concrete model/version, approved hosting location, exact input/proposal schema, bounded budget, no tools/fallback and a consented processor policy.
4. Take only frozen authorized candidates and minimal context; evidence snippets are **untrusted data**, not model instructions.
5. Validate that returned IDs, hashes and passage quotes resolve to the requested snapshot; ignore hallucinated or stale references.
6. Record invocation outcome, input/prompt/model/rules digests and minimal protected output. Unknown execution and refusals yield no positive finding.
7. Compare against the LLM-off baseline using independently labeled NL/FR candidate retrieval and reviewer metrics before making quality claims.

### 5.3 Ruleset registry and reproducibility

Use a **semver-versioned, canonical decision-ruleset registry** for rules and thresholds that affect observations, plus a cryptographic digest of its resolved content. Keep secrets, deployment runtime constants, networking timeouts, API endpoints and unrelated security settings **out** of this registry.

**Deterministic replay manifest:** original draft/exhibit bytes and SHA-256; exhibit inventory and confirmed mapping revisions; parsed/OCR representation IDs and config digests; search corpus/index and candidate ordering; source locator/coordinate contract; ruleset content digest and engine version; claim segmenter version; selected evidence links; stored model proposals and input hashes where relevant; human decision receipt identity; timezone/canonicalization version where ordering matters.

**Replay tests:** Given identical frozen inputs, canonical outputs agree under documented deterministic behavior. If a dependency changes, the dependent observation becomes stale; a new index/query/model run is **new evidence discovery**, not replay. No automatic restoration of stale human approval.

---
## 6. Privacy, security, custody and deletion — mandatory pre-pilot gate

The existing [SEC-01–SEC-16 checklist](https://github.com/haytamAroui/caseproof/blob/main/docs/security/PILOT_DATA_SECURITY_GATE.md) is the **source of control requirements**, not this specification's substitute for legal/security approval. Confidential legal evidence is **blocked** from an unapproved environment even when the software passes tests, the files are redacted, or the provider advertises EU hosting.

### 6.1 A deployable data-flow decision must identify

- **Actual actors and authority:** firm/client as appropriate, data controller/processor roles, legal/professional-secrecy basis, firm permission, third-party rights and per-matter sharing/processing/export limits.
- **Actual environment:** source location/region, Supabase and network path, service/API region, isolated OCR worker, logs/telemetry, key custody, backups/retention, access and incident owners. A localhost web/API + Supabase backend is **not** fully local/offline.
- **Optional AI:** named Requesty/model route or approved alternative; provider and subprocessors; input fields; EU region vs actual onward transfers; DPA/contract terms; training and retention restrictions; abuse-monitoring logs; deletion mechanics; disabling and revocation. **No document bytes or derived confidential text leave an approved boundary before signoff.**
- **All derivatives:** extracted passages, OCR words and crops, embeddings/indexes, model prompt/response records, candidate claims, semantic proposals, human receipts, downloaded DOCX/PDF and reference manifests. Each has the same or stricter sensitivity controls as its parent as appropriate.
- **Rights inheritance:** a derived document may not bypass a parent's processing/export restrictions merely because it has a new hash or version.

### 6.2 Retention and deletion policy (additions beyond v3)

| Data class | Required design/acceptance rule |
|---|---|
| Immutable original and version ledger | Client-specific contract/legal hold; auditable authorized delete/offboard path with any lawful exceptions documented. |
| OCR/derived text, crops and indexes | Rebuildability and TTL policy; purge on permitted source deletion/revocation, and test that stale links do not reveal cached excerpts. |
| Embeddings and model inputs/outputs | Approved processor and geography; minimum required retention, encryption, access audit, no generic logging; index deletion and cache invalidation evidenced. |
| Reviewer decisions and signed receipts | Protect provenance, distinguish retention from immutable *display* claims, document how retention/legal holds and erasure requests interact. |
| Exports and Word local downloads | Server revocation **cannot revoke an already downloaded file**. Warn user; define local custody and recipient access expectations. |
| Final-PDF candidates, render diffs and approval receipts | Treat as confidential derivatives inheriting restrictions; store exact PDFs and comparison summaries only in approved custody; retain/revoke per policy; do not log complete final briefs, visual diffs, access URLs or signatures. |
| Provider backups, analytics and incident logs | Explicit retention, legal grounds, subprocessors and realistic delete/restore/backup-expiry evidence; unknown stays unknown. |

**Must-test security properties:** cross-matter and same-org permission denial, revocation at start/mid-response, source-rights downgrade, prompt injection in documents/OCR, ZIP/PDF bombs, parser network egress, output XSS, untrusted hyperlinks, signed URL expiry, hidden logs, duplicate/lost writes, derivative-rights inheritance, retention/legal-hold/restore and protected receipt lookup. Use real enforcement checks; a mocked denied request is not enough to declare a deployment isolated.

**Pilot approval record:** Exact commit/environment/region, data class, approved provider/subprocessors and transfers, SEC-01–16 decisions, professional-secrecy/privacy reviewer, security reviewer, firm sponsor, intended tasks and dates, deletion/incident plan, and signed allowed-use record. A blanket “NDA signed” is **not** enough to authorize all processing.

---

## 7. Gold set, falsification, evaluation and human study

### 7.1 Three deliberately different evidence sets

1. **Repository synthetic regression set:** deterministic NL/FR/EN examples, seeded wrong page/quote/date/amount, duplicate source, OCR uncertainty, prompt injection and omitted claim. Use for CI and code regression, **not** external accuracy claims.
2. **Independent annotated holdout:** rights-cleared genuine-format DOCX/inventory/PDF data, with actual original-page and passage annotations by qualified reviewers. Hide ground truth from engineers/model prompts and measure full class denominators. A small 3–5 dossier set is **exploratory**, not statistically representative.
3. **Controlled practitioner pilot:** 2–3 interested firms where feasible, independent participating lawyers, permissions and approved deployment. Collect actual work outcomes; do not conflate a single volunteer's observations with market acceptance.

**Corpus composition:** Dutch, French and mixed NL/FR; clean reference controls and seeded known-bad errors; uncited factual claims; same numbers in different contexts; wrong source version and duplicate passages; fabricated page, missing/changed qualifier or negation; OCR scans with mixed text layer; physical/printed/bundle page discrepancies; Word tables/footnotes/revisions/long clauses; opponent assertions if separately authorized.

### 7.2 Metrics — with denominators, baselines and uncertainty

| Layer | Metrics | Must disclose |
|---|---|---|
| Reference/claim discovery | TP, FP, FN, recall, precision by NL/FR and story region | Independent gold claim/reference denominator; unsupported/unscanned part count; no TN/FPR invention. |
| Evidence retrieval | Recall@1/@5/@10, top-k source/version/page correctness, duplicate handling, query latency | Corpus/index omissions, source availability, no-hit rate, cross-language cohort, truncation. |
| Kernel checks | Exact quote/value detection, wrong page/source detection, false technical confirmation, OCR abstention | Number of cases actually assessed, ambiguous anchors, visual comparison coverage. |
| LLM proposals | Candidate ranking gain vs lexical baseline, invented-source rate, misattribution, qualifier/negation warnings, cost/latency | Full model/version/prompt/corpus hashes, outcome unknown, provider requests; **not truth**. |
| Human safety | **False-confirm rate**: known wrong/unsupported suggestions accepted ÷ independently known wrong/unsupported suggestions reviewed; missed-error rate; inter-reviewer agreement | Review condition, false-confidence cases, seeded and genuine examples, independent adjudication. |
| Lawyer productivity | Median/dispersion of time per task, navigation and edit time, new errors introduced, work completed, repeat willingness | Baseline tasks, role, order, familiarity, environment and actual seconds. |
| Final artifact preflight | Rate of older/wrong PDFs correctly rejected, material citation/number/negation change detection, false `MATCH`, missed visual differences, abstentions and exact-hash approval integrity | Adjudicated pairs of approved DOCX and candidate final PDFs; conversion path, PDF parsing/OCR limitations, page/story omissions and reviewer overrides. Separate actual-filed-byte comparison where evidence exists. |
| Commercial acceptance | Paid/conditional written commitment, willingness to reuse, objections, follow-up frequency | Actual authorized signer, price/conditions, alternatives and non-buyers. |

**No automatic perfect-accuracy gate:** “Catch every gold error” in a tiny set encourages over-flagging and false safety. Before the independent evaluation, specify per-class minimum sensitivity/precision, acceptable uncertainty, maximum false confirmations and stop conditions with the firm/independent reviewer. Report confidence intervals only where sample size and sampling justify them. A measured failure can lead to `REFINE` rather than a deceptive pass.

### 7.3 Human-study design

- **Engineering baseline:** Run exact frozen cases with LLM **off** and on, compare model/retrieval outputs; no human carryover confound.
- **Practitioner study:** Counterbalance **manual**, **CaseProof LLM-off**, and **CaseProof LLM-assisted** conditions across matched cases/reviewers. Do not make the same lawyer first study a specific brief without assistance and then repeat **that same brief** as the claimed AI benefit; memory changes the outcome.
- Randomize or counterbalance task order, capture actual on-screen originals shown and final artifacts, and keep independent known-bad labels concealed from the participant.
- Require reviewed source links rather than treating agreement with an AI proposal as proof. Measure “correctly rejected unsupported suggestion” as well as missed errors and reviewer time.
- Use actual NL/FR practitioners to judge language/legal relevance, with third-party adjudication when reviewers disagree.

### 7.4 Stop conditions and pilot decision

**Immediately stop/contain** on cross-matter data exposure, unauthorized AI/OCR egress, unsafe source replacement, stale or wrong-source confirmed output, privacy rights failure, incorrectly portrayed complete review, missing permission, a known unsupported claim represented as technical/semantic system truth, **or a mismatched/stale/incompletely compared PDF labeled `READY_TO_FILE`**.

**Exploratory commercial target from v3:** discover real previously missed problems and obtain at least **two documented paid/conditional pilot commitments** from qualified lawyers/firms. This is a proposed decision threshold, not proof that two commitments exist or a substitute for safe technical operation.

**Possible outcomes:** `PROCEED` if repeated pain, demonstrable safe usefulness and credible payment; `REFINE` if the work is useful but retrieval/UI/price/security is wrong; `RECONSIDER` if frequency/ROI is poor. Synthetic CI alone cannot decide.

---

## 8. Implementation sequence — gaps only, preserve working code

**No implementation is authorized by this Markdown alone.** If the owner approves execution, change the smallest existing layer, add independent evidence, and avoid creating parallel engines. Preserve `main` and previous receipts until each PR passes review.

| Order | Workstream | Concrete action | Merge/acceptance gate |
|---|---|---|---|
| **0a** | Rights & recruitment | Begin approved firm outreach; rights-cleared corpus and privacy/security architecture review in parallel | Written permissions; named reviewers; no confidential upload until signoff. |
| **0b (P0)** | Post-merge PR #209 acceptance | Re-verify the merged signed read contract and coverage semantics; test real-signed actor, stale rights, DOCX stories and no model egress | Independent review and negative signed-user evidence. **Merge/CI alone does not close this gate.** |
| **1 (P0)** | Claim identity/coverage | Formalize `ClaimUnit`, versioned story locator, omissions, human split/merge/exclude, revised snapshot binding | Independently reviewed contract; identical-input stable IDs, edits invalidate/link conservatively. |
| **2 (P0)** | Evidence link model | Add source-bound candidate/link entities without duplicating kernel; preserve one-to-many/many-to-many relationships | Source/version/representation/page/hash integrity tests; permission and stale negatives. |
| **3 (P0)** | Signed per-claim lexical search | Adapt authorized evidence search to existing signed dossier and rights path; frozen index and source provenance | Real signed-user test, current-grant before/after, missing/duplicate pages, no-match/partial not disproved. |
| **4 (P0)** | Claim and reference reconciliation | Connect selected evidence links to technical checks and human review; separate denominators in UI/release | No false complete review; no model promotion; human statuses distinct from literal fidelity. |
| **5 (P1)** | Add Fact Cite / DOCX | Explicit human-selected Stuk/Pièce source/page insertion; new version; recheck; valid hyperlinks | Actual authorized original page; DOCX save/reopen; no unintended mutation or stale link. |
| **6 (P1)** | Ruleset, replay, receipts | Canonical decision-affecting registry/digest and exact dependency ledger; preserve historical receipts | Same frozen inputs reproduce checks; changed inputs stale; authorized external verifier negative tests. |
| **6b (conditional P0)** | Final Artifact Verification | On a separately authorized generated/uploaded final PDF, compare against the approved DOCX/snapshot, inspect substantive and visual differences, and obtain exact-PDF-hash human approval | Old-draft PDF, changed citation, negation, number, missing footnote, OCR failure and altered post-approval PDF cannot pass or retain `READY_TO_FILE`. Deferred non-filing pilots must explicitly label `FINAL_PDF_NOT_CHECKED`. |
| **7 (P1)** | Word channel | Complete actual host pane auth, permissions, edit/undo, reload/coauthoring safety, save/reopen | Real Word desktop host/version, signed source, denial and recovery tests. **Not automatically first-pilot blocking.** |
| **8 (P1/P2)** | Exhibit production | Preserve confirmed Stuk/Pièce mapping and add numbering/combined exhibits incrementally | Independent page/index consistency, permitted derivative, original preservation and file-size limits. |
| **9 (P2, gated)** | Optional multilingual retrieval/Requesty | First prove candidate generation recall; diagnose Requesty `OUTCOME_UNKNOWN`; then apply approved reranker | Rights/DPA/retention, model schema/telemetry, LLM-off parity, NL/FR eval improvement, injection tests. |
| **10 (external)** | Evaluation/pilot | Run independent falsification, human study and paid-pilot request | Measured results, stop conditions, actual signed partner evidence; no synthetic claims of approval. |

**Parallel dependencies:** Recruitment, permission clearance and security review start immediately, even while draft PR #209 is repaired; product validation must not be deferred until all engineering is complete. Engineering can safely use **synthetic** data while legal approval is open.

### 8.1 PR #209 — post-merge regression and independent acceptance

1. Verify the merged `GET` uses existing authenticated frozen-snapshot retrieval, not `DossierStore.load()`. Assert **no new snapshot RPC** on read and no stale/readback bypass; keep this as a post-merge regression test.
2. Expand segmenter fixtures beyond `Art. 12` and `M. Dupont`: `Mme`, NL `art.`, legal sections, monetary decimal punctuation, page references, dates, enumerations, long and multiple claims, tables, footnotes and revisions. Where safe segmentation is impossible, mark a boundary as ambiguous or unscanned; do not manufacture precision.
3. Freeze the status/lineage representation; ensure original source version, region and parser version can be recovered, and bound all returned candidate text to a current signed snapshot. Avoid treating a “hash-looking string” alone as full source attestation.
4. Prevent oversized output and unbounded serialized candidate text; apply response budgets, content security headers and no-cache as appropriate.
5. Prove no model calls, no confidential-data egress, and no expansion of signed matter grants. Tests must include lost/expired token, same-org denied case, revoked actor, replaced original, stale inventory and unchanged receipt states.
6. Explicitly keep `claim_review_coverage` unmeasured/partial pending a later claim ledger. **Do not add a superficial `verified` property** just to align with the new workflow text.

**Merged-code note:** PR #209 is no longer awaiting merge. The six checks above are continuing independent acceptance criteria; they must not be described as already independently accepted merely because the code and CI were merged.

### 8.2 Avoid the DeepSeek-induced rebuild trap

`apps/api/main.py` is a demo adapter. The full signed journey is composed elsewhere. Do **not** “fix missing auth/OCR/Storage” by implementing copies of existing `SupabaseAuthUserVerifier`, `SignedOriginalsStorage`, `LocalPDFOCR` or `DossierStore`; instead audit their live wiring, failure modes and scope-specific acceptance. Keep the kernel a logically isolated package inside the modular monolith unless measured tooling/ownership requirements justify separate distribution.

---

## 9. Twelve-week *planning* calendar (not a release promise)

| Window | Engineering lane | Independent firm/security/evaluation lane | Exit criterion |
|---|---|---|---|
| **Weeks 1–2** | Audit exact head; PR #209 read/write fix; claim identity/coverage contract; replay/ruleset design | Recruit firms, classify data/rights, choose approved custody/OCR/LLM options; assemble synthetic/adjudication protocol | Reviewed contracts, no open P0 semantics, synthetic safe route. |
| **Weeks 3–4** | Versioned claim/link entity; signed lexical per-claim search; rights/currentness tests | Independent label template; secure corpus intake prep; firm workflow observations | One claim → authorized candidate original page → manual selection, without model. |
| **Weeks 5–6** | Reconciliation, separate claim/reference review status, initial claim evidence table | Begin blinded synthetic/genuine-format falsification; privacy review decision | No false `COMPLETE`, stable source link, false-confirm safety tests. |
| **Weeks 7–8** | Add Fact Cite DOCX save/reopen, exact-snapshot recheck, ruleset digest/manifest; design final-PDF parity and exact-byte receipt contract | Pilot readiness/real rights signoffs where available; collect baseline manual task time | Complete synthetic LLM-off lawyer task end-to-end; correct original page in artifact; approved parity test design. |
| **Weeks 9–10** | Final-PDF preflight prototype and negative synthetic older-draft/changed-PDF tests where prioritized; Word host and Stuk/Pièce numbering if capacity allows; stabilize security/recovery | Independent NL/FR evaluation and human study under approved data boundary | No false `READY_TO_FILE` on tested mismatch; exact PDF review required before any file-ready feature is accepted. |
| **Weeks 11–12** | Optional LLM on only after model/privacy approval and retrieval baseline; export verifier tests | Counterbalanced off/on review study; paid/conditional pilot asks and stop/go decision | Evidence-led `PROCEED/REFINE/RECONSIDER` recommendation, **not automatic launch**. |

**Scheduling rule:** Week numbers are coordination windows. If customer authorization or real Word host acceptance slips, record blocked status and cut optional scope; **do not** claim a completed pilot, declare a feature accepted on synthetic tests, or waive privacy/security gates. An LLM-off pilot can proceed without Requesty after exact-env data-use approval; Word can remain deferred if independent web/DOCX delivery meets the lawyer task.

---

## 10. Acceptance ownership matrix

| ID | Work product / decision | Accountable owner | Required evidence | Status at v4 drafting |
|---|---|---|---|---|
| A00 | Commercial scope/ADR decision | Product owner | Explicit accepted v4 scope and any superseding ADR/roadmap change | **OPEN** |
| A01 | Merged PR #209 signed claim-read safety | Lead engineer + security reviewer | No-write read regression, rights/stale denial, NL/FR boundaries, independent review | **CODE MERGED**; 26 CI passed/9 skipped; external acceptance still **OPEN** |
| A02 | Claim-unit and coverage contract | Lead engineer + legal reviewer | Stable same-input IDs; offset/story/lineage exceptions; real format fixtures | **OPEN** |
| A03 | Source/version/anchor link contract | Evidence-kernel/domain lead | Typed independent findings; source/passages with version hashes; collision/ambiguity tests | **OPEN** |
| A04 | Per-claim signed lexical retrieval | API lead + security reviewer | Genuine signed actor, before/after grants, source-scope denial, Recall@k on known items | **OPEN** |
| A05 | Claim review and release separation | Review/release lead | Exact snapshot decisions; two coverage denominators; no false complete release | **OPEN** |
| A06 | Add Fact Cite DOCX | DOCX/Word engineer + lawyer reviewer | Human-selected page correct; actual DOCX save/reopen and linked original | **OPEN** |
| A07 | Ruleset and replay | Verification lead | Canonical digest; frozen replay; stale dependency tests | **OPEN** |
| A08 | Real Word host pane | Word integration engineer | Named Word desktop version, auth/undo/reopen/coauthoring negative tests | **OPEN**, optional pilot channel |
| A09 | Stuk/Pièce package production | Export engineer + NL/FR litigation reviewer | Correct numbering/index/actual pages; rights and PDF/DOCX integrity | **OPEN** |
| A10 | Requesty/provider and multilingual retrieval | Product/security/privacy owner + ML engineer | Approved processor terms; no tools; provenance, corpus recall and comparison | **OPEN**, optional |
| A11 | Independent falsification | Independent legal reviewer + QA | Source-labeled, rights-cleared NL/FR holdout; error-class denominators | **OPEN** |
| A12 | Human review experiment | Pilot lead + independent lawyers | Counterbalanced conditions; false-confirm metrics; actual time measurements | **OPEN** |
| A13 | Privacy/security deployment gate | Firm sponsor + privacy/security reviewers | SEC-01–16 decisions for exact build/environment/data class, DPA as required | **OPEN / NOT APPROVED** |
| A14 | Commercial pilot disposition | Product owner + participating firms | Real usage, workflow value, pricing/commitment evidence | **OPEN** |
| A15 | Final Artifact Verification / exact PDF approval | Export/DOCX engineer + security owner + independent litigation reviewer | Approved-DOCX vs wrong-version PDF, altered citation/number/negation, missing footnote/visual content, parser abstentions, exact-hash actor confirmation, mutation invalidation and current rights checks | **OPEN / NOT IMPLEMENTED**; mandatory before any `READY_TO_FILE` claim |
| A16 | Actual filing-byte correspondence (future, optional) | Authorized firm operator + audit reviewer | Actual uploaded or verified submitted PDF bytes match approved PDF SHA-256; reject mismatch, explicitly report unverifiable filing | **OUT OF INITIAL SCOPE**; do not imply actual filing from approval alone |

**Evidence rules:** Each row should eventually carry `OPEN / BLOCKED / EVIDENCED / APPROVED`, a named person, commit/environment, actual test/run or private evidence URI, date, negative-case result and independent reviewer signature where required. This table is **not** a self-attestation of acceptance.

---

## 11. High-risk failure modes and controls

| Failure mode | Severity for release | Control and must-have negative test |
|---|---|---|
| Candidate endpoint unexpectedly writes new signed snapshots | **P0** | Separate retrieval from processing; assert zero write RPCs for a GET. |
| Review is labeled complete though only citations were detected | **P0** | Separate claim and reference denominators, warn on unknown claim recall, scoped release. |
| Wrong source/version or page gets a confirmed link | **P0** | Exact original digest, inventory confirmation, page space, duplicate handling and reviewer inspection. |
| An OCR passage is elevated to authentic original transcription | **P0** | Visual original inspection, per-finding OCR uncertainty, representation-state/quality warnings. |
| NL→FR evidence never retrieved yet output implies no support | **P0** | No-hit-with-scope warning, manual selection, labeled cross-language retrieval recall before enabling. |
| An untrusted model passage changes a human/technical finding | **P0** | Separate proposal envelope; no tools; strict schema/source IDs; invariant and injection tests. |
| Stale claim maps to a new DOCX after edit | **P0** | Snapshot-bound IDs, conservative revision correspondence and stale-invalidation tests. |
| Rights-restricted derivative can be processed/exported | **P0** | Rights inheritance and signed server-side re-checks for new SourceVersions and export. |
| Confidential claim/embedding remains after deletion or revocation | **P0 for client data** | Custody, retention/deletion/backup policy and scoped access/egress tests. |
| LLM provider request outcome unknown; automatic retries duplicate egress | **P1** | Durable outcome-unknown record, provider telemetry check, no blind retry. |
| Citation links break on Word save/reopen or printing | **P1** | Real host/reader tests, scope-bound link resolver, separately accepted QR verifier. |
| An older, uncorrected PDF is selected after an approved DOCX review | **P0 for ready-to-file labeling** | Compare approved DOCX/review snapshot with exact final PDF; material citations and visual differences block `READY_TO_FILE`; human last-mile review. |
| A PDF is modified after lawyer approval or approval is mistaken for filing | **P0 for ready-to-file labeling** | Approval receipt binds exact PDF SHA-256; byte change makes it stale; actual filed-byte verification is separate and not inferred. |
| Human rubber-stamps wrong proposals | **P0 for pilot** | Seeded known-bad claims, no preselected confirmation, false-confirm measurement and stop threshold. |
| “All gold errors caught” achieved only by overwhelming false flags | **P1** | Per-class precision and workload/time metrics; pre-registered decision thresholds. |

---

## 12. Later modules — only after measured demand

1. **Legal-authority module (separate scope):** Check citation parsing, source existence, exact quote/pinpoint and subsequent treatment **as separate questions** using official or properly licensed databases with timestamped source snapshots. `NOT_FOUND` never proves a citation fake, and good-law status remains advisory. Verify Juportal, CURIA, HUDOC, official-data reuse and connector licensing before design. Prefer licensing/partnership to unauthorized scraping.
2. **Source-linked chronology:** Only after claim-evidence links and source-date accuracy are measured; generated events must retain original anchors and reviewer disposition.
3. **Ask My Docs / contradiction exploration:** New data-use, retrieval, model and evaluation boundaries. Avoid selling a chat response as confirmed evidence.
4. **Netherlands/France expansion:** A locale-policy and official-source strategy plus separate practitioner and data-rights evaluation, not just renaming labels.
5. **Opponent mode:** Shared engine, separately approved evidence universe and benchmark as specified in Stage 9 annex.

**Competitor note:** V3 lists Clearbrief, LexSelect and other citation products based partly on vendor/search summaries. Do **not** assert verified pricing, profit, market share or unique novelty from those summaries. A broader workflow may be commercially attractive, but commercial evidence comes from observed Belgian lawyer work and priced commitments, not inferred company valuations.

---

## 13. Unverified assumptions, decisions and release blocks

| Question | Current disposition |
|---|---|
| Can CaseProof find all factual propositions in a 150-page real NL/FR brief? | **Unverified**; candidate detection and reference recall must be measured separately. |
| Does full evidence retrieval cover all permitted sources with high recall? | **Unverified**; lexical adapter exists, signed claim retrieval and multilingual recall are incomplete. |
| Can an LLM reliably rank NL/FR supporting and contradictory passages? | **Unverified**; requires privacy gate, Requesty diagnosis, independent gold baseline and human evaluation. |
| Can a real Word task pane safely insert and reopen citations? | **Unverified**; synthetic Office API tests do not close real-host acceptance. |
| Is the exact pilot deployment authorized for confidential lawyer evidence? | **No approval evidenced**; SEC-01–16, signed rights, subprocessor/region and firm acceptance open. |
| Will lawyers pay for this workflow in Belgium? | **Unverified**; no qualified paid-pilot evidence is represented here. |
| Does an export signature prove factual/legal truth? | **No**; it proves only integrity/lineage within the documented, inspectable signature and source scope. |
| Should Word be required for the first commercial test? | **Owner decision open**; architecture allows web/DOCX-first, real Word as separate channel. |
| Should v4 replace ADR 0018 as commercial scope? | **Owner decision open**; a reviewed superseding ADR is required if scope changes. |
| Is PR #209 ready to merge? | **Already merged** into `main` at `af438c37`; remaining independent signed-rights, coverage and practitioner acceptance is **not established**. |
| Does v4.1 verify that a corrected DOCX is the PDF a lawyer will file? | **Not yet implemented/accepted.** Final-PDF parity plus exact-hash lawyer approval is P0 before any `READY_TO_FILE` state; initial non-filing pilot must say `FINAL_PDF_NOT_CHECKED`. |
| Can CaseProof prove the approved PDF was actually filed? | **No.** A future authorized filed-byte or trustworthy docket/submission receipt comparison is required; e-filing remains outside initial scope. |

### Formal decision to request before any new roadmap implementation

> **Approve v4 as the target technical contract for a narrowly scoped, evidence-first pilot, preserving existing signed code; authorize only audited gap implementation on reviewed branches; keep customer-data security/legal gates and any commercial-scope supersession separate.**

This is a **decision proposal**, not an approval recorded by this file.

---

## 14. Source register and change history

### Primary requirements and design source

- User-provided **`caseproof-final-workflow (3).md`** (v3): nine-stage flow, principles, build plan, LLM-off behavior, pilot proposal, acceptance owners and future modules.
- User-provided **`Texte collé(10).txt`** (DeepSeek codebase-only analysis): kernel strengths and development-only warnings; its blanket “missing auth/Storage/OCR” assertions contradicted by current code. External code claims are independently checked before inclusion.

### Current repository implementation evidence

- [PR #208 — duplicate pinpoint mapping fail-closed, merged](https://github.com/haytamAroui/caseproof/pull/208)
- [PR #209 — merged claim candidates and code audit](https://github.com/haytamAroui/caseproof/pull/209) (squash `af438c37`, 9 November 2026 Brussels time)
- [Claim discovery parser (PR #209)](https://github.com/haytamAroui/caseproof/blob/main/infrastructure/parsers/docx_claim_discovery.py)
- [Claim discovery tests (PR #209)](https://github.com/haytamAroui/caseproof/blob/main/tests/test_docx_claim_candidates.py)
- [Signed dossier journey](https://github.com/haytamAroui/caseproof/blob/main/apps/api/dossier_journey.py)
- [Reference discovery](https://github.com/haytamAroui/caseproof/blob/main/infrastructure/parsers/docx_reference_discovery.py)
- [Existing authorized lexical evidence search](https://github.com/haytamAroui/caseproof/blob/main/apps/api/litigation_evidence_search.py)
- [Requesty provider transport](https://github.com/haytamAroui/caseproof/blob/main/apps/api/requesty_extraction.py)
- [Core evidence source versions](https://github.com/haytamAroui/caseproof/blob/main/packages/evidence_kernel/domain/source_versions.py)
- [Core technical fidelity](https://github.com/haytamAroui/caseproof/blob/main/packages/evidence_kernel/domain/fidelity.py)
- [Claim-evidence ledger primitives](https://github.com/haytamAroui/caseproof/blob/main/packages/evidence_kernel/domain/finding_links.py)
- [Signed Supabase auth verification](https://github.com/haytamAroui/caseproof/blob/main/apps/api/supabase_auth_verifier.py)
- [Private originals Storage adapter](https://github.com/haytamAroui/caseproof/blob/main/apps/api/signed_supabase_originals.py)
- [PostgreSQL case adapter](https://github.com/haytamAroui/caseproof/blob/main/apps/api/postgres_case_repository.py)
- [Local OCR worker and word geometry](https://github.com/haytamAroui/caseproof/blob/main/infrastructure/parsers/pdf_ocr.py)
- [Release completeness and its limited denominator](https://github.com/haytamAroui/caseproof/blob/main/application/litigation/release_completeness.py)
- [Signed release/export](https://github.com/haytamAroui/caseproof/blob/main/apps/api/dossier_export_release.py)
- [Development Word add-in limitations](https://github.com/haytamAroui/caseproof/blob/main/apps/word_addin/README.md)
- [Pilot rights/security gate](https://github.com/haytamAroui/caseproof/blob/main/docs/security/PILOT_DATA_SECURITY_GATE.md)
- [Practitioner corpus/study protocol](https://github.com/haytamAroui/caseproof/blob/main/docs/pilot/P6_PRACTITIONER_AND_CORPUS_PROTOCOL.md)
- [Current commercial ADR](https://github.com/haytamAroui/caseproof/blob/main/docs/adr/0018-pre-submission-verification-freeze.md)

### Case study motivating v4.1

- *Farhat v. Cutera, Inc.*, U.S. District Court, Northern District of California, Case No. 3:26-cv-05674-TSH, **Order Discharging Order to Show Cause**, ECF No. 27, 28 October 2026, pp. 1–2 (two-page court PDF supplied with the CaseProof review). The order reports counsel's declaration that a corrected draft existed but an earlier version was converted and filed; the court discharged its order and declined sanctions at that time, while warning counsel to review the final filing. It **does not prove** that Legora generated each inaccurate authority, and the underlying motion/corrected drafts/redline were not part of the supplied PDF. The U.S. court's Rule 11 discussion is **not a Belgian legal obligation**.

### v3 → v4 change log

| Change | Reason |
|---|---|
| Explicit byte integrity **versus** correct exhibit identity | A SHA-256 match cannot authenticate a third party's evidence or select the right Stuk/Pièce. |
| Separate reference-review and claim-review completeness | Existing release policy counts detected references only. |
| PR #209 `GET` side-effect and segmenter fixes | Verified read endpoint calls snapshot-writing `DossierStore.load()`; naïve punctuation splits legal abbreviations. |
| Typed `ClaimUnit` / `EvidenceCandidate` / `ClaimEvidenceLink` / receipts | Make every stage interoperable without inventing a parallel kernel. |
| Separate frozen snapshot claim ID and cross-revision lineage | Versioned identity cannot promise stable IDs across arbitrary editing. |
| NL/FR retrieval **before** reranking | An LLM cannot rerank supporting passages missing from the candidate set. |
| Stronger OCR provenance and uncertainty projection | Word confidence in a sidecar is not automatically a visible, correctly bound warning. |
| Explicit search-scope/recall metrics | Fully scanned/indexed data does not prove a relevant supporting passage was found. |
| Ruleset digest limited to decision-affecting settings | Avoid an impractical “every constant in one registry” requirement. |
| QR verifier permissions, keys, expiry and retention | A printed code cannot safely promise public access to confidential sources. |
| Model, index, derived-record deletion design | Model proposals and embeddings create additional confidential artifacts. |
| Counterbalanced practitioner study | Simple LLM-off first, then on for the same reviewer/case introduces memory bias. |
| ADR/owner decision and release-blocking Word choice explicit | v4 cannot silently change accepted commercial scope or declare Word mandatory. |
| Corrected DeepSeek “skeleton” diagnosis | Current repo has auth, storage, PostgreSQL, OCR and disputes verification beyond the toy `main.py`. |

### v4 → v4.1 update log (10 November 2026)

| Change | Reason |
|---|---|
| New Section 2.6 and Stage 9B final-artifact preflight | The approved DOCX and the PDF actually intended for filing can be different versions despite correct underlying evidence checks. |
| Exact final-PDF SHA-256 and authenticated lawyer approval | Cross-format textual/visual parity and a reviewer's approval of **specific bytes** are different from general claim review or signed export. |
| Explicit `FINAL_PDF_NOT_CHECKED` and `ACTUAL_FILING_NOT_VERIFIED` states | Prevent a non-filing pilot, checked DOCX or approval receipt from implying the actual court submission was verified. |
| Conditional P0 readiness gate, tests, owners, privacy and roadmap | A filing-ready product claim must reject older, changed, unreadable or unapproved PDFs; no new e-filing or case-law verification scope is assumed. |
| PR #209 historical status corrected | It is merged with 26 green synthetic CI checks; independent acceptance and real-user validation remain open. |
| Source-scoped U.S. court example | The Farhat order demonstrates a possible last-mile version-control failure without proving which system generated every bad citation or changing Belgian-law requirements. |

---

**End of v4.1 (updated v4).** The immediate actionable engineering focus is **claim identity → signed evidence retrieval → versioned claim–source link → human decision → scope-safe release**, building on merged PR #209, with final-PDF parity as an additional **conditional P0** when any artifact is represented as ready to file. This is a requirements and acceptance document, **not evidence of deployed functionality or customer acceptance**.