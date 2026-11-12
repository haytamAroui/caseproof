# Reconstruct the 74-version applied ledger and test PR204 upgrade

**Status:** isolated deployment-candidate acceptance, 12 November 2026.
No remote schema migration is approved by this test alone.

## Original recorded history, not rewritten source

`caseproof-dev` currently records **74** migration versions. GitHub's
active `supabase/migrations` directory has 73 files; the histories have
19 applied-only versions and 18 repository-only versions. PR #218 restored
and SHA-256-pinned the exact original SQL for *every one* of those applied
74 versions, including five known source-content divergences and three
originally missing named statements.

The new `scripts.probe_historical_74_upgrade` reconstructs the original
**version + name + exact SQL bytes** of each recorded migration in a brand
new temporary, unlinked local Supabase v3.1.0 stack. It refuses unknown
sources, altered SQL hashes, absent audit receipts, duplicate versions, or
unexpectedly changed source character length.

The job first runs `supabase db reset --local --no-seed` to install all 74
original applied statements in their recorded timestamp sequence. Only if
all 74 succeed does it add the existing unchanged PR #204
`20261106210000_caseproof_release_acknowledgement_fence.sql`, then call
`supabase migration up --local` to test the **75th** pending migration.
Every failure stops the job and is reported via bounded metadata; no raw
SQL, user records or Supabase keys enter artifacts.

## Scope and remaining safety gates

An isolated 74-to-75 replay demonstrates **historical SQL reconstruction
and local migration upgrade feasibility**, not that current live database
objects, RLS grants, functions and records exactly equal their historical
ledger. Schema drift might exist after the recorded migration. This test
does not load actual client records or prove live signed-user release
workflows.

Keep the live `caseproof-dev` history unchanged. For activation:
- Independently compare installed live schema and RLS/grants against the
  expected prerelease state, including the five historical source divergences.
- Validate the genuine signed reviewer-to-release flow and authorization
  denial, plus a restore procedure.
- Deploy the API/frontend release contract and SQL trigger atomically
  under a reviewed rollout plan; perform post-deployment negative tests.
- Do not apply all 18 local-only versions, rename history or use
  `migration repair` merely to make timestamps agree.

Sources: issue #216, ADR 0037, PRs #218/#222/#223.
Supabase official docs:
https://supabase.com/docs/reference/cli/supabase-migration-up
