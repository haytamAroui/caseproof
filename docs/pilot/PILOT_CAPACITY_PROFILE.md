# CaseProof pilot capacity — evidence-based profile

**Status: NOT APPROVED for confidential pilot capacity.** Updated 5 November 2026.
This replaces the earlier unsupported statement that 150 pages were an approved
full-product envelope. Do not advertise 150 or 200 pages as signed-user support.

## Current implemented development admission boundary

The Python source of truth is \`application/capacity_envelope.py\`, schema
\`caseproof-capacity-envelope-v1\`, \`approval=development_only_not_pilot_approved\`.
The frontend imports the generated
\`frontend/src/shared/api/capacity-policy.json\`. CI fails on contract drift.

| Boundary | Enforced development value | Interpretation |
|---|---:|---|
| Intake sources | Exactly 4 | 1 DOCX, 1 UTF-8 inventory, 2 PDF exhibits |
| Bytes per original | 5 MiB | Preflight and parser bound, independent of total |
| Total original bytes | 12,000,000 | Across 4 originals; before registration/write |
| Inventory text | 1 MiB | Additional limit; 512 unique Stuk/Pièce identities |
| PDF physical pages | 64 per PDF | Parser/mapping bound; not proof 64 OCR pages complete |
| Optional OCR original bytes | 3 MiB | Independent isolated OCR budget |
| OCR extraction | 20,000 words and 1 MiB TSV per page | Bounded engine output; not proof of recognition accuracy |
| Visual assessment | 4 unique pages per frozen check | Existing fail-closed visual budget; remaining pages may be unassessed |
| Visual regions and crops | 96 regions per page, 200,000 bytes per crop | Processing ceilings, not comprehensive page coverage |
| Frozen JSON/Markdown | 2,000,000 bytes each | Precondition for successful release |
| Frozen DOCX | 5 MiB | Reopen and hash checks still mandatory |

A viewer's larger historical-source read ceiling does not enlarge the
upload/parser envelope. Partial/unreadable pages and unassessed quotations
remain visible, not counted as verified.

## Measurement layers and claims

| Evidence | Measured fact | Does not prove |
|---|---|---|
| Earlier 150-page synthetic signed profile | Recorded 3.869 s discovery-only stage in [historical CI run](https://github.com/haytamAroui/caseproof/actions/runs/41875113829) | Full 150-page intake, scanned OCR, visual review, release and browser navigation |
| Earlier 200-page page-worker test | 34.845 s, four 50-page text PDFs, 2 concurrent workers, checkpoint replay | Signed intake, OCR, DOCX export or 200-page UI |
| New two-scanned-exhibit NL/FR harness | See final-head CI logs under \`CAPACITY_LOCAL_MEASUREMENT\` | Real-lawyer accuracy, a 100-page OCR envelope |
| New signed F3–F6 harness | See final-head live run with stage durations, restart, revocation, zero-residual cleanup | 150/200-page signed envelope, production rollout |
| 100 OCR pages and 50 MB source | **UNMEASURED / UNSUPPORTED** | Cannot promote to admitted pilot limits |

## Recorded measurements — 5 November 2026, synthetic only

These measurements were run on PR #198 at an earlier development commit
\`4b152d0\`. Re-run at the final accepted head before citing them for a release.

| Measurement | Observation | Provenance |
|---|---|---|
| Four-original local admission, two raster-only PDFs (one NL, one FR), Docker-network-isolated OCR, JSON/Markdown/DOCX output | 84,023 input bytes; 4.271 seconds total: admission 0.569, OCR 3.559, output 0.143; OCR 10 words NL + 10 words FR | [Local OCR measurement](https://github.com/haytamAroui/caseproof/actions/runs/42088213606/job/127458956924) |
| Same local test output bytes | JSON 955; Markdown 1,044; DOCX 37,523. Parent peak RSS 104,260 KiB; child maximum RSS 104,260 KiB (not summed and not Docker/browser peak) | Same run |
| Four-original signed F3–F6 development workflow with a scanned exhibit, independent review, correction/recheck, two partial releases, historical retrieval, grant revocation and zero-residual teardown | 322.712 seconds wall time including setup and cleanup; wrapper peak RSS 95,116 KiB. The web/browser and OCR subprocess peak memory was **not** measured. | [Signed journey measurement](https://github.com/haytamAroui/caseproof/actions/runs/42088213454/job/127458955579) |

The signed scenario is not a two-scanned-PDF NL/FR high-load scenario.
No throughput confidence interval, repeated-run distribution or safe
concurrent workload is established. These measurements cannot approve a
150-page or 200-page full-product limit. Only the limits already enforced in
the versioned development profile are currently admitted.

## Exit criteria before raising limits (T20–T29)

1. Capture exact commit, host/worker versions, staged durations and peak
   memory for the **entire signed workflow** with at least two scanned
   languages and proposed high-volume representative mixtures.
2. Approve D01: concurrency, PDF/OCR pages, files, memory, wall-clock,
   artifact growth, worker timeouts and degraded/partial visual policy.
3. Version the accepted limits and reject over-limit requests before
   any irreversible original write; preserve negative and lost-ack behavior.
4. Verify source/crop/page fidelity, worker death and lease fencing,
   cancellation, authorized refresh and cross-matter denial at the accepted
   boundary. A child-worker benchmark alone does not satisfy the gate.
5. Verify browser memory/switch/reopen, export binary digest, historical
   read and cleanup on signed development infrastructure at the accepted
   envelope. Record measured data only; no source text or private URLs.
6. Obtain named owner/security/practitioner approval where applicable.
   Until then keep \`development_only_not_pilot_approved\`.

The genuine signed F3–F6 test is an **engineering integration smoke test**.
A development upload limit is a safety boundary, not a promised acceptable
latency, throughput, detection rate, or supported confidential-data profile.
