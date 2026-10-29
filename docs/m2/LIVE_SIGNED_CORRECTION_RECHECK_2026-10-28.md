# M2 signed reviewed correction and independent recheck — LIVE development evidence

**Date:** 28 October 2026. **Status: PASSED for the narrow signed synthetic TXT development slice.** This is not a product, production-security, Microsoft Word, PDF or court-ready acceptance.

## Exact evidence

- Implementation: merged [PR #117](https://github.com/haytamAroui/caseproof/pull/117) at `main@d9e27879b146eb54d3a82216dabcd1d54210e9d7`. Initial protected run failed (identified permission mismatch).
- Diagnostic: merged [PR #118](https://github.com/haytamAroui/caseproof/pull/118), protected [run #40678303773](https://github.com/haytamAroui/caseproof/actions/runs/40678303773) showed concurrent registrations both denied (404) due to accidental `draft:write` in general signed source-read guard; no residue.
- Remediation: merged [PR #119](https://github.com/haytamAroui/caseproof/pull/119), `main@613950107128af4f14f999df1598c762c0a44655`: initial private owner grant receives `draft:write` only with active organization authority; read/register/ingest/state retains independent read/upload permissions; **initial authored brief and later correction both require current org+matter `draft:write`**. Added scoped service-role-only synthetic org-only revocation test, canonical migration inventory and API contract assertions. Eight PR CI workflows SUCCESS.
- **Protected live acceptance [run #40679567871](https://github.com/haytamAroui/caseproof/actions/runs/40679567871): SUCCESS** on `main@613950107128af4f14f999df1598c762c0a44655`. Actual GoTrue users and private Supabase Storage/PostgREST, not mocked acceptance. The logs attest:

| Marker | Observed stage |
| --- | --- |
| `LIVE_TXT_1` | Three real signed development users |
| `LIVE_TXT_2` | Real signed matter/owner grant, atomic audit and replay, foreign denial |
| `LIVE_TXT_STAGE3` | Exact bounded metadata and concurrent one-original registration |
| `LIVE_TXT_3A` | Direct signed client ingestion denied; verified server-only promotion |
| `LIVE_TXT_3` | Immutable original upload, SHA-256 readback and negative access |
| `LIVE_TXT_4` | Strict UTF-8 source snapshot, immutable replay |
| `LIVE_TXT_5` | Organization-only `draft:write` revocation **blocks authored brief**, restored authority creates brief, signed check/review |
| `LIVE_TXT_5A` | Organization-only `draft:write` revocation **blocks correction preview and commit**; after restoration, preview exact range, new immutable draft version, revision CAS and idempotent replay, different-input collision and stale head denial, fresh mismatch check and independent review |
| `LIVE_TXT_6` | Uvicorn killed and restarted, fresh GoTrue login reopens source, old/new immutable draft versions, parent linkage, corrected quote, new check and review |
| `LIVE_TXT_7` | Revoked case/source/review/Storage/correction access fails |
| `LIVE_TXT_8` | Scoped original and fixture cleanup |

Final log sentinel: `LIVE_CREATED_MATTER_INGESTED_TXT_AUTHORED_REVIEW_COLD_RESTART_PASSED`.

**Independent Supabase MCP post-run query:** all **19** inspected categories zero: Auth users, organizations, organization members, matters, matter grants, documents, document versions, journey fixtures, journey operations, journey sources, exhibit heads/events, brief versions/events, check runs, review events/receipts, audit events, original Storage objects. **27** installed forward-only development migrations, including five #117 and three #119 permission/counterexample fixes. No customer data was used or left behind.

## Precisely what passed and what did not

This is one bounded **synthetic UTF-8 TXT** source and a single numeric literal assertion (`125 EUR` → `126 EUR`). Correction changes an **authored brief representation** and persists an append-only version; it neither changes nor repairs the original source or a Word document. A new check reports quote mismatch, never a semantic/legal contradiction. Previous human review does **not** authorize the new version, and release/filed status remains false.

**OPEN:** multiple originals/real PDF/DOCX/OCR and page coordinates, confirmed `Stuk/Pièce` exhibit mapping, general unified NL/FR/EN zero-quote/date/value checks on live complete source corpus, durable worker retries, browser click E2E, real Microsoft Word host insertion/undo/coauthor/reopen, linked DOCX/PDF/index/bundle with exact manifest and separate authorized recipient delivery, independent customer-facing security/privacy review, legal gold-label calibration and commercial pilot. The developer-only signed SECURITY DEFINER RPCs are not approved for broad deployment.

**Source of truth:** [roadmap](../ROADMAP.md), [M1 proof](../m1/LIVE_CREATED_TXT_JOURNEY.md), [M3 Word acceptance](../m3/WORD_INTEGRATION_ACCEPTANCE.md), [M4 delivery acceptance](../m4/DELIVERY_ACCEPTANCE.md).
