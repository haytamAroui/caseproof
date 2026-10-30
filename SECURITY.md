# Security and retention

CaseProof is restricted to synthetic development data until the
[SEC-01–16 gate](docs/security/PILOT_DATA_SECURITY_GATE.md) is approved.
See the [retention design](docs/security/RETENTION_DESIGN.md).

## Matter deletion and backups

Soft deletion immediately denies subsequent authorized matter reads/writes,
original downloads, OCR crops, review and export requests, including its owner.
Previously downloaded bytes cannot be recalled; in-flight responses and any
previously issued bearer URLs require separate lifetime controls.

After the configured grace period (development default 30 days), the reaper
removes the matter's live private Storage objects through the Storage API,
verifies the prefix is empty, and transactionally purges its database data.
Failed operations remain denied and retryable. Legal holds prevent purge.
Only a minimal pseudonymous erasure receipt is retained.

**Verified 30 October 2026:** the connected organization reports the Free plan.
Supabase documents managed daily backups for Pro/Team/Enterprise, not Free.
Therefore a claim that this development project has daily backups retained for
X days would be false. External exports, PITR and provider-internal disaster
recovery retention have not been independently inventoried. Do not promise an
expiry period without evidence for the actual environment.
Supabase database backups and Storage object backups are separate concerns;
a database backup does not itself back up Storage file bytes. Verify the exact
plan, PITR settings, external exports and object replication/lifecycle before a
client environment is approved. Reference:
[Supabase backup documentation](https://supabase.com/docs/guides/platform/backups).

No restored application may serve requests until deletion has been replayed
against an independently preserved erasure register and verified. A restore drill
and verified backup-expiry period remain open production gates.

## OCR worker isolation boundary (PR #140)

The Docker CI egress probe uses `--network none` and verifies an outbound HTTP
attempt is denied inside that container. This is a **test-runtime** control,
not evidence that the currently integrated API launches OCR in that container.
The in-process OCR adapter's subprocess path additionally requires a Linux
network namespace and fails closed when it cannot create one; this may block
OCR on restricted hosts. Before deployment, OCR must execute in a separately
isolated worker/container with no outbound networking, bounded CPU/memory and
execution time, and explicit source/result transport. Do not enable the
in-process adapter on a host that lacks its enforced sandbox.

Private VPC subnets alone are not proof of zero egress: check NAT, internet
gateways, IPv6 egress, private endpoints, DNS and service egress policies.
Cloud Run internal ingress controls incoming requests and do not by themselves
block outgoing traffic. Production isolation remains an independent gate.

Backup expiry is **not known** for this development environment. Hard deletion
removes live matter objects and database records after the configured grace
period; it does not guarantee deletion from backups, PITR, external exports or
provider disaster-recovery copies. An `X days` expiry promise must not be
invented. Obtain the provider's actual retention policy and verify restore
replay of the erasure register before authorizing real client data.
