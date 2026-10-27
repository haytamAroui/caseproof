# M2-B packet 4 — Reversible correction: source → version → recheck

**Status: disposable PostgreSQL engineering / source-preserving text-only fixture.**
No customer-facing endpoint, no approved DOCX/Word editing, no live Supabase
migration, and no binding authenticated real reviewer deployment.

## Workflow accepted by this packet

1. Existing signed-boundary check (synthetic verifier in CI) creates an
   immutable, persisted check run from confirmed separately sourced exhibits.
2. A reviewer with current explicit private matter and organization
   permissions records a human `confirmed_candidate` disposition for a
   specific observation. This is **not** a legal or release approval.
3. `CorrectionProposal` pins the exact prior run hash, original brief
   version, exact original representation SHA, changed range and before/after
   text. Pure `preview_correction` validates the changed range.
4. The application must first preserve and verify **NEW ORIGINAL BYTES** as a
   separate immutable source and document version in the Vault. This packet
   supports only identity-normalized UTF-8 text/plain; genuine DOCX editing
   and source page coordinates remain blocked pending parser integration.
5. An append-only `_m2_correction_plans` prepare row freezes the proposal,
   fresh source/version IDs, expected brief/review revisions, graph digest
   and authorization snapshot; same request UUID + different data is denied.
6. The existing M2 graph store promotes the separately verified source with
   its **own transactional graph CAS + audit event**. An append-only
   `graph_applied` stage event is then committed. These are independently
   committed transactions — **NOT atomic together** — and a crash between
   them is resolved via exact same-ID idempotent graph replay.
7. The existing private check route is invoked again for the new brief
   version. It requires the live current case/matter grants, confirmed
   register and verified independent evidence sources. A brand-new immutable
   run is published, followed by an audited `rechecked` stage event. A
   revoked reviewer or changed source fails closed. No stale run approvals
   are transferred, and the old original + reviewed check remain immutable.
8. Undo is a **new** reviewed correction + separately preserved restored
   source and new graph version; it never updates a past source or rewrites
   earlier audit history.

## Engineering acceptance

Disposable Postgres test script:
`python -m scripts.verify_m2_disposable_corrections` after the M1, Vault,
M2 review, brief-graph and private-check scripts.

Covers durable plan → graph → fresh checked run, process restart, injected
failure after graph commit before stage append and same-request recovery,
stale competing prepared writes, organization/per-matter reviewer revocation,
idempotency collision, immutable original/readback, audit and API-role denial.

## Strict nonclaims

- Production `draft:write` permission **does not yet exist** in ADR-0017;
  current tests use reviewer `review:request` and `draft:check` only in
  disposable infrastructure. A real editor must receive separately
  approved authorization and signed-user RLS wiring.
- This packet **requires** pre-preserved verified target bytes; it does not
  create new originals or execute a Word file edit for the user. A future
  authorized source-preservation application service must own upload and
  content safety, media normalization, signature/version and storage
  reconciliation. Corrupted/absent source bytes must not be promoted.
- The immutable correction plan and the graph head are different transaction
  boundaries. Stage receipts are recoverable/idempotent, not a claim of a
  global distributed transaction. Crashed work may remain prepared and
  must be reconciled by an approved worker.
- M2-B is still **OPEN** for live Supabase Auth, least-privilege RLS,
  private Storage, DOCX/PDF/OCR positional fidelity, guarded worker,
  signed reviewer audit, and full multi-user/matter end-to-end validation.
- Neither rule checks nor reviewer dispositions permit filing, automatic
  correction of someone else's document, semantic legal verdict or release.
