# F1 workflow v3.1 retrofit — 2 November 2026

Scope: S0 signed access, S11 historical navigation, S12 recovery, S13 private-state boundaries. C05/C06/C12/C14/C16/C20/C21/C24/C25 apply. Existing ADR 0027 and generated workspace contracts remain authoritative. No database, provider, permissions, persistence, dependencies or deployment changes.

| Requirement | Audit classification | Implementation / evidence |
| --- | --- | --- |
| Signed grants, foreign/ungranted denial, current-grant revocation, browser-clock expiry, cold sign-in | Already implemented | [F1 engineering receipt](F1_SIGNED_WORKSPACE_ACCEPTANCE.md); not a new live run |
| Cancelled old-view response can still process denial or body | Confirmed missing fence | `shared/api/transport.ts`; adversarial unit tests deliver 200/401/403/404 and a body stream after abort; session remains current, no bytes returned |
| Session-loss return navigation | Confirmed missing | `app/recovery.ts`, `app/App.tsx`; validated read-only matter/report binding, memory only, explicit reopen after fresh sign-in; no automatic action or restored forms |
| Accessible recovery and fresh denial | Added synthetic regression | `tests/auth.spec.ts`: expiry purges DOM, reconnect does not reopen automatically, explicit reopen performs a fresh read and revocation clears again; axe scan |
| Processing/access disclosure | Confirmed missing on sign-in | Existing details/semantic primitives; development/synthetic scope, unknown deployment policy and download limits; no compliance assertion |
| Section 23 guide pointer | Confirmed missing | Added authoritative blueprint stage mapping and F1 rules; existing receipts preserved |
| Genuine signed browser against the retrofit code head | Passed on `ffe83b45d42948be9de47b7f89958c31317cfd03` | [Protected run 41437514935](https://github.com/haytamAroui/caseproof/actions/runs/41437514935): genuine sign-in, cold reopen, expiry/relogin/explicit recovery, foreign/ungranted/revoked denial and zero-residual teardown |
| Independent privacy/security/manual screen-reader/representative corpus/deployment approval | Open independent gates | No approval inferred from CI or prior receipts |

Rollback: revert this PR; no stored data or API migration. Recovery destination is a navigation hint, never access authority. Expiry/revocation cannot recall previously downloaded files or erase information already observed. No continuous revocation monitoring added.

## Measured execution evidence

Executable head `ffe83b45d42948be9de47b7f89958c31317cfd03` passed all 17 ordinary PR workflows plus the protected genuine signed-browser workflow (18 successful workflow conclusions). [Frontend CI](https://github.com/haytamAroui/caseproof/actions/runs/41437521527) ran 61 frontend unit tests, 17 production-build browser tests including axe, 57 affected Python tests, generated contract checks, Ruff/mypy, lint/build and policy checks. [F1 disposable PostgreSQL](https://github.com/haytamAroui/caseproof/actions/runs/41437521352) also passed. The kernel workflow separately retains the full locked regression and deliberately protected live gates; do not confuse skipped general live jobs with the separately executed F1 run.

[Protected genuine run 41437514935](https://github.com/haytamAroui/caseproof/actions/runs/41437514935) emitted:

- `F1_GENUINE_EXPIRED_HISTORY_EXPLICIT_RELOGIN_REOPEN_PASSED`
- `F1_GENUINE_SIGNIN_CATALOG_REPORT_COLD_RELOAD_FOREIGN_UNGRANTED_AND_BROWSER_CLOCK_EXPIRY_PASSED`
- `F1_GENUINE_GRANT_REVOCATION_DENIAL_AND_PRIVATE_VIEW_CLEAR_PASSED`
- `M05_STORAGE_EMPTY_VERIFIED`
- `ZERO_RESIDUAL_VERIFIED`
- `DOSSIER_COMPLETE_SIGNED_JOURNEY_AND_TEARDOWN_PASSED`

Browser expiry advances the browser clock against a genuine provider expiry; it does not prove wall-clock provider expiry. Fresh login restores the Python Playwright clock with epoch seconds. Real report assertions use the existing 30-second client read budget, without automatic retry or changed acceptance outcomes. Diagnostics emit only fixed stage names and HTTP status numbers. Earlier failed runs retained independent zero-residual cleanup and are not passing acceptance evidence.

Local commands also passed: frontend contracts/lint/policy/tests/build; affected Python Ruff and strict mypy; 22 workspace auth/report/catalog tests. Local Chromium download failed, so browser evidence above comes from actual GitHub cloud runners. This receipt-only follow-up changes no executable code, SQL, workflow or dependencies. Its own cloud status must still be checked before merge. Independent review, privacy/security/manual accessibility, representative fixtures and production approval remain open.
