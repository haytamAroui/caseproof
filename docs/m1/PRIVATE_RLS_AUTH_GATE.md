# M1-B Security Gate — default-private matter RLS and real signed-user acceptance

**2026-10-27 | Pre-deployment security proposal; later deployed to dev, with security acceptance still OPEN**

> **Live update:** Exact M1 default-private installation was recorded in Supabase as migration `20261027160745` and verified read-only. [Live M1 deployment receipt](LIVE_DEV_PRIVATE_MIGRATION_RECEIPT_2026-10-27.md). The pre-migration state and proposed SQL passages below are historical context. Independent human review, the restricted app DB login and real signed-user live-db tests remain OPEN.

This packet follows frozen **ADR-0017 default-private litigation matters**.
It does not replace tenant-frozen ADR-0011's sector-neutral Evidence Kernel.
RLS deployment is an authorization-policy change, not a routine migration.

## Current reality / dependency

Live, **read-only** Supabase MCP inspection of project `caseproof-dev` on
2026-10-27: **0 Auth users, 0 memberships, 0 matters**; no
`caseproof._m1_matter_grants` and no `caseproof._m2_brief_versions` tables.
The foundation has older **organization-wide** read policies. Project
schema must not be expanded, nor customers/tests inserted, without approval.

Issues **#37** and **#64** contain older conflicting assumptions about
org-wide case reads; apply the *recorded default-private* decision consistently.
In Postgres, permissive SELECT policies are combined with OR: merely adding
a new private policy alongside `tenant_case_read` would leak other matters.
Our candidate **drops the old org-wide case/document policies** within the
same SQL transaction, then adds exact case-grant predicates.

## SQL candidate

`db/proposals/PIV-M1_default_private_rls_candidate.sql` is **not a
production migration**. It assumes the separately approved M1 grant schema
exists. It changes READ policy and grants only:

- An `authenticated` principal may SELECT its own currently active matter
  grants. An existing active organization membership with `case:read` is
  necessary, but never sufficient to read an unassigned case.
- `cases`: active org `case:read` **and** active exact-case grant with
  `case:read`.
- `documents` and `document_versions`: both **case:read + evidence:read**
  in active org membership **and** the same exact-case grant.
- Grant lookup is ownership scoped through `auth.uid()`; no
  `user_metadata` or client-provided role/tenant is an authority.
- `anon` has no table privileges, and `authenticated` receives SELECT
  only. No INSERT/UPDATE/DELETE, no audit data, no private Vault, no
  exhibit/m2 control-plane access, no new SECURITY DEFINER functions,
  and no privileged helper.
- Explicit indexes support active case + actor lookups.

Supabase reference: [RLS and grants](https://supabase.com/docs/guides/database/postgres/row-level-security).
The approved operating role and exposure of the private `caseproof` schema
must be independently reviewed. Do not expose all private tables through
PostgREST just to make this test pass.

## Disposable CI acceptance — real PostgreSQL RLS, NOT real signed JWTs

`scripts.verify_m1_private_rls` applies the proposed policy **only** to the
localhost disposable PostgreSQL CI service, after M1/M2 fixtures.
It creates 2 separate orgs with 3 users/3 matters plus a foreign user.
The test checks:

- Each user reads only its **one** assigned matter, even when both
  users are active members of the same organization.
- Read-only access to exactly one document and original version; no
  cross-org, cross-case, arbitrary role, audit or M2 event read.
- An evidence action removed at org level denies evidence while retaining
  case read. Removing matter case:read denies the case AND evidence.
- Revoked matter grant and revoked membership remove all visible private
  records on the next statement; no legacy org-wide policy survives.
- Two transactions in the same `psql` connection show that `SET LOCAL`
  claim/role context has no leakage after commit; anonymous and SQL
  mutation attempts fail.

**Fixture warning:** setting `request.jwt.claim.sub` inside CI is only a
role-policy test. It proves **NOTHING** about whether an HTTP token was signed.
Never grant users direct DB credentials that can freely SET JWT claims.
Do not confuse successful PostgreSQL RLS fixture tests with end-user Auth.

## Separate real signed-user acceptance required for M1-B

1. Security owner approves the schema diff and removes all conflicting
   organization-wide policies. Write a rollback plan that fails private,
   **never** restores insecure org-wide reads implicitly.
2. Provision two confirmed, development-only Supabase Auth accounts in one
   org and one in another through a **supported Auth API/dashboard flow**.
   Do **not** SQL insert into `auth.users`, create synthetic JWTs as real
   sessions, or publish passwords/tokens in CI artifacts or chat.
3. Use a real user bearer accepted by the pinned Supabase Auth server
   (`SupabaseAuthUserVerifier` already exists), then a reviewed
   least-privilege PostgREST/DB access boundary. A user's `id` is from the
   **verified bearer**, never X-Tenant-Id, HTTP user_id or custom SQL.
4. Prove actual signed A1/A2/B1 same-org, per-matter, and cross-org isolation
   with positive tests that retrieve allowed source versions. Prove
   tampered/expired/unknown token failures, grant/action revocation,
   session invalidation and database connection/session cleanup.
5. Test with an actual **non-BYPASSRLS** runtime role, not owner,
   `postgres`, service_role or a privileged custom role. Verify grants and
   effective `current_user`; ensure no secret key enters browser/UI.
6. Approve production storage/inventory, human `draft:write` policy, and
   confidential/legal source handling in separate gates.

**No live SQL, auth users, sessions, storage policies, production migration or
customer documents were created by this candidate.** M1-B, M1-C and M2-B
remain OPEN until genuinely authenticated acceptance and human security signoff.
