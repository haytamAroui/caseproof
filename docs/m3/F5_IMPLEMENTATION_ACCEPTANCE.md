# F5 — Correction preview, commit, activation and recheck

Status: implementation OPEN; this document is an acceptance checklist, not a completion claim.

Authority: `frontend/BLUEPRINT.md` governs UI architecture; `docs/PRODUCT_WORKFLOW.md` governs stage behavior; existing Python correction and draft-revision contracts govern writes. Do not create another roadmap or rewrite the blueprint.

## W06 — Preview

- Bind the requested edit to the authenticated matter, exact draft version, report snapshot, supported DOCX part/range and immutable source hashes.
- Obtain exact old/new text and supported-span assessment from the backend. Display accessible semantic deletion/insertion and exclusions without changing originals.
- Fail closed on ambiguous anchors, unsupported DOCX structures, changed revisions, revoked access or conflicting input.
- Preview is read-only and cannot imply successful application or human approval.

## W07 — Commit, activation and recheck

- Require explicit user confirmation and an operation ID bound to the complete request payload.
- Revalidate authorization, draft version, report context and preview preconditions server-side at commit.
- Preserve original bytes and hash; produce a distinct, content-addressed derivative draft and atomically activate only the authorized version.
- Treat lost acknowledgement as unknown, never success. Reconcile through authorized durable status/readback; do not blindly repeat consequential writes.
- Recheck the active draft through the canonical verification pipeline and show old and new reports as distinct immutable snapshots, preserving independent identity/page/fidelity/support and coverage dimensions.
- Invalidate dependent old approvals; do not carry human dispositions or export authorization to the new version automatically.

## Acceptance gates

- Python, SQL and generated TypeScript/schema contracts agree; negative cases reject stale, unsupported, cross-matter and revoked requests.
- Tests prove original SHA-256 unchanged, no duplicate activation, rollback on failed commit, and deterministic recovery after timeout/restart.
- Browser acceptance uses an actual signed user, preserved synthetic DOCX and evidence, preview → explicit commit → activate → recheck → compare → cold reopen.
- Accessibility, architecture, security and all applicable CI checks pass at the exact PR head SHA. Skipped external gates remain explicitly open.
- Update `frontend/BLUEPRINT.md` and `docs/STATUS.md` with linked evidence only after tests pass; never replace architecture authority or claim legal/security approval.

## Implementation order

1. Inventory existing correction routes, draft revision SQL and frontend transport/generated contracts.
2. Add missing contract/negative tests and backend transition/reconciliation behavior.
3. Implement W06 and W07 within `frontend/src/features/corrections` and compose with the existing workspace.
4. Run targeted tests, signed-browser acceptance and full CI; fix failures before ready-for-review.

## Pending implementation review

The working changes add server-resolved main-body reference anchors, fail-closed
preview and commit checks, actor-scoped recovery metadata, and independent
previous/rechecked report views. These are implementation candidates, not an F5
completion claim. The recovery RPC proposal requires disposable PostgreSQL
adversarial tests and independent security review before any development
migration. Signed-browser acceptance must register and clean up derivative
objects even if the commit response is lost. Recheck/version binding, cold
reopening, revocation, competing operations, and actual final-head cloud CI
remain acceptance gates.

## Local verification before combined commit

Full local Python suite: 2,031 passed, 4 skipped, 0 failed. Frontend lint,
typecheck, 78 existing unit tests and production build passed. The added
Playwright correction journey has not executed: both Chromium downloads returned
invalid archives. Disposable PostgreSQL recovery tests are wired into CI but
have not executed locally; the runner cannot run PostgreSQL under a non-root UID.
Recovery SQL remains a proposal in `db/proposals/F5_dossier_correction_recovery.sql`,
not an installed migration. Genuine signed-browser acceptance and final-head CI
remain open. No production deployment or live database change was performed.
