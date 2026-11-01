# Deployment, retention and model authority evidence

Implements the engineering evidence layer for [ADR 0025](../adr/0025-deployment-data-retention-and-model-authority.md).
The ADR remains proposed and SEC-01–16 remain independently evidenced approval gates.

## Scope / evidence / owner matrix

| Scope | Executable evidence | Current boundary | Owner |
|---|---|---|---|
| Hosted | `deployment-assessments/hosted.json` plus completeness checker | Capture, flows, operator/regions, retention durations and approvals not supplied | Named deployment/security/privacy owners TBD |
| Hybrid | `deployment-assessments/hybrid.json` plus completeness checker | Assess both firm and service sides; no inherited approval from hosted | Named deployment/security/privacy owners TBD |
| Firm-controlled | `deployment-assessments/firm_controlled.json` plus checker | Installer/customer configuration and full-perimeter evidence not supplied | Firm operator + security/privacy owners TBD |
| Offline | `deployment-assessments/offline.json` plus checker | Separate claimed configuration; no whole-machine no-egress claim | Firm operator + security/privacy owners TBD |
| OCR namespace | `scripts.capture_ocr_egress`, CI PCAP and receipt | Real isolated namespace capture, loopback positive control and denied synthetic outbound TCP attempt; synthetic bitmap OCR, missing-input failure and successful retry run during capture | Engineering evidence; no customer approval |
| Generative annotations | `application/litigation/model_notes.py`, prompt-injection/authority tests | Separate immutable note/review request bound to snapshot and authorized destination; no provider invocation, persistence or authoritative mutation | Verification lead, named reviewer TBD |
| English references | M2 canonical unsupported-reference tests and #160 measurement | Six lettered Exhibit examples flagged for manual review, not inventory/source/page/fidelity matched | Detection/evaluation owner TBD |

## Explicit retention statement

CaseProof has no service-wide zero-retention policy. Development originals are
preserved in private Storage, derived OCR/geometry and review/snapshot records in
the database, exports in downloaded/CI artifact files, and test logs/artifacts in
runner/provider facilities. The original, representation, review and export are
separate retained objects. Temporary files, captures, caches and provider backups
must be assessed separately; deleting an application row is not backup erasure.

Each profile lists originals, OCR, crops, translations, reviews, reports, hashes,
reference strings, verdicts, identifiers, timing, queues, logs, caches, temp files
and backups. It requires what is kept, location, actual duration in seconds,
access roles, deletion evidence and legal-hold rules. Backups additionally require
expiry, restore proof and re-deletion of restored data. Values are deliberately
unset until measured/contractually established for the exact mode. **Unset does
not mean zero**, indefinite permission or approval. Confidential data remains
blocked when a required schedule or approval is missing.

The synthetic capture artifact in the new CI job has an explicit seven-day
artifact setting. That setting applies only to that artifact; it says nothing
about Actions logs, database backups, customer originals or third-party retention.

## Run and inspect

```bash
uv run --locked python -m scripts.assess_deployment_evidence docs/security/deployment-assessments/hosted.json
# Expected nonzero until actual owner/evidence/retention fields are supplied.
docker build -f docker/ocr-worker.Dockerfile -t caseproof-ocr-worker:ci .
uv run --locked python -m scripts.capture_ocr_egress --output /tmp/fresh-caseproof-capture
```

The capture tool needs Linux, Docker, sudo, nsenter and tcpdump. It captures only
the isolated OCR network namespace, with fixed synthetic sentinels; it must not be
used with client data. A positive loopback packet is required, preventing an empty
or broken capture from being called proof. The outbound probe must fail and the
capture must contain no non-loopback packets. Synthetic bitmap OCR and an input
failure/retry are exercised. It is **not** a full dossier-document
processing, browser/Auth/API/Storage/telemetry/update/support capture or a test of
all failure/retry paths. Each mode's whole-perimeter capture and field-level trace
still needs actual authorized configuration, matching build/config hashes and
review of encrypted-capture observation limits. Do not relabel this receipt as one.

The evidence checker always returns `client_data_authorized=false` and
`sec_01_16_approved=false`, even for a structurally complete record. Owner identity,
contracts, payload minimization and actual network/backup behavior require review.

## Model authority

Model output is limited to `{kind: note|review_request, text: ...}`. Extra finding,
verdict, approval, snapshot or human-decision keys are rejected. Host configuration
supplies provider/model/version. A short-lived actor/destination/snapshot-bound
release is required; the function returns a labelled `ModelNote`, never a modified
report. Prompt-injection text stays annotation data. No new model provider is
configured, and no annotations are persisted or automatically rendered in reports.
Any future adapter must use this boundary and separately authorize persistence;
notes must never be merged into the deterministic or reviewer decision structures.
