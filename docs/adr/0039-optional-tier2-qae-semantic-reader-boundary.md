# ADR 0039 — Optional Tier-2 QAE Semantic Reader Boundary and Evaluation Contract

**Date:** 25 November 2026  
**Status:** PROPOSED architecture boundary and isolated evaluation contract — **NOT** part of Pilot Core, **NOT** deployed, **NOT** end-to-end offline verified in real conditions, **NOT** authorized for confidential client documents, and **NOT** a commercial or accuracy claim. Extending [ADR 0018](0018-pre-submission-verification-freeze.md), [ADR 0025](0025-deployment-data-retention-and-model-authority.md), and [ADR 0038](0038-pre-filing-truth-layer-and-competitive-strategy.md).

---

## 1. Context

CaseProof's Pilot Core (**Tier 1**, merged on `main` at `0a4bbb1f`) executes Belgian pre-filing verification deterministically with **zero LLM in any verdict**: exhibit identity, 3-space pagination (`pdf_page`, `printed_page`, `bundle_page`), exact verbatim quotes, same-role Decimal/date comparisons, offline versioned legal packs, reservation cues, lawyer-defined conditions, and DOCX↔PDF parity.

At the same time, CaseProof contains an earlier domain-neutral Quote-Anchored Extraction runtime (`application/extraction/`) inspired conceptually by AZComply's multi-component QAE architecture (without copying AZComply code, schema, or data). An adversarial audit on `main` (`0a4bbb1f`) established two facts:
1. Grounded extraction + deterministic Python post-processing solves real blind spots of pure regex (paraphrased claims, FR↔NL bilingual exhibits, multi-scalar sentences, status shifts like *"envoyé pour signature"* vs *"signé"*, and uncited counter-exhibits).
2. However, **exact quote matching plus deterministic Python rules does NOT guarantee semantic truth**: an LLM can attach an exact quote to the wrong role in a multi-scalar sentence (*« facture de 12 500 €, dont 2 500 € déjà payés »*), truncate a quote right before a negation or FR/NL reservation, miss visual pixel anchors, or emit unverified cross-exhibit entity links.

---

## 2. Decision — Strict Two-Layer, Three-Level Architecture

### 2.1 Independent Two-Layer Isolation (No Silent Coupling)
- **Tier 1 — Deterministic Core (Always-On, 0% LLM):** Runs independently on confirmed/progressive inputs without any model provider, network egress, or Tier-2 state. Tier-2 success, mislabeling, crash, timeout, or partial failure MUST leave Tier-1 findings and digests byte-identical.
- **Tier 2 — Optional QAE Semantic Reader (Post-M5 Target / Isolated Spike):** Enabled only per matter with explicit `ContentRelease` authorization and an approved provider/deployment profile. Tier 2 can **never** upgrade a Tier-1 `FAIL`, `UNVERIFIED`, `OCR_UNRELIABLE`, or `NOT_ASSESSED` result to green (`Correspondance constatée` / `CONFIRMED_SUPPORTED`).

### 2.2 Explicit Three-Level Epistemic Contract for Tier 2
1. **Level 1 — `MODEL_CANDIDATE`:** Raw model proposal (`quote`, extracted scalar/status, polarity, provider/model/prompt provenance). Treated as untrusted hypothesis only.
2. **Level 2 — `MECHANICALLY_GROUNDED_LEAD`:** Mechanically checked review lead only (*Piste de relecture* — **never** labeled `"validated"` or `"Écart constaté"` in user-facing output):
   - Exact unique substring match in derived text only (zero fuzzy quote promotion).
   - Surrounding context expansion across sentence, block, and page boundaries, scanning unified FR/NL/EN negations, reservations (*sauf, hormis, sous réserve, sans préjudice, behoudens, onverminderd, onder voorbehoud, tenzij*), and status qualifiers (*envoyé pour signature, projet, ontwerp*).
   - Mandatory multi-scalar warning (`MULTI_SCALAR_SENTENCE_ROLE_UNVERIFIED`) whenever multiple amounts or dates coexist in the containing sentence.
   - Deterministic `Decimal`/date/status/cross-exhibit rules emit candidate review leads showing both brief and exhibit passages side-by-side (`human_semantic_support = "NOT_ASSESSED"`).
3. **Level 3 — `HUMAN_DECISION`:** Explicit, version-bound lawyer disposition on the exact passages and frozen SHA-256 source versions.

---

## 3. Five Binding Safety Refinements

Before any Tier-2 QAE path can leave isolated synthetic evaluation, all five invariants below are mandatory:

1. **Bordereau ≠ Entities:** Confirming the bordereau binds `Pièce/Stuk ↔ file` only. A single exhibit frequently contains multiple distinct invoices, amendments, or contracts. Every cross-exhibit entity link MUST carry either an explicit shared identifier proof or explicit human confirmation; otherwise cross-exhibit leads MUST be flagged `unconfirmed_bordereau_insufficient`.
2. **`SourceBlock` ≠ Visual Pixels:** Preserve the full provenance chain `(document_id, version_id, representation_id, char_span, pdf_page, visual_bboxes[])`. Surrounding negation/reservation scanning MUST cross block and page boundaries. If visual bounding boxes are missing for any spanned block, surface `visual_anchor_unavailable` explicitly; if a spanned page has uncertain OCR, keep `OCR_UNRELIABLE_SOURCE_PAGE` and block numeric auto-comparison.
3. **Opening PDF ≠ Examination:** Opening an exhibit page records an access trace (`source_opened_at`) only — never proof of semantic review. Confirmation requires an explicit lawyer action bound to the exact snapshot hash. `reject_lead` and `waive` MUST preserve `human_semantic_support = "NOT_ASSESSED"` and can never promote to `CONFIRMED_SUPPORTED`.
4. **Review Budgeting Without Masking:** `P0` triage limits may prioritize high-stakes leads for immediate inspection, but deferred leads MUST NEVER be dropped or hidden. Every coverage manifest MUST disclose exact counts of `deferred_leads_count`, `unread_exhibits`, `unreadable_ocr_pages`, and `excluded_by_preselection`, with the invariant `zero_p0_means_clean = False`.
5. **Data Minimization Before Provider Transmission:** Never transmit full source documents blindly to a model provider. Require an authorized per-matter `ContentRelease` with explicit `destination`, `retention_policy`, and `max_total_chars`, transmit only explicitly scoped block excerpts, and record a zero-raw-text `TransmissionManifest` (compliant with SEC-07 log sanitization). Even local-model modes must undergo whole-perimeter network capture per [ADR 0025](0025-deployment-data-retention-and-model-authority.md) before claiming zero external traffic.

---

## 4. Isolated Evaluation Protocol & Status Boundaries

1. **Volet 1 — Scripted Adversarial Boundary Harness (CI, $0, Zero LLM Calls):** Reproducibly injects faulty model outputs (wrong role in multi-scalar sentence, quote truncated right before cross-block/cross-page negation, missed FR/NL reservations, hallucinated quote, missing pixel boxes, OCR uncertainty, unconfirmed entity links, and provider timeout/crash) alongside clean cases (`envoyé pour signature ≠ signé`, FR↔NL bilingual discrepancy, uncited cross-exhibit credit note) and proves Tier-1 byte-invariance.
2. **Volet 2 — Separate Opt-In Live Model Evaluation (Gated, Budgeted):** Executed only on explicit owner opt-in and budget approval on annotated synthetic FR/NL dossiers, measuring precision, **false positives, missed cases, total review burden, latency, and actual USD cost**. No live model calls run automatically or in CI.
3. **Status Discipline:** Merging code or passing CI establishes *Implemented (synthetic)* only — never deployed operation, complete offline E2E acceptance, SEC-01–16 clearance, or M5 commercial validation. Pilot Core development and M5 practitioner interviews remain unaffected by this ADR.
