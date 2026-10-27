# M1-B private-matter migration — live dev verification receipt

**Observed:** 27 October 2026, connected Supabase MCP, project `caseproof-dev`.
**Disposition:** **INSTALLED in development; engineering security configuration verified; signed-user acceptance OPEN; independent human security review NOT VERIFIED.**
This receipt supersedes *only* the pre-deployment inventory statements in the earlier [rollout packet](EXACT_DEV_PRIVATE_SCHEMA_ROLLOUT.md). It does not approve production or confidential customer matter processing.

## Verified live state (read-only inspection)

- Supabase migration history contains `20261022001009_caseproof_tenant_foundation` and **`20261027160745_caseproof_m1_dev_atomic_private_grants`**.
- `caseproof._m1_matter_grants` exists, with RLS enabled. All eight currently inspected `caseproof` relations have RLS enabled, including cases, documents, document_versions, membership, audit, and idempotency relations.
- The old permissive organization-wide `tenant_case_read`, `tenant_document_read` and `tenant_document_version_read` policies are absent. Their replacements are `m1_private_case_read`, `m1_private_document_read` and `m1_private_document_version_read`. The own active matter-grant SELECT policy is `m1_own_private_grant_read`.
- Inspected policy expressions require `auth.uid()`, current active organization membership, current active exact-case grant and appropriate actions: `case:read` for cases; both `case:read` and `evidence:read` for documents and source versions. Access is not inferred from an organization membership alone.
- Table privilege inspection: `anon` has no SELECT on CaseProof tables; `authenticated` has SELECT but no INSERT/UPDATE/DELETE on organizations, organization_members, cases, documents, document_versions and _m1_matter_grants; neither role has direct access to audit_events or idempotency_records. `anon` has no USAGE on `caseproof`; `authenticated` has USAGE.
- Schema/data inspection: **zero** `auth.users`, organizations, memberships, matters and grants. Positive authorized retrieval and adversarial same-organization denial have therefore **not** been established on this live database.
- Database role inspection: `authenticated` is non-login and non-BYPASSRLS; `postgres` and `service_role` have BYPASSRLS. The expected non-owner/non-BYPASSRLS application login `caseproof_m1_reader` does **not** exist on this dev project.
- The Supabase Security Advisor reports two **INFO** `rls_enabled_no_policy` notices on `caseproof.audit_events` and `caseproof.idempotency_records`. These are intentionally denied from client roles at present; do **not** introduce broad policies merely to silence the notices. [Advisor reference](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy).
- No M2 brief/check/reviewer tables are included in this migration.

## What this proves, and what it does not

Installed policy names, RLS flags and GRANTs have been verified **on the target development database**, not merely in a disposable fixture. They are necessary but insufficient. Because there are no dev Auth users or assigned matters, **no genuine positive/negative signed-user access test has been run against this database**. This inspection was not an independent human security review. A green [ephemeral signed-Auth workflow](../../.github/workflows/m1b-dev-signed-private-rls.yml) is still a test against **disposable** PostgreSQL, not live remote DB integration.

## Next gated acceptance sequence

1. Independently review the installed exact migration, security threat model, table/schema GRANTs, PostgREST exposure, rollback-to-deny path and audited grant issuance/revocation. Record a human reviewer and approval evidence; neither a script nor this receipt may impersonate that approval.
2. Provision the fixed `caseproof_m1_reader` app login only through a reviewed, least-privilege, secret-managed deployment; it must not own tables, bypass RLS or be available to a browser. Review how the real verified bearer is bound to a transaction-local subject, transport and pool cleanup.
3. Provision confirmed A1/A2 (same organization, *different* matter grants) and B1 (foreign org) through supported development-only Supabase Auth. Never SQL-insert `auth.users` or fabricate signed tokens. Populate controlled synthetic case/source-version fixtures and trusted audited grants, never confidential customer data.
4. Exercise the **actual dev DB** through remotely verified bearer → restricted login: positive own-case+source-version read, denied same-org ungranted matter and cross-org read, tampered/expired token, permission/grant/membership revocation, pool reset, signed-out session behavior. Capture sanitized pass/fail evidence, migration identifier and test commit SHA; cleanup test identities through supported Auth admin APIs.
5. Separately build and deploy reviewed M2 schemas, real private immutable Storage, PDF/DOCX/OCR fidelity, exhibit confirmation, durable review/recheck, and the Word/M4 journey. Do not treat the M1 RLS deployment as evidence that these exist.

References: [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security), [M1 Backend Exit Contract](BACKEND_EXIT_CONTRACT.md), [security gate](PRIVATE_RLS_AUTH_GATE.md), [authoritative roadmap](../ROADMAP.md).
