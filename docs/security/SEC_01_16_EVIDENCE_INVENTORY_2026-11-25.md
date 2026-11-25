# SEC-01..16 Evidence & Field-Level Data-Flow Inventory — 25 November 2026

**Status:** **OPEN / NOT AUTHORIZED FOR REAL CLIENT DATA.**  
**Codebase baseline:** `main` commit `44824863e984feecf23b16bd869e76c112a3ed70`  
**Development database audited (read-only MCP):** `caseproof-dev` (`ldwmocpxwskvhoojndrd`, Postgres `17.11.0.003`, `eu-central-1`, 78 applied migrations; Nov 24 SQL sync merged in [PR #237](https://github.com/haytamAroui/caseproof/pull/237) `4f2ab321`)  
**Authority:** [PILOT_DATA_SECURITY_GATE.md](PILOT_DATA_SECURITY_GATE.md) · [SEC-01-SEC-16.md](../m5/SEC-01-SEC-16.md) · [PILOT_DATA_FLOW.md](PILOT_DATA_FLOW.md) · [ADR 0025](../adr/0025-deployment-data-retention-and-model-authority.md)

> [!CAUTION]
> This inventory reconciles **existing engineering evidence** against the 16 mandatory pilot controls so an independent security/privacy reviewer and law-firm sponsor can audit what is implemented versus what remains **BLOCKED**. Nothing in this document certifies any control or authorizes uploading real client documents.

---

## 1. Field-Level Data-Flow Matrix Across Deployment Topologies

Every data element below is treated as potentially confidential / personal / privileged under Belgian professional secrecy and GDPR.

| Data Element | Topology A: Offline / Local Harness (`scripts/run_prefiling_partner_demo.py`, `serve_offline_legal_workbench.py`) | Topology B: Current Signed Development (`apps/api/*` loopback + EU `caseproof-dev` Supabase) | Topology C: Target Hosted / Hybrid EU Pilot (Not yet deployed/approved) |
| --- | --- | --- | --- |
| **Original DOCX / PDF / scan bytes** | Loopback process RAM/local disk only; zero outbound network | Uploaded via HTTPS/TLS to private Supabase Storage (`caseproof-originals-dev`, `eu-central-1`); read back by SHA-256 | Must be pinned to approved EU region or firm-controlled custody perimeter before pilot |
| **Inventory & exhibit labels (`Pièce`/`Stuk`, filenames)** | Local loopback only | Persisted in private `caseproof.*` Postgres tables (RLS enforced) | Persisted in approved DB with contractual retention & erasure schedule |
| **Derived OCR text & page crops** | Local deterministic parser / OCR only | Isolated OCR worker namespace (no outbound non-loopback in CI capture); derived geometry stored in private Postgres | Must run in approved isolated worker with OS-enforced egress denial + bounded temp cleanup |
| **Reference strings, quotes, SHA-256 hashes, IDs, verdicts, timing** | Local loopback JSON / ZIP | Stored in private Postgres check runs, review ledger, and immutable release manifests | Treated as confidential metadata; excluded from generic third-party telemetry/error trackers |
| **Human review decisions & rationales** | In-memory session or offline pack | Append-only signed ledger (`_m2_review_events`, `_m2_review_receipts`, `audit_events`) bound to `auth.uid()` | Immutable actor-attributed ledger with revocation & audit integrity |
| **Exported Annotated DOCX / JSON / Markdown + HMAC receipts** | Downloaded directly to user's machine; SHA-256 digest only | Generated server-side via `annotated_docx()`, signed with separate rotatable `CASEPROOF_RECEIPT_HMAC_SECRET` | Must include explicit non-signature / non-*constat* notice; expiring authorized artifact URLs |
| **Remote LLM / external AI APIs** | **None (`0%` LLM in Pilot Core)** | **None (`0%` LLM in Pilot Core)** | **None by default** (`BE-09` deferred until after M5; requires separate approval + data-flow capture) |
| **Backups & provider logs** | Local OS only | Managed Supabase backups/logs in `eu-central-1` (provider backup-expiry proof **UNVERIFIED**) | Requires contractual retention, tested restore drill, and documented backup-erasure policy |

---

## 2. Per-Control Evidence Reconciliation (`SEC-01`..`SEC-16`)

*Alignment note:* Control numbering follows [PILOT_DATA_SECURITY_GATE.md](PILOT_DATA_SECURITY_GATE.md) (authoritative 16-control gate). No control is marked `APPROVED` until independent external/owner sign-off is recorded.

| ID | Control | Current Status | Existing Engineering Evidence (`main` `44824863`) | Blocking Gap to Reach `APPROVED` |
| --- | --- | --- | --- | --- |
| **SEC-01** | Threat model & trust map | **PARTIAL** | [PILOT_DATA_FLOW.md](PILOT_DATA_FLOW.md), [DATA_RIGHTS_ENFORCEMENT_ROUTE_AUDIT.md](DATA_RIGHTS_ENFORCEMENT_ROUTE_AUDIT.md), CSP/loopback boundaries in `apps/api/litigation_development_app.py` | Formal reviewed threat model covering prompt injection, file bombs, cross-tenant bleed, OCR spill, and stolen links with named risk owners |
| **SEC-02** | Encryption in transit | **OPEN** | HTTPS/TLS used by Supabase client adapters (`apps/api/signed_supabase_originals.py`, `workspace_auth.py`); loopback-only dev host check | Independent TLS configuration capture & cipher/fallback verification on actual target deployment |
| **SEC-03** | Encryption at rest & keys | **PARTIAL** | Separated HMAC receipt signing key + zero-downtime key rotation (`CASEPROOF_RECEIPT_HMAC_SECRET`, `tests/test_hmac_receipt_key_rotation.py`, PR #233) | Provider encryption-at-rest proof for DB, Storage, backups, and temp OCR disk; formal key-rotation & leak-response SOP |
| **SEC-04** | Authentication & authorization | **PARTIAL** | Signed-user PostgREST/Storage RLS + revocation tests in CI (`m1-m2-integrated-disposable-ci.yml`), live `caseproof-dev` catalog check (`rls_enabled=true`, `rls_forced=true`, `search_path=""`) | Genuine signed-user live-RLS acceptance on exact target environment + independent review of authenticated `SECURITY DEFINER` RPCs (Supabase Advisor `0029`) + enable leaked-password protection (`auth_leaked_password_protection`) |
| **SEC-05** | Original-byte provenance | **PARTIAL** | Read-side canonical JSON SHA-256 verification (`PR #231`), private Storage digest readback, append-only review/audit tables, real Postgres 17 CI check (`PR #233`) | Independent adversarial tamper testing on target deployment |
| **SEC-06** | OCR location & egress | **PARTIAL** | Synthetic isolated OCR worker network capture (`run 41666612265`, loopback-only control + denied outbound attempt) and CI `real-ocr` (`synthetic-scan-ocr.yml`) | Exact-head OS-enforced runtime egress denial + named approved worker hosting/version for pilot |
| **SEC-07** | Data minimization | **PARTIAL** | No third-party analytics/telemetry in `frontend/`; strict storage boundary lint (`frontend/scripts/check-boundaries.mjs`) | Audited log-sanitization test proving zero raw quotes, tokens, or personal data in runtime/error logs on target host |
| **SEC-08** | Retention & deletion | **PARTIAL** | [RETENTION_DESIGN.md](RETENTION_DESIGN.md), `matter_retention` & `retention_storage_fence` migrations + disposable PG retention CI | Customer-visible retention schedule, legal-hold procedure, and verified backup-expiry / deletion proof |
| **SEC-09** | Subprocessor & transfers | **OPEN** | `caseproof-dev` verified in `eu-central-1` (`ldwmocpxwskvhoojndrd`); 0 external LLM subprocessors | Complete signed subprocessor register (hosting, DB, storage, DNS, monitoring, email) with legal entities, locations, and transfer terms |
| **SEC-10** | Lawful role & professional secrecy | **OPEN** | Working draft DPA at [docs/m5/dpa-working-draft.md](../m5/dpa-working-draft.md) | External Belgian counsel review (bar professional secrecy / OVB / Avocats.be), GDPR DPIA, and executed DPA with pilot firm |
| **SEC-11** | File & model security | **PARTIAL** | Bounded DOCX/PDF container validation (`application/documents/file_boundary.py`), structured per-file corrupt/locked rejections (`PR #233`), `annotated_docx()` active-content refusal, 0% LLM in verdict path | Formal adversarial file-bomb / malware / parser-budget test receipt on target worker + dependency advisory disposition |
| **SEC-12** | Penetration / security test | **OPEN** | Disposable SQL adversarial tests and CI supply-chain checks | Independent risk-proportionate security assessment / pentest with critical/high findings remediated |
| **SEC-13** | Incident response | **OPEN** | None signed off yet | Named incident owner, escalation runbook, GDPR/contractual breach-notification criteria, and tabletop rehearsal |
| **SEC-14** | Backup, DR & availability | **PARTIAL** | Isolated PostgreSQL 17 backup/restore + erasure-replay CI (`restore-simulation`) | Actual target-provider Supabase restore drill, documented RTO/RPO, and backup-retention verification |
| **SEC-15** | Reviewer & export control | **PARTIAL** | `PR #204` release acknowledgement fence, `PR #233`/`#234` HMAC vs SHA-256 UI clarity, stale-snapshot 409 guards, real `annotated_docx()` export, logout/session-clear transport tests | Independent review of export-grant boundaries and cold-reopen verification on target deployment |
| **SEC-16** | Support & deployment runbook | **PARTIAL** | [DEPLOYMENT_EVIDENCE_RUNBOOK.md](DEPLOYMENT_EVIDENCE_RUNBOOK.md), version-pinned `uv.lock` / `package-lock.json`, GitHub `main` ruleset enforced (`GH013`) | Version-pinned target deployment & rollback drill, patch cadence, offboarding procedure, and named pilot contacts |

---

## 3. Non-Negotiable Release Rule

Real client or confidential legal uploads remain **BLOCKED** until:
1. Target deployment topology (local-only, hybrid, or hosted EU) is locked based on `M5-01` partner discovery,
2. All 16 controls above are independently evidenced and signed off for that exact environment and commit, and
3. An executed DPA + Belgian professional-secrecy sign-off and named law-firm sponsor approval are on file.
