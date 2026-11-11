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

## 11 November 2026 — Historical SQL provenance ledger

A read-only comparison of the 19 deployed migration versions absent from the repository's ordered migration directory against their original SQL sources has confirmed:

- **12 byte-for-byte identical SQL sources** stored in the repository under different timestamped migration filenames.
- **4 divergent source candidates** (Phase 3 geometry payload, Phase 3 four-source bundle, and two DOCX scripts). A matching logical name does **not** establish executable equivalence.
- **3 versions without a same-name source candidate** (Phase 3 acceptance registry, Phase 3 draft-bundle role and the combined M0.5 run registry/OCR cleanup).

The evidence manifest `docs/security/caseproof_dev_migration_lineage_20261111.json` includes the exact `SHA-256` fingerprints of the applied SQL statements, their character lengths and candidate paths. `python -m scripts.verify_migration_lineage --report-only` validates the immutable source-classification evidence. Without `--report-only`, the command exits 2 to preserve the release blocker.

**This is source provenance, not a corrected migration directory.** Do not duplicate renamed SQL under both versions inside `supabase/migrations` or execute all candidate files as if they were a safe chronological chain. The recorded historical contents of the four divergent and three unsourced migrations need exact controlled recovery and dependency review before any fresh replay or history repair.

## Historical SQL recovery — 11 November 2026

Seven previously unresolved SQL statements (four divergent candidates and
three previously absent sources) have been recovered byte-for-byte from
the development migration ledger to `db/historical_applied/`. All 19 unmatched
live versions now have locatable and hash-checked historical SQL:
12 through existing repository candidate files and 7 through the archive.

This closes the **SQL provenance gap only**. It does **not** reconcile the
18 repository-only versions, prove replay order, approve the current SQL
privileges, or authorize a linked Supabase reset, deployment or history repair.
The P0-3 migration release gate remains BLOCKED.

### Same-version migration fingerprint verification — 11 November 2026

A separate exact-content audit examined **all 55 applied versions** that
already have matching-version local migration filenames. **54 match exactly**.
The single exception is `20261106092710_caseproof_data_rights_ledger_shadow`.

Its historical recorded SQL locks the case row with `FOR UPDATE OF c`;
the local source contains `FOR UPDATE OF c FOR SHARE OF m,g`. The
precise historical applied SQL has been archived separately with its SHA-256
fingerprint. A read-only live function check confirms the **currently installed**
`caseproof_rights_manage` includes the membership share lock; this finding
concerns historical SQL provenance and is not proof of a current missing lock.

All **74 deployed migration statements** now have a locally locatable,
fingerprint-checked original SQL body (54 matching-version files, one
same-version archive, 12 alternate-version sources, seven additional archives).
This **does not** mean the 18 repo-only migration versions are reconciled or
that a canonical fresh-install replay succeeds. The P0-3 release gate stays
BLOCKED.

## 11 November 2026 — Literal natural-order replay diagnostic

A separate disposable PostgreSQL job now attempts every tracked
`supabase/migrations/*.sql` file in **unmodified filename order**, using
the same synthetic Supabase role/auth/storage stubs as the existing retention
CI. It stops at the first SQL error and uploads a bounded JSON result.

The job is expressly named a **diagnostic**, and its `--diagnostic` exit zero
means only that the experiment produced a result. The release-gate invocation
returns nonzero without real Supabase CLI fresh-install/upgrade evidence.
It does not silently reorder migrations, use the archived applied SQL,
connect to the development Supabase instance, or approve any permissions.

A PostgreSQL-stub pass would still **not** equal Supabase CLI `db reset`
success. The official local CLI configuration, full auth/storage schema,
and 18 repository-only version reconciliation require further work.

### First reproduced natural-order blocker — 11 November 2026

A real isolated PostgreSQL 17 run first failed after **36 successfully
applied migration files** (out of 73), at
`20261030114000_m05_ocr_sidecar_cleanup_fk.sql`:

`ERROR: relation "caseproof.ocr_geometry_sidecars" does not exist`

The failing SQL alters `caseproof.ocr_geometry_sidecars`. Its tracked
table creator, `20261030140000_caseproof_phase3_private_ocr_geometry.sql`,
sorts **later**. The actual recorded development migration chronology
created the table at `20261030093045`, before the combined M0.5
registry/OCR cleanup at `20261030111946`. The two repository timestamps
have diverged from that deployed chronology.

The first diagnostic run failed earlier because the disposable harness did
not record completed migration versions; that harness error was corrected.
The above missing-table error is the next reproduced blocker.

CI now pins this **specific expected failure**, so a different regression or
unexpected replay success cannot silently pass the diagnostic. This is a
**recorded blocker**, not a fix: never hide it by disabling SQL, editing
historical live migration receipts, or renumbering already-applied files.
The approved canonical baseline/upgrade strategy remains to be selected.

## 11 November 2026 — Version-pinned disposable replay candidate

The existing retention test already applies **22 deferred migrations** after
its sorted prefix and thereby avoids the verified OCR sidecar ordering failure.
That order is captured explicitly in
`docs/security/disposable_replay_candidate_v1.json`, with all 73 filenames
pinned so new migrations cannot silently be included.

A **separate** PostgreSQL 17 service job executes this candidate, recording a
synthetic migration version receipt after each successful SQL file and
producing a bounded first-failure or full-application report. This is a
candidate, not a corrected Supabase migration directory: it is not the default
Supabase CLI filename order, it uses simplified disposable auth/storage stubs,
and it cannot authorize any deployment or `supabase_migrations` history edit.

The candidate is allowed to pass without declaring the release gate open.
Subsequent work must reconcile the historical version mapping, choose an
approved canonical baseline, prove a **real Supabase CLI** local clean install,
verify an upgrade from the recorded history, and obtain independent security
approval. P0-3 stays BLOCKED.
