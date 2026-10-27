# CaseProof dev M1/M2 migration synchronization — 27 October 2026

Project: `caseproof-dev` (Supabase ref `ldwmocpxwskvhoojndrd`). **Development only; no customer data or production access.**

After the owner requested that merged migrations be applied rather than left as proposals, the following SQL was applied through the connected Supabase MCP `apply_migration`, using the merged and disposable-PostgreSQL-tested source SQL with the outer explicit transaction wrapper removed (Supabase migration execution handles the transaction):

| Applied migration version | Name | Code path | Verified result |
| --- | --- | --- | --- |
| `20261027195417` | `caseproof_m2_dev_atomic_private_review` | `supabase/migrations/20261027195417_caseproof_m2_dev_atomic_private_review.sql` | 11 M2 tables; all 11 RLS-enabled; both `anon` and `authenticated` denied direct read/write |
| `20261027195451` | `caseproof_m1_signed_invoker_read_views` | `supabase/migrations/20261027195451_caseproof_m1_signed_invoker_read_views.sql` | 2 PostgreSQL views with `security_invoker=true` and `security_barrier=true`; `authenticated` gets SELECT only, `anon` denied |

Existing migration `20261027160745` (`caseproof_m1_dev_atomic_private_grants`) remains installed and was not reapplied.

MCP inspection after deployment verified no direct M2 table access for client roles, no exposed M2 SELECT policies and no callable M2 trigger functions for `anon`/`authenticated`. The Security Advisor listed 13 INFO items for RLS-enabled tables with no policy (11 private M2 tables plus the two existing server-only audit/idempotency tables); this is the intentional default-deny configuration, **not** a reason to grant browser read access.

**Not implied:** Real positive/negative signed-user live private-matter grants, private Storage original-byte upload/read, HTTP integration with the live M2 writer, human review and full correction/recheck across live Supabase are still separate acceptance work. The previously successful protected one-click run used genuine Supabase Auth tokens against a disposable PostgreSQL/Vault instance. Do not treat migration installation itself as full M1/M2 acceptance.

## Operational rule

When working on a database-changing PR, merge reviewed code, check GitHub's migration file against the applied migration list through **Supabase MCP**, apply only missing approved **development** migrations, then verify tables, RLS, grants and security advisories. If the database is not in the expected state, stop and report drift rather than retry blindly or add database admin credentials to GitHub Actions. Never claim there is an unattended automatic MCP bridge: a developer/agent must perform the connected post-merge step, unless a separately configured deploy pipeline is built.

No manual environment secrets were added for either migration.
