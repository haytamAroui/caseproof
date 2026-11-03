# ADR 0032 — Scoped reviewed release and historical artifact boundary

**Status:** Proposed F6/M4 engineering decision in [PR #178](https://github.com/haytamAroui/caseproof/pull/178), 3 November 2026. Development installation, independent security review, signed-browser acceptance and production approval remain open.

## Context

M3 provides immutable original source versions, a canonical dossier snapshot, saved human review decisions, and F5 correction/recheck. M4 must produce a bounded human-usable report and supported annotated DOCX, then allow an authorized user to retrieve exactly the frozen released bytes after corrections or a worker restart. Existing report reads and review permission are **not** authority to create a released artifact.

The constitutional and workflow-v3.1 hierarchy is retained. S10–S11 supply journey and acceptance requirements, not a parallel verification engine, filing service, or new machine-verdict state.

## Decision

1. **Separate authorization.** Introduce `export:request` only in the existing organization and matter permission arrays. Require an active non-anonymous signed user with both scoped grants, an undeleted matter, current draft version, matching immutable source bundle/inventory confirmation and at least one persisted human decision. Review permission and draft-write permission do not imply export permission. The backend never accepts a caller-authored tenant or review receipt as authority.
2. **One frozen manifest, no reassessment.** Generate bounded JSON, inert Markdown and supported annotated DOCX from the same preserved report and human-decision ledger. Include the exact case, draft, snapshot, source hashes, coverage, review identity and digest, supported output types, byte lengths, SHA-256 hashes and limits. It is a *review provenance record*, not semantic support, lawyer signature, filing certification or a new finding state.
3. **Private durable release.** Commit an immutable manifest and exact artifact bytes in `caseproof.dossier_releases` through the signed, scope-checked PostgreSQL `caseproof_dossier_export_release` function only. RLS remains enabled; direct authenticated and anonymous table access is revoked. Signed permission/readback checks occur on every history, status and binary request. The server verifies both the release HMAC and the independent manifest digest on all read/replay paths, then hashes the actual bounded bytes before download. Matter retention and purge cascade to historical release bytes.
4. **Idempotency and concurrency.** Caller chooses a stable UUID operation ID. A lost POST response is an *unknown* outcome: reconcile exact status with the same ID before any new release command, not blind retry. Transactionally lock the matter before source-currentness and release-count checks, preventing competing-write lock upgrades. Bound historical releases to at most 50 per matter in the development slice, and reject unsupported or oversized outputs before committing.
5. **Historical reads are not current approvals.** Already-released bytes remain retrievable as historical only while the actor still has current export/read grants, the release receipt/digest and stored bytes are intact, and retention allows it. A changed draft/inventory/source invalidates a new current release from stale review, but does not mutate or silently reauthorize an older release.

## Rejected alternatives

- Reusing `review:request` or `draft:write` to authorize a release (privilege confusion).
- Storing authoritative export bytes or signing keys in browser storage (confidentiality and durable integrity failure).
- Regenerating a supposed frozen historical artifact from current sources (historical rewrite).
- Returning success after an uncertain network response, or retrying the POST with a new ID (duplicate release).
- Adopting RFC 8785/Ed25519, universal DOCX tracked changes, optional PDF/CSV, public share links, external court filing or a Word host as F6 prerequisites without separate ADR and independent acceptance.

## Contract and test evidence

- Backend routes: `apps/api/dossier_export_release.py`, mounted by the existing dossier API; new versioned `caseproof-reviewed-release-v1` and `caseproof-release-preview-v1` responses. No new machine finding enums or reclassification rules.
- Development SQL candidate: `supabase/migrations/20261103080000_f6_reviewed_release_ledger.sql`.
- Frontend: `frontend/src/features/exports/`, existing session-fenced binary transport and same-origin workspace routes.
- Tests: `tests/test_f6_reviewed_exports.py`, `scripts/verify_retention_disposable.py`, `frontend/src/features/exports/api.test.ts`, `frontend/tests/exports.spec.ts`.
- Measured acceptance, remaining gaps and explicit nonclaims: `docs/m4/F6_IMPLEMENTATION_ACCEPTANCE.md`.

## Rollback and release controls

Before development installation, review exact constraints, grants, SQL SECURITY DEFINER behavior, retention dependencies and migration order. Development rollback must first ensure no unrecovered private releases or legal holds; never silently discard a legal record. This ADR is **not** permission to install on a shared project or handle confidential client material. Independent legal/privacy/security review and genuine signed-browser NL/FR real-format artifact/reopen/link validation are separate gates.
