# ADR 0027 — F1 signed workspace and frozen-report navigation

Status: implementation candidate for owner-requested complete F1, 1 November 2026.
No production or client-data approval. Security-sensitive changes require review;
passing code tests does not establish independent review or live acceptance.

The static React client uses same-origin development login/logout endpoints over
existing pinned CaseProof Supabase password sign-in and remote `/user` validation.
The server returns only an access token and verified expiry, never refresh tokens.
No new Auth provider, cookies, account creation, password reset, persistent browser
storage, admin credential input or background refresh is introduced. Reload and
expiry require fresh sign-in. Browser timers and request epochs clear local state;
each backend read still performs its existing authorization independently.

The loopback composition can explicitly serve a built frontend from its trusted
filesystem configuration. Static files have a fixed build allowlist, same-origin
CSP, no-store and no-referrer. API paths never use the SPA fallback. No production
mount or automatic exposure is authorized. Login validates origin/fetch metadata,
limits input and attempts, hides provider errors and never logs credentials.
Provider sign-out cannot immediately invalidate already-issued JWTs; current matter
grants and expiry remain server checks. Local clearing does not recall downloads.

## Read-only report catalog proposal

`db/proposals/PIV-F1_workspace_report_catalog.sql` adds one narrowly scoped
SECURITY DEFINER function because authenticated callers cannot read the private
snapshot table. Empty search_path, fully qualified names, explicit nonanonymous
Auth, active membership, exact matter grant permissions and nondeleted case are
required before projecting metadata. PUBLIC and anon have no EXECUTE. No table
access or write permission is granted. This is an exception requiring review,
not a workaround for denied RLS. No new entity, relationship, table or index.

| Existing relation | Relationship / scope | Use |
| --- | --- | --- |
| cases | tenant `org_id`, opaque case ID | Nondeleted authorized parent, shared transaction lock |
| organization_members | `(org_id,user_id)` | Active case/evidence read actions |
| _m1_matter_grants | `(org_id,case_id,user_id)` | Active case/evidence read grant |
| dossier_snapshots | `(org_id,case_id,snapshot_hash)`; composite case FK | Frozen brief ID, hash and creation timestamp only |

The existing snapshot primary key supports 20-row hash-keyset navigation with one
lookahead row. Ordering is explicitly by hash, not time/currentness. There is no
per-row source content, provider data, verdict or human decision in the list.
Opening a link uses the existing frozen-report read, integrity receipt and freshness
checks. Browsing does not create a snapshot or run a check. Empty catalogs do not
assert complete verification. Foreign/revoked/missing resources clear private UI
state; transient service errors show no cached catalog. Legacy manual report links
remain compatible. No new report authority or historical freshness claim.

Installation is separate from preparing this proposal. Disposable PostgreSQL tests
must cover empty/list/paging, same-org ungranted, foreign, anonymous, revoked member,
revoked grant, deleted parent and denied direct-table access. Live installation,
returned migration version and native catalog/advisor evidence must be recorded
before genuine signed browser acceptance can close F1. Rollback revokes/drops only
this new function and removes the new auth/catalog/static integration; snapshots,
originals, existing grants and legacy clients are preserved.

## Verification and disclosure

Ordinary CI runs synthetic transport/browser cases and disposable PostgreSQL.
The separate `caseproof-dev` environment workflow runs actual password login in
Chromium, signed report selection, cold reload/relogin, foreign/ungranted denial,
current-grant revocation and deterministic browser-clock expiry of a real signed
session. Browser-clock expiry is not an observed provider wall-clock expiry.
Existing M0.5 registered fixture setup, finally teardown and independent zero-residual
verification remain mandatory. No browser traces, screenshots or input-value logs
are retained in that genuine credential test. Failure messages are sanitized.

F1 does not include F2 viewer selection, F3 intake, F4 review writes, F5 correction
or F6 export. Existing synthetic backend workflows remain regressions. UI locale
coverage and independent security/manual accessibility acceptance are separate
release gates. No claim of F1 completion until exact-head evidence is recorded.

Provider references: [password sign-in](https://supabase.com/docs/reference/javascript/auth-signinwithpassword),
[sign-out scope and access-token lifetime](https://supabase.com/docs/reference/javascript/auth-signout).
