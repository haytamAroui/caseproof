# Canonical fresh-install candidate — Supabase CLI

**Status:** proposed, 12 November 2026. This is an isolated proof, not a
production baseline or approval to modify the shared dev migration history.

## Context

GitHub tracks 74 SQL migrations, and the `caseproof-dev` ledger records 76
applied migration versions. There are 19 remote-only and 18 repository-only
versions. The original repository filename order fails on the OCR sidecar
cleanup dependency in the genuine Supabase CLI. A pinned candidate dependency
order (from PR #220) applied all 74 SQL files against disposable PostgreSQL
with synthetic auth/storage, but that is not equivalent to official CLI reset.

## Candidate profile and guarantees

`scripts.fresh_supabase_cli_profile` uses the existing version-pinned
`docs/security/disposable_replay_candidate_v1.json`. It asserts historical
SQL receipt integrity, creates a brand-new temporary **unlinked** Supabase
project, and starts the official local stack without application migrations.

It then copies the exact bytes of all 74 source migrations into a temporary migration directory: **51 files retain their original
historical timestamps**, and only **23 dependency-deferred files** receive
ascending, uniquely generated test-only timestamps after the 51-file prefix. It runs
`supabase db reset --local --no-seed` under Supabase CLI **3.1.0**.
The job must observe an application entry for each expected alias and return a
successful real CLI reset, otherwise it fails and uploads a bounded JSON
diagnostic. It records a SHA-256 receipt for the complete original-to-temporary-name mapping and SQL bytes.

**Nothing is renamed or overwritten in `supabase/migrations`.** The aliases
never leave the temporary project. The test receives no remote credentials,
does not invoke a history repair and does not mutate `caseproof-dev`.
It uploads no original SQL, passwords or raw CLI logs.

## Non-goals and follow-up gates

Temporary aliases must never be deployed to an existing project: they are
not approved historical versions. A clean local test would prove only that
this precise full-stack fresh profile is executable. It does not prove schema
equivalence to the 76-version live database, correctness of RLS or
`SECURITY DEFINER` privileges, an upgrade path from live history, backup and
restore, reviewer sign-off, or confidential-client pilot readiness.

ADR 0037 remains proposed. Independent architecture and security reviewers
must approve a durable fresh-install strategy and a **separate** upgrade
strategy before this becomes release-authorized. The missing PR #204
release-acknowledgement fence remains a separate coordinated deployment gate.

References: PRs #218, #220, #221; Supabase documentation:
https://supabase.com/docs/reference/cli/supabase-db-reset

### Version-gate discovery

The first real CLI run proved that renaming **all** 74 sources is incorrect:
`20261027202734_caseproof_m1_private_originals_storage.sql` validates the
presence of original migration version `20261027160745` in
`supabase_migrations.schema_migrations`. The corrected test profile keeps
all 51 prefix-version labels; only 23 deferred sources need new temporary
names to make the dependency sequence valid. No SQL body is altered.
