# CaseProof — Deep Codebase Audit (2026-11-11)

**Snapshot:** local `main` = `af438c3771add91f3b4b83409d464a0c05031670` (PR #209) · `origin/main` = `e4195a7c` (PR #211).
**Method:** read-only static audit across every layer + independent measurement (route enumeration, AST scans, `pytest --collect-only`, `gh run list`, `gh api rulesets`). No repository file was modified by this audit.

**Scope covered:** 1 191 files / 150 378 lines (499 Python · 275 Markdown · 106 SQL · 95 TS · 25 TSX · 41 JSON).

---

## 0. Verdict in one paragraph

This is a **serious, unusually disciplined codebase with a serious documentation and operational gap**. The *engineering* is largely real: a pure evidence kernel with 309 passing tests, a fail-closed hexagonal layering, real Supabase Auth + RLS + Storage transports, real PDF/DOCX/OCR parsers, a React 19 frontend that implements nearly all of its blueprint, and 2 322 Python + 156 JS test IDs. There is **no authentication bypass, no cross-tenant read, no SQL/command injection, no XXE, no path traversal** found anywhere. What is *not* real: **there is no deployment of any kind**, **one third of the API codebase is unreachable**, **the documentation lags the code by 13 merged PRs and misstates the merge gate**, **the contract-freeze guard that is supposed to protect the architecture checks the wrong file**, and **live service-role credentials sit ungitignored in a public repo working tree**. The product is genuinely further along than its own status ledger says, and genuinely further from production than the green CI badge suggests.

---

## 1. What is inside the code — layer by layer

### 1.1 `packages/evidence_kernel/` — 2 385 LOC, 14 files — **the strongest asset in the repo**

Twelve domain modules, all pure stdlib Python. Zero forbidden imports (verified exhaustively). No `TODO`/`NotImplementedError`/stub markers anywhere.

| Module | Real responsibility | Grade |
|---|---|---|
| `source_versions.py` | Immutable source bytes + versioned derived representations | production logic, in-memory storage |
| `anchors.py` | Typed, representation-bound citation locators (TextSpan / PdfRegion / SheetRange / StructuredField) | **production** |
| `fidelity.py` | Independent citation resolution + exact content fidelity, 4-way outcome | **production** |
| `finding_links.py` | Revision-bound finding↔evidence assessment links; recomputes fidelity server-side | **production** |
| `grounding.py` | Policy-versioned, fail-closed eligibility gate with optimistic re-read | **production** |
| `coverage.py` (596) | Versioned issue/source coverage inventory, anti-cherry-picking link check | **production** |
| `provenance.py` / `provenance_binding.py` | Deterministic per-tenant hash chain + read-only bridge | **production** |
| `evidence.py` / `workflow.py` / `store.py` | v1 legacy compatibility surface | reference |
| `ports.py` | `EvidenceRepository` Protocol | **dead code — zero references repo-wide** |

`Decimal` is used for all PDF geometry; **zero `float`** in the entire kernel.

### 1.2 `domains/` — 1 096 LOC, 15 files

- **`domains/disputes/`** (the ACTIVE product): `exhibit_identity` (identity resolves only against a CONFIRMED_COMPLETE inventory; fails closed to `NOT_ASSESSED`/`NOT_IN_INVENTORY`/`AMBIGUOUS`/`SOURCE_MISSING`), `dossier_verification` (4 independent dimensions, hard-coded `"support": "not_assessed"` at `dossier_verification.py:172`), `multisource_manifest` (duplicate-source rejection, `assert_authorized` raises if *any* source is inaccessible), `reference_detection` (NL/FR regex: `stuk`/`stukken`/`pièce`/`pièces` + `bis`/`ter`), `page_labels`, `exhibits` (CAS revision), `docx_exhibit_page_policy` (**dead** — parallel inline copy lives at `application/litigation/library.py:58-63`).
- **`domains/finance/`** — legacy ExceptionDesk. **Zero litigation code imports it.** Kept as compatibility per ADR 0018/0019.
- **`domains/construction/`** — **effectively unreachable.** Only referenced by tests, evals and one demo script.
- **`domains/evidence_signals.py`** — sits at `domains/` root, **outside every `RULES` root in `scripts/check_architecture.py`** → never scanned by the boundary checker.

### 1.3 `application/` — 5 180 LOC, 49 files

Clean separation: `application/` holds pure policy + Protocol ports; `apps/api` holds identity/transport/persistence. No meaningful duplication.

- `application/litigation/` (24 modules) — the active product logic: matter policy (default-deny), unified review, paraphrase guard, regional fidelity, review-cycle CAS, release completeness.
- `application/extraction/pipeline.py` (693) — **finance-era LLM pipeline, NOT on the litigation path.** The live dossier path uses only deterministic components; no LLM produces a dossier finding.
- `application/runtime/` — `worker.py`, `documents.py`, `pages.py` (`PageCoordinator`) are **real but not production-mounted**.
- `application/documents/file_boundary.py` — **genuinely strong** ASVS V5 preflight (traversal, symlinks, encryption, zip-bomb ratio, absolute paths).

### 1.4 `infrastructure/` — 3 314 LOC, 27 files

All parsers are **real**, not stubs: `pypdf` text layer, `zipfile`+`defusedxml` DOCX (including real `w:ins`/`w:del` tracked changes), poppler+tesseract OCR in a `--network none` Docker/unshare sandbox, PDF visual fidelity (dual-view), OOXML structured editing, DOCX export. Every failure mode raises a typed refusal; `OCRUnavailable` is recorded as a *state*, never as success.

**But**: `persistence/m1_exhibit_memory.py` is a test fixture; `execution/postgres_jobs.py` is real SQL against tables that **have no live migration**; `telemetry/operations.py` is **unwired** (`observe_tool` referenced only by one test); `supabase/multisource_readback.py` is **unwired**.

### 1.5 `apps/` — 18 244 LOC, 116 files

| App | Mounted routes | Verdict |
|---|---|---|
| `apps/api` (72 files) | **95** (66 `/v2`, 21 `/dev`, rest static) | substantially real, Supabase-backed, **loopback-pinned** |
| `apps/worker` (4 files) | 0 | **231 LOC, one job type, one-shot CLI, no daemon** |
| `apps/web` (10 files) | 0 (served by API) | ClearBrief = real UI calling the real API; `review/` = Linux-only; `prototype/` = orphaned offline toy |
| `apps/word_addin` (30 files) | 0 (client) | real Office.js add-in, real PKCE/OAuth, read-only, **no host ever tested** |

**Critical structural fact:** `apps/api/main.py` is **not the application**. It is an 89-line dev demo with a caller-controlled `X-Tenant-Id` header (`main.py:58-62`) and an in-memory store. The real app is `apps/api/litigation_development_app.py` via `apps/api/dev_live_entry.py`. **33 of 72 API modules are unreachable from any entry point**, including both Postgres `CaseAccessRepository` implementations, the whole `authenticated_*` composition layer, `contracts_v2`, `requesty_extraction`, and every `disposable_*` module.

### 1.6 `frontend/` — 147 files, ~19 k lines — **the most complete part of the product**

Vite 8.3.5 + React 19.3.1 + strict TS 6.0.3 + Router 8.5.1 + TanStack Query 5. **Zero TODO/FIXME/mocks in product source.** Every response is AJV-validated then semantically re-checked; unknown enum states fail closed. 107 vitest + ~55 Playwright tests, all route-intercepted with synthetic fixtures.

### 1.7 `supabase/migrations/` — 72 files, 8 996 SQL lines + `db/proposals/` — 28 files, `contracts/` — 5 files

All 80 `SECURITY DEFINER` functions pin `search_path` (0 gaps). All 15 RLS policies scope by `auth.uid()` + active membership + matter grant. Bucket `caseproof-originals-dev` is private (20 MiB).

### 1.8 `evals/` — 4 files + 3 corpus JSON (v1 14 cases, v2 19, v3 37)

NL/FR/EN/mixed — **no German**. `label_status: author_supplied_unadjudicated`, `legal_validation: false`, `independent_gold: false`.

---

## 2. What is NOT built, not wired, or not proven

### 2.1 Deployment — **nothing is deployable as written**

- No Dockerfile for the API or worker, no compose, no k8s/Helm/systemd manifest, no `[project.scripts]` entry. `docker/` contains **9 lines total**: an OCR *tool* image and a *test* image.
- `apps/api` is loopback-pinned by middleware (`litigation_development_app.py:215-219` → 403 `loopback_only`).
- `apps/worker` is a one-shot CLI; **no supervisor, no daemon, no scheduling**. OCR only advances when a human runs `python -m apps.worker.signed_page_worker --case … --job …` with a bearer in `CASEPROOF_WORKER_BEARER` (env var, contradicting the module's own "no stored bearer" docstring).
- `apps/word_addin` needs `npm run build` (`dist/live-auth.js` is gitignored) **and** a trusted TLS cert.
- The whole stack is **Linux-only by construction**: `infrastructure/parsers/pdf_ocr.py:13` and `worker.py:7` do an unconditional POSIX-only `import resource`; `parsers/limited.py:27` hard-fails off Linux.

### 2.2 CI reality — **the live acceptance family never runs**

| Workflow | Last 20 runs |
|---|---|
| `review-f6-live.yml` | **skipped × 20** |
| `review-f4-live.yml` | **skipped × 20** |
| `intake-f3-live.yml` | **skipped × 20** |
| `pr204-signed-release-ack.yml` | **skipped × 20** |
| `m1-m2-one-click-e2e.yml` | **skipped × 20** |

The gate is `if: github.head_ref == '<branch name>'` — a *branch name*, not an environment or a scope. 22 workflows use this pattern. The result: **`main` has no live signed-browser coverage at all**, and the gate evaporates the moment the branch is deleted. This is stated in `docs/security/DATA_RIGHTS_ENFORCEMENT_ROUTE_AUDIT.md:50-53` and **nowhere** in `AGENTS.md`, `STATUS.md` or `ROADMAP.md`.

Of 59 workflows: **24 have ≥1 success**, **10 only ever skip**, **23–25 have zero runs ever**.

### 2.3 The merge gate is two checks and zero human review

Live API (`gh api repos/haytamAroui/caseproof/rulesets`) confirms ruleset **25660385 "Protect main"** is `enforcement: active` with `current_user_can_bypass: never`, requiring exactly **2** status checks (`architecture`, `Disposable PostgreSQL concurrency and audit regression`) and **`required_approving_review_count: 0`**.

> **All three of `AGENTS.md:22`, `docs/STATUS.md:316` and `CLAUDE.md:9` state that branch protection is "NOT verified" / "returned none" / "read was 403".** That is stale: the ruleset was created **2026-10-22T19:40** and issue #5 is **CLOSED**. The 404 on `/branches/main/protection` is because protection is via *ruleset*, not the legacy endpoint — which is exactly what the docs misdiagnosed.

The real residual is different and undocumented: **no human code review is required**, and 23 of ~25 CI checks are non-blocking.

### 2.4 The `/v2` contract-freeze guard checks the wrong file

```python
# tests/test_architecture_freeze_v1.py:136
assert '"/v2/' not in (ROOT / "apps/api/main.py").read_text()
```

`apps/api/main.py` contains only `/health`, `/v1/claims`, `/v1/claims/{claim_id}` — it has **never** had a `/v2` route, so the assertion **cannot fail**. Meanwhile `contracts/v2_operation_matrix.json:2` claims `"status": "typed_contract_only_all_v2_routes_disabled"` and `:158` "all /v2 routes stay disabled", while the shipped app serves **66 mounted `/v2` routes across 63 path templates** (measured by instantiating `create_litigation_development_app()`).

The *matrix's own 6 operations* are genuinely unmounted — so the matrix scope is accurate, but its **global status string is false** and its **only enforcement point is inert**.

### 2.5 The migration set cannot be replayed in filename order

`caseproof._phase4_reference_decisions` is created **only** in `supabase/phase4_reviewed/caseproof_phase4_signed_reference_review.sql:2`. **No file under `supabase/migrations/` creates it**, yet 7 migrations / 20 references depend on it — including a DDL trigger (`20261030155817_matter_retention.sql:94`) and a PL/pgSQL `%rowtype` validated at function-creation time (`20261030161844_complete_dossier_journey.sql:32`).

`supabase db push` against the repo directory **fails**. CI hides this by reordering (`scripts/verify_retention_disposable.py:80-89`). The live dev DB necessarily received the phase4 SQL **out-of-band with no receipt**.

Additional drift:
- 2 repo filenames ≠ deployed versions (`20261031112127`→`20261105104752`; `20261103080000`→`20261103083932`).
- 2 **applied** migrations have **no repo file at all** (`20261105081249`, `20261105100916` — SQL parked in `docs/security/`).
- 20 of 72 migrations have **no deployment receipt**; the migration-integrity CI job byte-compares only **6 of 72** and asserts merely `>= 35` files exist.
- 3 `db/proposals/` files still carry *"DO NOT APPLY TO CASEPROOF-DEV"* headers yet **are** live.

### 2.6 Missing features (named in the docs, confirmed absent in code)

| Not built | Where the docs say so |
|---|---|
| Embedded DOCX/crop hyperlinks in the annotated DOCX | `docs/m4/F6_IMPLEMENTATION_ACCEPTANCE.md:27` |
| Claim-review path (claim → source link → human review → claim-coverage export) | `docs/CASEPROOF_FINAL_WORKFLOW_V4.md:128` |
| Organization-verified professional-name directory / second approver / fresh reauthentication | `docs/security/RELEASE_ACKNOWLEDGEMENT_PROVENANCE_PR204.md:7-9` |
| Real hosted MCP: deployed issuer, client consent registry, durable `HostContentGate` | `docs/m3/POSTGRES_HOSTED_MCP_OAUTH_ACCEPTANCE.md:26-28` |
| Statutory / Belgian art. 737 authority checking | `docs/CASEPROOF_DECISION_CATALOGUE_AUDIT_2026-11-10.md:17,33` |
| Desktop Microsoft Word host acceptance (LibreOffice insufficient) | `docs/pilot/P5_P6_ACCEPTANCE_MATRIX.md:29` |
| **All 16 SEC-01..16** pilot security gates | `docs/security/PILOT_DATA_SECURITY_GATE.md:17-32` |
| All of M5 (5 interviews, 2 observations, 3–5 dossiers, priced commitment) | `docs/ROADMAP.md:173-178` |
| Firm-controlled / offline packaging | `docs/ROADMAP.md:64` |
| **Frontend: P10 `/matters/:caseId/data`** retention/deletion disclosure | `frontend/BLUEPRINT.md` §17 |
| **Frontend: "run an explicit check"** — no UI, no `POST /dossier/checks`, no page-job progress | breaks §18 UF01 step G end-to-end |
| **Frontend: NL/FR i18n** — UI is English-only; no catalog, no framework | `frontend/BLUEPRINT.md` §1/§10 |
| Python CVE scanning (`pip-audit`/`safety` absent) | — |

### 2.7 What is *never exercised*

- `evals/` is **type-checked but never executed** in CI (`scripts/run_document_evaluation` has **0** workflow references). Default mode is `scripted_safety_only`; observed output is `status: blocked, proposals: 0, label_recall: 0.0` — the default eval measures the *safety rail*, not extraction quality.
- `scripts/validate_m0_independent_reviews.py` — **never invoked**.
- `tests/visual_gate_v2.py`, `tests/test_visual_dossier_api.py` — skip in CI (`CASEPROOF_VISUAL_EXECUTABLE` is never set).
- `infrastructure/telemetry/operations.py`, `infrastructure/supabase/multisource_readback.py` — unwired.
- `infrastructure/execution/postgres_jobs.py` — no live tables.
- `application/runtime/{worker,documents,pages}.py` — not production-mounted.
- `application/decision_ports.py`, `application/documents/finance.py`, `application/litigation/{model_notes,visual_calibration}.py`, `domains/disputes/docx_exhibit_page_policy.py` — **dead** (test-only).
- `packages/evidence_kernel/domain/ports.py` — **dead** (zero references repo-wide).
- `frontend/src/features/evidence/index.ts:2-20` — `PageImage`/`PageImageReader` declared, **zero implementations, zero consumers**.

---

## 3. Documentation vs. code — the drift is systematic

**Every stale statement points the same way: the docs lag the code. They never lead it.** The under-claims are concentrated in engineering progress; the over-claims are all in *status, completeness and readiness*.

### 3.1 Highest-risk stale statements

| Document | Claim | Reality |
|---|---|---|
| `docs/STATUS.md:105` | "M3 still lacks user-created matter intake, complete original page/crop browser viewer and applied correction. M4 has … not independently accepted corrected DOCX …" | **Every clause false** against merged code. It sits under "Historical baseline — 31 Oct 2026" but is the *only* M3/M4 sentence in the top half, and `ROADMAP.md:82` defers to STATUS.md as implementation truth. **Highest-risk stale line in the ledger.** |
| `docs/ROADMAP.md:93-94,155,166` | M3 needs browser viewer / correction / signed browser E2E; "Full M3 **OPEN**"; "full M4 … remains **OPEN**" | F1–F6 all merged and signed-accepted |
| `AGENTS.md:22`, `STATUS.md:316`, `CLAUDE.md:9` | branch protection "NOT verified" / "returned none" | ruleset **active** since 2026-10-22; issue #5 **closed** |
| `MEMORY.md:9` | "**Product:** ExceptionDesk, Belgian B2B invoice-versus-PO exceptions **first**. CaseProof dispute dossiers second." | **Directly contradicts ADR 0018/0019.** `MEMORY.md:10` baseline is 23 PRs behind; `:12` lists Storage / durable review / durable workers as "not yet implemented" — all exist. `AGENTS.md:3` tells every agent to read it first. **Most actively misleading document in the repo.** |
| `frontend/BLUEPRINT.md:284` | F6 M4 delivery = **"OPEN"** | shipped, signed browser run `41623751514` success, tree-identical to merge |
| `docs/STATUS.md:3` | newest entry 5 Nov | **13 PRs merged after it** (#194–#211): the entire rights ledger, release ack, paraphrase guard, blinded benchmark, source-identity hardening, duplicate-pinpoint fail-closed, claim candidates, statute parser — **zero** of them referenced |
| `docs/FEATURE_DELIVERY_MATRIX.md:3` | "AUTHORITATIVE implementation status: see STATUS.md" | both pointers resolve to something stale |
| `docs/CASEPROOF_AGENT_MASTER_TODO.md:4` | baseline `2a5420db` | **29 commits behind**; self-declared "operational entry point" (`:1145`) |
| `contracts/v2_operation_matrix.json:2,158` | "all /v2 routes stay disabled" | 66 live `/v2` routes; guard checks a file that never had one |
| `docs/m5/SEC-01-SEC-16.md` vs `docs/security/PILOT_DATA_SECURITY_GATE.md` | two SEC-01..16 registers | **incompatible ID spaces** (SEC-01 = "Matter authorization" vs "Threat model"); the m5 file is orphaned (0 inbound links) yet carries FAIL on SEC-09/10 |
| `docs/adr/` | — | **duplicate ADR 0020**, no index |
| `README.md:78` | "That workflow is **not built yet**" | F1–F6 shipped |
| `CLAUDE.md:11` | "`/v2` … remain unmounted" | 66 mounted |

### 3.2 Five competing "what is next" lists, none cross-linked

`ROADMAP.md` "Immediate delivery sequence" (31 Oct, not updated for F1–F6) · `CASEPROOF_AGENT_MASTER_TODO.md` (3 Nov, 29 commits stale) · root `AGENT_MASTER_TODO.md` (5 Nov, no inbound links) · `CASEPROOF_FINAL_WORKFLOW_V4.md` (10 Nov, **uncommitted**, "NOT IMPLEMENTED") · `CASEPROOF_DECISION_CATALOGUE_AUDIT_2026-11-10.md` (10 Nov, **uncommitted**, unlinked).

The two **newest and most specific** documents are the two an agent is least likely to find.

### 3.3 Documentation volume

`docs/` = **203 files / 1.52 MB**. The five authority docs alone = **~366 KB / 3 517 lines** — roughly 1 800 pages of prose for a product whose entire v1 surface is 66 API routes and 9 frontend features. `frontend/BLUEPRINT.md` (98 KB) is nearly as large as the three authority docs combined and is **not** in the authority set. 80+ lines exceed 400 characters; the longest is 1 275 chars — whole paragraphs fused into one line, hostile to diff and grep. Roughly **60–70 % of the authority set is archive or superseded plan**, but the "this is archived" labels sit at the top of files whose bodies are 5× the live section.

---

## 4. Security findings

### 4.1 P1 — live service-role credentials in a PUBLIC repo working tree, not gitignored

**Verified:** `gh repo view` → `{"isPrivate":false,"visibility":"PUBLIC"}`. `.gitignore` is 10 lines with **no `.env` entry**. `git check-ignore --no-index .env` → exit 1 (ignored by nothing). `git ls-files .env` → untracked. The file contains a populated `SUPABASE_SERVICE_ROLE_KEY` (`sb_secret_…`, bypasses RLS entirely) and a `SUPABASE_ACCESS_TOKEN` (`sbp_…`, project/org administration), plus an `OPENAI_API_KEY`. Same for `backend.log` / `frontend.log`.

Not committed — but one `git add .` away from publication. `MEMORY.md:17` states the rule this violates. **No secret value was printed during this audit.**

### 4.2 P1 — service-role key injected into 8 `pull_request`-triggered workflows

Eight workflows inject `secrets.CASEPROOF_DEV_AUTH_ADMIN_KEY` into a job that checks out and executes PR-controlled code, guarded by `github.head_ref == '<branch name>'` over **18 branch names that all still exist on the remote**. The guard is *name-based*, not *content-based*.

Mitigations that are real: `github.repository == 'haytamAroui/caseproof'` + `head.repo.full_name == github.repository` (fork-blocking), `environment: caseproof-dev`, `permissions: contents: read`, `persist-credentials: false` in 6 of 8.

This **directly contradicts the repo's own runbook**, `docs/m1/REAL_DEV_AUTH_RUNBOOK.md:22`: *"Never expose this key to frontend, PR workflows, logs or external services."*

**Mitigating compliance:** AGENTS.md's specific prohibition (no PostgreSQL admin DSN / CA PEM / role-bypass secret in CI) **is respected** — the only `PGPASSWORD` is the disposable `caseproof_ephemeral_ci` service-container password.

### 4.3 P2 — `required_approving_review_count: 0`

Ruleset 25660385 requires 2 status checks and **zero** human approvals, with `require_code_owner_review: false`. `CONSTITUTION.md` C13/C16 assume review enforcement. **Neither `AGENTS.md`, `STATUS.md` nor `CLAUDE.md` mentions this** — they instead carry a stale claim in the opposite direction.

### 4.4 P2 — three conflicting SEC-01..16 registers

See §3.1. A silent mis-mapping in a security gate: an auditor landing on the m5 file reads "SEC-01" as "Matter authorization" while the pilot gate means "Threat model and trust map".

### 4.5 P2 — receipt HMAC key shares custody with the Supabase admin key

`dossier_journey.py:213-219` derives the receipt key by domain separation from `CASEPROOF_DEV_AUTH_ADMIN_KEY` — the **same** secret as the Supabase admin key (`dev_live_entry.py:31`). Domain separation prevents cross-protocol reuse, but one compromise forges receipt attestations, and rotation breaks historical verification (no key ID in the manifest, no old-key path). Documented in ADR 0036:106-113 and **unresolved** — a pilot blocker.

The HMAC implementation itself is **correct**: domain-separated derivation, fail-closed on missing key (`dossier_journey.py:567-571`), constant-time `compare_digest` everywhere, payload-covered, publishable-key rejected.

### 4.6 P2 — `__import__("os")` + fixed `/tmp` append path

`apps/api/signed_document_parse.py:203`: `if __import__("os").environ.get("CASEPROOF_OCR_DIAGNOSTICS") == "YES": open("/tmp/caseproof-ocr-diagnostic.txt", "a")`. Unnecessary obfuscation plus a world-writable fixed path (symlink-attack target) in a diagnostic branch. Content is non-sensitive (`page=<n> reason=<code>`); impact low, pattern should change.

### 4.7 P2 — hosted MCP is a safe building block but **not safe to expose**

`hosted_mcp_app.py` is well built (origin allowlist, strict bearer, per-request `HostContentGate`, mirrored-header validation). But `supabase_oauth_mcp_verifier.py:92-94` sets the resource audience to a **locally asserted** value — *"effective local MCP policy bindings, NOT claims minted by Supabase"* — which is weaker than ADR 0024's wording implies. The block on plain Supabase session tokens is host-policy dependent, not cryptographic. **And `create_hosted_mcp_app` is imported only by a test — it is not wired into any entrypoint.** Correct posture today; must not be flipped to public without amending the ADR or cryptographically binding the audience.

### 4.8 Clean surfaces (verified, not assumed)

| Surface | Result |
|---|---|
| SQL injection | **0** f-string/`%`/`.format()` SQL across `apps/ application/ infrastructure/ scripts/ domains/ packages/` — all psycopg uses `%s` placeholders; `caseproof` schema not client-writable |
| Command injection | **0** `subprocess(shell=True)` repo-wide; argv lists only; executables allowlisted (`pdf_ocr.py:133`); sandbox `--network none`; scrubbed child env; RLIMIT_AS/CPU/FSIZE/NOFILE |
| XXE | `safe_docx_xml.py:21-24` `forbid_dtd`/`forbid_entities`/`forbid_external` + depth/node caps; `minidom` only reached after validation |
| Zip bomb / traversal | `file_boundary.py:18-40` (≤128 entries, ≤8 MiB, ≤2 MiB/entry, ≤80× ratio, no symlink/encrypted/`..`/absolute); `private_filesystem_byte_store.py` uses `O_NOFOLLOW|O_DIRECTORY` segment-by-segment |
| Path traversal on asset routes | `/word-assets/{asset_path:path}` and `/dev/clearbrief/{asset}` use **exact allowlists**, no normalization |
| Auth bypass | none found; `UnavailableBearerVerifier` → **503, never allow**; signature verified only by remote Auth, never locally |
| Tenant isolation | all 80 SECURITY DEFINER functions pin `search_path` (**0 gaps**); all 15 RLS policies scope by `auth.uid()` + membership + grant |
| `eval`/`exec`/`pickle`/`yaml.load` | **0 hits** in product code |
| `sys.path` manipulation | 1 hit, test-only |
| Prompt injection | model output may only become a separately-labelled object (`model_notes.py:37`); injection text stays inert data |
| Supply chain | `uv.lock` (279 KB) + `package-lock.json` (130 KB) committed; `uv run --locked` + `npm ci` everywhere; **0** `curl\|bash`; frontend deps **exactly pinned** (no `^`/`~`); 0 unpinned pip/npm |

---

## 5. Test suite — real, with a measurable weak tail

**2 322 Python test IDs** (1 360 `def test_` × parametrization) + **156 JS/TS** = **2 478** total. **4 skipped** (0.17 %), **0 xfail**, **0 `pytest.mark.skip`**, **0 `continue-on-error`**, **0 `if: false`** in CI.

| Category | Share | Notes |
|---|---|---|
| Real behaviour | **~78 %** | kernel/domain/application logic on real bytes |
| Testing the test-double | ~6 % | |
| **Tautological / grep-the-source** | **~7 %** | the weak tail |
| Meta / CI-shape / doc-shape | ~9 % | YAML assertions, JSON equality |

**~160 tests assert on literal source text** rather than behaviour — e.g. `test_p6_privacy_disclosure.py:8-15` (7 substring assertions on a `.tsx` file), `test_data_rights_enforcement.py:134-135` (greps `dev_live_entry.py`), `test_clearbrief_workspace.py:215-248` (**34** substring assertions on `workspace.js`), `test_architecture_freeze_v1.py:136` (the inert `/v2` guard). These pass if the string exists *anywhere* in the file, including in a comment.

**`tests/adversarial/` has exactly ONE file** (464 lines, 91 IDs, 15 hand-labelled oracle cases) despite being the security-critical folder. It is genuinely strong — metamorphic Unicode fuzz, stale-digest, hidden-contradiction, cross-tenant, chain-truncation, prompt-injection-as-inert-data — but **all against `InMemory*` implementations, never a real adapter**. No homoglyph/bidi/confusable attacks anywhere in the repo.

**Fixture reality (the single most important question):**
> **Only 2 binary document fixtures are committed** — `synthetic_invoice.pdf` (2 384 B, real PDF, 2 pages) and `synthetic_supplier.eml` (357 B). **Zero committed DOCX. Zero committed scanned images.**

All DOCX/PDF/scan bytes are **programmatically generated at test time** (`tests/fixtures/factory.py:37-181`, `visual_fidelity.py:26-79`, `dossier_journey.py:8-56`, `scripts/m0_real_format_fixtures.py:52-181`). The claim is **backed by real bytes**, but there is **no golden-binary regression corpus** — if a generator changes, the fixture changes with it.

Weakest layer: **`apps/worker` — 1 test file, 8 test IDs** for 3 modules including the lease/fence worker.

**Windows parity:** 48 of 186 test modules **cannot be collected** on Windows (POSIX-only `import resource`). No `windows-latest` matrix row exists. The repo is Linux-only in practice; the owner works on Windows.

---

## 6. Consolidated findings by severity

### P0 — must address now

| # | Finding | Evidence |
|---|---|---|
| **P0-1** | **Live service-role key + Supabase PAT + OpenAI key in an ungitignored `.env` inside a PUBLIC repo working tree.** Rotate all three; add `.env`, `.env.*`, `*.log` to `.gitignore`. | §4.1 — verified |
| **P0-2** | **Service-role credential injected into 8 `pull_request`-triggered workflows** gated only by branch name, with all 18 branches live. | §4.2 — verified |
| **P0-3** | **The `/v2` contract freeze guard is inert** — it checks `apps/api/main.py` (3 routes, never had `/v2`) while 66 `/v2` routes are mounted and the contract's global status string is false. | §4 of infra audit; `test_architecture_freeze_v1.py:136` — verified |
| **P0-4** | **`supabase/migrations/` cannot be replayed in filename order** — `_phase4_reference_decisions` is created only outside the migration set; 7 migrations depend on it. `supabase db push` fails. | §2.5 — verified |

### P1 — should address before any pilot

| # | Finding |
|---|---|
| **P1-1** | **No deployment target exists** for API, worker, or add-in. Nothing is deployable as written. |
| **P1-2** | **Live signed-browser acceptance never runs on `main`** — 22 workflows gated by `github.head_ref == '<branch>'`; 10 have 0 successes ever. |
| **P1-3** | **`required_approving_review_count: 0`** on an active ruleset; 23 of ~25 CI checks non-blocking. |
| **P1-4** | **Documentation lags the code by 13 merged PRs** and misstates the merge gate in 3 files. `STATUS.md` is the implementation-truth pointer and is stale. |
| **P1-5** | **`MEMORY.md` states the superseded finance-first product** and is a first-class required read. |
| **P1-6** | **Three conflicting SEC-01..16 registers.** |
| **P1-7** | **Receipt HMAC key shares custody with the Supabase admin key**; no rotation path (ADR 0036, unresolved). |
| **P1-8** | **33 of 72 API modules unreachable**; `apps/api/main.py` is a naming trap that misleads any reader about tenancy, auth and persistence. |
| **P1-9** | **All 16 SEC-01..16 pilot gates OPEN** — no independent security review, penetration test, incident plan, backup drill, or erasure proof exists. |

### P2 — quality / hygiene

| # | Finding |
|---|---|
| **P2-1** | `pydantic` is banned by `packages/evidence_kernel/AGENTS.md:20` and ADR 0008:28 but is **absent** from the kernel ban list (`check_architecture.py:11`). A `from pydantic import BaseModel` in the kernel passes CI green. Same for `starlette`, `psycopg`, `asyncpg`, `sqlite3`, `requests`, `httpx`, `boto3`, `subprocess`. |
| **P2-2** | **Dynamic-import bypass** — `getattr(importlib, "import_module")("fastapi")` and `sys.modules[...]` injection are **not detected**, a direct breach of `CONSTITUTION.md:38`. |
| **P2-3** | `domains/evidence_signals.py` + `domains/__init__.py` are **outside every `RULES` root** → never scanned. |
| **P2-4** | ~160 grep-the-source tests give false confidence; `tests/adversarial/` has one file; `apps/worker` has 8 test IDs. |
| **P2-5** | No committed binary DOCX/scan fixtures; no golden-byte regression corpus. |
| **P2-6** | Kernel has **no `py.typed`, no `__all__`, no packaging config, empty `domain/__init__.py`** — the "public kernel contracts" that C09-A:34 says need an ADR to change have **no automated guard**. (`contracts/architecture_baseline_v1.json` lists `independent_kernel_package` under `defer`, so this is a quality gap, not a contract violation.) |
| **P2-7** | `packages/evidence_kernel/domain/ports.py` is 100 % dead. |
| **P2-8** | Frontend: no `.gitattributes` → `npm run lint` and `npm run contracts:check` **fail on every Windows checkout** (CRLF vs Prettier LF). Verified: the generated TS is byte-identical; only line endings differ. |
| **P2-9** | Frontend: **NL/FR i18n is absent** — the UI is English-only despite §1/§10 declaring NL/FR/EN as the first-market set. |
| **P2-10** | Frontend: no "run an explicit check" UI → the §18 first-matter-and-check journey **cannot be completed by a user**. |
| **P2-11** | `frontend/BLUEPRINT.md` not updated for F6 (shipped, marked OPEN), the DOCX editor / native Word handoff, or the P0 paraphrase-guard panel — violating the blueprint's own §1 rule. |
| **P2-12** | `__import__("os")` + fixed `/tmp` append path in the OCR diagnostics branch. |
| **P2-13** | `docker/ocr-worker.Dockerfile` is the *production default* OCR image but is unpinned (no digest, no apt version pins, no `USER`, no `HEALTHCHECK`). |
| **P2-14** | `Pillow` is declared in `pyproject.toml` with no import found in source — unnecessary CVE surface. |
| **P2-15** | GitHub Actions are **tag-pinned, not SHA-pinned** — a mutable tag in 8 workflows that hold a service-role key. |
| **P2-16** | Python CVE scanning is absent (`pip-audit`/`safety` not in `pyproject.toml`). |
| **P2-17** | No per-migration rollback artifact for any of the 72 migrations (C11 requires rollback/recovery analysis). |
| **P2-18** | 2 applied migrations have no repo file; 20 of 72 have no receipt; the integrity CI gates only 6 of 72. |
| **P2-19** | Duplicate ADR `0020`; no ADR index. |
| **P2-20** | Two DOCX paths **disagree** on tracked changes — `engines.parse_docx` includes `w:ins` text with a warning; `docx_region_inventory` excludes such parts as `REVISION_STATE_UNRESOLVED`. |
| **P2-21** | Standalone PNG/JPEG originals are **accepted by Storage but never parsed** (`parse_bytes` has no image branch). |
| **P2-22** | OCR confidence is captured but **never calibrated** (`calibration_status: 'not_available'`, `probability: None`); `conf < 60` only triggers human review. |
| **P2-23** | `docs/adr/0025` names subprocessors as literally `"TBD"`. |

### Dead / unreachable inventory (for cleanup)

`apps/api`: 33 of 72 modules unreachable (incl. both Postgres `CaseAccessRepository` impls, all `authenticated_*`, `contracts_v2`, `requesty_extraction`, all `disposable_*`).
`application`: `decision_ports.py`, `documents/finance.py`, `litigation/model_notes.py`, `litigation/visual_calibration.py`, `runtime/{worker,documents,pages}.py` (unmounted), `review/memory.py` (demo only), `extraction/journal.py::MemoryJournal` (demo only).
`domains`: `construction/` (fully unreachable), `disputes/docx_exhibit_page_policy.py`.
`kernel`: `domain/ports.py`.
`infrastructure`: `persistence/m1_exhibit_memory.py`, `telemetry/operations.py`, `supabase/multisource_readback.py`, `execution/postgres_jobs.py` (no live schema).
`frontend`: `features/evidence/index.ts` port, `premium-audit.json` (stale absolute path), `scripts/p6-dependency-audit.mjs` (not wired to any npm script).
`apps/web`: `prototype/` (orphaned, unserved), `apps/word_addin/demo_app.py`.

---

## 7. Constitutional compliance

**COMPLIANT (20):** C01, C02, C03, C04, C05, C06, C07, C08, C09, C09-A, C10, C12, C14, C15, C17, C18, C19, C20, C21, C22, C23.
**PARTIAL (5):** C11 (no rollback artifacts), C13 (`required_approving_review_count: 0`), C16 (only 2 required checks; no release record artifact), C24 (`MEMORY.md` stale, `AGENTS.md` misstates the gate), C25 (code review not enforced).

The engineering discipline is genuinely high. The failures are **governance and operations**, not code logic.

---

## 8. Recommended sequence (customer-outcome-first)

**Week 1 — stop the bleeding (no product risk, immediate)**
1. Rotate `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ACCESS_TOKEN`, `OPENAI_API_KEY`; add `.env`, `.env.*`, `*.log` to `.gitignore`; delete the local `.env`/`*.log`. *(P0-1)*
2. Move all `CASEPROOF_DEV_AUTH_ADMIN_KEY` consumers to `workflow_dispatch`-only, or protect the `caseproof-dev` environment with required reviewers; delete the 18 stale remote branches; SHA-pin `actions/checkout`. *(P0-2)*
3. Fix the `/v2` freeze guard to assert against the *real* composition root (`litigation_development_app.py`) and restate the contract status accurately. *(P0-3)*
4. Add a `supabase/migrations/` entry that creates `_phase4_reference_decisions`, and make the CI replay run the set **in filename order**. *(P0-4)*

**Week 2 — make the truth match the code**
5. Refresh `STATUS.md` to the current head; correct `AGENTS.md`, `CLAUDE.md`, `ROADMAP.md`, `README.md`, `BLUEPRINT.md` (F6), and `MEMORY.md` on M3/M4/branch protection.
6. Collapse the 5 competing "next" lists into one; demote the other 4 to clearly-marked archives; add a `docs/adr/README.md` index and resolve the duplicate `0020`.
7. Designate one canonical SEC-01..16 register; rewrite the other two as cross-references.
8. Set `required_approving_review_count: 1` and add the remaining CI workflows as required checks.

**Weeks 3–4 — turn green CI into real coverage**
9. Replace the 22 `head_ref == '<branch>'` gates with environment/scope-based gating so live acceptance **runs on `main`**; add `main` to the required checks.
10. Wire `evals/` into CI as an executed gate (not just mypy); execute `validate_m0_independent_reviews`.
11. Commit a golden binary fixture set (real DOCX with Word-authored revisions, a real scanned/fax PDF, a multi-generation photocopy) to close the no-golden-corpus gap.

**Weeks 5+ — build the missing product**
12. **Build the deployment target** (API image + worker supervisor + TLS) — nothing exists today.
13. Implement the three named missing features: embedded DOCX/crop hyperlinks, the claim-review path, and the organization-verified approver directory.
14. Frontend: add "run an explicit check" (closes the §18 journey), the P10 data-disclosure page, and an NL/FR catalog.
15. Derive a dedicated receipt key (`CASEPROOF_RECEIPT_KEY`) with a manifest key ID and retained verification keys (ADR 0036).

**Do not do:** add a second vertical, a DomainPack, or a generic EvidenceState — ADR 0018/0019 forbid it without a superseding ADR and evidence-led customer pull.

---

## 9. Method & limitations

**Executed:** AST route enumeration of the real FastAPI composition (95 mounted routes, 66 `/v2`, 21 `/dev`); exhaustive import scan of `packages/evidence_kernel`; `check_architecture.py` RULES-root coverage check; `pytest --collect-only` (2 322 IDs); `gh run list` across 59 workflows; `gh api repos/…/rulesets`; `git check-ignore` / `git ls-files` on `.env`; `grep` for the migration table-creation site; STATIC verification of the `_phase4_reference_decisions` dependency.

**Could not verify:** live `caseproof-dev` catalog (Supabase MCP not connected in this session — every LIVE/DEPLOYED claim is read from the repo's own receipts); GitHub environment protection rules; actual retention/backup/TLS behaviour (provider-side); `apps/web/review/` runtime (Linux-gated, could not execute on this host); any real Word-host behaviour; whether the 33 unmounted modules were intended for later wiring or are obsolete; whether the 18 stale remote branches carry branch-level protection.

**CI reality at audit time:** `main` = 24 workflow runs, 23 success, 1 skipped, 0 failed. The single skip is the `workflow_dispatch`-only one-click E2E.

**No file was modified by this audit.**
