# F5 — Correction preview, commit, activation and recheck

Status: supported F5 implementation delivered; genuine signed development acceptance passed at `526b8ef2`. Final amended-head CI remains required in PR #177. External security/legal/privacy and release approvals remain separate.

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

## Pre-acceptance development record (superseded by evidence below)

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

## Development integration update

- Upstream head `63d2a3be` includes the authenticated-session browser-test fix.
- Recovery lookup installed in `caseproof-dev` (`ldwmocpxwskvhoojndrd`) as
  `20261103033846_f5_dossier_correction_recovery`; definition and grants verified
  through MCP. Anonymous execution denied; authenticated access is still checked
  against current membership, reviewer grants and actor-scoped operations.
- Fixture derivative registration installed as `20261103034132_f5_correction_fixture_ownership`.
  This hook records exact file paths during reservation for protected registered
  test matters before any upload. Matters without registry ownership are unaffected.
- Protected F5 workflow extends the real signed F3/F4 journey with preview, lost
  commit acknowledgement, durable reconciliation, activated-version recheck,
  comparison and cold reopening. The existing wrapper always tears down owned
  objects and verifies zero residuals. Execution remains pending at this update.
- Existing development advisors report SECURITY DEFINER exposure warnings and
  leaked-password protection disabled; catalog verification is not independent
  security approval or genuine signed-user RLS acceptance.
- Production was untouched. Full F5 acceptance remains OPEN until final-head
  disposable SQL, protected browser and all applicable cloud checks pass.

## Genuine signed development acceptance — 3 November 2026

[Protected run 41574806741](https://github.com/haytamAroui/caseproof/actions/runs/41574806741)
at `526b8ef203b94cfd28361218d766001ee8634fe3` passed against the real development
backend using registered synthetic DOCX, inventory, text PDF and scanned PDF.
The run executed exact preview, explicit commit/activation with a deliberately
lost acknowledgement, read-only operation reconciliation, activated-draft
recheck, independent report comparison, original-byte SHA-256 readback, process
restart/sign-in, historical-to-active recovery, empty new-draft review history,
and genuine signed revoked-recovery denial. It verified Storage empty and
`ZERO_RESIDUAL_VERIFIED` after teardown, including the registered derivative.

Disposable PostgreSQL acceptance also passed at this revision: competing
activation, stale-parent rejection, idempotent replay, revoked membership/grants,
audit rollback, derivative registration rollback and preservation of the prior
review row while the new snapshot has no decisions. These role-bound SQL tests
are not presented as genuine live Auth tests.

Both installed function bodies match repository SHA-256 values:
- Recovery: `104604bb8cdfabfb8411d83049d9bcfb4bf73613f39a8f90d0d82710bdb2d8e3`.
- Fixture ownership: `e7bac5fadd37784dd0da73c10c43fe18cb0e37f9b1bc103a1be0e098bd57496c`.

A prior protected run failed shortly after sign-in; its cause was not established.
Stage diagnostics were added without exposing credential or document arguments.
The fixed public exception contract is covered by an unchanged regression test.
The passing run above does not erase that observation.

Final integration includes bounded 180-second correction/recheck deadlines and
accessible pending feedback. The final amended commit must pass all applicable
checks; exact final SHA and workflow links are recorded in PR #177. The tested
correction scope is deliberately conservative: plain single-run main-body
references; complex structures, ambiguous occurrences and tracked changes abstain.
No representative legal-corpus accuracy or production approval is claimed.

The automatically triggered ready-for-review run subsequently localized an
early failure to creation-response capture, before source upload. The harness
now captures the actual signed creation response through `route.fetch`, records
the matter before forwarding the response, and avoids reading response bytes
after navigation. It does not retry matter creation. Signed F5 acceptance runs
on PR code changes (including drafts), reopening and manual dispatch; changing
review metadata alone no longer starts a duplicate live fixture run.
