# CaseProof — pre-submission exhibit verification: complete v1 user workflow

**Decision date:** 28 October 2026. **Authority:** [ROADMAP.md](ROADMAP.md), [ADR 0018](adr/0018-pre-submission-verification-freeze.md), [CONSTITUTION.md](../CONSTITUTION.md). This is the **product acceptance specification**, not a claim that any browser journey is already implemented, secure for clients, legally approved or commercially validated. [Historical Clearbrief-class workflow](https://github.com/haytamAroui/caseproof/blob/486b239926b681d76e1e3f79d30e3dc7098ab6d8/docs/PRODUCT_WORKFLOW.md) is superseded for launch scope.

**User job:** a Belgian civil/commercial litigator about to file conclusions checks whether detected `Stuk/Pièce` factual references point to the right preserved exhibit and correct page and whether an actual source representation contains the quoted text or appropriately matched number. The software reports located/matched, mismatched and unresolved references; an authorized lawyer alone decides semantic support and corrections. **No court filing, legal advice, case-law checking or legal-validity certificate.**

**First commercial experience:** web workspace, `upload → verify → inspect source → review → export`. Word is **not required** to perform this journey. Accept genuine DOCX and text/image PDF as bounded input formats, not as license to silently alter or regenerate legal conclusions. The supported subset of DOCX formatting must be declared.

## Inputs, exact coverage and output contract

| Artifact | Authority and handling | What absence means |
|---|---|---|
| **Conclusions DOCX** | Original preserved; identify checked draft version/hash and language; extract reference candidates from supported paragraph/table/footnote parts; provide unprocessed-structure coverage | Missing/unparseable draft blocks check and cannot become “zero findings” |
| **Inventory** | Upload separate inventory document or structured list; parse *proposals*, lawyer confirms `exhibit_id ↔ Stuk/Pièce alias`, order, amendments, page labels | No inventory → `NOT_IN_INVENTORY` or `NOT_ASSESSED` by declared scope; do not silently synthesize a definitive one |
| **Preserved exhibits** | One or more separately preserved originals, optionally an assembled bundle; content hash, version, physical page, OCR crop/representation, ingestion and authority metadata | An inventory label without authorized source = `SOURCE_MISSING`, not proof of late/noncommunication |
| **Optional existing bundle** | Source for bundle-page offsets; separate physical PDF / printed page / compiled bundle page mapping; never assume all three equal | Missing or conflicting mapping = `UNMAPPED` / `CONFLICTING` |
| **Output** | Per-reference findings + actual source link/crop + reviewer decision + scoped verification run record + annotated or corrected DOCX where safely supported | Incomplete or unsupported export must fail visibly and leave source draft intact |

Languages: support NL/FR citation labels and case text, including mixed-language documents. UI language, source language, draft language and output language are independent; no translation is treated as original evidence. EN UI/testing support can be retained, but full EN legal-domain feature parity is not a launch guarantee. Citation candidates without quotes still receive existence/page checks; all-zero-error controls can legitimately return no findings.

## User journey and transitions

### 0. Sign in, choose a permitted matter (M1)

**Action:** lawyer authenticates, chooses/creates a private matter, sees only permitted matters. No tenant/matter authority is taken from URL, DOCX, HTTP header or model output. Roles and permissions are current server-owned checks.

**User sees:** `Matter ready` or a concrete blocked reason; private files, source coverage and prior reviews belong only to that matter.

**Acceptance:** real signed user and same-org ungranted user must have different rights; denied/revoked/expired actor cannot inspect source, edit review, export or receive pending job results. Server restart preserves state. No customer data before security signoff.

### 1. Upload and preserve the source universe (M1)

**Action:** upload `conclusions.docx`, separately identifiable inventory, original PDF/text/scanned exhibits. Each original is immutable, SHA-256 checked on readback; never replace bytes in place. Keep PDF page 1-based display distinct from internal 0-based parser locator and from printed/bundle numbers. Upload and processing have stable operation IDs.

**User sees:** clear file types, accepted/rejected, pages processed, pages `needs OCR`, crop availability, originals vs generated text, duplicate labels, corrupt files, permissions and file budgets. Processing progress is not an evidentiary approval.

**Failure:** corrupt/password protected/oversize/unreadable/unsafe file stops only its affected scope; sources remain preserved with errors and remaining denominators. No invisible zero-page completion; retries/restarts reconcile persisted job state rather than duplicate sources.

### 2. Confirm the exhibit register (M1)

**Action:** CaseProof proposes Stuk/Pièce number, name, alias and source-version matches; the lawyer confirms or rejects independently of candidate OCR text. Source/exhibit internal ID stays stable across label renumberings. Separate `listed_in_inventory`, `source_in_custody`, `communicated_proven` and `filed_proven`, with the latter two never inferred from this workflow.

**Page contract:** physical PDF pages, printed labels and bundle positions are independent; a uniquely found exhibit can be `RESOLVED` even if its page is `UNMAPPED`. Reordering or replacing a source creates a new register revision and invalidates affected checks.

**Failure:** ambiguous aliases, multiple candidate files, missing source, wrong page space, duplicate label and no confirm permission require review; never choose a match because it has the highest OCR score.

### 3. Detect references in the draft and freeze the checked scope (M2)

**Action:** parse every supported DOCX content region and candidate legal-exhibit reference (e.g. `Stuk 4, p. 3`, `Pièce 7, p. 5`, aliases or references without pinpoint). Detect exact citation occurrence and its draft location; link each candidate to the confirmed register snapshot. User may add/correct missing reference detections without silently editing the original file.

**User sees:** total candidates detected, checked/not-assessed, checked source/page scope, reasons for omissions, unsupported footnotes/tables, and source completeness. If all references cannot be detected with required coverage, report explicitly.

**Failure:** an unmatched draft citation is not a pass. A no-citation/zero-quote draft is valid as an input, with `0 references detected` and its extraction limitations disclosed.

### 4. Run one source-bound evidence check (M2)

**Action:** a scoped deterministic pass checks exhibit existence, pinpoint mapping, exact literal quotations where applicable, and **only unambiguous same-role** values (amount/date/currency/unit/tax basis). Every candidate result carries exact original/representation identifiers, provenance, processing and rules version. No mandatory LLM, vector DB or agent loop.

**Four independent dimensions:**

| Dimension | Typed states | Authority |
|---|---|---|
| Exhibit identity | `RESOLVED`, `NOT_IN_INVENTORY`, `SOURCE_MISSING`, `AMBIGUOUS` | Server-confirmed source/inventory identity |
| Page location | `MAPPED`, `UNMAPPED`, `CONFLICTING` | Independent original/printed/bundle mapping |
| Text/value fidelity | `EXACT_MATCH`, `MISMATCH`, `OCR_UNRELIABLE`, `NOT_ASSESSED` | Reproducible source-bound checks with OCR abstention |
| Semantic support | `NOT_ASSESSED`, `CONFIRMED_SUPPORTED`, `CONFIRMED_QUALIFIED`, `CONFIRMED_CONTRADICTED` | **Human reviewer only** after contextual inspection |

**Critical distinctions:** `EXACT_MATCH` is not the truth of a claim, the authenticity of a document, or a semantic-support decision. `QUALIFIED` is not an OCR-confidence state. Unreviewed low-fidelity OCR requires `OCR_UNRELIABLE`, crop inspection and optional transcription correction linked to the original, not an automatic exact-match green status. Quote-free claims can still be checked for exhibit/page existence. Unknown VAT basis, negations, third-party allegations, different dates/roles and conditional text cannot be confidently auto-compared.

**Failure:** timeout, unavailable representation, source mismatch, stale register/draft, partial OCR or unauthorized scope becomes `NOT_ASSESSED`/specific unresolved state. A model suggestion never writes authoritative `CONFIRMED_*` support or reviewer actions.

### 5. Inspect each finding beside the actual source (M3)

**Action:** web results show an assertion/citation, detected reference, inventory identity, physical/printed/bundle page, immutable original viewer and cropped original image when relevant, plus extracted text **marked as derived**, with citations back to source versions.

**User sees:** sortable `needs attention`, `located/matched`, `mismatch`, `not assessable` categories without one global “verified” label. Default ordering prioritizes unresolved and actionable mismatches; a clean scoped run may show no errors. Every checked finding shows neighboring context and a direct reopen link; unavailable source or crop never becomes silently substituted OCR text.

**Failure:** broken link, crop not tied to correct page, incomplete coverage and mismatch between source hash and image prevents confirming that finding.

### 6. Human review and safe proposed correction (M3)

**Action:** authorized reviewer inspects original and context; chooses confirm support, qualify, contradict, dismiss mismatch, request more evidence or record a correction proposal with rationale. Human decision records exact current review/run/draft/source snapshot, actor, time and audit; a sole reviewer is labelled solo, not independent peer review.

**Correction:** produce a preview of exact original draft span and replacement; do not overwrite preserved original, alter opponent material, strip tracked changes or silently edit unsupported DOCX structures. Applying generates a new draft revision or an explicit annotated-only output; affected references are rechecked.

**Failure:** revoked permission, stale selection/changed draft, concurrent edit, ambiguous OCR, missing audit or unknown external acknowledgment blocks promotion/revision. A second retry must reconcile the first operation ID, not duplicate a decision.

### 7. Recheck, produce report and export (M4)

**Action:** re-run affected checks against the new exact draft/source/inventory snapshots; freeze a manifest and generate reviewed/annotated or supported corrected DOCX, a machine-readable run record and human-readable verification report. Export only after authorized reviewer and explicit export grant; no automatic filing/share.

**Report MUST include:** original and output hashes, artifact/document versions, source universe and per-page processing status, detected/checkable/not-assessed reference denominators, mapping and OCR uncertainty, exact source/crop locators, findings and human dispositions, unresolved/excluded items, engine/parser versions, timestamp, reviewer role and limitations. Do not call it a court certificate.

**Integrity:** generated outputs remain immutable, reopen actual DOCX and any PDF produced with an independent reader, verify targets and page links against exact manifest. Preserve known formatting, lists, tables, footnotes and tracked-change semantics within the published support matrix; refuse unsupported transformations. A completed report may list unresolved items; it never claims all evidence proved.

**Failure:** missing review, stale version, failed rendering/link verification, storage/audit failure, permissions revoked or unexplained scope changes block marked-current export. Prior exports remain attributable to earlier snapshots but are not re-certified after edits.

### 8. Download and hand off manually (M4)

**Action:** authorized lawyer downloads the exact reviewed output/report. Actual court filing, transmission and delivery receipt remain external human actions. In v1, copying to a recipient or e-Deposit submission is not a required app capability.

**User sees:** reviewed output version, source/check manifest, unresolved counts, who approved what, and explicit `NOT FILED BY CASEPROOF`. A saved download cannot be revoked retroactively; only hosted future access can be withdrawn.

### 9. Reopen the same matter on another day (M1–M4)

**Action:** sign in again, reopen original files, source map, checked draft revisions, reviewed findings and exported manifest after a cold process restart.

**Acceptance:** there is no implicit approval from past session tokens; revoked actors cannot reopen, and all data/review lineage remains reproducible for currently authorized actors.

## UI pages — minimum, no second word processor

| Screen | Actual purpose | Must-not-do |
|---|---|---|
| **Matters** | Authorized matters and source health | No cross-tenant source previews |
| **Upload & inventory** | Preserve DOCX/inventory/exhibits; confirm candidates and three page spaces | No invented inventory, authenticity or filing status |
| **Findings** | Per-reference states, source location, missing/partial coverage | No green global “all true” badge |
| **Review** | Side-by-side original crop/context, independent findings, human disposition/correction preview | No auto semantic confirmation |
| **Exports** | Exact reviewed DOCX and report, re-openable manifest, release failures | No court filing or legal certificate |

Use accessible keyboard navigation, screen-reader labels, stable focus, explicit status text (not color alone), reliable text scaling and NL/FR terminology. Partial source sets and empty states must be visible. Do not construct a proprietary Word competitor or force editing inside a new rich-text editor.

## One complete v1 launch acceptance (not currently passed)

A genuinely signed user in an approved staging environment:

1. Creates a restricted matter and imports a real-format synthetic NL/FR DOCX, inventory, text PDF and image-only scanned PDF; verifies preserved bytes/hash and per-page status.
2. Confirms exhibit identities and page spaces, including a uniquely resolved exhibit with **unmapped** pinpoint and a duplicate/ambiguous label.
3. Runs a comprehensive scoped reference check on correct, missing, wrong-page, mismatched-value, negative/conditional, zero-quote and unreadable items; sees complete denominators, original page crops and no false confidently mapped/matched findings in the fixed test set.
4. Reviews one uncertain OCR crop, records human confirmation or non-confirmation and makes a safe versioned correction; rechecks dependent reference(s).
5. Exports reviewed/annotated DOCX + scoped verification report; opens the **actual bytes** independently, checks source links/formatting, and confirms the immutable manifest.
6. Stops server, signs in again, reopens the same source/draft/review/output history; tests ungranted/expired/revoked actor denials, stale changes, interrupted jobs and failed audit.
7. Presents that real experience to practitioner reviewers; collects their measured time, corrections and objections separately from a legally/operationally authorized customer pilot.

**A passing synthetic path is not a sellable release.** Legal/confidentiality, hosting, operational resilience, customer authorization and commercial pilot gates remain independent. [M4 detailed output acceptance](m4/DELIVERY_ACCEPTANCE.md).

## Interface independence — optional channels never redefine v1

- **Web:** first full experience.
- **Word:** optional future client to start the same check from selected text, inspect crop, insert a source reference and recheck; [host contract](m3/WORD_INTEGRATION_ACCEPTANCE.md) remains an engineering reference, **not launch acceptance**.
- **API:** mandatory first-class case-scoped contracts for all clients; current signed application authorization and durable job boundaries are the authority.
- **MCP:** future thin adapter to authorized API actions, not a new authority/control plane, mandatory daemon or direct access path to original bytes. No external tool call creates legal or review approval.

## Privacy, lawful processing and trust

- Initial demo uses synthetic or explicitly rights-cleared fixtures. A redacted client dossier is not automatically anonymous or permissible; real files require assessed professional secrecy, GDPR, signed agreements, appropriate closed-processing assurance, retention/deletion and security approval.
- Cloud location, pseudonymization or zero-retention **alone** does not prove professional-secrecy compliance. Never route confidential evidence to unapproved remote inference, trace/logging or support tools.
- Original custody, inference/OCR location and audit/provenance are separate ports; firm-controlled/local processing is a possible later deployment based on customer needs, not a current claim.
- No legal-advice output, automated Book 8 judgment, procedural deadline status or AI Act certification. Intended use, applicable transparency and high-risk classification require legal review when relevant. Refer to [source and law notes in roadmap](ROADMAP.md).

## Commercial experiment — independent of feature shipping

**Five weeks from the first practitioner conversation**, not a preannounced launch date: five disconfirming conversations, two workflow observations, 3–5 controlled dossier evaluations only if justified, one priced signed paid/conditional proposal. Record baseline and assisted total time, false flags and review time, `0/N` false matched/mapped observations, no material missed seeded errors except explicitly unresolved, reviewer-requested report and deployment requirements, price and decision. Do not encourage lawyers to stop sampling checked results; measure *calibrated* trust.

**Proceed** only with repeated pain, satisfactory safe verification and a credible commitment; **refine** workflow/pricing/deployment if value exists; **reconsider niche** if rare/unpaid/adequately solved. No automatic product pivot based on fresh competitors. [M5 in roadmap](ROADMAP.md).

## Milestone mapping / source-of-truth

- **M0:** scope, dataset rights, synthetic fixtures, evaluation design, change control.
- **M1:** real-format secure intake, inventory, PDF/DOCX/scans, page & crop coverage.
- **M2:** all detected references, identity+pinpoint, literal/value, OCR abstention, scoped check record.
- **M3:** authenticated web inspect/review/correction preview and persisted actions.
- **M4:** supported version-safe DOCX, report, correct links and authorized export/reopen.
- **M5:** practitioner evidence and priced commitment; no production launch merely from research.
- **M6:** only explicitly authorized Word/MCP/enterprise channels and other future hypotheses.

Engineering receipt truth is in [STATUS.md](STATUS.md), not inferred from this journey. Older `PIV-00–20` and `F01–F42` ledgers document historical capability targets; they cannot silently override this acceptance.
