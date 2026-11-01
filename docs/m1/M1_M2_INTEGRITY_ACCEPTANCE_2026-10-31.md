# M1/M2 acceptance increment — 31 October 2026

**1 November superseding evidence:** merged PR #159 (`05576ba`), [protected live run](https://github.com/haytamAroui/caseproof/actions/runs/41258188700), installed migrations `20261031234906`, `20261031235117`, `20261101004423`, and [exact failed-fixture recovery](https://github.com/haytamAroui/caseproof/actions/runs/41258188830). Signed synthetic correction/recheck, cold restart, revocation and zero-residual cleanup passed. Historical pending-install/run statements below are superseded; independent external approval remains absent.

**State:** signed synthetic development acceptance passed; **M1 and M2 are NOT formally complete**. The sole source of release truth is [ROADMAP.md](../ROADMAP.md) and its signed acceptance gates.

## Defects resolved by the increment

| Boundary | Before | New invariant / proof |
|---|---|---|
| M1 immutable multi-file upload | On a third-file hash mismatch, first and second originals could already have been written | Preflight the **complete** manifest's registered case, version, original SHA, organization, payload type/size and actual SHA **before first network write**. Negative tests assert zero writes for tampered last original, wrong type and cross-org metadata |
| M1 lost upload acknowledgement | A network-unknown write/409 could leave a partially stored dossier that could not retry safely | On `PrivateStorageOutcomeUnknown` or `PrivateStorageExists`, require **fresh signed `get_verified`** of the exact registered SHA. A 409 or timeout alone is never success, no upsert/overwrite, revoked and corrupted readback fail closed. Retries are recoverable, but Storage batch writes remain non-atomic across network failure |
| M2 legacy DOCX discovery | An empty/unconfirmed candidate inventory could be shown as `not_in_inventory`; a crop pointer could be labeled a verified PDF page | No signed confirmation exists in this adapter: identity is `not_assessed` with reason (or `ambiguous` for duplicate candidates), page is `page_unmapped`, crop page is a separately named **candidate**. This legacy route is marked noncanonical; canonical signed dossier remains authoritative |
| M1/M2 actual source bytes | Contract-only tests did not exercise the new M0 trilingual file corpus in the integrated CI | Exercise bounded Linux DOCX/PDF parsers on real synthetic NL/FR/EN DOCX and searchable/scanned PDFs. Assert source SHA, PDF physical page and no invented DOCX page, and scan partial/needs-OCR. Explicitly retain partial DOCX-story and recognition recall coverage |

## Executed test paths

- `tests/test_signed_multisource_journey.py` (preflight, retry, revocation, corruption).
- `tests/test_m1_m2_fail_closed_acceptance.py` (missing/unconfirmed inventory, duplicates, candidate crop).
- `tests/test_m1_m2_real_format_intake.py` (real-format source parsing, M0 synthetic corpus).
- `tests/test_phase4_headless_api.py` (authorized route/review/export contract).
- The existing **M1+M2 integrated disposable PostgreSQL** CI then runs real RLS, signed-boundary **synthetic** identities, review/correction/recheck and source custody; see [.github/workflows/m1-m2-integrated-disposable-ci.yml](../../.github/workflows/m1-m2-integrated-disposable-ci.yml).
- The repository's architecture CI includes full Python test, Ruff, mypy and original boundary suite. Passing the PR head means **engineering evidence only**.

## What remains OPEN for milestone acceptance

| Gate | Still needed |
|---|---|
| M1 signed synthetic staging | **PASSED:** genuine Auth, private Storage, four-file intake, page/crop reopening, restart, revocation and cleanup in run 41258188700. Customer approval is separate. |
| M1 custody and OCR policy | Customer-approved worker/region and egress, retention, backup/restore, malware/DOCX ZIP/PDF limits, external independent security and bar/professional-secrecy review |
| M2 whole-draft coverage | Representative NL/FR/EN mixed real-format population, pinned detection denominators, unsupported DOCX story portions, explicit inventory confirmation and page-space correctness; no statement that “every reference” is caught |
| M2 canonical signed lifecycle | **PASSED for supported synthetic API scope:** snapshot → check → review → correction → recheck → cold restart → revocation → cleanup. Representative typed date/amount/translation metrics, full browser acceptance and independent review remain open. |
| Release authorization | Named owners for P3-01..04, current-head live acceptance receipt, security/ethics/privacy decisions and signed M1/M2 milestone exit; absent here |

**Do not close M1 or M2 from this PR alone.** A signed-user synthetic test, disposable database or candidate crop is not a production-approved Belgian litigation dossier. M3 may consume the merged candidate contracts, but the separate pilot and live development gates remain.

## Live multi-source probe repair (candidate)

The protected multi-source probe now uses the installed DOCX/inventory/two-PDF contract,
checks signed Auth identity and registered source metadata, generates parseable PDF bytes, retains a separate
cleanup list across process restart failures, requires explicit authorization-denial
HTTP status codes, and permits manual dispatch from protected `main` rather than the
historic feature branch. The companion regression tests exercise PDF parsing and a
forced failure during restart. This is a candidate until the PR head passes required
CI and a separately protected live run succeeds. The probe covers a DOCX draft, one inventory and
two PDF exhibits (one image-only); it does **not** prove the complete DOCX → check → review → correction
→ recheck journey, representative OCR accuracy, or independent security/legal approval.


## Draft correction/recheck candidate

The canonical dossier API now implements bounded DOCX preview, two-stage commit
and recheck against the new active draft. The database implementation is proposed
in `db/proposals/M1_M2_dossier_draft_revisions.sql`; it is **installed in caseproof-dev**; see [deployment receipt](LIVE_DRAFT_REVISION_INSTALLATION.md).
Disposable PostgreSQL acceptance exercises pending-version signature isolation,
idempotent reserve/activate, wrong readback rejection, activation privilege fences,
audit rollback, active manifest switching, confirmation/snapshot invalidation and
revocation. Coordinator tests exercise real DOCX bytes and uncertain upload retry.
See [persistence design](DRAFT_REVISION_PERSISTENCE_DESIGN.md). All-current-head CI,
reviewed deployment, protected signed staging acceptance and independent evaluation
remain separate requirements; these additions do not close M1/M2 by themselves.
