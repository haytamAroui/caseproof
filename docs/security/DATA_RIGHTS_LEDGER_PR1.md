# Data Rights Ledger — PR 1 shadow-mode implementation

**Status:** development-only, pending CI, caseproof-dev signed acceptance and owner review.
**Authority:** ADR 0036 owner decisions (6 November 2026).
**Not legal advice.** Belgian counsel must approve controller/processor allocation.

## Scope and invariant

PR 1 introduces **only observation**. An existing signed source read still
requires the exact current matter and Storage permissions, byte digest and
length, and second signed metadata read. A rights shadow failure, missing
policy, revoked rights RPC, network timeout or malformed policy **cannot**
upgrade evidence access, block an otherwise-authorized original response or
change exported artifacts. Rights enforcement is PR 2. A signed reviewed-release
manifest extension is PR 3. There is no UI, RAG, mandatory model, deletion
scheduler, implicit consent or backfill in PR 1.

## Write authority

The append-only `caseproof.source_rights_policies` relation is private, RLS
enabled, and has no direct browser grants. Only the
`public.caseproof_rights_manage` RPC appends rows. PostgreSQL validates
signed non-anonymous `auth.uid()`, active organization membership with
`case:read` and `rights:manage`, active reviewer grant with both rights,
and the actual creator of the matter. A live, not deleted/purging, exact
case/document/source-version join is required.

The RPC serializes writes against a locked matter row. `p_expected_version=0`
creates version 1; otherwise it must match the latest source-version policy.
An exact duplicate request ID and payload replays idempotently; conflicting
replays and competing stale writes fail. Every new version atomically records
a linked `source_rights_changed` audit event.

Classification is explicitly `CLIENT_UPLOAD` and
`CLIENT_CONFIDENTIAL`. `process=true` requires a nonempty, bounded,
recorded firm authorization reference; `indexForSearch` and
`useAcrossMatters` default to false. `export` applies only to the same
matter. Unexpected fields and nonboolean permissions are rejected.

## Read and shadow path

`public.caseproof_rights_current` repeats fresh signed membership and
matter-grant checks, joins the exact source version, and returns only policy
version and decision flags. It never returns a firm authorization reference.
The dev signed-originals endpoint calls this RPC with the **existing bearer
and publishable key** only after verified original byte readback. It logs
action, decision, reason, and policy version; no bearer, content, matter ID or
authorization reference. Legacy source versions return
`policy_status=missing`, producing `UNKNOWN`, never an implicit ALLOW.

A separate pure Python evaluator returns ALLOW, DENY or UNKNOWN with a stable
reason code. Its output is not consulted by any read, export or mutation
authorization gate. If the rights RPC is not deployed or cannot be contacted,
the original response is preserved and a sanitized shadow-unavailable event
is logged.

## Existing retention and destructive cleanup

The new policy rows are append-only. UPDATE and ordinary DELETE fail even
for direct privileged SQL. The *existing* authorized retention finalize
transaction can remove policy history by cascading its source-version or
matter deletion, only when its service JWT and transaction-local cleanup
sentinel are present. No new purge endpoint or general policy-delete path
is added. Existing erasure receipts remain minimal and erase the additional
rights audit events in the existing audit table.

## Acceptance gates

- Unit: missing/invalid/explicit policy decisions, cross-matter restrictions,
  signed projection parsing, redaction and shadow failure isolation.
- Disposable Postgres: legacy missing policy, signed permission denial,
  exact source ancestry, replay conflict, two real concurrent writers with
  one winning append, immutable history, one audit row per new version, and
  existing legal hold/storage/soft-delete/finalize purge.
- On caseproof-dev: verify migration footprint and permission grants;
  run signed authenticated/current-grant reads and review redacted logs.
  No fixture grants or policy rows may be written to the live project except
  an owner-approved, explicitly enumerated synthetic allowlist.
- Before PR 2: CI green on the exact merge SHA, real signed shadow
  observations showing legitimate flows unchanged, adverse/unknown decision
  counts measured, practitioner/security review recorded.
- PR 3: include selected rights policy version/decision in the existing
  signed release manifest; preserve legacy receipts without re-signing.

**Deployment caution:** The dev endpoint is opt-in by composition and uses
only its configured development publishable key. This PR does not establish
firm-controlled deployment readiness or third-party verification of HMAC receipts.
