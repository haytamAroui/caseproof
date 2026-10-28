# ADR 0018 — Freeze first commercial hypothesis: pre-submission exhibit verification

**Status:** ACCEPTED as the owner's new **commercial product hypothesis and scope** on 28 October 2026; **pilot and customer deployment are NOT approved** by this ADR. [Authoritative milestones](../ROADMAP.md) and [workflow](../PRODUCT_WORKFLOW.md) specify the implementation/acceptance truth. All v1 scope decisions are frozen pending practitioner evidence, except legal/security corrections and defects that protect existing invariants.

## Context and decision

CaseProof previously committed to a broad Clearbrief-class Word-first writing-to-delivery product under ADR 0016. Repeated competitor comparisons, Microsoft Copilot integration risk and missing customer evidence caused launch-scope drift. The owner now chooses **one testable commercial hypothesis** instead of more positioning debates:

**Buyer:** Belgian civil/commercial litigation practices doing recurring exhibit-heavy pre-filing review.

**Job:** upload conclusions DOCX, a separately confirmed Stuk/Pièce inventory, and preserved source documents/scanned bundles; locate all detected factual exhibit references, resolve exhibit IDs and independent physical/printed/bundle page spaces, check literal/typed same-role fidelity, abstain on unreliable OCR, show original image crops, require human semantic-support decisions, and export an annotated/safely corrected DOCX and scope-bound review record.

**v1 client:** independent **web verification workspace**; backend runs without Word, MCP or LLM. Shared authenticated application API is first-class. Word add-in and deployed MCP server are optional **future channels** with separate acceptance, not first-product blockers.

**Explicitly excluded in v1:** case-law or legal-authority verification, legal research, legal argument writing, substantive legal advice, filing deadlines, Book 8 sufficiency automation, court filing/e-Deposit/e-CODEX, new sectors or generic legal agent features. Do not let dormant prototypes, historical F/PIV references or competitor discoveries silently re-enter launch scope.

**Competitive thesis:** a candidate advantage from correct Belgian inventory/exhibit/page mapping and OCR uncertainty abstention, not a proven moat, exclusivity claim or automatic revenue. Validate with five disconfirming conversations, two workflow observations, then 3–5 controlled dossiers if warranted and a priced signed paid/conditional commitment request within five weeks from first conversation. A failed niche test does not invalidate the evidence kernel. Outcomes are **proceed/refine/reconsider**, not an automatic pivot.

## Supersession and retained commitments

- **Supersedes ADR 0016 only** for the *commercial promise, mandatory Word-first interface, full Clearbrief-class parity as a prerequisite, and broad M5/M6 feature ambitions*. ADR 0016 remains historical evidence of the earlier direction and of accepted architectural decisions.
- **Preserves** ADR 0011 hexagonal modular monolith, six responsibilities, `packages/evidence_kernel` sovereignty and its neutral anchors/provenance; `domains/disputes/` as the only litigation domain; ADR 0017 private matters; prior finance compatibility code; security, Supabase Auth/RLS, runtime recovery and audit requirements; Constitution C01–C25.
- Existing signed **synthetic TXT** live receipts remain valid only within their recorded scope; not evidence that full PDF/DOCX/scanned ingestion, semantic conclusions, Word or web outputs, legal/pilot permissions or commercial launch are complete.
- No data migration, source code edit, privilege grant, release, production upload, customer data handling or court action is approved by this documentation decision. Preserve Git history and link earlier [roadmap](https://github.com/haytamAroui/caseproof/blob/486b239926b681d76e1e3f79d30e3dc7098ab6d8/docs/ROADMAP.md) and [workflow](https://github.com/haytamAroui/caseproof/blob/486b239926b681d76e1e3f79d30e3dc7098ab6d8/docs/PRODUCT_WORKFLOW.md) rather than silently rewriting history.

## Trust semantics that cannot drift

1. System fact: `exhibit identity` is independent of `pinpoint page` and of `fidelity`. Semantic support is **human-confirmed only**. No system-authoritative `VERIFIED` or `BOOK8_SUFFICIENCY_PASS` state.
2. Image-backed/OCR source is not an authenticated transcription merely because a string matches extracted text. Confidence deficiencies require explicit `OCR_UNRELIABLE`, original-image inspection and reviewer disposition. `QUALIFIED` is semantic, not an OCR status.
3. `MAPPED` must identify the correct preserved original page; no silent conversion between physical PDF, printed and compiled bundle page spaces. Unknown/corrupt/partial input is excluded or unresolved, not clean.
4. Reviews and edits are actor-authorized and version-bound. Preserve immutable originals; export a separate immutable version and exact scope manifest; report what was not processed. Review is not filing authority or legal certification.
5. Custody, processing location and provenance/audit are independent ports. Confidential client files require separately authorized security/professional-secrecy controls. Do not claim fully local/firm-controlled deployment before it exists and is tested.
6. For EU AI Act, classification is **intended-use-specific** and not automatically avoided by choosing deterministic checking. Regulation (EU) 2026/1744 moves applicable Annex III high-risk obligations to **2 December 2027**; this is not an AI Act certification claim. Check applicability of other obligations individually. [Official amendment](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32026R1744). Noncommercial bBSARD/bLLeQA datasets are not available for paid training/retrieval without appropriate rights.

## Implementation consequences

Use the existing milestone numbers for new *product outcomes*, clearly superseding their old meanings: **M0 scope/evals; M1 custody, DOCX/PDF/scan and inventory; M2 unified check; M3 web review; M4 DOCX/report export; M5 practitioner commercial validation; M6 only justified integrations**. Do not rename the evidence kernel or create an additional domain. The prior `docs/m3/WORD_INTEGRATION_ACCEPTANCE.md` is retained only as a **deferred Word-channel contract**. The current `docs/FEATURE_DELIVERY_MATRIX.md` is a dated historical Clearbrief comparison ledger, not v1 scope authority.

The web client and optional adapters must call the same signed application API and must not become independent evidence-verification engines. Avoid a new rich-text editor. The first usable product is measured by a completed review/export, not by a headless JSON report, a test dashboard or an Office task-pane prototype.

## Post-freeze specification closure (no commercial pivot)

The subsequent acceptance-only rules in [pre-M3 verification contract](../contracts/PRE_M3_VERIFICATION_SPEC.md) and [SEC-01–16 client-data security appendix](../security/PILOT_DATA_SECURITY_GATE.md) **clarify** the existing verification promise; they do not expand v1, reintroduce Word, grant data-use permission or supersede the freeze. Identity now includes `NOT_ASSESSED` for no usable inventory; fidelity adds `TRANSLATION_REVIEW_REQUIRED` for cross-language prose. OCR has a default isolated self-hosted processing boundary; explicit DOCX story-region denominators prevent a false completeness claim. The [roadmap's pre-M5 gates](../ROADMAP.md#pre-m5-hard-prerequisites--the-commercial-experiment-must-have-an-exit) specify the decision authorized by PROCEED, locale-aware same-role normalization, representative dossier page scale and a falsifiable data-security checklist.

**These contracts are currently designed, not implemented, accepted or customer-authorized.** Actual M3 work and confidential pilots remain gated on corresponding evidence.

## Owner change-control rule

Before altering this hypothesis: present **actual practitioner evidence** (frequency, baseline burden, correction success, price and re-use), the options and costs, changed milestone/test dependencies and privacy/legal consequences. Obtain an explicit owner decision; record a superseding ADR and modify both authoritative docs in one reviewed PR. **Competitor existence, marketing claims or strategic speculation alone are not a trigger.**

**Decision threshold:** proceed on recurrent pain + safe complete task + paid/conditional commitment; refine where value exists but the workflow/pricing/security is wrong; reconsider where the use case is rare, already adequately handled or not worth paying to solve.
