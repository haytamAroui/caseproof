# M0 (PIV-00) — Belgian litigation product and engineering baseline

**31 October 2026 additive evaluation update:** the 26 October baseline below is historical (including its older ADR 0016, language-target and Word/finance implementation assumptions). The authoritative first-market scope is [ADR 0018](../adr/0018-pre-submission-verification-freeze.md), [ADR 0019](../adr/0019-evidence-engine-and-first-market.md) and [the current roadmap](../ROADMAP.md): independent, web-first Belgian FR/NL exhibit verification; English participates in synthetic evaluation but is **not** a new full-parity launch requirement. New v3 NL/FR/EN/mixed fixtures and mechanical rights/label audit are described in [evaluation README](../../evals/litigation/README.md) and the [M0 adjudication packet](TRILINGUAL_ADJUDICATION_PACKET.md). No independent human/legal adjudication or customer-processing approval has yet been recorded.

**Date:** 2026-10-26. **Baseline code:** `main@f643ae9cd5170add32c79e2bd2d2324468e7d95e` (merged PR #60). **Purpose:** pin observed capabilities and acceptance work before modifying any product contracts. **Status:** M0 implementation planning and synthetic evaluation only; no product readiness claim. Recheck before each PIV work packet.

## Authority and ownership

1. `CONSTITUTION.md`: non-negotiable trust/security/deployment/CI controls.
2. `docs/ROADMAP.md`: **only active product delivery backlog**, PIV-00–20; previous finance-first product order superseded.
3. `docs/PRODUCT_WORKFLOW.md`: end-to-end user/transition contract, **proposed**.
4. `docs/adr/0016-belgian-litigation-product-pivot.md`: formal product pivot and compatibility.
5. ADR-0011 and prior ADRs: technical architectural constraints remain; dated finance-first delivery choice is historical.
6. `contracts/architecture_baseline_v1.json`, `contracts/action_catalog.v1.json`, `contracts/v2_operation_matrix.json`: machine contract inventory. These are **not installed permissions**.
7. `docs/STATUS.md`: implementation snapshots, not a source of production authorization. Links to dated and present caveats.

No duplicate backlog in CORE/LIT/AP, prior Belgian audit or research notes. Assign packet *responsibility* to existing boundaries, not to fictitious people.

## Feature truth table — checked against repository tree/README/STATUS on pinned main

| Capability | Evidence present on baseline | Actual state / gap | Owner / next packet |
|---|---|---|---|
| Pure Kernel: source versions, typed anchors, fidelity/support separation, coverage, provenance | `packages/evidence_kernel/` and tests | Python reference contracts; not a deployed litigation truth service | kernel; preserve contracts |
| Finance reconciliation and extraction | `domains/finance/`, `application/documents/`, `application/extraction/` | Disposable and synthetic reference; not litigation rules | compatibility; not a rewrite |
| Requesty inference and checkpointed workers | `apps/api/requesty_extraction.py`, `application/runtime/`, scripts/tests | Candidate-only, gated internal/disposable; no proven customer/live-model quality | application runtime; PIV-04/12 |
| PDF, UBL, MIME parsing | `infrastructure/parsers/`, `tests/fixtures/documents/` | Selected bounded synthetic parsers; no production DOCX/OCR/scan coverage | document intake; PIV-04/05 |
| Auth/tenancy | `apps/api/supabase_auth_verifier.py`, SQL fixtures, `apps/api/main.py` | Real signed identity→least privilege app DB session NOT established; `/v1` demo header is not auth | API/identity; PIV-02 |
| Storage and durable source/review | `apps/api/*vault*`, `db/proposals/`, disposable integration tests | No actual customer-grade private object Storage, installed evidence schema or authorized promotion | infrastructure; PIV-03 |
| Synthetic reviewer/draft pack | `apps/web/review/`, `application/review/`, `application/dossiers/` | Suggestions/draft export only, not release/filing or litigation workbench | review/output; PIV-08/14–16 |
| Matters and restricted case grants | baseline case-access model | Current org-wide authorization does NOT demonstrate private same-org matters | application access; PIV-02 |
| Exhibit registry, citation/draft graph, legal brief check | no integrated authoritative litigation route | Not implemented; no semantic/law correctness claims | disputes/application; PIV-06/07/09 |
| NL/FR/EN case search and Word citation loop | no `apps/word_addin/` | Not implemented; lexical/performance unmeasured | retrieval/Word; PIV-10/11 |
| Legal authority verification, procedural/court readiness | no approved local authority service | Out of initial factual scope; unverified law refs stay unchecked | qualified legal owner; PIV-17/18 |
| Hosted sharing, actual filing and receipts | no authorized integration | Not implemented. Export ≠ filing. | application/ops; PIV-15/18 |
| PIV-01 corpus/protocol | `evals/litigation/m0_corpus_v1.json`, `scripts/validate_litigation_corpus.py` in this PR | Newly authored synthetic/gold-data baseline; cannot prove accuracy | evaluation; PIV-01 |

**Live branch variance:** PR #57 (EI-005) is still open and not on `main` at this pin. Do not silently treat its new topology, boundary review or finance reconciliation as merged product code. Rebase/merge separately only after conflicts, review and CI resolve.

## Non-negotiable M1–M4 contracts to settle

- PIV-02: current bearer verification, explicit matter access, same-org restricted matter decision, worker delegation, revoke/cross-tenant denial, demo route isolation.
- PIV-03: originals/representations/links/head/event/audit/store transactions, installed migrations, immutable objects, quarantine, retention, backup and restore.
- PIV-04/05: processing limits (bytes/pages/DOCX ZIP/OCR), page-level states, no-model deterministic runner, failure/restart/OUTCOME_UNKNOWN/cost ledger.
- PIV-06/07: stable source/exhibit/draft IDs, Stuk/Pièce aliases, versioned page maps, ambiguous/duplicate mappings, confirmed assertion→anchor graph, printed/PDF/bundle page distinction.
- PIV-08–11: draft and source side-by-side, quoted-span fidelity versus semantic judgment, no-findings clean states, source universe declared and incomplete material disclosed, safe Word range preview/undo/recheck.
- PIV-14–16: one frozen version manifest, dependency-specific invalidation, re-open/verify links, solo policy *explicit* vs independent reviewer, publication rights distinct from reading.
- PIV-20: monitored cost and retention, privacy-safe adoption definitions, recovery drills, signed acceptance evidence before customer use.

## M0 exit gate, outstanding owner decisions

- **Delivered by M0 PR:** authoritatively scoped ADR; pinned baseline; claims register; synthetic corpus; label integrity tests; benchmark protocol; README/STATUS pointers.
- **Not delivered:** independent legal gold review, genuine in-court or customer datasets, measured lawyer task times, product smoke journey, signed user→DB proof, private cloud Storage, production implementation.
- **Owner/qualified reviewer needed:** confirm initial civil/commercial matter profile and confidential matter isolation policy; approve actual task gold answers/benchmark protocol before sales comparisons; verify all Belgium-specific claims independently.
- **Next:** PIV-02/03/04 contracts and first authenticated, preserved, deterministic intake slice. Do not enable customer uploads as a shortcut.


## Language scope correction (M0 follow-up)

The product target is **NL/FR/EN**, including UI, supported document workflows, matter search/query language and available output templates. The prior M0 corpus `m0_corpus_v1.json` remains immutable historical test data. `m0_corpus_v2.json` adds separately labeled original English clean/adversarial examples and a mixed NL/FR/EN case. This is **scope and fixture coverage, not implemented translation, OCR, Word or legal correctness**. All three language cohorts require human gold adjudication and comparable benchmarks.
