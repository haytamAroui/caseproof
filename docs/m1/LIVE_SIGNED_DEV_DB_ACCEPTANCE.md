# M1-B — actual CaseProof dev DB signed-RLS acceptance

**Candidate code:** opt-in, dev-only, protected main-only test. **Not yet executed on actual remote DB.** The installed migration is `20261027160745`. This packet does **not** establish independent human security review or M1 completion.

## What this adds

Unlike the existing manual [disposable RLS test](../../.github/workflows/m1b-dev-signed-private-rls.yml), the new [actual dev DB acceptance workflow](../../.github/workflows/m1b-live-dev-private-db-acceptance.yml) connects to the **already migrated** `caseproof-dev` Postgres database. The runner:

1. Pins the project, expected migration, private policies, admin connection hostname/project name, **TLS certificate verification**, main-only manual event and protected environment; refuses to proceed unless Auth users, organizations, memberships, cases and grants are initially **empty**. It aborts on pre-existing dedicated reader login.
2. Creates one randomized **temporary** `caseproof_m1_reader` login with inherited `authenticated` privileges, not a table owner or `BYPASSRLS`. The password exists only in runner memory; this is a runtime acceptance fixture, **not** an approved permanent app role.
3. Uses the official dev Auth Admin API to create three separately confirmed ephemeral users (A1, A2, B1), signs them in over HTTPS, and remotely verifies their genuine signed user identities.
4. In **one transaction**, inserts minimal synthetic rows with two same-org distinct private matters and one foreign-org matter, a synthetic document/version metadata row for each and service-actor audit entries for test grant issuance. **No original file bytes** are put in a bucket and no real clients are involved. This is a test-admin privilege path, **not** a production human grant-issuance implementation.
5. Runs the existing `SignedPrivateMatterReader` over **real remote non-BYPASSRLS Postgres connections**: own matter/source metadata positive, same-org and foreign-org negative, tampered/missing bearer denied, transaction-local actor cleanup, org evidence-action revocation, grant revocation and membership revocation.
6. Attempts to remove exact test data and the temporary DB role **before** deleting Auth accounts. All teardown failures fail the test and demand manual dashboard investigation; there are no unbounded deletes. No credentials, user IDs or source bytes are logged.

## Protected GitHub environment requirements

Existing environment: `caseproof-dev-live-auth` — restrict to **main** and independent reviewers where supported; disable bypass. Keep secrets **environment-only**, not repo/org-wide.

- Existing `CASEPROOF_DEV_PUBLISHABLE_KEY` and `CASEPROOF_DEV_AUTH_ADMIN_KEY` (CaseProof dev only).
- **New** `CASEPROOF_DEV_DB_ADMIN_DSN`: exactly this project's owner connection URL for direct (IPv6) or Supavisor **session** pooler (IPv4), port 5432, database `postgres`, with a privileged password; never a transaction-mode 6543 connection. From **Supabase → caseproof-dev → Connect**; don't invent pooler DNS names. Keep the DSN out of files, logs, chat, PRs and browser code.
- **New** `CASEPROOF_DEV_DB_CA_PEM`: exact trusted Postgres server CA PEM, obtained from the database SSL settings, to enforce `sslmode=verify-full` and server host verification. Do not turn validation off to get a green test.

GitHub Actions → **M1-B actual dev DB signed-user RLS acceptance (manual protected)** → Run workflow → `main`. A merged PR, valid environment secrets and owner-enforced review are necessary. The connector may be unable to dispatch manual workflows: **do not** call the test passed until an actual sanitized workflow log confirms completion and complete cleanup.

## Gates not closed by this workflow

- The ephemeral fixture's admin-written organization/matter/grants are **not** an independently approved production **actor-audited** issuance/revocation API; real human authorization, grant state machine and audit durability remain to be built.
- Auth logout/session revocation and concurrency against real pooled sessions remain separately to be tested. The existing Auth verifier's successful `/user` lookup does not automatically prove immediate logout revocation semantics.
- Original private Storage bytes, immutable source readback, PDF/DOCX/OCR, durable M2 persistence and genuine Word/M4 output are still OPEN.
- No permanent production database login or new migration is deployed by merging this PR. No CI result is an independent human security approval.

Sources: [Supabase DB connection modes](https://supabase.com/docs/guides/database/connecting-to-postgres), [Supabase TLS verification](https://supabase.com/docs/guides/platform/ssl-enforcement), [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security).
