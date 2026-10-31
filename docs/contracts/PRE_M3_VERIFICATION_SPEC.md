# Pre-M3 verification contract — four hard prerequisites

**Status:** binding **target design** for CaseProof v1, **not yet implemented or accepted**. **Decision:** 28 October 2026, specification closure in follow-up to [ADR 0018](../adr/0018-pre-submission-verification-freeze.md). This document resolves four ambiguities identified after [ROADMAP.md](../ROADMAP.md) and [PRODUCT_WORKFLOW.md](../PRODUCT_WORKFLOW.md) were frozen. It changes **no commercial scope**.

**Gate:** M1 source ingestion and M2 verification engineering may continue. **M3 implementation against production-shaped review contracts and any M3 acceptance claim are blocked until the following four rules are signed off as explicit implementation contracts and their M1/M2 fixtures are available.** This file defines those rules; writing it does not prove their implementation. Do not use a UI default to conceal an unresolved state.

## 31 October executable implementation candidate

[ADR 0022](../adr/0022-verification-contract-report.md) and
[acceptance matrix](../m3/VERIFICATION_CONTRACT_ACCEPTANCE.md) implement the
engineering contracts in the signed dossier path. This supersedes an interpretation
that no code exists. Complete M3 acceptance still requires current-head execution,
independent review and the named external/customer-environment approvals. No
practitioner, bar or customer-processing approval is inferred from merged code.

## P3-01 — Translated quotations and cross-language claims

**Problem:** a French draft may quote or paraphrase a Dutch exhibit (or vice versa). A literal comparison cannot judge a translation, and a translation is never source-original text.

**Decision:** add `TRANSLATION_REVIEW_REQUIRED` to the **text/value fidelity** vocabulary alongside `EXACT_MATCH`, `MISMATCH`, `OCR_UNRELIABLE`, and `NOT_ASSESSED`. This is a **non-confirming review state**, not a semantic conclusion or a confidence score. The observed quote/reference retains its own draft-language text, the *unaltered source-language original* and exact page/crop anchors. A human may confirm semantic support using the source; the fidelity state does **not** become `EXACT_MATCH` solely because the meaning appears aligned.

**Priority:** source/page unavailable or OCR unreliable remains an identity/page/OCR blocker; a translated assertion with reliable source text uses `TRANSLATION_REVIEW_REQUIRED`; if both translation and OCR are uncertain, retain `OCR_UNRELIABLE` as the fidelity state plus independent `translation_review_required=true` annotation so neither reason is lost. If original-language comparison is out of declared support, mark `NOT_ASSESSED` with an explicit typed reason rather than fabricate `MISMATCH`.

**Allowed separate normalization:** unambiguous monetary/date/currency values may be deterministically compared across NL/FR labels under the [same-role policy](../ROADMAP.md#pre-m5-hard-prerequisites--the-commercial-experiment-must-have-an-exit); this does not authorize translated prose equivalence or an AI-supported legal finding.

**UI and test:** display “Source text (NL)” and “Draft assertion (FR)” side-by-side and a conspicuous translation-review tag; save original and any optional reviewer translation as distinct revisioned fields, never overwrite original. Test a translated quote with identical meaning, a false-friend/negation, a conditional qualifier, a literal bilingual mixed passage, and a scanned source that is also a translation. Machine cannot emit `CONFIRMED_SUPPORTED` or `EXACT_MATCH` for translated prose on translation alone. **Acceptance owner:** M2 contracts + bilingual practitioner reviewer; M3 only consumes this contract.

## P3-02 — OCR location, provider and processing boundary

**Default v1 architecture decision:** OCR executes in an **isolated self-hosted processing worker inside the explicitly approved CaseProof evidence-processing environment**, with private original-byte access restricted to the exact authenticated case/work item. In synthetic local/dev tests the same function may run locally/CI. **No external third-party OCR API, remote computer-vision endpoint or generative OCR service receives confidential customer material by default.** This is a *target requirement*, not a claim that the worker, its sandbox or a compliant customer environment already exists.

**Before any customer-source OCR:** security sign-off must document exact hosting account/region/operator, executable and OCR/model versions, OCR dependencies, isolation and least-privilege byte-access, outbound egress policy, ephemeral file and swap handling, temporary retention, crash/log telemetry, deletion, encryption, subprocessors and all transfers. Any third-party/cloud OCR alternative requires **separate approval and a named processor/region/data-flow and contractual/privacy review** before its use; it cannot become an environment-variable silent switch. “Self-hosted in cloud” does **not** equal on-premises or automatically satisfy professional secrecy.

**Data boundary:** OCR creates a versioned derived representation and bounding box/crop pointer referenced to the original-byte hash, page index, render scale and transformations. Confidence is merely an extraction signal; no low-quality representation is authoritative. Raw content and image crops must not be logged to generic diagnostics; image delivery is signed and permission-bound. Outbound model calls remain opt-in and independently reviewed, never a necessary step for deterministic exhibit checking.

**UI and test:** each source page has processing method `TEXT_LAYER`, `OCR_LOCAL_WORKER`, `NOT_PROCESSED`, or `FAILED`, with OCR version and `OCR_UNRELIABLE` where appropriate; never display a blank OCR page as empty evidence. Negative tests: network-egress-denied OCR still works for approved local model, timeout/restart produces `NOT_PROCESSED` (not a pass), revoked matter access fails, ephemeral spills and unauthorized metrics do not contain document text, crop coordinates refer to original. **Acceptance owner:** M1 worker/security; no real data until [pilot security gate](../security/PILOT_DATA_SECURITY_GATE.md) passes.

## P3-03 — DOCX reference-detection coverage denominator

**Scope unit:** a *document region* is a distinct OpenXML story part / text-bearing structured location discovered from the DOCX package, with identity, XML part name, stable source locator where possible, and processing status. **Never infer document-wide coverage from checking the main-body text alone.**

**Mandatory enumerated regions** (whether or not parsing is implemented yet):

| Region type | v1 reference policy | If not safely parsed |
|---|---|---|
| Main-body paragraphs, including runs/hyperlink text | **MUST SCAN** when supported | `UNPROCESSED_REGION`; no full-coverage claim |
| Table cells, including nested tables | **MUST SCAN** where text contains or may contain citations | `UNPROCESSED_REGION`; no full-coverage claim |
| Footnotes and endnotes | **MUST SCAN** for factual exhibit references | `UNPROCESSED_REGION`; no full-coverage claim |
| Headers/footers | **MUST ENUMERATE**; scan supported textual regions; no assumption that they lack citations | `UNPROCESSED_REGION` with count and part |
| Textboxes, drawings, shapes, embedded objects, altChunk, field-code results | **MUST ENUMERATE/POSSIBLY UNSUPPORTED**; do not silently claim included | `UNSUPPORTED_REGION`, locator/type/count in report; scoped review only |
| Tracked inserted/deleted text and move ranges | **MUST DETECT revision presence**; don't silently choose final/markup view | unresolved text revision means `REVISION_STATE_UNRESOLVED` and blocks a document-wide completeness claim; reviewer must fix an explicit frozen view before full scan |
| Comments, hidden text and metadata | Declare **excluded from filed-document body** unless explicitly selected for check | named exclusions/possible uninspected citations, not “all content checked” |

**Coverage recording:** `regions_discovered`, `regions_supported`, `regions_scanned`, `regions_unprocessed`, `regions_unsupported`; per-type counts, identifiers and nonempty reason codes; `references_detected`, `references_mapped`, `references_checked`, `references_not_assessed`; `source_pages_total`, `source_pages_text_processed`, `source_pages_ocr_processed`, `source_pages_failed_or_skipped`. Never use “references total” to imply ground-truth recall. **All detected** means all *within declared successfully scanned regions*; unscanned regions are prominent and may contain unknown references.

**Full-coverage wording:** only allowed when every mandatory content region was enumerated/scanned on an explicit frozen revision view and source page coverage is complete for the claimed check types; unknown structured parts prevent it. A **scoped** report remains allowed with conspicuous unsupported regions and a quantified denominator. If the extraction layer cannot enumerate a part, mark `COVERAGE_UNKNOWN` and prohibit a whole-document “all references checked” statement.

**UI and test:** coverage details must be available before any green result, with raw-XML fixture containing paragraphs, nested table, footnote, header, text box, tracked insertion/deletion, and a clean no-citation DOCX. Seed at least one reference in a supported region and one in an unsupported region and demonstrate the correct scanned/unknown breakdown. **Acceptance owner:** M1 DOCX parser + M2 detection; M3 displays, never invents, the counts.

## P3-04 — Inventory absence versus genuine negative result

**Decision:** extend **exhibit identity** state enum to include `NOT_ASSESSED`. This applies when inventory is **missing, unparseable, unconfirmed, incomplete for the claimed scope, or outside the declared source universe**. Include one typed reason: `INVENTORY_MISSING`, `INVENTORY_UNPARSEABLE`, `INVENTORY_UNCONFIRMED`, `INVENTORY_INCOMPLETE`, or `OUT_OF_SCOPE`.

`NOT_IN_INVENTORY` is available **only when** there is a **supplied, successfully parsed, reviewer-confirmed inventory with declared completeness for the relevant exhibit scope**, and a deterministic label/alias search proves the cited exhibit was not listed **in that inventory revision**. It is **not** a legal conclusion that the party failed to communicate or deposit it.

`SOURCE_MISSING` means a cited inventory item is resolved within a confirmed inventory but no authorized preserved source is present; this is independent of filing/communication status. `AMBIGUOUS` requires multiple plausible identities under a usable inventory, **not merely multiple page mappings of one identified exhibit**. `RESOLVED` may coexist with `UNMAPPED` pinpoint. Never return `NOT_IN_INVENTORY` on an empty parsed inventory unless a reviewer explicitly confirmed that genuinely empty inventory is complete for the scope.

**UI and test:** missing inventory → identity `NOT_ASSESSED(INVENTORY_MISSING)`; unreadable inventory → `NOT_ASSESSED(INVENTORY_UNPARSEABLE)`; unconfirmed candidate → `NOT_ASSESSED(INVENTORY_UNCONFIRMED)`; confirmed complete inventory missing Stuk 4 → `NOT_IN_INVENTORY`; listed Stuk 4 without source → `SOURCE_MISSING`; unique Stuk 4 but unknown printed page → identity `RESOLVED` + page `UNMAPPED`. **Acceptance owner:** M1 inventory confirmation + M2 resolver.

## Pre-M3 gate: proof of closure, not merely prose

M3 may start product-shaped implementation only when reviewed M1/M2 contracts and fixtures implement **all four P3-01..04**. Required signed-off evidence: typed enum schema/migration plan, supported DOCX-region coverage matrix and denominators, an approved OCR processing topology and worker safety test, and deterministic negative tests for absent inventory, translated quotes and partial coverage. Record the reviewers, exact commit and test receipts in the M3 PR.

This specification is **DESIGNED only** as of creation. It does not close the **implemented** or **live accepted** gate. Work on M1/M2 and independent prototype spikes may continue in parallel, but do not label M3 passed or treat a UI mock as closure.
