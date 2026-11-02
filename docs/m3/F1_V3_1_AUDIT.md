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
| Genuine signed browser against this retrofit head | Unverified until executed | Existing protected workflow remains a separate acceptance gate; synthetic routes do not prove live RLS |
| Independent privacy/security/manual screen-reader/representative corpus/deployment approval | Open independent gates | No approval inferred from CI or prior receipts |

Rollback: revert this PR; no stored data or API migration. Recovery destination is a navigation hint, never access authority. Expiry/revocation cannot recall previously downloaded files or erase information already observed. No continuous revocation monitoring added.

Execution evidence will be appended after checks run. No passing claim is made by this audit table alone.
