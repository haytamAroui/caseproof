# CaseProof / ExceptionDesk — verified engineering status

## 2026-10-23 — Persisted exact text evidence increment

PR #51 is merged at `9dabe59a4ddeea2f9aaed9b4d83c32af67683099`; its
verified feature head passed 881 unit tests, eight real disposable Vault
integration tests, type/lint/architecture and migration checks in
[CI 39938192806](https://github.com/haytamAroui/caseproof/actions/runs/39938192806).

[TEXT-INT-001](tasks/TEXT-INT-001.md) adds internal read composition for the
existing persisted graph plus actual Vault bytes. Its first identity UTF-8
representation reuses original bytes, preserves exact code-point offsets and
separates citation/fidelity from support/approval. A separate-process PostgreSQL
fixture demonstrates recovery and negative cases; new-head CI evidence must
be recorded on its PR. No live migration, new authoritative facts table,
production identity, parser/OCR/LLM pipeline or human decision is introduced.

## 2026-10-23 — Vault integration increment (feature branch)

Base `main` is `901c51d08dfac577d56799889701416e9139940d`, including PRs
#45/#46/#50; its architecture, disposable PostgreSQL and canonical migration
checks were verified successful. PR #49 supplies private filesystem bytes;
PR #50 supplies the disposable DB-API VaultLedger driver. Neither is a live
Supabase Storage deployment. Older snapshots below predate those merges.

[VAULT-INT-001](tasks/VAULT-INT-001.md) adds a real psycopg + filesystem +
coordinator integration command to required PostgreSQL CI. It exercises
fresh-process recovery, retry/concurrency, lost acknowledgments, tampering,
audited availability loss, rollback and scoped denial. New-head CI evidence
must be recorded on its PR before this increment is called verified.
Synthetic actors and postgres-owner fixtures do not establish genuine Auth,
runtime RLS or production read authorization. No live grants, migrations,
storage buckets, HTTP routes or approved decisions are introduced.

**Last verified:** 2026-10-22 UTC against `main` commit `66db73667cc4932995e0376d7f1b7c9279c70041`, merged PR #35. **Not a live release certificate.** Recheck GitHub before acting; this file can become stale.

**Product direction:** ExceptionDesk finance-first supplier invoice ↔ purchase-order exception resolution; CaseProof factual dispute dossiers only after finance validation. Repository name stays `caseproof`. AZComply remains independent.

## Implemented and tested

| Slice | Status and supporting evidence | Not proven / not wired |
|---|---|---|
| Stage 0 / finance reference | Modular Python kernel, initial `Decimal` total-amount discrepancy comparator, CI. | Full VAT, line-item, amendments or customer-facing finance pipeline. |
| Stage 1 KRN-101–109 | In-memory immutable source/representation versions, typed anchors, fidelity vs semantic support, findings, scoped source/issue coverage, promotion gates, provenance, API v2 proposal and adversarial tests. | Persisted complete graph, genuine authenticated approval. |
| S2-001/002/002A | Application access boundary, seven-table canonical `caseproof` migration in dedicated development Supabase project, PostgreSQL 17 disposable RLS/CAS/rollback tests. | Production role and user-issued session-to-live-DB proof. |
| S2-003/005/006 | Remote Supabase `/user` Auth verifier, read-only case adapter, manual signed-user test harness. | Real A/B accounts and completed signed-Auth test run; application wiring. |
| S2-004 / PR #28 | Internal **disposable-only** atomic observation + audit + receipt proof with concurrent and failure tests. | Production transaction service, human decision/approval route. |
| S2-007 / PR #29 | Synthetic two-tenant RLS and revocation fixture; protected manual genuine-Auth workflow. | Real signed-user test, live least-privilege DB session binding and revocation tests. |
| S2-008 / PRs #30–33 | Durable graph design; **disposable** SQL source/representation/anchor graph, typed locator codec and read-only PostgreSQL JSONB reconstruction. | Installed graph migration, full finding/assessment/coverage persistence, object-backed source authenticity. |
| S2-009 / PRs #34–35 | **Internal** put-once/read-back Vault protocol + recovery; **disposable** PostgreSQL pending-intent, case revision, audited availability and idempotent replay proof. | Real private Storage bucket, verified object bytes, real VaultLedger driver, availability-head publication. |

**CI snapshot:** main `66db736` had successful `Kernel boundary` run [39746350280](https://github.com/haytamAroui/caseproof/actions/runs/39746350280) and migration integrity run [39746350518](https://github.com/haytamAroui/caseproof/actions/runs/39746350518). The PR #35 test branch passed 778 Python tests + PostgreSQL 17 fixture in [39745880251](https://github.com/haytamAroui/caseproof/actions/runs/39745880251). **Fixtures and unit doubles are not proof of cloud authorization or customer readiness.**

## Architecture contract consolidation (stacked proposal, NOT merged)

[ADR 0011](adr/0011-architecture-freeze-and-first-finance-slice.md) freezes the original six-responsibility architecture and shifts execution to parallel secure-foundation and synthetic-only finance product tracks. [Architecture baseline](../contracts/architecture_baseline_v1.json) and [Action catalog](../contracts/action_catalog.v1.json) are checked by tests: API ↔ KRN-102 ↔ persistence exact locator round trip (canonical `sheet_range`, PDF decimal strings, text normalization, sheet table ID), all uninstalled v2 approval actions blocked, no new permission grants or enabled routes. This feature PR is **stacked on unmerged PR #36**; no statement here implies it is live on main or deployed.

## Real blockers — must remain open until verified

**SEC-01: owner-controlled merge protection.** Repeated main CI succeeds; architecture negative-control PR #4 failed explicitly on `forbidden import domains.finance.reconciliation` in [run 39555343328](https://github.com/haytamAroui/caseproof/actions/runs/39555343328). GitHub rulesets query returned an empty list on 2026-10-22 and branch protection read returned 403 to the connector. **Neither proves main is protected.** Owner must enable/prove branch protection, mandatory status checks and review. [Issue #5](https://github.com/haytamAroui/caseproof/issues/5) stays open until verified. Never merge sabotage PR #4.

**[SEC-02: real signed Auth and secure DB runtime](https://github.com/haytamAroui/caseproof/issues/37).** Create two separate confirmed **development** Auth accounts, configure approved protected GitHub environment, run S2-007 manual workflow, then implement/test true verified bearer-to-least-privilege tenant DB authorization, session revocation and pool cleanup. Signed Auth→synthetic SQL claims in the fixture is **not** true live database identity propagation.

**[STORAGE-01: actual immutable private bytes](https://github.com/haytamAroui/caseproof/issues/38).** No private bucket/real object bridge, scanning/quarantine, row-level object access, signed URL threat tests, persistent object availability recovery, or verified external Storage transaction boundary.

**[DATA-01: durable kernel and authorized decisions](https://github.com/haytamAroui/caseproof/issues/39).** S2-008 proposal schema remains under `db/proposals/`. No installed representation/anchor/assessment/coverage/head migrations; no server-bound `/v2` approval route, authenticated human-attestation policy, or fully persisted case resolution.

**OPS-01: crash recovery and [MVP-01 end-to-end product](https://github.com/haytamAroui/caseproof/issues/40).** S2-010 leased durable workers/recovery unimplemented. The current `apps/api/main.py` is a development-only `/v1/claims` in-memory app trusting caller-provided `X-Tenant-Id`. `apps/web` does not exist. No real invoice/PO upload, extraction, issue inbox, review or export customer journey.

## Next work — prioritize an actual usable outcome

1. **Resolve SEC-01** with owner-approved merge enforcement; don't silently relax constitution C13/C25.
2. **Connect trusted Auth and data layer:** SEC-02 real signed-user integration + least-privilege app DB session, scoped positive and negative test evidence.
3. **Implement real private Vault:** STORAGE-01 private bucket adapter, proper intent/availability migration/ledger, verified byte read-back and automatic quarantine/reconciliation (no direct public URL).
4. **Finish the narrow persisted evidence/decision graph**, not another full suite of unrelated prototypes. Retain exact source/version/anchor/coverage/revision and audit semantics.
5. **One complete deterministic finance vertical slice:** signed-in user uploads invoice + PO, inspects exact cited source, sees discrepancy, records permitted human resolution and downloads evidence-linked report.
6. Validate customer time saved; only then implement optional agent orchestration, ERP/Peppol integrations and dispute expansion.

**Do not invent** real accounts, Storage buckets, approval status, CI checks, revenue or deployment. Update this file after each substantive change; mark human approval/production states separately.

## EI-001 — integrated extraction candidate runtime (feature branch)

Branch `feat/evidence-intelligence-v1`, based on main `6e8290faa638f3d1159add37e52a3558a870a7ba`. Adds Requesty-only HTTP integration, bounded discovery/extraction/repair strategies, independent entity boundaries, item-level quote and signal checks, rejected-candidate/conflict ledger, Kernel finding/link/coverage projection and disposable PostgreSQL checkpoints/events. [ADR 0012](adr/0012-evidence-intelligence-candidate-runtime.md) and [task/persistence review](tasks/EI-001.md) delimit scope. No Kernel changes, production migration, provider SDK, live model request, customer documents, approval route or deployment. Finance-first product remains; construction is an experimental second vocabulary only.

Local locked pytest (988 tests), Ruff, strict extraction mypy, architecture check, compilation and offline demo pass. Real PostgreSQL recovery tests are wired into CI, not locally executed; the final suite count and cloud results will be recorded on the combined PR. Live provider quality/cost baseline **not measured**. Production Auth/Vault authorization, rich parsers, reviewer UI/decisions, durable accepted evidence graph and independently verifiable dossier remain open gates.

## EI-002 — source-preserving document intake (stacked feature PR)

Branch `feat/document-intake-extraction`, based on PR #53 HEAD `26b2946e2775045eed5372b9c05a72372d2ddf85` (still open, not silently merged). Implements bounded Linux PDF/XML/MIME parsers, page/path/part mappings, checkpointed normalization and explicit failures, internal authorization+Vault composition, native XML scalar citations and deterministic UBL comparison. The shared extraction runtime is reused without Kernel changes. [ADR 0013](adr/0013-document-normalization-and-evaluation.md), [review/test specification](tasks/EI-002.md).

Four repository-owned synthetic files and an evaluator distinguish scripted safety checks from opt-in live Requesty measurement. Requesty credentials/model are **not configured here**; no live model accuracy or cost is claimed. No production route, canonical migration, mailbox, customer upload, OCR service or deployment. The MIME extension affects the internal/disposable Vault reference only. Production identity, malware scanning/isolation, review/decision and dossier gates remain open. Final local/CI evidence belongs to the combined PR.
