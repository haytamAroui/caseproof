# M1 — CaseProof-dev live private RLS audit through Supabase MCP

**27 October 2026** — Project `caseproof-dev`, ref `ldwmocpxwskvhoojndrd`. This document replaces the abandoned direct-Postgres-GitHub acceptance candidate in PR #95. **No new database DSN or CA certificate secret is required.**

## What was actually verified

The read-only catalog query in [`scripts/m1_live_mcp_readonly_audit.sql`](../../scripts/m1_live_mcp_readonly_audit.sql) was **executed through the connected Supabase MCP** `execute_sql` action against the real development database. Its result:

| Check | Observed |
| --- | --- |
| Migration `20261027160745` installed | true |
| One expected private SELECT policy per protected relation; no overlapping SELECT/ALL policy | true |
| All four protected relations have RLS, authenticated SELECT but no authenticated write and no anon SELECT | true |
| `audit_events` / `idempotency_records` have no client SELECT policies | true |
| Permanent `caseproof_m1_reader` DB login absent | true |
| Auth users, organizations, cases and matter grants | **0 each** |

The Supabase Security Advisor still lists two informational `rls_enabled_no_policy` notices on audit/idempotency, **consistent with deliberately unavailable client policies**. The query also checks for `auth.uid()`, case/evidence action requirements and matter predicates; **this is a catalog structural inspection, not a proof that particular signed users are correctly isolated**.

## How to repeat

Use the connected **Supabase MCP**, select the exact project ID above, and execute the **read-only** SQL in `scripts/m1_live_mcp_readonly_audit.sql` using the `execute_sql` action. Also run `list_migrations` and `get_advisors(type=security)`. No GitHub Actions DSN, administrator credential, CA secret, database-role creation, fixture creation or SQL data mutation is required.

Avoid running this query against a different project or replacing it with a fictitious CI result. A subsequent nonempty dev state does not prove a security failure, but means the zero-fixture snapshot has changed and must be reviewed.

## Genuine Auth testing — existing protected workflow, no new secrets

The existing [manual M1-B signed Auth to **disposable RLS** workflow](../../.github/workflows/m1b-dev-signed-private-rls.yml) already creates three genuine, confirmed ephemeral Supabase Auth users through supported Admin APIs, verifies remote sessions and binds them to a **local disposable** non-BYPASSRLS PostgreSQL database. It uses the existing protected `caseproof-dev-live-auth` **environment-only** `CASEPROOF_DEV_PUBLISHABLE_KEY` and `CASEPROOF_DEV_AUTH_ADMIN_KEY`. It verifies no live-dev database authorization, but exercises same-org and cross-org matters, original-version metadata, revocation and transaction cleanup against the same reader.

**M1-B is still OPEN.** Supabase MCP `execute_sql` runs privileged catalog/admin queries and does not automatically become an unprivileged connection cryptographically bound to a real end-user JWT. Reporting MCP role/claim simulation as real signed-user live-database acceptance would be misleading. A future live application integration test must provide a genuine least-privilege runtime path and actor-audited grant issuance; no shortcut via `postgres`, `service_role` or manual claim injection should be accepted. Independent human security review, private Storage, real-original workflows, M2 persistence and Word/M4 delivery are separate pending gates.

## Security boundary

No change to deployed migrations, RLS policies, Supabase Auth users, storage buckets, database roles or tenant rows was performed in this audit. The new PR removes its previously proposed privileged GitHub Action credentials and runner rather than concealing them in another configuration.

References: [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security), [Supabase database advisors](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy).
