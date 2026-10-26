# M1 — Evidence Library combined implementation PR (PIV-02–06)

**State:** internal synthetic/reference slice. **Architecture audit:** [PIV-02–06 task-by-task results](HEXAGONAL_AUDIT.md). **Not M1 customer-ready completion.** No public route or real confidential upload is enabled. Principal authority remains [ROADMAP](../ROADMAP.md) and [workflow](../PRODUCT_WORKFLOW.md). M0 remains on main; finance and sector-neutral kernel contracts retained.

## Integrated path delivered in this PR

1. **Authorized read composition (PIV-02):** `AuthenticatedEvidenceLibrary` accepts bearer tokens only through existing `CaseAccessService`; requires both `case:read` and `evidence:read` from the server member/organization; does not accept client tenant IDs or user-claimed permissions. It rechecks Auth, case revision, current catalog and exact Vault bytes before returning an inventory or text preview. Foreign case/revoked/changed bytes are denied.
2. **Preserved sources (PIV-03):** reads only previous verified scoped `VaultCoordinator` source intents; original source/version SHA, parser identity and derived representation ID returned for reproducibility. No new persistence schema, private live object bucket, authenticated writer, production migration or backup/restore claim.
3. **Model-free processing (PIV-04):** `EvidenceIndexer` inventories up to 32 preserved sources with independent ready/partial/failed flags, no inference dependencies, no source text leaked in listing. One corrupt/unsupported document is explicitly marked failed without losing other rows. The preview path must pass fresh authorization and returns bounded parser-produced locators.
4. **Bounded PDF/DOCX (PIV-05):** existing isolated Linux parser gains restrained DOCX text paragraphs/notes (safe ZIP entry/path/size/ratio/active/external checks) and page-specific PDF blank/visual warnings. Physical PDF pages are **1-based** in UI, internal parser block page indices 0-based. Text-only DOCX cannot prove rendered Word pagination; `page_unmapped` is explicit; scans are `needs_ocr_or_review`, not imaginary OCR. No image transcription, rendered geometry, DOCX layout correctness, malware attestation or external conversion.
5. **Exhibit registration (PIV-06):** pure immutable domain register with stable exhibit IDs, aliases, independent printed/PDF/bundle pages, ambiguous/unresolved/suggested/confirmed decisions and revision-CAS proposal. Multiple entries claiming a Stuk/Pièce label cannot auto-resolve. This does not install authorized persisted register-write transactions or exhibit/communication/filing proof.
6. **Document fidelity limitation:** DOCX nested text boxes are rejected rather than falsely flattened into one quote. Footnote/endnote separators are preserved; the parser still does not establish Word's rendered reading order, OCR or output page numbers.
7. **Synthetic developer journey:** `uv run --locked python -m scripts.demo_litigation_evidence_library`. Uses independently authored M0 v2 corpus text **only**, not scanned/image-backed source. Result labels `real_auth:false`, `customer_storage:false`, `release_authorized:false`.

## Integration and security gates

| Gate | Status after this PR | Evidence needed before confidential customer use |
|---|---|---|
| Bearer verification and matter authorization | Internal composition over existing interfaces; tests with synthetic verifier | Signed genuine user token→least-privilege DB session, role/member revocation, same-org matter isolation decision |
| Source custody | Scoped Vault protocol + exact read in reference/disposable tests | Installed schema, production private Storage bucket, quarantine/virus isolation, retention/deletion, recovery drills |
| Durable ingestion and worker | Existing disposable jobs, no new write route | Authorized evidence:write grant and true transaction/outbox; resumable intakes, server budgets, fail/retry reconciliation |
| PDF/DOCX processing | Bounded parsers, explicit partial/incomplete statuses | Actual DOCX/image-backed OCR eval, parser sandbox/container threat review, layout/page-map validation |
| Confirmed Stuk/Pièce mapping | Pure typed register + revision proposal | Authenticated human confirmation, durable CAS/audit, conflict UI and storage |
| Readable dossier UX | Internal typed inventory and text preview | Production reviewer UI, accessibility, page display/original inspection, full import/export product journey |

**Do not claim M1 milestone complete** until all gates and an end-to-end signed, durable case walkthrough on approved infrastructure are recorded. No provider/key or LLM was invoked. All new source files remain bounded and internal; no `/v2` route is mounted. PIV-07–09 brief checking belongs to M2.

## Test and threat assumptions

- Positive: clean Dutch/French/English UTF-8, alias pinpoint, mixed source previews, bounded DOCX paragraphs and notes.
- Negative: cross-tenant/foreign, missing action, revocation during parsing, source/catalog change, unavailable/mismatched Vault, duplicate source labels, ZIP-slip, macros, embedded objects, external relationship, unknown PDF text, page mismatch.
- Fixture doubles and worker tests do **not** prove that production Supabase Auth/Storage have been exercised.
- CI is required on PR HEAD: `uv run --locked pytest -q`, `uv run --locked ruff check .`, architecture, mypy partitions, disposable PostgreSQL/recovery, browser, plus `uv run --locked python -m scripts.demo_litigation_evidence_library`. Record actual results; do not assert green in advance.

**Next:** PIV-02 signed DB/matter authorization and PIV-03 production Vault integration and persisted exhibit CAS under separate human security/schema approval. Then integrate inventory workbench and actual private DOCX/PDF samples.


## NL/FR/EN scope and evidence

Dutch, French and English are product languages for the UI, evidence workflow/search and supported outputs; source, UI and output may differ. M0 v2 contains English clean, mismatch, ambiguous, unprocessed-scan and tri-language fixtures. This remains synthetic evidence only. No actual language-specific production UI, semantic retrieval results or approved human translations were delivered in M1.
