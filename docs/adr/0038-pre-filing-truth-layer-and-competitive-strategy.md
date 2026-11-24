# ADR 0038 — Pre-Filing Truth Layer, Target Extensions, and Competitive Strategy

**Date:** 24 November 2026  
**Status:** ACCEPTED as the owner's refined product strategy and scope alignment, extending [ADR 0018](0018-pre-submission-verification-freeze.md), [ADR 0019](0019-evidence-engine-and-first-market.md), and [ADR 0026](0026-frontend-foundation.md). **Pilot, client-data processing, legal certification, and customer release remain NOT approved by this ADR.**

**Companion authority:** [Product Strategy — 24 November 2026](../PRODUCT_STRATEGY_2026-11-24.md), [M0–M6 Roadmap](../ROADMAP.md), [Product Workflow](../PRODUCT_WORKFLOW.md), [Offline Legal Corpus Pilot](../OFFLINE_LEGAL_CORPUS_PILOT.md), and [Frontend Blueprint](../../frontend/BLUEPRINT.md).

---

## 1. Context

Between 28 October and 24 November 2026, two developments created drift between CaseProof's earlier documentation and its actual owner-approved product direction:

1. **Owner framing (23 November 2026) and active implementation:** CaseProof's active engineering (`docs/OFFLINE_LEGAL_CORPUS_PILOT.md` and `feat/demo-belgian-dossier`) introduced a bounded, versioned offline Belgian legal-article corpus (discovered via LawCodex/be and captured from Justel/Moniteur), distortion and subtle-trap checks (omitted opening reservations, `"signé"` vs `"envoyé pour signature"`), lawyer-defined dossier conditions (*conditions définies par l'avocat*), omission signaling (`omission`), and a 4-state lawyer-facing display taxonomy (*Écart constaté*, *Contrôle impossible*, *Appréciation requise*, *Correspondance constatée*). Meanwhile, earlier October docs still read as if any statutory article checking were categorically prohibited in v1.
2. **Verified competitive synthesis (24 November 2026):** A direct audit of 28+ verification tools, Benelux legaltech products, global legal AI platforms, and open-source references clarified where CaseProof sits in the real Belgian litigation stack and which product patterns to adopt versus refuse.

Without a superseding/extending ADR, coding agents and stakeholders receive conflicting instructions on scope, target extensions, competitor positioning, licensing guardrails, and the official frontend.

---

## 2. Decision

### 2.1 Market wedge: Step 3 (Independent Pre-Filing Truth Audit)
CaseProof owns the **independent, deterministic, post-assembly pre-filing audit layer** for Belgian FR/NL civil and commercial litigation—sitting strictly downstream of drafting tools (Word, Alice.law, Nexa Legal, Harvey, Microsoft Copilot, Ex Ante, Brieflee, Ordalie) and exhibit-bundling tools (CourtMerge, PiecesPerfect/Praxis, Doxflow Legal), and strictly upstream of court filing (DPA-Deposit / e-Deposit / Rechtspraak).

CaseProof applies the exact same verification workflow to **human-drafted and AI-drafted conclusions**. Treating AI-drafted briefs as a first-class input does not authorize building AI brief drafting inside CaseProof.

### 2.2 Scope reconciliation: Pilot Core vs. Target Extensions vs. Explicit Non-Goals
This ADR refines ADR 0018's scope boundary without lifting its first-market discipline or its security/commercial gates:

- **Pilot Core (first commercial proof):**
  1. Conclusions DOCX + Stuk/Pièce bordereau + preserved PDF/scanned exhibits reconciliation with **3 independent page spaces** (`pdf_page`, `printed_page`, `bundle_page`). **Progressive confirmation default:** the initial audit runs immediately on proposed mappings—keeping unconfirmed exhibit-identity items explicitly `NOT_ASSESSED (INVENTORY_UNCONFIRMED)` under P3-04—so lawyers see immediate value and confirm mappings inline during triage (strict pre-audit confirmation remains an optional firm policy).
  2. Deterministic quoted-passage and same-role typed value verification with explicit OCR uncertainty abstention and above-the-fold original source pixels/crops.
  3. Visible coverage denominators (`regions_discovered / scanned / unprocessed / unsupported`, unreadable pages) plus explicit lawyer `omission` signaling.
  4. Accountable human review decisions (`Confirm / Qualify / Reject / Waive`) bound to exact snapshots—preserving both the machine finding and the human disposition.
  5. Frictionless Word round-trip correction and recheck (carrying forward strictly unchanged findings; reopening changed/affected findings) and cold-reopenable, tamper-evident export traces.
- **Target Extensions (explicitly authorized in-scope engineering tracks, subordinate to Pilot Core):**
  1. **Bounded chosen-corpus legal-article verification:** comparing cited Belgian statutory articles/paragraphs against an explicitly selected, versioned, offline content-addressed FR/NL corpus pack (Justel/ELI/Moniteur provenance). **Hard guardrail:** never perform live unpinned web scraping at check time, never fabricate absent historical versions (`UNDETERMINED / requested_version_absent_from_chosen_corpus`), and never assert temporal applicability or legal validity.
  2. **Targeted distortion & subtle-trap flagging (not general semantic verification):** deterministically verifying omitted opening reservations (*« Hormis les cas où la loi en dispose autrement »*) in matched quotations, while **flagging for human appraisal (`Appréciation requise`)** known lexical traps (`"signé"` vs `"envoyé pour signature"`), cross-language FR↔NL quotes (`TRANSLATION_REVIEW_REQUIRED`), dropped negations, and unlinked verifiable assertions—never claiming general semantic coverage.
  3. **Lawyer-defined conditions (*conditions définies par l'avocat*):** structured, dossier-scoped checklist rules (e.g., requiring proof of receipt for a *mise en demeure*) whose retrieved passages always route to human appraisal when interpretation is required.
- **Explicit Non-Goals ("Refuse to Build"):**
  - No AI brief drafting or argument generation (stay the neutral auditor of human and AI prose).
  - No PDF exhibit merging, tab stamping, or bundle assembly (read CourtMerge/PiecesPerfect/Doxflow bundles cleanly instead of competing with them).
  - No general Belgian case-law search engine, legal research portal, or meeting transcription.
  - No court e-Filing (DPA-Deposit / e-Deposit / Rechtspraak / e-CODEX).
  - No global green "verified" badge, no LLM-decided verification verdicts, and no automated Book 8 evidentiary sufficiency conclusions.

### 2.3 The 7 Core Product Pillars
All product engineering prioritizes seven synergistic capabilities detailed in [PRODUCT_STRATEGY_2026-11-24.md](../PRODUCT_STRATEGY_2026-11-24.md):
1. Deterministic "No-LLM Verdict" Core.
2. 4-State Epistemic Dashboard (*Écart constaté*, *Contrôle impossible*, *Appréciation requise*, *Correspondance constatée*) backed by the 4 independent backend dimensions.
3. 3-Space Page Reconciliation (`pdf_page` ≠ `printed_page` ≠ `bundle_page`).
4. 3-Pane Instant-Snap React Cockpit with live PDF pixels and non-obscuring bounding boxes above the fold.
5. Distortion, Subtle-Trap, and Lawyer-Defined Condition Detectors.
6. Versioned Offline Belgian Legal Corpus with strict refusal on missing versions.
7. Word Round-Trip Recheck and Cold-Reopenable Diligence Export.

### 2.4 Single Official UI Lock
- **`frontend/`** (React 19 + strict TypeScript + Vite + `pdfjs-dist`, native FR/NL/EN) is the **sole official product user interface**, governed by [frontend/BLUEPRINT.md](../../frontend/BLUEPRINT.md).
- **`scripts/serve_offline_legal_workbench.py`** is strictly an offline engine verification and developer test harness, not a competing product UI.
- **`apps/web/*`** are legacy/historical prototypes retained only for regression compatibility until retired.
- New pilot-facing capabilities (exhibits, legal corpus packs, omission signaling, subtle-trap highlights, lawyer-defined conditions) must converge into `frontend/` via canonical Python application contracts rather than splitting users across separate interfaces.

### 2.5 Licensing, Integrity, and Non-Exclusivity Guardrails
- **Open-source licensing:** Study public UI/architecture patterns only within license boundaries. **Never copy or vendor AGPL-3.0 code** (e.g., Mike OSS) into proprietary CaseProof. Record license/notices before adopting any permissive (MIT/Apache) dependency.
- **Integrity vs. server-signed receipt vs. legal certification:** Explicitly distinguish CaseProof's two export integrity levels:
  - **Authenticated server release (`caseproof-reviewed-release-v1`, ADR 0032/0036):** carries both `manifest_sha256` and a **server-side domain-separated HMAC-SHA256 receipt** verifying byte integrity and server origin on replay (asymmetric RFC 8785/Ed25519 signing and third-party trusted timestamps remain deferred; HMAC key-custody separation/rotation remains an open security item).
  - **Disconnected offline ZIP pack (`scripts/check_offline_legal_docx.py`):** carries **SHA-256 digests only** (unauthenticated byte consistency verified against an externally stored hash).
  - **Neither** may ever be described as a qualified electronic signature (eIDAS QES), court filing receipt, or *constat d'huissier*.
- **Competitive honesty (preserving ADR 0018/0019):** Compare concrete observed behavior (source crops, 3-space pagination, OCR abstention, deterministic isolation, offline corpus pinning) against existing vendors; never claim market exclusivity, untested competitor inability, or regulatory/bar certification.

---

## 3. Retained Commitments and Gates

This ADR **preserves without weakening**:
- [CONSTITUTION.md](../../CONSTITUTION.md) (C01–C25) and [ADR 0011](0011-architecture-freeze-and-first-finance-slice.md) hexagonal dependency rules (`packages/evidence_kernel` stays pure and sector-neutral).
- The four independent backend evidence dimensions (`exhibit identity`, `page location`, `text/value fidelity`, `human semantic support`) and `Decimal` money rules.
- All M0–M6 milestones, P3-01..04 pre-M3 contracts, P5-01..04 pre-M5 prerequisites, and [SEC-01–16 pilot security controls](../security/PILOT_DATA_SECURITY_GATE.md).
- [ADR 0019](0019-evidence-engine-and-first-market.md) evidence-led expansion gate for any non-Belgian-litigation vertical.
- Existing ExceptionDesk finance compatibility code and tests as non-active regression coverage.
- Owner change-control rules: commercial validation on 3–5 representative FR/NL dossiers (measuring total review time, critical errors caught/missed, and false-alarm rate) plus explicit owner approval are required before any paid beta or scope expansion.
