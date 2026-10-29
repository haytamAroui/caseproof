# Live signed PDF/DOCX original → parser → Word evidence retrieval

**Date:** 28 October 2026. **Status: PASSED — narrow development signed original and read-only Word API integration.** Not full M1-B or M3 product/host acceptance.

## Exact accepted implementation and receipts

- Merged [PR #121](https://github.com/haytamAroui/caseproof/pull/121) at `main@486b239926b681d76e1e3f79d30e3dc7098ab6d8`. Eight PR CI workflows SUCCESS. Final independent Codex code review: no major issues after the DOCX ZIP signature fix.
- Applied and canonicalized four forward-only migrations:
  - `20261028114522_caseproof_dev_signed_pdf_docx_register_parse_manifest.sql`
  - `20261028114616_caseproof_dev_service_verified_binary_parser_promotion.sql`
  - `20261028114940_caseproof_dev_m2_preserve_partial_pdf_docx_unknown.sql`
  - `20261028114956_caseproof_dev_cleanup_verified_binary_source.sql`
- Protected main-only genuine Supabase [GitHub Actions run #40684874908](https://github.com/haytamAroui/caseproof/actions/runs/40684874908), job **Signed PDF/DOCX ingestion and Word preview, protected main**, SUCCESS, with marker `LIVE_SIGNED_PDF_DOCX_WORD_SEARCH_RESTART_CLEANUP_PASSED`.

## What the protected job actually exercised

Three real temporary GoTrue users, exact owner/ungranted/foreign rights, two separate newly created **private synthetic development matters** (one genuine generated PDF original and one DOCX, not pre-seeded), SHA-256 registered metadata, signed immutable Storage upload, actual signed readback, existing-object outsider denial, a credential-stripped bounded Linux pypdf/DOCX parser, and service-role-only atomic promotion.

- `LIVE_BINARY_SOURCE` × 2: real original SHA, extracted exact text, immutable representation, parser identity, physical PDF page or unverified DOCX layout, replay and audit.
- `LIVE_BINARY_WORD` × 2: signed exact query, physical PDF page when known, **no unconfirmed Stuk/Pièce citation**, direct signed byte-identical original download.
- `LIVE_BINARY_RESTART` × 2: real uvicorn stop/start, fresh signed login, identical parsed source/manifest, authored brief and saved review reopened, then revoked actor denied further source/Word access.
- `LIVE_BINARY_FORMAT_PASSED: PDF`; `LIVE_BINARY_FORMAT_PASSED: DOCX`; final sentinel `LIVE_SIGNED_PDF_DOCX_WORD_SEARCH_RESTART_CLEANUP_PASSED`.

The DOCX source remains **partial** because printed pagination is not verified. The tested PDF contains an extractable physical page. The M2 quote check appropriately returned quote candidate support for the clean PDF, but **candidate_quote_not_assessed_partial** for DOCX. Neither is a semantic legal finding. Separate disposable/unit tests assert blank/scanned PDF `needs_ocr` and incomplete coverage, never invented OCR text.

## Independent post-run database readback

Supabase MCP queried **20 categories** and found **zero rows** in all: `auth.users`, organizations, organization members, cases, matter grants, documents, document versions, dev fixtures, operations, sources, **parse manifests**, exhibit heads/events, brief versions/events, M2 check runs, review events/receipts, audit events and private-original Storage objects. **31 installed development migrations**.

Privilege audit: both `public.caseproof_dev_ingest_verified` and `public.caseproof_dev_ingest_parsed_verified` are executable only by `postgres`/`service_role`, **not** `anon` or `authenticated`. Their trusted development server requires GoTrue-verifiable signed caller and current case grants. There is no published service key to a browser or Word pane.

## Word host facts and remaining work

PR #121 adds a localhost same-origin development server for the task pane and public-only sign-in configuration, pinned auth bundle build and a separate [ReadDocument development manifest](../../apps/word_addin/manifest-live-dev.xml). It allows safe signed search and byte-verified original inspection; citation insertion remains disabled because the exhibit is unconfirmed. Automated simulated Office API and task pane tests ran and passed.

**No actual supported Word desktop/web host was operated** in this acceptance. Host-side PKCE dialog behavior, saving/reopening the Word document, coauthor-safe insertion, undo and draft recheck are separate M3 milestones. A configured OAuth provider and `https://localhost:3000/auth-callback.html` redirect allowlist still require explicit setup, and the local HTTPS dev certificate must be trusted. See [Word runbook](../../apps/word_addin/README.md) and [M3 acceptance](../m3/WORD_INTEGRATION_ACCEPTANCE.md).

**Open M1-B:** this is **one source per development matter**, ≤5 MiB per PDF/DOCX, with no scanned-file OCR production quality, no durable background parser job, no multi-document exhibit graph, no confirmed Stuk/Pièce register and no validated PDF viewer/print-page mapping. PDF/DOCX **content extraction is live tested**, not the entire evidence library; final customer privacy/security signoff, linked deliverables and release authority remain open. No confidential source processing is authorized by this milestone.

[Authority: Roadmap](../ROADMAP.md) · [Implementation/security packet](SIGNED_PDF_DOCX_WORD_BRIDGE.md).
