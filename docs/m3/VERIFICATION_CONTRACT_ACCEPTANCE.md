# Verification contract/report acceptance — 31 October 2026

Engineering candidate, not a pilot release. [ADR 0022](../adr/0022-verification-contract-report.md)
resolves implementation behavior. User requested a large test-to-readiness PR; this
receipt separates executable evidence from external approval and final milestone closure.

| Contract | Implementation | Required automated evidence | External/open limit |
|---|---|---|---|
| P3-01 translation | Signed bounded language declarations plus explicit translation markers; independent flag, literal state and OCR priority | `tests/test_verification_contracts.py`; signed language-context snapshot/reopen/export assertions | Declarations are not language detection; bilingual practitioner adjudication pending |
| P3-02 OCR boundary | Existing enforced isolated runner; new per-page status/version ledger; explicit unknown counts | Executable visual/OCR CI; Docker loopback-only namespace test; signed scan abstention | Customer operator/account/region, data flows and security signoff not approved |
| P3-03 DOCX coverage | Inventory ledger → extraction → discovery → frozen report; prevent structured/hidden double counting | Raw XML with tables, stories, hidden/textbox, revisions; unsupported denominator; browser ledger and exported DOCX | Unsupported stories remain unprocessed; recall stays unmeasured; known metadata can conservatively reduce full coverage |
| P3-04 inventory | Existing pure policy now governs signed dossier; typed missing/unparseable/unconfirmed/incomplete reasons | Every InventoryStatus through real discovery and dossier; omitted row regression | Completeness is explicitly reviewer-confirmed within supplied scope, not court filing proof |

## Workflow evidence to run on the committed revision

- Locked full suite, affected Ruff/mypy, architecture and roadmap consistency.
- Real sandbox OCR, document fixture corpus and crop lineage; no network interface
  except loopback in OCR container. No confidential inputs.
- Actual browser: coverage details, translation tag, escaped quote, crop decode/hash,
  explicit review, failed-save retry, definitive rejection, signout cancellation,
  keyboard/native labels and narrow layout.
- Signed caseproof-dev: generated original bundle → upload/readback → inventory
  confirmation → declared-language check → private snapshot → crop/review → process
  restart → identical export. Assert translation flag survives OCR uncertainty and
  contract/ledger survives JSON/Markdown/actual DOCX reopening.
- Ungranted/foreign/revoked reads, forged snapshot, changed-confirmation stale denial
  and guaranteed test-run cleanup retained from existing acceptance.

No new migration or client-data permission. Existing protected test-user provisioner
and teardown are reused only for this feature branch. CI cannot close bar/ethics,
independent broader security, specialist legal opinion, practitioner interviews or
paid-commitment gates. Successful engineering allows review/merge, not release.

## Results

Current-head run links and exact counts are recorded in the PR after execution.
Before those receipts exist, this document is an acceptance protocol only.
