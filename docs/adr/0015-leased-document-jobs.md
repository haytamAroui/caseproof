# ADR 0015 — bounded leased document jobs

Status: implementation proposal under the owner's 24 October 2026 instruction for the next combined PR. Stacked on #55, not an approval to merge prerequisites, install DDL, deploy a worker, change grants, configure a provider or process customer documents. Kernel, installed actions, canonical migrations and production routes stay unchanged.

## Decision

Add one internal document-intelligence job type, with immutable server-derived actor/case/source references and frozen parser/provider/model/vocabulary/configuration versions. Queue status is execution state only. `succeeded` means an unapproved review proposal was durably captured; it never establishes complete coverage, factual truth, authorization or approval.

`AuthenticatedExtractionScheduler` derives the actor and scope using existing bearer authorization for case/evidence reads and finding proposals. SQL independently checks active membership, granted actions, case revision, effective policy and verified source-intent metadata. A stored bearer token, private path, callback or provider credential is never a job input. The worker is trusted internal composition scoped to an explicitly selected case; this disposable owner-connection reference is **not** service delegation or least-privilege production identity.

Claim one eligible scoped row with `FOR UPDATE SKIP LOCKED`, assign a random lease token and increasing attempt, use database time for expiry and keep provider/parser operations outside SQL transactions. Heartbeats extend leases while work runs. Every extraction reserve/transition acquires the current job fence **inside the same transaction** as the checkpoint/event mutation. Cancellation, expiry or replacement prevents the old worker from writing another checkpoint. The existing checkpoint stores each dispatch and received response; no second checkpoint/fact authority is added.

Expired jobs with prepared/received/completed steps may reuse the original run ID and replay. A dispatched or outcome-unknown step blocks automatic retry. Cancellation during a possibly dispatched call records `outcome_unknown`; it cannot promise to recall an external request. No API resets that state. Known pre-dispatch transient failures use bounded attempts and database-time backoff; checkpoint inspection vetoes retry if a dispatch is unresolved. Unexpected execution failures remain unknown. A lost finish acknowledgement is recovered by querying the durable job or replaying the exact finish, never running the provider again blindly.

Reuse `DocumentIntelligence`, typed entity/slot contracts, source-preserving parsers, Requesty adapter port, existing signal checks, conflicts/coverage and frozen review records. A worker loader freshly reads scoped Vault bytes before and after extraction. Engine changes or changed sources block the job. A completed candidate result can be passed to the existing review repository and draft pack builder after their current-source checks. There is no automatic promotion, publication, email, payment, notification, outbox consumer or legal action.

## Persistence and failure limits

Disposable job + append-only event records are committed atomically. Stable tenant/case/request identity and immutable fingerprint provide enqueue replay. Attempts, statuses, safe reason codes, availability/lease timestamps and result digest are durable. Events contain operational metadata, never documents, quotes, model prompts, tokens or exception messages. The result artifact contains sensitive proposed evidence and must remain tenant-authorized.

The only DDL is `db/proposals/EI-004_disposable_worker.sql`; public/client grants are revoked and RLS is enabled with no policies. Owner fixtures can tamper; checksums are consistency checks, not authentication. Source read-back outside a SQL transaction is a best-effort freshness check, not atomic production approval. If access/source state changes while executing, checkpoint/final writes fail closed; an expired job is subsequently blocked by the next internal claim. Scoped workers require supervision and explicit polling; no deployed supervisor, global tenant scanner, timeout kill-switch or resource provisioner is installed.

Production service delegation, least-privilege DB roles, actual immutable Storage/scanning, real human attestation, accepted-finding persistence and approved export remain open gates. This PR implements the S2-010 lease/recovery reference, not the full production S2-010 release gate or an external-effects outbox.

## Verification and rollback

Contract/adversarial tests cover source aliases, invalid plan fields, changed versions, source-to-review replay, unapproved output and safe failure mapping. Real disposable PostgreSQL tests cover concurrent claims, skip-locked progress, expired worker fencing, no retry after dispatch, process restart with no second inference, cancellation, heartbeat, bounded retries, audit rollback, lost commit acknowledgement, cross-tenant/revoked access and result integrity. Existing full CI and browser journey remain required. No live Requesty performance or cost is measured.

Rollback: stop the synthetic runner and revert additive code; dispose only the ephemeral CI database. No live migration/data change or Kernel contract needs reversal. See [EI-004 data/test review](../tasks/EI-004.md).

References: [PostgreSQL row locking](https://www.postgresql.org/docs/current/sql-select.html#SQL-FOR-UPDATE-SHARE), [date/time functions](https://www.postgresql.org/docs/current/functions-datetime.html), [ADR 0011](0011-architecture-freeze-and-first-finance-slice.md), [ADR 0012](0012-evidence-intelligence-candidate-runtime.md).
