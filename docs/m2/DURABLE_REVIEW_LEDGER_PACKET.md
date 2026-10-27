# M2-B packet 1 — Durable verification-run and review ledger (disposable)

**Scope:** non-production integration slice. This packet does **not** close M2-B, M1-B
or authorize real customer data. The principal roadmap remains `docs/ROADMAP.md`.
The integrated deterministic checker is the merged M2-A engine from PR #71.

## What this adds

- SQL proposal `db/proposals/PIV-M2_disposable_review_runs.sql`, installed only in
  the existing localhost ephemeral PostgreSQL CI service. Stores immutable,
  source-scoped verification run payloads, per-run revision heads, immutable
  reviewer events, audit FK and replay receipts. No RLS policies for API roles,
  no function SECURITY DEFINER, no new production migration.
- `DisposableM2ReviewLedger` ties an independently computed
  `VerificationRun` to an exact case, M1 exhibit revision and current
  explicit per-matter `draft:check` grant. Only the separately granted
  `review:request` reviewer can write a human disposition. The adapter checks
  each *processed* document/version against current verified Vault intents and
  checks source digests on any linked observations; incomplete material remains
  explicitly incomplete, not a pass.
- Immutable verification records use a separate payload SHA and frozen
  `snapshot_hash`. Reviewer decisions are bounded, revision-CAS guarded and
  hash chained. Each review event, receipt and audit entry is committed in one
  PostgreSQL transaction. Repeated exact requests replay; competing stale
  revisions and re-used IDs with changed payloads fail closed.
- Real disposable PostgreSQL tests exercise synthetic NL source bytes read back
  through Vault, Stuk alias confirmation, date/amount candidate run creation,
  reviewer replay, independent-process persisted readback, concurrency, foreign
  actor, revocation, stale case/exhibit, digest mismatch, append-only triggers,
  and injected audit transaction rollback. There is **no use of Requesty**.

## Acceptance boundaries

The restricted actor UUID in this disposable adapter comes from a **trusted
synthetic test harness** and is NOT extracted from an HTTP request, JWT claim
or ordinary PostgREST role. PostgreSQL CI runs as the local owner; it does
not prove real Supabase RLS or least-privilege user authentication. This adapter
is deliberately not mounted into `apps/api/main.py`.

The current M2 run checker consumes version-pinned `BriefRepresentation`
and `EvidencePreview` from independently authorized callers. This packet does
**not** persist a full immutable original DOCX/PDF brief with anchor graph,
enforce a production-ready page-level index denominator, perform signed Auth,
upload customer originals, independently prove OCR geometry, apply reviewer
corrections to documents or provide Word UI. Existing `review_cycle` remains
the pure correction/undo/recheck contract, and no review decision is legal
approval or court filing.

## M2-B remaining acceptance order

1. Finish M1-B real signed Auth, private-matter RLS, approved schema, private
   immutable source custody, durable worker and real OCR quality (#37, #38, #64–68).
2. Persist original brief/representation/assertion/reference graphs with real
   byte-bound source anchors, version and scope invalidation, and worker replay.
3. Implement the production least-privilege repository and mount a protected
   headless check/review/correction API with server-owned identity and
   transactional revalidation.
4. Persist reversibly applied draft corrections, not just previews; prove
   cross-process idempotent apply, review invalidation and checked recheck.
5. Rerun real signed-user E2E security, separate-source swap, failure injection,
   and NL/FR/EN corpus benchmarks. Release/Word UX remain distinct gates.

## Required validation

`uv run --locked pytest -q`, Ruff, strict M2 mypy, architecture check and
`uv run --locked python -m scripts.verify_m2_disposable_runs` in required CI
against the ephemeral PostgreSQL 17 service. The script must fail rather than
skip if the local CI flag, database, M1 grants or verified Vault proposal is
missing.

**Security review required** before any schema migration or customer release.
