# ADR 0025 — Deployment data boundaries, retention and non-authoritative model notes

**Date:** 1 November 2026. **Status:** proposed clarification of the existing
M1/M2 and SEC-01–16 contracts; no deployment, client-data or milestone approval.
Extends [ADR 0018](0018-pre-submission-verification-freeze.md) and
[ADR 0022](0022-verification-contract-report.md); preserves deterministic and human
authority. [Roadmap](../ROADMAP.md) · [security gate](../security/PILOT_DATA_SECURITY_GATE.md).

## Context

A web interface does not determine custody or processing location. An isolated OCR
container is not evidence about every browser, API, telemetry or backup connection.
Synthetic CI, encrypted transport and hashes do not establish anonymity or
professional-secrecy approval. The following are explicit acceptance requirements,
not claims that the assessments or tests have already been completed.

## Decisions and closure evidence

| Item | Scope and rule | Required evidence | Accountable owner |
|---|---|---|---|
| Deployment data flow and egress | Assess hosted, hybrid and firm-controlled modes separately; offline is a separate claimed configuration. Treat hashes, reference strings, IDs, verdicts and timing as potentially personal/confidential, in addition to source bytes, crops and OCR text. This is a conservative handling rule, not a blanket legal classification. | Versioned field-level flow map, endpoints/subprocessors/regions, key custody, permitted destinations and a synthetic network-capture test for the exact configuration; reviewed deviations and residual risks. | Deployment/security lead with privacy reviewer; named assignees **TBD**. |
| Retention and deletion | Replace blanket “zero retention” product wording with an explicit schedule: what is kept, where, for how long and who can access it. Cover originals, derived text/crops, reviews, reports, queues, logs, caches, temporary files and backups. | Customer-visible schedule with actual durations, deletion/expiry proof, access roles, legal-hold exceptions, backup expiry and restore/re-deletion tests. Unspecified durations remain **OPEN**, not zero. | Data/operations owner with privacy reviewer; named assignees **TBD**. |
| No mandatory generative model | Generative output may add only a separately labelled note or review request, with provider/model/version provenance and permitted data-release policy. It never writes, overrides or promotes a deterministic finding, source/page/fidelity state, reviewer decision or approval. | Separate note schema/storage/permissions and regression tests showing model output, failure or prompt injection cannot change deterministic snapshots or human decisions. This does not grant permission for remote processing. | Verification engineering lead with security reviewer; named assignees **TBD**. |
| Unsupported English references | English Exhibit references are unsupported human-review items. Discovery is not inventory matching or source/page verification; never alias them to numbered Pièce references. | Regression findings remain `NOT_ASSESSED`/`UNMAPPED`, with no matched source, plus benchmark counts separating supported verification from unsupported notices. | Detection/evaluation lead; named assignee **TBD**. |

The English example is the **six lettered Exhibit verification misses** measured
in [PR #160](https://github.com/haytamAroui/caseproof/pull/160). That PR adds six
unsupported notices; it does not turn them into successful matches. The 18-case,
19-reference author-labelled synthetic sample is not representative-client
accuracy acceptance or independently adjudicated gold.

## Network-capture acceptance

For each claimed mode, pin the build, machine/service boundary, configuration and
test corpus. Exercise login, upload, OCR, check, review, correction/recheck, export,
restart, failure/retry, telemetry and support paths. Include expected Auth/API,
Storage/DB, DNS, update and model endpoints; distinguish permitted egress from
unexpected egress. An offline claim must test the whole claimed perimeter, not
only the OCR container. No-network controls must be exercised during failure too.

Use synthetic sentinels. Capture destination/timing evidence and correlate it with
field-level application traces: encrypted packet capture alone cannot establish
which payload fields were sent. Record observation limits, temp files, capture
access and capture deletion/retention. Captures can themselves contain sensitive
data. Keep them out of public CI artifacts unless reviewed safe for publication.

## Evidence ownership and release

Every item records mode/environment, data class, build/configuration, named owner,
dated artifact links, limitations, reviewer and state
`OPEN / EVIDENCED / APPROVED / BLOCKED`. Owner roles above are placeholders, not
completed assignments or signatures. Missing evidence or approval blocks the
corresponding customer-data claim under SEC-01–16. Retention exceptions and
provider-specific promises cannot describe the whole CaseProof service.

This ADR creates no new legal conclusion, customer permission, English inventory
support or optional-model requirement. Corpus review, practitioner evaluation and
formal M0/M1/M2 acceptance remain separate. Implementations and tests must be
recorded as later evidence; this document alone closes none of those gates.

## Implementation and evidence

The [deployment evidence runbook](../security/DEPLOYMENT_EVIDENCE_RUNBOOK.md) supplies four fail-closed mode records, retention and backup fields, a completeness checker, and a synthetic OCR namespace packet-capture CI job. The model-note constructor accepts only a separate labelled note or review request bound to a content release; it does not mutate reports or human decisions. Tests cover authoritative-field rejection and unchanged deterministic/human values. These are engineering controls, not whole-mode captures or independent approval. Named owners and actual deployment retention evidence remain required. English Exhibit handling remains covered by PR #160, including its six unsupported verification misses.
