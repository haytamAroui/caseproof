# M4 — Reviewed DOCX, evidence report and safe export acceptance

**Status:** proposed **v1 product acceptance**, not yet implemented or customer-accepted. Governed by [ROADMAP.md](../ROADMAP.md), [PRODUCT_WORKFLOW.md](../PRODUCT_WORKFLOW.md), [ADR 0018](../adr/0018-pre-submission-verification-freeze.md), and [CONSTITUTION](../../CONSTITUTION.md). This replaces the former Word-first mandatory linked-bundle publishing scope. M4 is completed **from the independent web workspace**, without Microsoft Word installed or an MCP client.

## Outcome

A lawyer downloads the exact approved **annotated or safely corrected DOCX** and a reproducible **verification run record/report** explaining which factual exhibit references were checked against the confirmed inventory and preserved source pages, which matches/mismatches were found, what OCR/coverage was unreliable, and which human actions were taken.

The source DOCX and exhibits are never silently rewritten. **No “all facts true”, legal sufficiency, court readiness, deadline compliance, filing or AI Act certification.**

## Preconditions

- Authenticated active actor with exact matter/check/review/export action grants; no client-supplied tenant authority.
- Immutable original hashes, exact source versions and page anchors; a confirmed inventory/exhibit revision; current draft revision/processing coverage; complete or transparently scoped check run; a human reviewer disposition where required.
- Original PDF physical pages, printed page labels and compiled bundle pages are distinct. Source crop and representation text must refer to the same source version.
- Unreliable OCR, unprocessed source or unsupported DOCX structure never upgrades to `EXACT_MATCH`, `MAPPED`, confirmed semantic support, or an implicitly clean whole-dossier report.

## Required output contract

| Output | What must be present | Adversarial acceptance |
|---|---|---|
| **Reviewed DOCX** | Version-bound annotated original or reviewed correction if safe, exact changed spans and stable Stuk/Pièce references, retained original as separately downloadable | Format/footnote/track-change/table integrity; unsupported edit refused or annotated-only; no silent flattening |
| **Human-readable report** | Original and checked draft IDs/hashes, inventory revision, source universe and per-page scope, identity/location/fidelity/semantic separate, unresolved and exclusions, reviewer actor/role/action/time | No global truth claim; missing/unreadable pages explicit, a clean scoped run can show zero issues |
| **Machine-readable run record** | Deterministic typed observations, source and representation hashes, exact crop/page locator, parser/check versions, user corrections/dispositions, status and scope denominators | Schema versioned; no forged `CONFIRMED_*` or audit; no raw confidential quotes in generic telemetry |
| **Output manifest** | Artifact hashes, source/version dependencies, draft/check/review identity, link destinations, release scope and audit receipt | Reopen actual bytes; every supported source link targets right original page, stale manifest cannot appear current |
| **Optional compiled index/bundle** | Only when a v1 pilot actually needs it and separately accepts it; derive from one frozen manifest | No accidental second pagination/identity authority; no silent bundle reordering |

**Verification report ≠ legal certificate.** The report shows observations, exact support limitations and human decisions, not admissibility, authenticity or whether court rules were complied with.

## Review and export authority

- Review may be independent firm reviewer or documented solo policy (clearly labelled solo). Machine output proposes; only the authorized human can mark semantic support, qualify or contradict.
- **Reviewer disposition and export permission are distinct.** Current server-side checks bind `actor + matter + action + draft + original source set + inventory revision + check run + reviewer snapshot + output manifest` immediately before export.
- Material changes to source bytes, register/order/page mapping, draft, provider/processing version where relevant, check scope or reviewer policy invalidate dependent approvals. A denial/revocation or missing audit record blocks export.
- Stable operation IDs and durable reconciliation prevent duplicate correction/export from retry, crash or uncertain acknowledgment. A previous immutable export stays identifiable as historical, never silently updated.
- The user may download permitted output. **External sharing, recipient grant and court filing are outside the v1 mandatory journey** and must not be inferred from download. No e-Deposit/DPA external filing without separately authorized integration and an actual external receipt.

## Required changing-dossier regression

Start with E-v1 (preserved original), D1 (draft), I1 (inventory), C1 (check) and R1 (human review), plus unrelated U.

1. Produce O1 (annotated/corrected DOCX and report) under an authorized frozen manifest. Reopen both bytes.
2. Replace E with new immutable E-v2; reorder/rename an exhibit in I2; modify D2; keep U unchanged.
3. Verify E-v1/O1 remain immutable and accurately labelled historical. Affected identity/page/quote observations and R1 become stale. An unrelated checked scope may remain current only if its declared dependencies did not change; whole-universe searches do not.
4. Stale reviewer tries to export D2 with C1/R1 and is denied, even after restart or lost acknowledgment.
5. New run C2, reviewer R2 and output O2 derive source links/page offsets from the new manifest and are reopened and inspected against actual source bytes.
6. Test corrupted original, missing page crop, OCR-unreliable source, failed rendering, revoked export right, concurrent edit, failed audit and new reviewer policy. Every failure blocks a claimed-current released artifact.

## Full v1 M1→M4 product acceptance

Using **real signed staging users with synthetic/rights-cleared NL/FR/mixed fixtures**:

1. Create private matter; upload conclusions DOCX, confirmed inventory, one text PDF and one image-only PDF; verify immutable hashes, page coverage and source previews.
2. Resolve labels including an exhibit with unique identity but unmapped pinpoint; run M2 full-reference check with missing/wrong/clean values, uncertain scan and zero-quote control.
3. In **web**, inspect image crop, record a human decision, propose safe revision and recheck current version; browser refresh, server restart, re-sign-in and revoked access all behave as specified.
4. Export and reopen **actual DOCX/report** bytes, hash and validate all source links against original page targets; preserve declared formatting in supported subset and surface unsupported details.
5. Verify protected download, previous export immutability, altered-source stale rejection and output audit. No test should require an Office host or deployed MCP server.
6. Record actual supported host/browser versions, limits, accessibility and security evidence. A test inspecting only JSON and a green headless CI are insufficient.

## Pilot / launch gates

**M4 technical exit** requires complete signed synthetic web acceptance and output-byte integrity, not just an API response. **M5** separately requires practitioner usefulness and a priced/conditional commitment. **Customer/pilot use** requires independent legal/privacy/security rights and operations review; an M4 pass does not authorize confidential customer documents or represent commercial viability.

Deferred Word interaction details: [optional integration contract](../m3/WORD_INTEGRATION_ACCEPTANCE.md). Historical full dynamic exhibit/recipient-share requirements remain in [prior M4 contract in Git history](https://github.com/haytamAroui/caseproof/blob/486b239926b681d76e1e3f79d30e3dc7098ab6d8/docs/m4/DELIVERY_ACCEPTANCE.md) and do not silently re-enter v1.
