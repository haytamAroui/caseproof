# Live platform hardening receipt — `caseproof-dev` (2026-11-12)

**Scope:** development Supabase project `ldwmocpxwskvhoojndrd` (`caseproof-dev`, `eu-central-1`, Postgres 17.11).
**Authority:** owner instruction to remediate the findings in `docs/audits/DEEP_CODEBASE_AUDIT_2026-11-11_v2.md`.
**Applied by:** coding agent, using the Supabase Management API with the project access token already present in the local `.env` (no secret value was read into, printed into, or committed to any file, log, or repository).

> **This is a development receipt.** No production system was touched. It is **not** a security sign-off, a pilot approval, or evidence that any confidential material may be processed. SEC-01…16 remain OPEN in `docs/security/PILOT_DATA_SECURITY_GATE.md`.

---

## 1. What was changed

### 1.1 Live project configuration (no SQL, no repository migration)

| Setting | Before | After | Effect |
|---|---|---|---|
| `password_min_length` | 6 | **12** | Removes the Supabase floor. |
| `password_required_characters` | *(none)* | **lowercase : uppercase : digits : symbols** | Password must contain a character from each class. |
| `disable_signup` | false | **true** | The project no longer accepts public sign-ups. Sign-in is unaffected. Dev fixture provisioning uses the service-role admin API (`/auth/v1/admin/users`), which is not blocked by this flag. |
| `security_update_password_require_reauthentication` | false | **true** | A password change requires re-authentication. |
| `features.s3Protocol.enabled` | true | **false** | Removes the S3-compatible Storage path, which is not governed by the `storage.objects` RLS policies. No S3 credentials existed (`storage.s3_keys` does not exist), so nothing was using it. |
| `fileSizeLimit` (project default) | 52 428 800 (50 MiB) | **20 971 520 (20 MiB)** | Matches the `caseproof-originals-dev` bucket limit, so an accidentally created bucket cannot accept a larger object. |

### 1.2 Migrations applied to `caseproof-dev`

Two migrations, applied in filename order and recorded in `supabase_migrations.schema_migrations` with their exact SQL.

#### `20261106210000_caseproof_release_acknowledgement_fence.sql` (already in the repository, previously uninstalled)

Installs `caseproof.release_acknowledgement_fence()`, a `BEFORE INSERT` trigger on `caseproof.dossier_releases`. It rejects any release whose `manifest.release_acknowledgement` is not an object of exactly 10 keys matching the row's own `actor_id`, `release_id` and `snapshot_hash`, with `schema = caseproof-release-ack-v1` and `intent = AUTHORIZE_REVIEW_RECORD_RELEASE`.

Its own header required installation "only together with API release changes"; PR #204 (which produces the acknowledgement in `apps/api/dossier_export_release.py:436-461`) is merged and live, so that precondition was satisfied. The only writer of `dossier_releases` is the `caseproof_dossier_export_release` RPC, and the fixture grant `caseproof_f6_fixture_export_grant` does not insert into that table.

#### `20261113000000_caseproof_platform_hardening.sql` (new)

1. **`FORCE ROW LEVEL SECURITY` on all 42 `caseproof` relations.** RLS was already enabled, but a table owner bypasses it unless FORCE is set. Every relation is owned by `postgres`, which holds `BYPASSRLS`, so **no live behaviour changes today**; the invariant is now explicit and survives a future relation owned by a role that does not hold `BYPASSRLS`.
2. **Fixed least-privilege application role `caseproof_m1_reader`.** Created with `LOGIN`, `NOSUPERUSER`, `NOBYPASSRLS`, `NOCREATEDB`, `NOCREATEROLE`, `NOREPLICATION`, `NOINHERIT`. Grants: `USAGE` on schema `caseproof` and `SELECT` on exactly the five protected relations (`cases`, `documents`, `document_versions`, `organization_members`, `_m1_matter_grants`). It holds **no** `INSERT/UPDATE/DELETE/TRUNCATE/TRIGGER/REFERENCES` on any of them, owns none of them, and inherits no superuser or `BYPASSRLS` role.
   **No password is stored in this repository.** The role therefore cannot authenticate until the deployment owner provisions a credential through a reviewed, secret-managed path, as required by `docs/m1/SIGNED_PRIVATE_RUNTIME_PACKET.md` and `docs/m1/LIVE_DEV_PRIVATE_MIGRATION_RECEIPT_2026-10-27.md:26`.
   *Note:* `apps/api/signed_private_matter_reader.py` is not yet imported by any entry point, so this role is a security foundation, not a live privilege reduction.
3. **Revoke `SELECT` on `extensions.pg_stat_statements` and `extensions.pg_stat_statements_info` from `PUBLIC`.** The grant was held by `PUBLIC` (`=r/postgres` in `pg_class.relacl`), so revoking only from `anon` and `authenticated` was a no-op. `dashboard_user` and `postgres` retain their own grants.
4. **`log_min_error_statement = 'fatal'`** for roles `postgres` and `authenticator`. `ALTER DATABASE ... SET` requires `SUPERUSER`, which the migration role does not hold on a managed project, so the parameter is set per role: `postgres` covers direct and management connections, `authenticator` covers PostgREST sessions. Normal traffic was already unlogged (`log_statement='ddl'`, `log_min_duration_statement=-1`), but any **errored** statement was written to the database log in full, and a PostgREST direct table read inlines filter values into the statement text.

The migration ends with a fail-closed verification block: it raises if any `caseproof` relation lacks forced RLS, if the `pg_stat_statements` views remain readable by `anon`/`authenticated`, if the reader role holds write privileges on a protected relation, if it owns one, if it inherits a privileged role, if its attributes are not least-privilege, or if `log_min_error_statement` was not applied to the `postgres` role.

##### Correction applied after the first application (portability)

The first application of this migration used an unconditional `alter role authenticator set log_min_error_statement = 'fatal'`. `authenticator` is a **Supabase-provided role** and does not exist on a bare PostgreSQL instance, so the migration **failed** when replayed against the `postgres:17` container used by the disposable replay candidate (`ERROR: role "authenticator" does not exist`). Every preceding statement — forced RLS, the reader role and its grants, the `pg_stat_statements` revokes — had already succeeded in that container, so the defect was isolated to the log-setting block.

The migration was corrected to apply the setting **only to roles that exist**, and the corrected migration was **re-applied** to `caseproof-dev`. The re-application is idempotent: forced RLS re-applies, the existing reader role is reused, the revokes re-apply, and the log setting re-applies. The recorded `supabase_migrations` statement for version `20261113000000` was updated to the corrected text so that the repository file, the recorded statement and the applied SQL agree. The superseded first text remains in git history at commit `b1e85e3`, and the receipt records the change explicitly rather than silently.

Live read-back after the correction: forced RLS 42/42 · reader role present · `pg_stat_statements` leak 0 · release triggers 4 · applied migrations 76 · `log_min_error_statement=fatal` on 2 roles · recorded statement length equals the repository file length.

### 1.3 Repository line-ending normalisation (`.gitattributes`, new)

The repository had **no `.gitattributes`**. On a Windows checkout with `core.autocrlf=true`, 1 215 tracked files materialise with CRLF bytes. Several of the repository's own verifiers read those bytes directly, so they failed on Windows while passing on Linux CI.

`.gitattributes` now declares `* text=auto eol=lf` with explicit per-extension overrides and `-text`/`binary` for binary assets (the `tests/fixtures/documents/synthetic_supplier.eml` fixture is preserved byte-for-byte, because its RFC-822 line endings are part of the fixture).

**Effect, measured:** `npm run contracts:check` and `npm run lint` (Prettier) both failed on Windows before and pass now. The migration-lineage and historical-upgrade verifiers went from failing to passing.

---

## 2. Verification performed

### 2.1 Live state, read back after the change

| Check | Before | After |
|---|---|---|
| `caseproof` relations with forced RLS | 0 / 42 | **42 / 42** |
| `caseproof_m1_reader` role exists | 0 | **1** (not superuser, not BYPASSRLS, LOGIN) |
| reader role: `USAGE` on schema `caseproof` | – | **true** |
| reader role: `SELECT` on the 5 protected relations | – | **5** |
| reader role: write privileges on protected relations | – | **0** |
| reader role: owns a protected relation | – | **0** |
| `pg_stat_statements` readable by `anon`/`authenticated` | **2 objects** | **0** |
| triggers on `caseproof.dossier_releases` | 3 | **4** |
| applied migrations | 74 | **76** |
| `log_min_error_statement` on `postgres` / `authenticator` | `error` (default) | **`fatal`** |
| `password_min_length` / `disable_signup` | 6 / false | **12 / true** |
| Storage `s3Protocol` | enabled | **disabled** |

### 2.2 Repository verification

| Check | Result |
|---|---|
| `python scripts/check_architecture.py` | **PASS** |
| `python scripts/verify_migration_lineage.py` | no exception; `historical_source_parity_verified: true`, `all_unmatched_applied_sql_locatable: true`, `all_applied_sql_receipts_locatable: true`, 57 matching-version receipts checked |
| `python scripts/audit_migration_inventory.py` | `local_count=74`, `applied_count=76`, `name_mismatch=0`; exit 2 is its designed "drift remains unresolved" release posture, not a failure |
| Full Python suite | **2 252 passed**, 4 skipped, 141 failed, 54 errors — **zero new failures** against a clean `HEAD` worktree baseline (148 failing), **7 previously failing tests now pass** |
| `npm run lint` (eslint + boundaries + prettier) | **PASS** |
| `npm run contracts:check` | **PASS** |
| `npm test` (vitest) | **107 passed / 21 files** |

The 141 remaining Python failures and 54 errors are **pre-existing Windows-platform failures** (POSIX-only `import resource` in `infrastructure/parsers/pdf_ocr.py:13`, Linux-only parser worker in `infrastructure/parsers/limited.py:27`, and no local PostgreSQL). They are unchanged from the `HEAD` baseline.

### 2.3 Files changed

**No product code was modified.** `apps/`, `application/`, `domains/`, `packages/`, `infrastructure/` and `frontend/` are untouched. The change set is:

| File | Change |
|---|---|
| `.gitattributes` | new — line-ending normalisation |
| `supabase/migrations/20261113000000_caseproof_platform_hardening.sql` | new — applied to dev |
| `docs/security/caseproof_dev_applied_migrations_20261111.json` → `…_20261112.json` | regenerated from live state (74 → 76 applied) |
| `docs/security/caseproof_dev_migration_lineage_20261111.json` → `…_20261112.json` | regenerated from live state |
| `docs/security/disposable_replay_candidate_v1.json` | new migration added to the pinned replay set and to the dependency-deferred suffix (23) |
| `scripts/audit_migration_inventory.py`, `scripts/verify_migration_lineage.py` | receipt filename constants |
| `scripts/fresh_supabase_cli_profile.py` | deferral count 22 → 23, source count 73 → 74 |
| `scripts/probe_historical_74_upgrade.py` | the 74-record base is still reconstructed byte-for-byte; the two newly applied migrations are now the pending upgrade path (74 → 76) |
| `tests/test_migration_lineage.py`, `test_migration_inventory.py`, `test_fresh_supabase_cli_profile.py`, `test_disposable_replay_candidate.py`, `test_s2_002_sql_contracts.py`, `test_s2_004_internal_observation.py`, `test_s2_008a_disposable_schema.py`, `test_s2_008a2_locator_codec.py`, `test_s2_008a3_readonly_reader.py`, `test_s2_009a_vault_protocol.py`, `test_s2_009b_disposable_ledger.py` | pinned migration-set pins updated (11 files) |
| `docs/security/CANONICAL_FRESH_INSTALL_PROFILE_CANDIDATE.md` | counts |
| `docs/CASEPROOF_FINAL_WORKFLOW_V4.md` | merged with upstream (earlier task) |
| `docs/audits/*`, `docs/pilot/REMEDIATION_ROADMAP_v1.1.md`, `docs/CASEPROOF_DECISION_CATALOGUE_AUDIT_2026-11-10.md` | audit and roadmap deliverables |

The hardening migration is placed in the **dependency-deferred suffix** of the disposable replay candidate and of the fresh-install CLI profile. It must run after every schema-creating migration, otherwise `FORCE ROW LEVEL SECURITY` would silently skip relations created later.

---

## 3. Rollback

```sql
-- 20261113000000
alter table caseproof.<relation> no force row level security;   -- per relation
revoke all on all tables in schema caseproof from caseproof_m1_reader;
revoke all on schema caseproof from caseproof_m1_reader;
drop role caseproof_m1_reader;
grant select on extensions.pg_stat_statements, extensions.pg_stat_statements_info to public;
alter role postgres reset log_min_error_statement;
alter role authenticator reset log_min_error_statement;

-- 20261106210000
drop trigger if exists release_acknowledgement_fence on caseproof.dossier_releases;
drop function if exists caseproof.release_acknowledgement_fence();
```

Project configuration is restored through the Supabase dashboard or the Management API with the previous values listed in §1.1.

---

## 4. Still open after this receipt

| # | Item | Status |
|---|---|---|
| 1 | **Session expiry** (`sessions_timebox_in_minutes`, `sessions_inactivity_timeout`) | **BLOCKED — plan-gated.** The Management API returns HTTP 402 `entitlement_required` / `auth.user_sessions`: *"User sessions can only be configured on Pro Plans and up."* The project is on the free tier. `sessions_inactivity_timeout` remains `0`, so a bearer does not expire by inactivity. **Closing this requires a paid plan upgrade — an owner decision, not an engineering task.** Until then, the mitigation is server-side: the API's own `/v2/workspace/session` limiter (12/min) and the per-release fresh Auth lookup. |
| 2 | **`caseproof_m1_reader` credential** | Role and grants exist; **no password is provisioned.** The role cannot authenticate until the owner sets one through a secret-managed path. |
| 3 | **Least-privilege runtime not yet live** | `apps/api/signed_private_matter_reader.py` is imported by no entry point, so the reader role is a foundation, not yet a live privilege reduction. |
| 4 | **Platform defaults can be re-applied** | Supabase re-applies some platform defaults on project configuration changes. The `pg_stat_statements` revoke and the auth settings must be re-verified after any such change. |
| 5 | **Auth accounts** | 25 accounts exist, all password-based, 22 of which have signed in. No leaked-password corpus check has been performed. |
| 6 | **Backup / PITR** | The Management API does not expose the backup configuration through the endpoints available here; the repository already tracks this as open (T74). |
| 7 | **Everything in `docs/security/PILOT_DATA_SECURITY_GATE.md`** | SEC-01…16 remain **OPEN**. Independent security review, penetration test, incident plan, backup-restore drill and professional-secrecy sign-off are untouched. |

---

## 5. Honest limits of this receipt

- The work was executed through the **Supabase Management API**, not the Supabase MCP, because no MCP server was connected to the working session. The MCP `list_migrations` tool calls the same Management API `POST /v1/projects/{ref}/database/query` endpoint under the hood, so the read and write path is equivalent — but that equivalence is my judgement, not a recorded fact, and the MCP tools were not exercised.
- The migration was applied and recorded by sending the migration SQL and the `schema_migrations` insert as a single multi-statement query, so the DDL and its receipt commit atomically. The recorded `statements[1]` is the exact repository file content.
- Verification is **read-only observation of the live database after the change**, plus the repository's own verifiers and test suites. No independent party reviewed it.
- The repository's `verify_migration_lineage.py` still reports `status: BLOCKED_MIGRATION_HISTORY_DRIFT` and `fresh_replay_verified: false`. That is correct and unchanged: **a fresh-install replay in filename order is still not proven**, because the recorded history contains 19 applied migrations whose versions do not match any repository filename and 3 superseded repository files that were never applied by their own version. This receipt does not close that gate.
- **Nothing here makes CaseProof pilot-ready.** It closes six configuration and database exposures and one CRLF-correctness defect. The open gates in `docs/security/PILOT_DATA_SECURITY_GATE.md` and `docs/pilot/P5_P6_ACCEPTANCE_MATRIX.md` are unchanged.
