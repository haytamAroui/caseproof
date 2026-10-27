# M2-B packet 2 — Versioned source-bound brief graph

**Status:** disposable backend engineering candidate; NOT live Auth, production
storage, production M2-B acceptance or a lawyer-facing Word/editor release.
This packet follows merged [PR #82](https://github.com/haytamAroui/caseproof/pull/82)
and uses the M2-A deterministic checking engine.

## Capabilities delivered by this packet

- Private PostgreSQL proposal with immutable per-brief versions, ordered
  references, ordered typed factual assertions, revision-locked logical heads,
  append-only events and audit FK.
- Each normalized `BriefRepresentation` is tied to explicit **document ID,
  source-version ID, verified Vault intent ID and original SHA-256**, not to
  a filename or an unverified quoted passage. A separate normalized text SHA
  and versioned parser identifier remain distinct from the original digest.
- The disposable application adapter reads original Vault bytes independently,
  computes SHA-256 and verifies a current source/version/case/intent binding
  against PostgreSQL under a shared source lock. A stale/unavailable source,
  changed bytes, missing private grant or changed case/exhibit revision fails
  closed. No assumption that normalized text is the same as PDF/DOCX bytes.
- A new logical draft revision **requires a distinct verified source version**
  and never rewrites the original. History remains immutable; an explicit
  historical load may read an older still-verified graph but is marked
  `is_current=False`. A default load rejects a superseded version or stale
  case/exhibit snapshot.
- Version-CAS, explicit idempotency request receipts, immutable audit events and
  rollback on audit failure. Even a reviewer-role actor is not allowed to
  bypass organization `finding:write` or a case `draft:check` grant.

## Explicit limits / next tasks

- Actor IDs in this adapter are synthetic fixture identities. Its
  `draft:check` grant supports **recording a normalized checking input in
  disposable CI only**. A production `draft:write` or equivalent policy,
  real Auth-bound least-privilege DB sessions and approved migration need a
  separate design/security review. No HTTP route mounts this adapter.
- `parser_id` and `representation_sha256` are versioned provenance
  assertions from a trusted caller: this packet does NOT independently
  certify parsing/OCR correctness, rendered DOCX pagination or stable
  citations across editor transforms. Acceptance with real PDF/DOCX/OCR
  and comprehensive NL/FR/EN corpora is still open.
- Existing M2 review check run publication is not **automatically**
  committed with this brief graph; a future transactional application
  composition must load the pinned graph + exhibit revision, verify source
  coverage, record the exact check snapshot and authorize reviewer writes.
- Corrections remain version-bound previews and reversals. A correction
  cannot quietly change the persisted draft: an actual corrected file
  requires a new verified immutable source version, updated reference
  offsets and a new check/review run.
- Customer release remains blocked on M1-B/C security, private storage,
  signed-user RLS, operational recovery and confidentiality approval.

## Required reproducible CI

- Ruff, full pytest, architectural boundary checker, strict mypy.
- Disposable PostgreSQL (localhost only):
  `python -m scripts.verify_m2_brief_graph` after the existing Vault
  and M2 ledger fixtures. Checks exact rehydration, ordered typed links,
  source-byte mismatch, private grant and organizational revocation,
  distinct immutable source versions, historical visibility, simultaneous
  CAS writers, replay, failed audit rollback and API-role table denial.
- No Requesty, live Supabase migrations, customer uploads or external API
  tokens are needed for this packet.
