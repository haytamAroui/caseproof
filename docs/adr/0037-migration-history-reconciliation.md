# ADR 0037 — Reconcile migration history without rewriting live receipts

**Status:** PROPOSED — 11 November 2026. **Scope:** CaseProof development database only.
**Owner decision pending.** This ADR does not approve a schema change or pilot release.

## Evidence (read-only)

- `caseproof-dev` contains **74** recorded migration versions; repository main has **72** migration files before remediation PR #215.
- The live ledger includes `20261030150030_caseproof_phase4_signed_reference_review`; the reviewed SQL lived outside the migration directory. PR #215 restores its exact bytes at that already-recorded version, and removes a hidden out-of-band installation step in disposable CI.
- Other repository/remote migration versions differ. Some SQL was deployed under alternative timestamps, and some deployed migrations remain in documentation rather than the migration directory.
- `caseproof._phase4_reference_decisions` exists in live dev, has RLS enabled, and direct authenticated SELECT denied. The role `caseproof_m1_reader` is not present in the live project.
- The snapshot `docs/security/caseproof_dev_applied_migrations_20261111.json` records **version/name metadata only**. It contains no document content, credentials, live SQL, or user records.
- `python -m scripts.audit_migration_inventory` reports unmatched version/name records and exits nonzero. An inventory match is **necessary, not sufficient**; SQL integrity and clean replay still need proofs.

## Proposed decision

**Do not renumber or edit already-applied migration SQL in place.** Keep the actual deployment receipts as authority for the development database. Treat a missing SQL source as a missing recoverability asset, not as permission to amend live migration history. Restore verified historical SQL under its recorded timestamp, with byte/provenance review where possible.

For remaining gaps, reconcile **one historical migration at a time** by matching the actual deployed SQL (not just its filename) to repository source; retain append-only evidence of mappings and deliberate differences. Historical scripts that were applied out of order must not be silently replayed in an invented sequence.

Before any CLI push, reset, baseline or history repair on a linked project:
1. Obtain a reviewed read-only snapshot of applied versions, function/table definitions, RLS and grants.
2. Complete SQL equivalence and dependency checks for every remote-only/local-only entry, especially the two DOCX SQL files and renamed page-worker/F6 scripts.
3. Choose a **new-install strategy**: a reviewed canonical baseline schema migration for fresh isolated installations, or a fully ordered historical chain if executable without divergent semantics. Verify both with actual disposable PostgreSQL and the applicable Supabase CLI.
4. Independently review impact on the existing live dev environment; no destructive reset or migration-repair command without explicit authorization.
5. Run fresh replay, upgrade-path replay, rights/RLS negative tests, signed-user admission/refusal, and rollback/restore drills; record commit, CLI version, database version, and CI receipts.

## Release gate

**BLOCKED** until all repository migration history and live receipt discrepancies are resolved or governed by an explicitly approved baselining plan, and a standard fresh-install process succeeds without hand-reordered, untracked SQL. Passing existing `verify_retention_disposable.py` alone does not satisfy this gate.

This ADR is independent of SEC-01–16 pilot approvals.
