# M0 NL/FR/EN/mixed corpus — rights, language and coverage manifest

**Status:** fictional synthetic project-authored examples. This is an **author declaration**, not external independent evidence of underlying rights or legal correctness. Source files [v1](../../evals/litigation/m0_corpus_v1.json), [v2](../../evals/litigation/m0_corpus_v2.json) and [v3](../../evals/litigation/m0_corpus_v3.json) are kept as distinct immutable versions.

| Asset | Origin and rights | Permitted use / limitations |
|---|---|---|
| v1 (14 cases) | Project-authored fictional text; author states CC0-1.0 | Offline synthetic structural validation only; earlier NL/FR/mixed baseline, no real source documents |
| v2 (19 cases) | v1 carried forward, five project-authored EN/mixed cases, CC0-1.0 declaration | Retained unchanged; legacy literal gold is author-supplied/unadjudicated |
| v3 (37 cases) | v2 preserved as an identical 19-case prefix; 18 new fictional case definitions with individual CC0 and no-client-data declarations | Tests four-dimensional contract boundaries and page metadata; still no real PDF/DOCX/image bytes, OCR, qualified legal review or externally measured quality |

**No real-client, court, litigation, or competitor source** is intended to be included. M0 script checks the declared source rights, historical carry-forward and metadata per new case; it **cannot verify a writer's ownership with a registry**. Any imported real evidence would require its own record of subject/custodian, licence/consent, lawful basis, confidentiality authorization, approved processing environment, retention and deletion and independent reviewer. Do not substitute a generic “anonymized” tag for authorization.

**NL/FR first commercial product; EN additional evaluation cohort.** The authoritative [product definition](../PRODUCT_DEFINITION_2026-10-31.md) freezes Belgian NL/FR v1 domain scope; adding English synthetic cases does not authorize equivalent Belgian English output, search/Word or court-language promises. Mixed cases intentionally test bilingual/trilingual references but not generative translation correctness.

**Real-format supplement (M0 next engineering increment):** [Generator](../../scripts/m0_real_format_fixtures.py) creates verified **real** NL/FR/EN DOCX drafts, selectable text PDFs and image-only scanned PDFs (plus mixed samples) from the entirely fictional v3 source text, with per-file hashes and page/crop metadata. The output is a CI artifact and is independently reopened by [tests](../../tests/test_m0_real_formats.py); see [real-format evidence](REAL_FORMAT_EVIDENCE.md). This removes the prior “no actual PDF/DOCX/image bytes” limitation for **synthetic test assets**, not the independent human/legal review or real-world OCR-quality limits. A project-authored material declaration is not a third-party legal rights opinion.

**Evidence and exclusions:** 37 author-supplied text/metadata scenarios cover clean controls, duplicate identities, page offsets and printed/bundle mismatches, missing/partial inventories, source missing, quote-free references, text discrepancies, translated claims, version conflicts and simulated unavailable OCR. They do **not** prove all DOCX story-region extraction, **measured** physical image OCR confidence, real-world PDF text-layer/visual contradictions, exact source-crop coordinates or realistic aggregate recall. The review packet [TRILINGUAL_ADJUDICATION_PACKET.md](TRILINGUAL_ADJUDICATION_PACKET.md) is the human decision gate.

**Execution and traceability:** run
`uv run --locked python -m scripts.validate_litigation_corpus` (historical v2),
`uv run --locked python -m scripts.audit_m0_trilingual` (current v3),
and both targeted test suites. Attach generated corpus SHA-256 outputs, exact CI workflow/job URL, reviewer attestations and approval decision to any M0 acceptance PR. Keep label status `author_supplied_unadjudicated` until a reviewed new version is approved.

**Formal M0 remains OPEN** without independently recorded qualified human label adjudication, external rights review where needed, and owner approval. Rights-cleared **fictional real-format bytes** and their hashes are a machine acceptance milestone, not a human or regulatory signoff. See [owner decision record](M0_ACCEPTANCE_DECISION.md).
