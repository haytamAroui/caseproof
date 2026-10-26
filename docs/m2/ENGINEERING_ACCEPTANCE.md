# M2 — Check & Correct: Backend Engineering Acceptance

**2026-10-26 · Big PR #71** stacked on [M1 PR #63](https://github.com/haytamAroui/caseproof/pull/63). **Authority:** [principal roadmap](../ROADMAP.md), [full workflow](../PRODUCT_WORKFLOW.md), [Belgian feedback audit](../research/BELGIAN_WEDGE_FEEDBACK_AUDIT_2026-10-26.md), ADR-0017, [CONSTITUTION](../../CONSTITUTION.md). M2 is the **litigation** product, not finance invoice/PO reconciliation.

## Scope and invariant

Run one **deterministic, no-LLM check** against a **versioned own/opponent brief + explicit exhibit register + versioned evidence scope**: (1) exhibit existence and physical page, (2) exact quote fidelity only when present, (3) cautiously compared date/amount candidates of the same explicitly typed factual role. Make the zero-quotation case first-class. Clean dossiers must be able to return zero discrepancies; missing/partial OCR must never masquerade as a pass. No automatic legal verdict, accusation, malpractice inference or filing.

**Trust boundary:** Kernel owns immutable lineage and evidence fidelity; application orchestrates; disputes owns exhibit identity and eventual domain rules; adapters own signed identity, actual storage and DB transactions. M2's pure candidate check **does not** authenticate, establish source authenticity or infer payment meaning from arbitrary text. Caller must verify exact server-owned source bytes, current matter grants and snapshot before invoking it. Signed-in users cannot change evidence authorization by a client-provided tenant ID.

## A/B/C gates

| M2 gate | Exit acceptance | Current status |
|---|---|---|
| **M2-A — engineering contracts & fixture end-to-end** | Typed versioned brief/ref/claim and exact source anchors; quote-free alias resolution, NL/FR/EN date/amount roles, conservative abstention on ambiguous value; reproducible coverage+snapshot report, reviewer decisions and correction/undo/recheck contract; injectable headless API with fail-closed private grants; regression + static + disposable Postgres CI | **Implementation in PR #71; verify exact PR-head CI before marking PASS** |
| **M2-B — durable authenticated integrated backend** | Real signed users, verified RLS/private source custody, persisted immutable brief graph, durable versioned run+findings+review audit transaction, recovery/idempotency, actual DOCX/PDF/OCR quality and index denominator, cross-process restart | **OPEN** — depends on M1-B #37/#38/#64–68, plus DB-backed PIV-07–09 persistence |
| **M2-C — product/court-facing release** | Real reviewer/Word UX, usability/localization, outputs/recipient controls, closed-environment evidence, legal rule authority and privacy approval | **DEFERRED** to M3–M6 release lanes |

**User decision:** M1 production integration can remain OPEN while building and testing M2-A. M2-B/C are not waived by green synthetic tests, and no confidential customer documents may be uploaded under this milestone alone.

## Implemented engineering slice

- \`application/litigation/brief_checks.py\`: pinned quote/reference resolution, plus **NO_QUOTATION** for a correctly resolved quote-free reference.
- \`application/litigation/factual_values.py\`: lexical token parser, explicit NL/FR/EN brief/source language, \`Decimal\` currency comparison and date parsing; payment/due/delivery/invoice roles; explicit abstention for mixed roles, negation, uncertainty, multiple values, VAT/currency context and partial scans. **Candidate difference, not semantic contradiction.** Narrow coverage by design.
- \`application/litigation/unified_review.py\`: \`BriefRepresentation\`, \`SourceScope\`, one unified run and reproducible snapshot hash; run record contains source/version and normalized representation digests, physical source anchors, checked/absent denominator, literal and value observations. Legal and filing states always \`not_assessed\`.
- \`application/litigation/review_cycle.py\`: reviewer dispositions and pure compare-and-swap revision proposals; non-destructive correction preview, exact undo and mandatory new version/recheck; **not a production DB transaction**.
- \`apps/api/litigation_check_service.py\` and \`apps/api/litigation_check_app.py\`: **unmounted opt-in** protected HTTP check with current signed subject, exact ADR-0017 \`draft:check\` grant, reauthorization and snapshot freshness; no legacy finance org-wide fallback, no public upload/edit/approve.
- \`scripts/demo_litigation_m2.py\`: reproducible synthetic source normalization → quote-free Stuk/Pièce alias → payment date + amount candidates → review report → reversible correction → new snapshot check.

## Tests required to pass

- NL/FR/EN and cross-language evidence, quote-free, quote-present, truly clean control, differing same-role payment value/date; French/Dutch grouped currencies vs English comma grouping and ambiguity.
- Unrelated dates, due vs paid, net/gross, missing/duplicate amounts, uncertain text and multiple candidate values cause \`needs_context/not_assessed\`, **not** a false adverse finding.
- Stuk/Pièce alias, versioned page, missing/partial source and source-scope denominator, stale case/exhibit/brief revision, untrusted source version; unsupported snapshots fail closed.
- Correction version CAS, stale range/undo, reviewer rationale and observation mapping; no legal release permission.
- Signed-session mock and rejected foreign/revoked same-org private matter; missing action and changed grants never query/return evidence. These are **contract tests only**, not a genuine Supabase login or live RLS claim.
- Full existing kernel/finance regression retained, Python 3.11 Ruff/myPy/architecture and CI disposable PostgreSQL concurrency/audit unchanged.

## Remaining work after M2-A

Real user Auth sessions and restricted matter RLS, durable private Vault and ingestion/worker, verified real OCR, persisted versioned brief/assertion/source/citation graph, atomic review ledger and idempotent correction application, reviewer/Word interface, locale-specific role candidate recall/precision benchmark, safe actual report renderer, live observability and per-matter costs. This is tracked in [M2 issue #69](https://github.com/haytamAroui/caseproof/issues/69) plus outstanding M1 integration tickets.

**Absolutely no claims:** correctness certification, clinical/legal accuracy, automatic adversarial rebuttal, official filing, buyer adoption, zero false positives, local closed cloud compliance, or proof that a regression suite represents live-model quality.
