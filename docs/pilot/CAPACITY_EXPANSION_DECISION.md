# Candidate 50–200-page pilot envelope — decision not yet made

**D01 / T20–T29 status: OPEN.** This document is a measurement/decision
request, not a new limit. PR #198 merged on 5 November 2026 with the
\`caseproof-capacity-envelope-v1\` **development** policy. Existing signed
F3–F6 acceptance uses a small four-original synthetic fixture.

## Hard constraints of the current admission

- Exactly 4 files: one DOCX, one UTF-8 inventory, **two** PDF exhibits.
- Each source at most **5 MiB**, all originals at most **12,000,000 bytes**.
- Each PDF at most **64 physical pages**; therefore this four-original
  intake can admit **at most 128 exhibit PDF pages**, subject to byte,
  parser and OCR constraints. It cannot admit 150 or 200 exhibit PDF
  pages through this exact pathway.
- OCR accepts each source only up to **3 MiB**, and at most 64 pages,
  with isolated resource/word/TSV budgets.
- The deterministic visual evaluator attempts at most **4 distinct
  pages per snapshot**. The remaining pages are not "visually verified".
- The page-worker's standalone 200-page text benchmark and previous
  150-page discovery run are **not full-product capacity evidence**.
  Export payload ceilings, browser navigation and historical bytes
  are separate limits.

## Proposed measured candidates (none authorized)

| Candidate | Current four-source admission | Required new evidence |
|---|---|---|
| 50 mixed text/scan pages | Possibly admitted if split across two PDFs and all byte/worker/visual budgets met | Signed journey with mixed NL/FR scan processing, honest visual unassessed states, export/reopen, process death and browser memory |
| 100 mixed/scan pages | Possibly admitted only if both PDFs meet 64-page and 3 MiB OCR input ceilings | Bounded 100-page OCR throughput, cancellations, memory, partial timeout and signed version-bound acceptance |
| 150 PDF exhibit pages | **Not admitted** (two × 64-page maximum) | Decide and implement multi-exhibit transport and broader source inventory, then measure full signed workflow |
| 200 PDF exhibit pages | **Not admitted** | Same expansion, plus concurrency, worker lease fencing, recovery/cancel, long review/export and browser latency/memory evidence |

## Acceptance plan before any expansion

1. Sponsor chooses the **representative** dossier shape: actual number of
   files/bytes/pages/scans, supported NL/FR languages and printed/bundle
   mapping, not one aggregate page number.
2. Engineers produce reproducible synthetic authorized signed F0–F6
   measurements at each candidate, including at least two real
   raster-only NL/FR scans. Capture wall time (per stage and overall),
   CPU/peak per-process RSS, browser memory/navigation, OCR failures,
   end-to-end artifact bytes and emitted reason codes.
3. Exercise first-page, middle-page and last-page worker crash/restart,
   cancellation and revocation under candidate load, stale lease,
   conflicting operation and checksum tamper, plus unknown-ack retry.
4. Verify over-limit **atomic refusal before original writes** at
   adjacent boundary values and that the UI, Python policy, generated
   contract and OCR/visual/export components agree.
5. Obtain a dated D01 signed decision naming supported deployment
   (machine, concurrency, timeouts), visual partial/refusal policy,
   capacity and honest limits. Keep a fallback narrower profile and
   rollback. Run final-head signed integration **after** the decision.
6. Keep independent T70/T73/T74/T61/T75/T76–T79 approvals separate.

No private client document may be used merely to make these measurements
without prior owner, privacy, legal and security permission.
