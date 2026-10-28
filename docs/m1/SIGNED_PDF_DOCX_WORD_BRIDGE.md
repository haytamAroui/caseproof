# Signed PDF/DOCX original-to-evidence integration — development implementation

**2026-10-28 · implementation candidate, pending protected live acceptance.**

This work extends the already proven signed three-user TXT journey without changing the sector-neutral Evidence Kernel or introducing a second authority for sources. It is a **development-only one-original-per-matter integration** and a read-only Microsoft Word bridge, not full M1-B/M3 acceptance or production authorization.

## Source and trust chain

1. Signed user with explicit current organization and per-matter grant registers a **real PDF or DOCX** (up to 5 MiB) by SHA-256, MIME and exact size. One immutable original per development matter. Existing one-TXT development flow remains.
2. Signed Supabase Storage upload disallows upsert. The loopback server downloads and verifies the original through the user's JWT and rechecks signed source metadata after Storage access. Current Auth identity is established independently by GoTrue. No browser-supplied text, page labels, parser confidence or actor ID can certify evidence.
3. A credential-stripped, CPU/memory/time-limited Linux subprocess parses the real file through existing **pypdf 6** and **defusedxml/ZIP** adapters, rejecting encrypted/active PDFs, embedded DOCX scripts, external relationships, zip bombs and other unsafe inputs.
4. Parser output is range-checked: exact UTF-8 representation, contiguous block offsets, immutable original and representation hashes, parser identity, explicit PDF physical pages and warnings. PDF blank/visual pages are **partial, require OCR or human review**; DOCX has **no invented Word/PDF pagination** and is explicitly partial. No OCR-success claim.
5. A **service-role-only** PostgREST function rechecks exact original bytes' SHA-256/length, registered media, active matter/organization grant, original Storage object's presence, and binds representation/manifest under one transaction with audit, unconfirmed exhibit and request-id replay. Signed clients cannot call it directly.
6. Signed state reopens the immutable original representation and parse manifest after server restart. M2 checks **abstain** on incomplete parser coverage instead of converting a source match/mismatch into verified support.
7. A bounded signed source-search endpoint exposes only exact text spans, physical page where known, and never a `Stuk/Pièce` citation until a separate confirmed mapping exists. Original download verifies SHA and is byte-identical; changed/revoked grants fail closed.
8. The Word task pane can use the development signed Auth provider to search and inspect this original. All real signed hits have `citation: null`, so **citation insertion remains blocked**. A local simulated Office test is not equivalent to testing an installed Word host.

## Acceptance and limits

The protected main-only `[live-binary-acceptance]` job creates three genuine GoTrue users, two separate synthetic private PDF/DOCX matters, uploads actual files, tests cross-user access denial, extracts exact bounded text with page/coverage status, authors a versioned draft, checks with correct abstention, saves review, exercises the Word-facing read-only search/download, kills/restarts uvicorn and fresh-signs-in, revokes grants and cleans Storage/fixtures. Do not mark this pass until the exact protected job is green and Supabase cleanup has been independently inspected.

**Open requirements:** externally supplied representative scans and OCR quality, more than one source per matter, durable background worker and retries, full Stuk/Pièce confirmation, source/PDF interactive viewer, source page-link validation, end-to-end browser test, real Word desktop/web host insertion/undo and DOCX save/reopen, semantic legal checking, validated linked deliverables and release/recipient approval. No customer uploads allowed by this work alone.
