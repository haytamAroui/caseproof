# M1-B — exact-dev-foundation private-grant installation packet

**Status: SQL candidate + disposable CI. NOT deployed. October 27, 2026.**

## Live read-only inventory

Via connected Supabase MCP, the dedicated **caseproof-dev** project
(`ldwmocpxwskvhoojndrd`) has:

- PostgreSQL 17.11; only installed canonical migration
  `20261022001009_caseproof_tenant_foundation`.
- Zero Auth users, organizations, memberships, matters and source documents.
- No `caseproof._m1_matter_grants` table, no M2 brief tables.
- Installed policies `tenant_case_read`, `tenant_document_read`,
  `tenant_document_version_read`, and `own_active_membership_read`.
  These are still organization-wide reads; they are not private-matter access.
- Supabase Security Advisor has two **INFO** findings for the deliberately
  default-denied `audit_events` and `idempotency_records` tables, with
  no direct client grants. This is not a reason to create permissive policies.
  [RLS linter reference](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy).

No SQL writes to this connected dev project were performed.

## What is proposed

[`PIV-M1_DEV_atomic_private_grant_install.sql`](../../db/proposals/PIV-M1_DEV_atomic_private_grant_install.sql)
is the **single-transaction** proposal for the presently empty foundation.
Its source policy body is copied from PR #86's reviewed
[`PIV-M1_default_private_rls_candidate.sql`](../../db/proposals/PIV-M1_default_private_rls_candidate.sql).
No disposable M1 function with a client-supplied actor ID is included.

The transaction first **requires** the exact foundation and refuses to run
on a project containing Auth users, organizations, memberships, cases,
documents or original versions, or with unexpected policies or an existing
private grant table. There is no silent backfill or import of cases.

It creates a per-matter, per-actor grant relation whose FK requires an actual
current organization and case. Grant role can only be `viewer` or `reviewer`,
with a bounded actions vocabulary, revision and active flag. It enables RLS,
and publishes only the read-only own-grant policy. **No API role can create,
update, delete, assign or revoke a grant**.

It atomically replaces the foundation's **three organization-wide read
policies** with private rules that require both current active organization
membership and an exact current matter grant:
`case:read` to read cases; `case:read + evidence:read` at both levels
for documents and specific immutable document versions. RLS joins and
`auth.uid()` are evaluated on the server. An unknown SELECT/ALL policy
aborts the transaction rather than ORing itself with the restrictive rules.
No table, source bytes, Vault or other case data become publicly exposed.

This is a candidate only: it deliberately supplies **no signed-user
authenticated matter-assignment transaction**, no admin grant editor, no
sensitive matter list API, no password or privileged service key, and
no `SECURITY DEFINER` functions.

## Required review and deployment sequence

1. Human security owner confirms the dedicated empty dev project's
   precise schema/policies against the live read-only inventory; confirms
   permission vocabulary, case-specific role semantics and attacker model.
   A DBA reviews schema grants, privileges, index behavior, PostgREST schema
   exposure, RLS policy combination and inheritance of the restricted app role.
2. Run the [standalone one-time disposable CI](../../.github/workflows/m1b-private-schema-acceptance.yml)
   on the current migration. It starts an **empty PostgreSQL 17** container,
   runs the canonical foundation, injects and removes rogue SELECT policies
   and unrelated Auth users, proves whole-transaction rollback, installs
   the candidate, proves private same-org and cross-org visibility,
   then tests the true non-BYPASSRLS reader, revocation and pooled-claim reset.
3. Require explicit human approval for a new **canonical reviewed migration
   file**, created using the installed Supabase CLI workflow, then apply to
   **caseproof-dev** only. A GitHub PR merge of this proposal is *not*
   permission to apply SQL, create users or start professional evidence.
4. Verify resulting policies/roles against the connected live DB; keep the
   `caseproof` schema non-public. Do not expose SQL config or its DB login
   credential to browsers. Provision independent development Auth users via
   the approved GoTrue API, with reviewer-sensitive operations later tied
   to session freshness and real authorization.
5. Before any grant writes, implement a **trusted actor-bound audited grant
   issuance/revocation transaction**. A direct SQL admin update without
   actor/audit provenance is not an accepted customer workflow. Include
   reviewed reason, request UUID, grant revision and tenant boundary.
6. Run genuine verified signed A/B/C live database acceptance with an actual
   non-owner/non-BYPASSRLS app connection and positive/negative source
   readback. Then separately verify confidential Storage, DOCX/PDF/OCR
   anchors and human approval before release.

## Incident rollback: deny reads, never restore org-wide visibility

If a policy problem is discovered after a reviewed rollout, the emergency
fallback is **deny**, not restore the previous organization-wide reads.
The DBA/security owner may approve a single-transaction revocation of
`authenticated` SELECT privileges on `cases`, `documents`,
`document_versions` and `_m1_matter_grants` while preserving stored
grants, sources and audit history for investigation. Re-enabling read access
requires a separately reviewed fixed policy and genuine signed-user tests.
Do not blindly execute a down-migration reinstating legacy org-wide SELECT.

The installer is **intentionally NOT rerunnable**. Unexpected schema/data
requires review and a data-aware corrective migration rather than a forced
`IF NOT EXISTS` migration.

## Explicit nonclaims

This packet and its green disposable CI **do not** establish that real
caseproof-dev private policies were deployed, that Supabase Auth sessions
can read real dev cases, that current sessions are revoked on logout,
or that private Storage/LLM/OCR/Word correction is production-secure.
This is PIV-02/M1-B infrastructure engineering, not M1-B final sign-off.

Primary tracking: [#37](https://github.com/haytamAroui/caseproof/issues/37),
[#64](https://github.com/haytamAroui/caseproof/issues/64),
[#68](https://github.com/haytamAroui/caseproof/issues/68).
