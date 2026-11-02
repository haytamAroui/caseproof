# ADR 0031 — Historical snapshot inspection boundary

Status: **implemented and signed-development-accepted in PR #174** (2026-11-02).
Production rollout and independent security assessment remain separate gates.

## Decision

Historical inspection is a distinct, read-only operation from current review,
correction, recheck, and export. The currentness predicates on consequential
writes remain unchanged. The historical report does **not** assert current
source availability or revive a lapsed permission.

The function `public.caseproof_dossier_historical_read(uuid,text)` reads only
stored snapshot bytes after checking a current authenticated, non-anonymous
user's active organization membership, matter grant, and non-deleted matter.
PUBLIC and `anon` function execution are revoked; direct table access is
not granted. The report read independently checks stored SHA-256 and the
server HMAC before returning data. Every historical original is fetched
through its current signed storage authorization and must match the frozen
source SHA-256 and byte count.

A missing, corrupted, revoked, cross-matter or purged source is unavailable;
neither the browser nor the API substitutes the current version. Unsupported
raster provenance is explicitly unassessed rather than guessed. Rendered
overlays are navigation aids, never human review or legal verification.

## Implementation and evidence

- Source-of-truth migration:
  `supabase/migrations/20261102150600_caseproof_historical_snapshot_read.sql`
  (identical to the reviewed proposal in `db/proposals/`).
- Installed in the **development** Supabase project. Function permission
  introspection confirmed `authenticated=EXECUTE` and `anon=DENIED`.
- Disposable PostgreSQL signed/anonymous, foreign-matter, revocation,
  soft-delete and teardown checks:
  `scripts/verify_historical_snapshot_disposable.py`.
- Historical/current HTTP report, original and raster-region endpoints;
  current-only correction, review and export write paths.
- Signed browser and real development fixture acceptance:
  `.github/workflows/pr174-signed-historical-live.yml`. The run verified
  old report and exact old source after confirmation change, raster rendering,
  rotation/zoom, cold reopening, denial of stale corrections and review,
  access revocation and **ZERO_RESIDUAL_VERIFIED**.
- PR #174 passed 20/20 checks on `973e7f2978cdb87a1e45d1edcbd05eb58d851fd3`.
  Subsequent changes require fresh CI on the new head.

## Scope and limitations

No production deployment, independent external security audit, or formal
professional/legal accuracy acceptance is claimed. Historical access is
limited by currently available preserved bytes, live signed permissions,
retention, and deletion policy. Raster overlays do not upgrade finding states.

Rollback removes the new historical function and routes only; do not alter
any existing freshness enforcement to make stale snapshots writable.
