# Matter retention design — development only

Authorized 30 October 2026. Existing tenant relationships remain:
`organizations → cases → documents → document_versions → OCR sidecars`;
case-scoped grants, reviews, brief/check history and audit refer to the same case.
No new customer-facing UI or production rollout.

Soft delete locks the case, requires its creator's current signed membership and
reviewer grant, records the deletion and revokes every matter grant atomically.
Restrictive case/document RLS prevents original/geometry access. Write guards
serialize descendant writes and grant changes against deletion, including
SECURITY DEFINER RPCs. Regranting a deleted matter is forbidden. Recovery of a
soft-deleted matter is deliberately unavailable through runtime APIs.

A private policy sets a 30-day grace period. A partial deleted-at index supports
bounded batches of 100 eligible cases. A legal hold prevents selection and
finalization. Policy/hold changes require privileged operator review.
The reaper uses the actual org/case Storage prefix, removes bytes via the Storage
API, verifies absence, then calls a service-only finalizer. Eligibility is checked
again under the case lock. Starting the Storage phase freezes hold changes;
a late hold request fails explicitly rather than implying erased bytes survive. Failures retain the deleted case for retry; concurrent
purges serialize and repeated completion returns the existing receipt. A failed
DB transaction cannot restore already removed bytes; the matter remains denied.
Unknown FK dependencies block the transaction rather than cascade blindly.

All known review/brief/check/source/parse/sidecar/idempotency data is purged in
FK order. Operation receipts containing the exact case UUID and the historical
acceptance registry entry are removed too. Other matters and tenant membership
are preserved. New case-associated persistence must extend this purge and tests.

Audit exception: original audit rows contain actor IDs, source fingerprints and
state payloads. Keeping them with a hashed case ID would not anonymize them and
would conflict with their case FK. Replace them transactionally with one minimal
private erasure receipt containing a case digest, deletion/purge times and event
count. No client/actor IDs, filenames, rationale or source hashes survive there.
The digest remains **pseudonymous**, not a claim of legal anonymization. Its
retention/access basis and duration need firm approval before client use.

Restore procedure: keep erasure receipts outside any restored application's
serving environment. Restore in isolation, deny all runtime access, compare case
UUID digests against the surviving erasure register and replay deletion before
reopening service. A restore that also rolls back that register is unsafe.
A real restore drill, provider backup expiry evidence, worker filesystem/cache
coverage and legal/privacy approval remain separate production gates.

Migration recovery: additive columns/tables/policies first; no existing matter
is deleted by migration. Before any rollback stop reapers. Do not undo deleted
flags or re-enable grants to roll back code. Hard purge is irreversible in the
live application; a backup is not an approved way to resurrect erased material.
