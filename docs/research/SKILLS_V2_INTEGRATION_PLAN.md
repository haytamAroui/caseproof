# CaseProof Skills v2.1 integration contract

**Status: staging / not installed.** Source: user-provided `CaseProof_Complete_Skills_v2.1.zip` (18 skills, product and landing workflows). The archive is a review artifact; it is not committed in this PR yet. Do not claim activation or production readiness.

## Source-of-truth checks against frontend/BLUEPRINT.md v1.1 (2026-11-02)
- Current frontend is Vite 8 / React 19 / strict TypeScript 6, React Router 8, TanStack Query 5. Do not use Next.js examples as implementation defaults.
- Python backend and generated API contracts own verification, authorization, review, versioning, release and export. Do not invent DTOs or frontend verdicts.
- Identity, page mapping, fidelity, support and processing coverage must be independently displayed; no overall verified badge.
- PDF.js viewer must honor source/hash/version and page geometry bindings. DOCX preview is derived and not Word-identical.
- Stable operation IDs, ambiguous outcome readback, session fencing, cache/object URL clearing, and no optimistic review confirmation.
- No external CDNs, telemetry, browser persistence or unapproved hosted models for confidential documents.
- NL/FR/EN accessibility and terminology need real native/legal review; synthetic fixtures do not satisfy that gate.
- Landing examples must be labelled synthetic and deployment claims bounded by actual evidence.
- Correction is a new draft derivative, never modification of the immutable original; redline tooling is an evaluation candidate only.

## v2.1 skill names and authority
Router: caseproof-router. Shared: foundation, i18n-accessibility. Product: frontend-engineering, evidence-ui, tabular-review, document-correction, recovery-session, report-export, verification-workflow, case-pack-invoice, product-qa. Landing: landing-page, claims-copy, motion, animation-review, diagram-flow, landing-qa. See archive README/MIGRATION for all 18 and do not install competing v1 names.

## Interaction with this PR
The existing `caseproof-verification-orchestrator` and `caseproof-recovery-ux` are research-stage supplements; they MUST NOT auto-activate alongside v2.1 verification-workflow and recovery-session. Compare rules and fold useful test cases into v2.1 before removing duplicate discovery folders. The `caseproof-legal-workflow-packs` skill is a separate future data-pack authoring guide; it must not introduce doctrinal Belgian claims.

## Integration gates
1. Preserve and hash original archive; unpack into review workspace; check for symlinks/traversal and manifest.
2. Validate names, references, frontmatter, checksums and QA ledger schemas.
3. Compare skill content to authoritative blueprint and live generated contract; log exact discrepancies.
4. Install only one active name per purpose after review; keep migration mapping.
5. Verify skill discovery and activation in the target agent harness.
6. Execute one real finding→source→saved human decision→readback with session-expiry and version-change negatives.
7. Execute one synthetic multilingual landing near-miss with pause/replay/manual inspection, reduced motion, responsive and accessibility tests.
8. Report build, CI, browser, security and practitioner acceptance evidence separately. No merge until completed or explicitly scoped.

## External-source controls
Mike OSS (AGPL), Anthropic legal plugins, Judicex, safe-docx and community skills are research inputs only. Require commit pin, licence review, threat model, no-network evaluation and fixture results before vendoring code. In particular, do not import CC-BY-NC visualization source into commercial product.
