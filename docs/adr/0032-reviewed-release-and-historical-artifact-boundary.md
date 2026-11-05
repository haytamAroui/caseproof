# ADR 0032 — Scoped reviewed release and historical artifact boundary

**Status:** F6/M4 development implementation in [PR #178](https://github.com/haytamAroui/caseproof/pull/178), 3 November 2026. The release migration was installed in **caseproof-dev** as version `20261103083932`, with RLS/private-table/function permissions checked; signed-browser acceptance and independent security/production approvals remain separate gates.

## Context

M3 provides immutable original source versions, a canonical dossier snapshot, saved human review decisions, and F5 correction/recheck. M4 must produce a bounded human-usable report and supported annotated DOCX, then allow an authorized user to retrieve exactly the frozen released bytes after corrections or a worker restart. Existing report reads and review permission are **not** authority to create a released artifact.

The constitutional and workflow-v3.1 hierarchy is retained. S10–S11 supply journey and acceptance requirements, not a parallel verification engine, filing service, or new machine-verdict state.

## Decision

1. **Separate authorization.** Introduce `export:request` only in the existing organization and matter permission arrays. Require an active non-anonymous signed user with both scoped grants, an undeleted matter, current draft version, matching immutable source bundle/inventory confirmation and at least one persisted human decision. Review permission and draft-write permission do not imply export permission. The backend never accepts a caller-authored tenant or review receipt as authority.
2. **One frozen manifest, no reassessment.** Generate bounded JSON, inert Markdown and supported annotated DOCX from the same preserved report and human-decision ledger. Include the exact case, draft, snapshot, source hashes, coverage, review identity and digest, supported output types, byte lengths, SHA-256 hashes and limits. It is a *review provenance record*, not semantic support, lawyer signature, filing certification or a new finding state.
3. **Private durable release.** Commit an immutable manifest and exact artifact bytes in `caseproof.dossier_releases` through the scope-checked PostgreSQL `caseproof_dossier_export_release` function: user JWTs authorize read/status/list/artifact, but **only the backend service role may execute a release write after independently verifying the bearer through Supabase Auth**. The signed user's UUID is passed as a trusted service assertion, and PostgreSQL rechecks current organization/matter export grants under a case lock. A direct browser RPC cannot forge a server HMAC. RLS remains enabled; direct authenticated and anonymous table access is revoked. Signed permission/readback checks occur on every history, status and binary request. The server verifies both the release HMAC and the independent manifest digest on all read/replay paths, then hashes the actual bounded bytes before download. Matter retention and purge cascade to historical release bytes.
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
- Development SQL source: `supabase/migrations/20261103080000_f6_reviewed_release_ledger.sql`; installed on `caseproof-dev` as `20261103083932` after passing disposable migration validation.
- Frontend: `frontend/src/features/exports/`, existing session-fenced binary transport and same-origin workspace routes.
- Tests: `tests/test_f6_reviewed_exports.py`, `scripts/verify_retention_disposable.py`, `frontend/src/features/exports/api.test.ts`, `frontend/tests/exports.spec.ts`.
- Measured acceptance, remaining gaps and explicit nonclaims: `docs/m4/F6_IMPLEMENTATION_ACCEPTANCE.md`.

## Rollback and release controls

Before any further development installation or production promotion, review exact constraints, grants, SQL SECURITY DEFINER behavior, retention dependencies and migration order. The development installation completed with a private RLS table and separated authenticated read/trusted-write RPC. Development rollback must first ensure no unrecovered private releases or legal holds; never silently discard a legal record. This ADR is **not** permission to promote to production or handle confidential client material. Independent legal/privacy/security review and genuine signed-browser NL/FR real-format artifact/reopen/link validation are separate gates.


## 5 November 2026 amendment candidate — T30–T34 review completeness

**Status:** Candidate product policy (D02) awaiting owner acceptance and exact-head CI/signed acceptance. This section extends, but does not waive, the reviewed-release authorization and historical integrity conditions above.

- The unit of review completeness is **one distinct detected finding reference**, not one raw persisted decision row. Every detected finding requires an applicable signed human disposition; supported, qualified and contradicted dispositions each count as *reviewed*, but never as verified or legally approved. Repeated identical decision rows do not increase the count; conflicting operation identities and orphan/malformed decisions fail closed.
- **Blocked:** zero detected findings or zero applicable human decisions. The report may be inspected using its existing read path; no reviewed-release claim follows from an empty set. **Partial:** at least one applicable finding decision, but some detected findings remain unreviewed. A partial release requires explicit acknowledgement at commit, states the unreviewed count and remains explicitly partial in the signed manifest. **Complete review:** every detected finding has at least one applicable saved decision. It establishes review-list completeness only, never OCR/text/source/semantic/filing completeness.
- Preview and commit use the same server calculation and do not trust a caller's readiness flag. The snapshot, current draft, grant and ledger are revalidated for the commit; the SQL trusted release RPC retains final transactional currentness, exact persisted-decision equality, signature and source checks. An interrupted commit is reconciled through the existing operation ID, never by blind retry.
- **Compatible schema:** Keep the installed v1 manifest and SQL storage schema; new manifests add a signed \`release_policy\` object. Older signed v1 manifests without that object remain byte-for-byte immutable and reopen as **legacy / completeness not attested**. Existing HMAC, manifest digest and artifact hash verification apply to both. Unknown policy versions fail closed; no SQL deployment is requested by this change.
- The export checklist must show separate release eligibility, finding-review completeness and coverage/abstention limitations. A release label cannot imply legal approval. User-facing links lead only through existing authenticated reference inspection and historical routes.

**Engineering acceptance still required:** final-head locked tests, frontend contract/build, signed browser partial/complete/revocation/recovery, independent security and lawyer pilot sign-off. No existing historical evidence is relabeled complete.
