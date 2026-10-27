# M1-B — Remotely verified Auth → default-private PostgreSQL read boundary

**27 October 2026 | Candidate (not deployed) | CaseProof dev only**

This packet follows [ADR-0017 default-private legal matters](../architecture/ADR-0017.md),
[PR #86's reviewed policy proposal](../../db/proposals/PIV-M1_default_private_rls_candidate.sql)
and [M1 security acceptance gate](PRIVATE_RLS_AUTH_GATE.md).

## Implemented headless reader

`apps/api/signed_private_matter_reader.py` is an application-only,
**unmounted** `SignedPrivateMatterReader`. It takes **only** a bearer
and canonical case/document/version IDs, not actor, org, SQL, tenant header,
role or a raw JWT claim. A configured `SupabaseAuthUserVerifier` contacts
the pinned Auth HTTPS endpoint to validate a real user before any DB claim is
set; expired/unknown/invalid tokens are denied.

The reader uses a DBA-provisioned, **fixed** `caseproof_m1_reader` login
that must be non-superuser, not `BYPASSRLS`, and must not own protected
tables. It inherits the read-only `authenticated` role. Every DB call binds
the remotely verified subject using **parameterized, transaction-local**
`request.jwt.claim.sub`; database `auth.uid()` and current active
organization membership plus exact matter grants are rechecked in SELECT.
A case read requires `case:read`. A source-version metadata read requires
both `case:read` and `evidence:read` at the member and matter level.
No original bytes, approval or write is returned.

Auth-verifier failure / privileged DB role / invalid subject fail closed.
Unavailable data and foreign matters are masked consistently; SQL failures
do not leak source, SQL, role, token or tenant identity. The DB session is
closed after the short read transaction. No direct `service_role` API
credentials or `postgres` owner connection can pass the boundary.

**Threat model limitation:** A direct arbitrary SQL session could set a
`request.jwt.claim.sub` GUC itself. The app DB login must never be made
available to external users; caller-supplied SQL is categorically forbidden.
The only acceptable production runtime is a reviewed server boundary with
its credentials managed outside the browser and an externally verified Auth
bearer. This code does **not** prove protected transport, connection pooling,
current session revocation, or real Supabase's deployed schema by itself.

## Automated, always-on engineering acceptance

`scripts.verify_m1_signed_private_reader`, gated by CI, opens an actual
**non-BYPASSRLS, non-owner** PostgreSQL TCP session against disposable
`127.0.0.1:5432/caseproof_s2_ci`. The login/password are fixture-only
values that must NEVER be reused on Supabase. It tests:

- Three distinct synthetic actors: A/B in the **same** organization with
  separate matters; C in a foreign org. All can read their own case and
  metadata source version; none may read each other's resources.
- Invalid bearer, noncanonical IDs, service-owner connection and SQL errors
  fail closed.
- Revocation of one case grant and one organization membership immediately
  denies the corresponding actor. Removing `evidence:read` denies source
  metadata while preserving `case:read`.
- Transaction-scoped `auth.uid()` does not survive COMMIT on the **same**
  physical PostgreSQL connection.
- No direct tenant ID, user ID or arbitrary DB query can enter the API
  method. SQL is constant and UUID values are bound parameters.

CI's `SyntheticVerifier` is explicitly **not a real signed Auth proof**.

## Manual, real signed-user integration

The new [protected M1-B workflow](../../.github/workflows/m1b-dev-signed-private-rls.yml)
can be **explicitly dispatched from `main` only**, with
`caseproof-dev-live-auth` protected environment approval and existing
environment-only `CASEPROOF_DEV_PUBLISHABLE_KEY` and
`CASEPROOF_DEV_AUTH_ADMIN_KEY` secrets.

It sets up a **local disposable** PostgreSQL service, loads the foundation,
M1 grant tables and default-private RLS proposal, and tests the local
unprivileged DB login. It then asks the pinned Supabase **dev Auth Admin API**
to create **three fresh confirmed ephemeral Auth identities**, generates
random passwords in runner memory, signs in over HTTPS to obtain genuinely
signed project tokens, validates issuer, signature, unique subject, user
identity and rejects a tampered JWT through the remote verifier. Each
actual verified Auth user ID is bound directly to the local, disposable
PostgreSQL fixture (no pseudonym, no claims supplied by HTTP). The **same**
reader checks allowed and forbidden cases/source versions and fresh grant
revocation. A `finally` block deletes all three ephemeral Auth users.
A cleanup failure fails acceptance and requires a dashboard investigation.
No password, token, email, subject UUID or provider response is logged.

**The manual workflow has no authority to install RLS or write matters on the
real Supabase database.** It tests real signed Auth **combined with**
actual read-only PostgreSQL RLS behavior on isolated synthetic rows.
It is **not** the final live remote signed Auth → live private DB E2E test.

## Remaining release gates

The actual `caseproof-dev` project is still missing approved and installed
M1 matter grants and M2 schemas; the last read-only inspection showed zero
Auth users/members/matters. It must not receive real confidential matters
before explicit human security review and reviewed M1 migration. Next:

1. Security approval for default-private RLS (including old policy removal,
   index impact and rollback) and dedicated restricted app login.
2. Controlled migration to **caseproof-dev**, then create real dev
   organization/matter grant fixtures with supported Auth/API provisioning
   and audit; run this reader against actual dev database with a restricted
   non-bypass login, not a test owner.
3. Verify revoked/signed-out session semantics against Supabase's actual
   session state, pooled transaction cleanup and concurrent revocation.
4. Deploy and test private Storage bytes, genuine PDF/DOCX/OCR lineage,
   and durable corrected document recheck.
5. Independent human security approval before staging/customer access.

**No live migration, user provisioning or Auth cleanup is executed by
normal CI or this PR.** The new manual job is an opt-in dev-only
action executed after merge and environment review.
