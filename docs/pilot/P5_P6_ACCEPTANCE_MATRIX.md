# CaseProof P5/P6 — operational and practitioner acceptance ledger

**Prepared:** 2026-11-04 · **Environment:** development / synthetic fixtures only.
**Baseline:** main `a449278b5e49038983b801eab2c49b5982cca531`.
**Scope:** This is an evidence collection and release gating worksheet, **not evidence that any host, person, deployment, backup, or customer dataset was tested**.

## Required final-head engineering evidence

| Gate | Required independent evidence | Current observation |
| --- | --- | --- |
| P5 DOCX appendix (T15/T60) | Synthetic real-format DOCX golden/readback tests, original ZIP-member comparison, Unicode/invalid-XML negative controls, final-head CI | Pending final-head workflow |
| P5 exhibit drift (T47/T48/T66) | Server-issued old/new snapshot correspondence, ambiguous/unsupported/renumbered/source/page tests; UI fails closed; no review transfer | Pending final-head workflow |
| P6 build and dependency hygiene (T72) | Pinned uv/npm lockfiles, locked install and frozen graph/SBOM generation; independent dependency review | Pending final-head workflow |
| P6 integrated signed journey (T77) | Protected genuine signed-browser run on exact PR HEAD; auth→matter→intake→confirm→verify→review→correction→recheck→release→restart/historical; adversarial denial and zero-residual fixture cleanup | Not executed for this HEAD |
| P6 release declaration (T79) | Complete reviewer/CI receipts, rollback and independently approved scope | Not approved |

Relevant protected workflow: [F6 genuine signed reviewed export](../../.github/workflows/review-f6-live.yml); offline tests are **not** real signed acceptance. A skipped, failing or older SHA gate never counts as pass.

## Human and operational gates — independently owned, not automatable by code alone

| Gate | Required evidence record | Closure rule |
| --- | --- | --- |
| T61 DOCX host interoperability | Host name, **desktop Word/LibreOffice** version, OS, date, fixture hash; reopen screenshots or inspected notes for paragraphs, styles, runs, tables, footnotes, comments, hyperlinks and corrected/annotated derivatives | Real test on each declared supported host; list unsupported constructs |
| T70 actual grants and RLS | Dev project ref, read-only catalog SQL, function owner/search_path, grants, policy tests, independent security reviewer, advisor output | No privileged simulated claim represented as signed RLS |
| T73 processing/egress/privacy | Selected local/hybrid/hosted topology, data flow, capture boundaries, OCR/model/provider regions, approved retention, exact UI disclosure | Deployment capture and contract evidence; no zero-egress marketing claim |
| T74 backup/restore/erasure | Approved isolated backup, restore timestamps, operator, artifacts/checksums for originals, OCR, snapshots, receipts, releases, legal-hold and deleted data | Prove authorized read and that deleted private data did not reappear; record cleanup; no production restore |
| T75 manual accessibility and languages | Browser/OS, actual screen reader/AT, keyboard/reflow/200% zoom/forced-colors/reduced-motion, NL/FR/EN examples, independent tester | WCAG 2.2 AA issues logged and repaired, not axe-only |
| T76 rights-cleared documents | Permission/license record, data owner, source hash, NL/FR/EN and scanned/text fixtures, source security classification, independent gold labels | No confidential source committed, uploaded or shared with unapproved tools |
| T78 practitioner utility | Consent/data terms; reviewer roles; timed manual vs CaseProof cases; recall, false approvals, uncertainty comprehension and review agreement with denominators | Real participants and reviewer sign-off; no invented outcomes |
| T79 pilot approval | Named accountable product/security/operational owners with dated decision, limits, rollback and signed evidence links | Explicit sign-off after all required gates pass |

## Evidence record template (one per gate)

```yaml
task_id: T77
status: PENDING # PASS / FAIL / PENDING
owner_or_reviewer: null # must be actual accountable person
implementation_commit: null
pull_request: null
execution_date_utc: null
environment_and_versions: null
fixture_rights_and_sha256: null
commands_or_protocol: null
workflow_run_or_private_evidence_uri: null
observed_result: null
adversarial_negative_cases: null
cleanup_and_zero_residual: null
limitations: null
rollback: null
approval: null
```

This worksheet does not create credentials or authorize production operations. Keep any client materials and private run artifacts outside public GitHub; use only redacted evidence metadata. Preserve source bytes and decision identities. Work requiring an owner decision or host access stays **PENDING**, even if automated CI is green.
