# Final hardening and verification — evidence gate

Status: **OPEN / NOT RELEASE AUTHORIZED**. This branch must not be marked ready or merged on the strength of this document alone.

## Scope
No product features. Reuse existing signed dossier, retention, OCR and CLI acceptance infrastructure.

## Required acceptance
- [ ] OCR process network egress is denied by an enforced runtime boundary (not Python monkeypatching). Capture a real outbound HTTP denial from within the worker.
- [ ] Bound worker memory, CPU and execution time. Prove a hostile/oversized PDF fails closed without leaking source bytes.
- [ ] Re-run the signed 150-page/60-reference dossier on this exact head; attach downloadable raw JSON metrics and logs. Record server peak RSS, discovery time and input hashes.
- [ ] Report TP/FP/FN for reference detection; never describe extraction accuracy as legal identity, OCR, page mapping or semantic-support accuracy. Statistical FPR requires a defined TN universe.
- [ ] Run a hostile PDF containing exfiltration instructions; prove no outbound transmission and no promotion of those instructions to trusted actions.
- [ ] Confirm cross-matter, export denial, revoked JWT, retention and legal-hold regressions.
- [ ] State backup expiry as unverified unless provider-specific retention and a restore/erasure replay drill are evidenced.
- [ ] Run the signed CLI workflow on this exact head; link the green run and downloaded report artifact.
- [ ] Full CI green and independent security/privacy review before marking ready.

## Existing evidence, not new-head acceptance
- Signed complete synthetic dossier: https://github.com/haytamAroui/caseproof/actions/runs/41089564559
- Disposable SQL regressions: https://github.com/haytamAroui/caseproof/actions/runs/41089564532
- Earlier 150-page benchmark: https://github.com/haytamAroui/caseproof/actions/runs/41081792051
- Retention signed run: https://github.com/haytamAroui/caseproof/actions/runs/41085730618

## Reporting rule
Do not write EGRESS_BLOCKED_VERIFIED, a PEAK_MEMORY value, or BENCHMARK_ACCURACY_100_PERCENT unless the corresponding exact-head execution artifact actually proves it. The earlier benchmark reports 60/0/0 reference extraction only, not legal verification.

## Release boundary
A green synthetic backend run does not authorize confidential client data or close the SEC-01–SEC-16 independent gates. Pilot validation, worker deployment isolation, provider backups, and external privacy/legal sign-off remain separately required.
