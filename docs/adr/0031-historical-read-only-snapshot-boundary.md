# ADR 0031 — Historical snapshot inspection boundary

Status: implementation proposal in PR #174, not installed or accepted.

Historical inspection must be a separate read-only operation from current review,
correction, recheck and export. Existing freshness predicates remain on those
operations. Historical reads recheck current membership, matter grants, retention
and deletion, then verify stored SHA-256 and server HMAC. They do not assert current
source availability or restore historical permission. Original-byte retrieval must
separately authorize each preserved version and verify its digest.

The SQL proposal `db/proposals/PIV-F1_historical_snapshot_read.sql` projects only
stored snapshot bytes under current read grants. It does not grant table access or
change current snapshot/read/write functions. PUBLIC and anonymous execution are
revoked. Installation, disposable adversarial SQL tests, signed development
acceptance, a versioned HTTP read projection, browser historical/current labels,
and source-version reopening are still required before claiming completion.

Rollback drops only the new function and its route. Existing currentness guards
must never be weakened to make an old snapshot writable.
