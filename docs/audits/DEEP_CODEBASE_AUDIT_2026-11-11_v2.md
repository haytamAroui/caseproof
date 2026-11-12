# CaseProof — Deep Codebase Audit v2 (2026-11-11)

**Supersedes:** `docs/audits/DEEP_CODEBASE_AUDIT_2026-11-11.md` (v1, retained unchanged for audit trail).
**Snapshot:** local `main` = `af438c3771add91f3b4b83409d464a0c05031670` (PR #209) · `origin/main` = `e4195a7c` (PR #211).
**Method:** read-only static audit across every layer + independent measurement (FastAPI route enumeration, AST import scans, `pytest --collect-only`, `gh run list`, `gh api rulesets`, `git check-ignore`). **No repository file was modified by this audit.**

> **Artifact type.** This is a **codebase assessment**, not a product assessment. It can establish what code exists, what is connected, and what the automated gates actually executed. It **cannot** establish production security, independent legal-document accuracy, or reviewer effectiveness. Those are separate artifacts requiring separate evidence — the same separation the project's own constitution draws between engineering completion, independent validation and human review.

**Scope covered:** 1 191 files / 150 378 lines (499 Python · 275 Markdown · 106 SQL · 95 TS · 25 TSX · 41 JSON).

---

## 0. Summary

This is a **serious, unusually disciplined codebase with a serious documentation and operational gap**. The engineering is largely real: a pure evidence kernel with 309 passing tests, fail-closed hexagonal layering, real Supabase Auth + RLS + Storage transports, real PDF/DOCX/OCR parsers, a React 19 frontend implementing nearly all of its blueprint, and 2 322 Python + 156 JS test IDs.

What is not real: **there is no production deployment target**, **one third of the API codebase is unreachable**, **the documentation lags the code by 13 merged PRs and misstates the merge gate**, **the contract-freeze guard that should protect the architecture checks the wrong file**, and **live service-role credentials sit ungitignored in a public repo working tree**.

The product is genuinely further along than its own status ledger says, and genuinely further from a pilot than the green CI badge suggests.

---

## 1. Corrections applied in v2

| # | v1 statement | v2 corrected | Reason |
|---|---|---|---|
| 1 | "no authentication bypass, cross-tenant vulnerability or injection vulnerability exists anywhere" | "**the checks performed did not surface** these classes; static analysis cannot establish absence" | Static review cannot prove absence. Overstated the evidence. |
| 2 | "COMPLIANT (20)" | "**COMPLIANT (21)** of 26 enforceable clauses (C01–C25 plus C09-A)" | Arithmetic error; 21 clauses were listed. |
| 3 | "3 517 lines / ~366 KB / roughly 1 800 pages" | "**3 580 lines / 400 KB / ~80–136 pages**" | Three wrong numbers in one sentence. The volume observation stands; the inflation did not. |
| 4 | "Nothing in these four apps is deployable as written" | "**runnable locally, not productionizable**" | "Deployable" conflated runnability with productionization. |
| 5 | "Dead code" (flat label) | Three-way taxonomy: **genuinely dead / intentionally dormant / unreachable-but-plausibly-future** | Static reachability cannot establish obsolescence. Deleting on that basis could discard legitimate capability. |
| 6 | "production-grade" (as a code-quality descriptor) | "**mature domain logic, in-memory storage**" | "Production-grade" collided with "production deployment". |
| 7 | Inert `/v2` guard ranked as a security P0 | Reclassified **Truthfulness P0**, with the security-relevant defence layer identified | The 6 prohibited operations have a second independent defence (permission grants + `CaseAccessService.authorize`); the failure is a lying machine-read artifact, not a directly exploitable route. |
| 8 | Windows collection failures "48 of 186 modules" | **42 modules error at collection** (measured directly: `pytest --co` → `42 errors … 1941 tests collected`) | Sub-agent figure not independently reproducible; own measurement used. |
| 9 | Dead-code / kernel hygiene in the same severity band as pilot blockers | Separated: pilot blockers elevated above hygiene | Pilot risk ≠ code hygiene. |
| 10 | *(new)* | Added P1-9 `caseproof_m1_reader` absent; P1-11 reviewer journey incomplete; DOCX tracked-changes divergence; PNG/JPEG accepted-but-unparsed; kernel public surface unfrozen; `evals/` never executed; Storyteller absent from `BLUEPRINT.md`; competitor-name leakage risk | Findings surfaced during v1 review that were under-ranked or omitted. |

---

## 2. What is inside the code

### 2.1 `packages/evidence_kernel/` — 2 385 LOC, 14 files — the strongest asset in the repo

Twelve domain modules, all pure stdlib Python. **Zero forbidden imports** (verified exhaustively across every import in every file). No `TODO`/`NotImplementedError`/stub markers.

| Module | Real responsibility | Grade |
|---|---|---|
| `source_versions.py` | Immutable source bytes + versioned derived representations | mature logic, in-memory storage |
| `anchors.py` | Typed, representation-bound citation locators (TextSpan / PdfRegion / SheetRange / StructuredField) | mature |
| `fidelity.py` | Independent citation resolution + exact content fidelity, 4-way outcome | mature |
| `finding_links.py` | Revision-bound finding↔evidence links; recomputes fidelity server-side | mature |
| `grounding.py` | Policy-versioned, fail-closed eligibility gate with optimistic re-read | mature |
| `coverage.py` (596) | Versioned issue/source coverage inventory; anti-cherry-picking link check | mature |
| `provenance.py` / `provenance_binding.py` | Deterministic per-tenant hash chain + read-only bridge | mature |
| `evidence.py` / `workflow.py` / `store.py` | v1 legacy compatibility surface | reference |
| `ports.py` | `EvidenceRepository` Protocol | **genuinely dead — one grep hit repo-wide** |

`Decimal` is used for all PDF geometry; **zero `float`** in the entire kernel.

### 2.2 `domains/` — 1 096 LOC, 15 files

- **`domains/disputes/`** (the ACTIVE product). `exhibit_identity` resolves identity only against a CONFIRMED_COMPLETE inventory and fails closed to `NOT_ASSESSED` / `NOT_IN_INVENTORY` / `AMBIGUOUS` / `SOURCE_MISSING`. `dossier_verification` computes four independent dimensions with `"support": "not_assessed"` hard-coded (`dossier_verification.py:172`). `multisource_manifest.assert_authorized` raises if **any** source is inaccessible. `reference_detection` is an NL/FR regex (`stuk`/`stukken`/`pièce`/`pièces` + `bis`/`ter`). `docx_exhibit_page_policy` is a **dormant parallel copy** of a rule implemented inline at `application/litigation/library.py:58-63`.
- **`domains/finance/`** — legacy ExceptionDesk. **Zero litigation code imports it.** Compatibility per ADR 0018/0019.
- **`domains/construction/`** — **genuinely unreachable.** Only tests, evals and one demo script reference it.
- **`domains/evidence_signals.py`** — sits at `domains/` root, **outside every `RULES` root** in `scripts/check_architecture.py` → never scanned by the boundary checker.

### 2.3 `application/` — 5 180 LOC, 49 files

Clean separation: `application/` holds pure policy + Protocol ports; `apps/api` holds identity, transport and persistence. No meaningful duplication.

`application/litigation/` (24 modules) carries the active product logic. `application/extraction/pipeline.py` (693) is a **finance-era LLM pipeline and is not on the litigation path** — the live dossier path uses only deterministic components; **no LLM produces a dossier finding**. `application/runtime/{worker,documents,pages}.py` are mature but **unmounted**. `application/documents/file_boundary.py` is a genuinely strong ASVS V5 preflight (traversal, symlinks, encryption, zip-bomb ratio, absolute paths).

### 2.4 `infrastructure/` — 3 314 LOC, 27 files

All parsers are **real**. `pypdf` text layer; `zipfile` + `defusedxml` DOCX including real `w:ins`/`w:del` tracked changes; poppler + tesseract OCR inside a `--network none` Docker/unshare sandbox; dual-view PDF visual fidelity; OOXML structured editing; DOCX export. Every failure mode raises a typed refusal; `OCRUnavailable` is recorded as a *state*, never as success.

`persistence/m1_exhibit_memory.py` is a **genuinely dead** test fixture. `execution/postgres_jobs.py` is real SQL against tables that **have no live migration**. `telemetry/operations.py` and `supabase/multisource_readback.py` are **dormant** — implemented and unit-tested, never wired.

### 2.5 `apps/` — 18 244 LOC, 116 files

| App | Mounted routes | Verdict |
|---|---|---|
| `apps/api` (72 files) | **95** (66 `/v2`, 21 `/dev`, rest static) | substantially real, Supabase-backed, **loopback-pinned** |
| `apps/worker` (4 files) | 0 | **231 LOC, one job type, one-shot CLI, no daemon** |
| `apps/web` (10 files) | 0 (served by API) | ClearBrief = real UI on the real API; `review/` = Linux-only; `prototype/` = orphaned |
| `apps/word_addin` (30 files) | 0 (client) | real Office.js add-in, real PKCE/OAuth, read-only, **no host ever tested** |

**Structural fact:** `apps/api/main.py` is **not the application**. It is an 89-line dev demo with a caller-controlled `X-Tenant-Id` header (`main.py:58-62`) and an in-memory store. The real app is `apps/api/litigation_development_app.py` via `apps/api/dev_live_entry.py`. **33 of 72 API modules are unreachable from any entry point** — including both Postgres `CaseAccessRepository` implementations, the whole `authenticated_*` layer, `contracts_v2`, `requesty_extraction` and every `disposable_*` module.

### 2.6 `frontend/` — 147 files, ~19 k lines — the most complete part of the product

Vite 8.3.5 + React 19.3.1 + strict TS 6.0.3 + Router 8.5.1 + TanStack Query 5. **Zero TODO/FIXME/mocks in product source.** Every response is AJV-validated then semantically re-checked; unknown enum states fail closed. 107 vitest + ~55 Playwright tests, all route-intercepted with synthetic fixtures.

### 2.7 `supabase/migrations/` — 72 files, 8 996 SQL lines · `db/proposals/` — 28 files · `contracts/` — 5 files

All 80 `SECURITY DEFINER` functions pin `search_path` (0 gaps). All 15 RLS policies scope by `auth.uid()` + active membership + matter grant. Bucket `caseproof-originals-dev` is private (20 MiB).

### 2.8 `evals/` — 4 files + 3 corpus JSON (v1 14 cases, v2 19, v3 37)

NL/FR/EN/mixed — **no German**. `label_status: author_supplied_unadjudicated`, `legal_validation: false`, `independent_gold: false`.

---

## 3. What is NOT built, not wired, or not proven

### 3.1 Deployment — runnable locally, **not productionizable**

- No Dockerfile for the API or worker, no compose, no k8s/Helm/systemd manifest, no `[project.scripts]` entry. `docker/` is **9 lines total**: an OCR tool image and a test image.
- `apps/api` is loopback-pinned by middleware (`litigation_development_app.py:215-219` → 403 `loopback_only`).
- `apps/worker` is a one-shot CLI — **no supervisor, no daemon, no scheduling**. OCR only advances when a human runs `python -m apps.worker.signed_page_worker --case … --job …` with a bearer in `CASEPROOF_WORKER_BEARER` (env var, contradicting the module's own "no stored bearer" docstring).
- `apps/word_addin` needs `npm run build` (`dist/live-auth.js` is gitignored) **and** a trusted TLS cert.
- The stack is **Linux-only by construction**: `infrastructure/parsers/pdf_ocr.py:13` and `worker.py:7` do an unconditional POSIX-only `import resource`; `parsers/limited.py:27` hard-fails off Linux.

### 3.2 CI reality — the live acceptance family never runs

| Workflow | Last 20 runs |
|---|---|
| `review-f6-live.yml` | **skipped × 20** |
| `review-f4-live.yml` | **skipped × 20** |
| `intake-f3-live.yml` | **skipped × 20** |
| `pr204-signed-release-ack.yml` | **skipped × 20** |
| `m1-m2-one-click-e2e.yml` | **skipped × 20** |

The gate is `if: github.head_ref == '<branch name>'` — a *branch name*, not an environment or a scope. **22 workflows** use this pattern. The result: **`main` has no live signed-browser verification at all**, and the gate evaporates the moment the branch is deleted. This is stated in `docs/security/DATA_RIGHTS_ENFORCEMENT_ROUTE_AUDIT.md:50-53` and **nowhere** in `AGENTS.md`, `STATUS.md` or `ROADMAP.md`.

Of 59 workflows: **24 have ≥1 success**, **10 only ever skip**, **23–25 have zero runs ever**.

### 3.3 The merge gate is two checks and zero human review

Live API (`gh api repos/haytamAroui/caseproof/rulesets`) confirms ruleset **25660385 "Protect main"** is `enforcement: active`, `current_user_can_bypass: never`, requiring exactly **2** status checks (`architecture`, `Disposable PostgreSQL concurrency and audit regression`) and **`required_approving_review_count: 0`**.

> **`AGENTS.md:22`, `docs/STATUS.md:316` and `CLAUDE.md:9` all state that branch protection is "NOT verified" / "returned none" / "read was 403".** Stale: the ruleset was created **2026-10-22T19:40** and issue #5 is **CLOSED**. The 404 on `/branches/main/protection` is because protection is via *ruleset*, not the legacy endpoint — exactly what the docs misdiagnosed.

The real residual is different and undocumented: **no human code review is required**, and 23 of ~25 CI checks are non-blocking.

### 3.4 The `/v2` contract-freeze guard checks the wrong file

```python
# tests/test_architecture_freeze_v1.py:136
assert '"/v2/' not in (ROOT / "apps/api/main.py").read_text()
```

`apps/api/main.py` contains only `/health`, `/v1/claims`, `/v1/claims/{claim_id}` — it has **never** had a `/v2` route, so the assertion **cannot fail**. Meanwhile `contracts/v2_operation_matrix.json:2` claims `"status": "typed_contract_only_all_v2_routes_disabled"` and `:158` "all /v2 routes stay disabled", while the shipped app serves **66 mounted `/v2` routes across 63 path templates** (measured by instantiating `create_litigation_development_app()`).

**Severity note (v2):** this is a **truthfulness** failure, not a directly exploitable one. The 6 matrix operations have a second independent defence — they are not in `contracts/action_catalog.v1.json`'s installed set, and `CaseAccessService.authorize` (`apps/api/access_control.py:246-257`) requires an installed action. The failure is that a **machine-read artifact asserts a false state**, and downstream agents will read it. Correct fix: assert **those 6 named operations** are absent from the real composition root — not a blanket ban on legitimate `/v2` routes.

### 3.5 The migration set cannot be replayed in filename order

`caseproof._phase4_reference_decisions` is created **only** in `supabase/phase4_reviewed/caseproof_phase4_signed_reference_review.sql:2`. **No file under `supabase/migrations/` creates it**, yet 7 migrations / 20 references depend on it — including a DDL trigger (`20261030155817_matter_retention.sql:94`) and a PL/pgSQL `%rowtype` validated at function-creation time (`20261030161844_complete_dossier_journey.sql:32`).

`supabase db push` against the repo directory **fails**. CI hides this by reordering (`scripts/verify_retention_disposable.py:80-89`). The live dev DB necessarily received the phase4 SQL **out-of-band with no receipt**.

Additional drift: 2 repo filenames ≠ deployed versions (`20261031112127`→`20261105104752`; `20261103080000`→`20261103083932`); 2 **applied** migrations have **no repo file** (`20261105081249`, `20261105100916` — SQL parked in `docs/security/`); **20 of 72** have no deployment receipt; the migration-integrity CI job byte-compares only **6 of 72** and asserts merely `>= 35` files exist; 3 `db/proposals/` files carry *"DO NOT APPLY TO CASEPROOF-DEV"* headers yet **are** live.

### 3.6 Named missing capabilities

| Not built | Source |
|---|---|
| Embedded DOCX/crop hyperlinks in the annotated DOCX | `docs/m4/F6_IMPLEMENTATION_ACCEPTANCE.md:27` |
| Claim-review path (claim → source link → human review → coverage export) | `docs/CASEPROOF_FINAL_WORKFLOW_V4.md:128` |
| Organization-verified professional-name directory / second approver | `docs/security/RELEASE_ACKNOWLEDGEMENT_PROVENANCE_PR204.md:7-9` |
| Real hosted MCP: deployed issuer, consent registry, durable `HostContentGate` | `docs/m3/POSTGRES_HOSTED_MCP_OAUTH_ACCEPTANCE.md:26-28` |
| Statutory / Belgian art. 737 authority checking | `docs/CASEPROOF_DECISION_CATALOGUE_AUDIT_2026-11-10.md:17,33` |
| Desktop Microsoft Word host acceptance | `docs/pilot/P5_P6_ACCEPTANCE_MATRIX.md:29` |
| **`caseproof_m1_reader` DB role** — 0 hits in `supabase/migrations/` and `db/proposals/`; `signed_private_matter_reader.py:108-146` asserts it exists; `docs/m1/LIVE_DEV_PRIVATE_MIGRATION_RECEIPT_2026-10-27.md:15,26` records it as absent and names provisioning as the next action | blocks the least-privilege runtime (issue #37) and gates SEC-04 |
| **All 16 SEC-01..16** pilot security gates | `docs/security/PILOT_DATA_SECURITY_GATE.md:17-32` |
| All of M5 (5 interviews, 2 observations, 3–5 dossiers, priced commitment) | `docs/ROADMAP.md:173-178` |
| Firm-controlled / offline packaging | `docs/ROADMAP.md:64` |
| **Frontend P10** `/matters/:caseId/data` disclosure page | `frontend/BLUEPRINT.md` §17 |
| **Frontend "run an explicit check"** — no UI, no `POST /dossier/checks`, no job progress → §18 journey not completable by a user | `frontend/BLUEPRINT.md` §18 |
| **Frontend NL/FR i18n** — UI is English-only; no catalog, no framework | `frontend/BLUEPRINT.md` §1/§10 |
| **Approved pilot capacity envelope** — `"approval": "development_only_not_pilot_approved"` | `application/capacity_envelope.py:21` |
| Python CVE scanning (`pip-audit`/`safety` absent) | — |

### 3.7 Never exercised

- `evals/` is **type-checked but never executed** in CI. Verified: `scripts/run_topology_comparison.py` appears only as a **mypy argument** (`kernel-boundary.yml:65`); `scripts/run_document_evaluation` has **0** workflow references — while the corpus *validator* runs in 3 places. Default mode is `scripted_safety_only`; observed output `status: blocked, proposals: 0, label_recall: 0.0`. **The default evaluation measures the safety rail, not extraction quality.**
- `scripts/validate_m0_independent_reviews.py` — **never invoked**.
- `tests/visual_gate_v2.py`, `tests/test_visual_dossier_api.py` — skip in CI (`CASEPROOF_VISUAL_EXECUTABLE` never set).
- `infrastructure/telemetry/operations.py`, `infrastructure/supabase/multisource_readback.py` — dormant.
- `infrastructure/execution/postgres_jobs.py` — no live tables.
- `application/runtime/{worker,documents,pages}.py` — unmounted.
- `application/decision_ports.py`, `application/documents/finance.py`, `application/litigation/{model_notes,visual_calibration}.py`, `domains/disputes/docx_exhibit_page_policy.py` — genuinely dead (test-only).
- `packages/evidence_kernel/domain/ports.py` — genuinely dead.
- `frontend/src/features/evidence/index.ts:2-20` — `PageImage`/`PageImageReader` declared, **zero implementations, zero consumers**.

---

## 4. Documentation vs. code

**Every stale statement points the same way: the docs lag the code. They never lead it.** Under-claims concentrate in engineering progress; over-claims concentrate in *status, completeness and readiness*.

### 4.1 Highest-risk stale statements

| Document | Claim | Reality |
|---|---|---|
| `docs/STATUS.md:105` | "M3 still lacks user-created matter intake, complete original page/crop browser viewer and applied correction. M4 has … not independently accepted corrected DOCX …" | **False in every clause.** Under "Historical baseline — 31 Oct 2026" but the *only* M3/M4 sentence in the top half; `ROADMAP.md:82` defers to STATUS.md as implementation truth. **Highest-risk stale line.** |
| `docs/ROADMAP.md:93-94,155,166` | M3 needs browser viewer / correction / signed E2E; "Full M3 **OPEN**"; "full M4 … remains **OPEN**" | F1–F6 merged and signed-accepted |
| `AGENTS.md:22`, `STATUS.md:316`, `CLAUDE.md:9` | branch protection unverified | ruleset **active** since 2026-10-22; issue #5 **closed** |
| `MEMORY.md:9` | "**Product:** ExceptionDesk, Belgian B2B invoice-versus-PO exceptions **first**." | **Contradicts ADR 0018/0019.** `:10` baseline 23 PRs behind; `:12` lists Storage / durable review / durable workers as "not yet implemented" — all exist. `AGENTS.md:3` tells every agent to read it first. **Most actively misleading document.** |
| `frontend/BLUEPRINT.md:284` | F6 M4 delivery = **"OPEN"** | shipped; signed browser run `41623751514` success, tree-identical to merge |
| `docs/STATUS.md:3` | newest entry 5 Nov | **13 PRs merged after it** (#194–#211) — entire rights ledger, release ack, paraphrase guard, blinded benchmark, source-identity hardening, duplicate-pinpoint fail-closed, claim candidates, statute parser: **zero** referenced |
| `docs/FEATURE_DELIVERY_MATRIX.md:3` | "AUTHORITATIVE implementation status: see STATUS.md" | both pointers resolve to something stale |
| `docs/CASEPROOF_AGENT_MASTER_TODO.md:4` | baseline `2a5420db` | **29 commits behind**; self-declared "operational entry point" (`:1145`) |
| `contracts/v2_operation_matrix.json:2,158` | "all /v2 routes stay disabled" | 66 live `/v2` routes; guard checks a file that never had one |
| `docs/m5/SEC-01-SEC-16.md` vs `docs/security/PILOT_DATA_SECURITY_GATE.md` | two SEC-01..16 registers | **incompatible ID spaces** (SEC-01 = "Matter authorization" vs "Threat model"); m5 file orphaned (0 inbound links) yet carries FAIL on SEC-09/10 |
| `docs/adr/` | — | **duplicate ADR 0020**, no index |
| `README.md:78` | "That workflow is **not built yet**" | F1–F6 shipped |
| `CLAUDE.md:11` | "`/v2` … remain unmounted" | 66 mounted |

### 4.2 "Storyteller" is not an approved design

`frontend/BLUEPRINT.md` contains **0 occurrences** of "Storyteller" or "cockpit", despite §1 declaring itself the single maintained UI authority. `docs/STORYTELLER_DESIGN_AUDIT.md` exists (12 526 bytes) but is referenced from **none** of `AGENTS.md`/`CLAUDE.md`/`MEMORY.md`. Any roadmap or phase that treats "Storyteller" as approved is asserting something the authority document does not record. Decide: adopt into the blueprint, or drop the term.

### 4.3 Five competing "what is next" lists

| Document | Lines | Tracked | Pointer status |
|---|---|---|---|
| `docs/ROADMAP.md` "Immediate delivery sequence" | 288 | yes | named authoritative by `AGENTS.md:5`; **not updated for F1–F6** |
| `docs/CASEPROOF_AGENT_MASTER_TODO.md` | 1 175 | yes | self-declared "operational entry point"; **29 commits stale** |
| `AGENT_MASTER_TODO.md` (root) | 83 | yes | **no inbound links from `docs/`**; duplicates the docs TODO |
| `docs/CASEPROOF_FINAL_WORKFLOW_V4.md` | 560 | yes (modified) | self-declared "NOT IMPLEMENTED"; conflicts with ROADMAP |
| `docs/CASEPROOF_DECISION_CATALOGUE_AUDIT_2026-11-10.md` | 43 | **no (untracked)** | newest and most specific; unlinked from every plan |

### 4.4 Documentation volume

The five authority docs total **3 580 lines / 400 KB** — approximately **80–136 printed pages** depending on rendering. `docs/` overall is **203 files / 1.52 MB**. `frontend/BLUEPRINT.md` (98 KB) is nearly as large as the three authority docs combined and is **not** in the authority set. 80+ lines exceed 400 characters; the longest is 1 275 chars — whole paragraphs fused into one line, hostile to diff and grep. Roughly **60–70 % of the authority set is archive or superseded plan**, but the "this is archived" labels sit at the top of files whose bodies are 5× the live section.

---

## 5. Security findings

> **Evidentiary limit.** Every result in this section comes from static analysis, source review, workflow-YAML review, migration-DDL review and live GitHub API queries. **No dynamic or adversarial testing against a running deployment was performed**, and no live `caseproof-dev` query was possible (Supabase MCP not connected in the audit environment). These checks **did not surface** the vulnerability classes below; that is **not** the same as establishing their absence. Dynamic, adversarial and independent penetration testing remain required (SEC-12).

### 5.1 P1 — live service-role credentials in a PUBLIC repo working tree, not gitignored

**Verified:** `gh repo view` → `{"isPrivate":false,"visibility":"PUBLIC"}`. `.gitignore` is 10 lines with **no `.env` entry**. `git check-ignore --no-index .env` → exit 1 (ignored by nothing). `git ls-files .env` → untracked. The file contains a populated `SUPABASE_SERVICE_ROLE_KEY` (`sb_secret_…`, bypasses RLS entirely) and a `SUPABASE_ACCESS_TOKEN` (`sbp_…`, project/org administration), plus an `OPENAI_API_KEY`. Same for `backend.log` / `frontend.log`.

Not committed — but one `git add .` from publication. `MEMORY.md:17` states the rule this violates. **No secret value was printed during this audit.**

### 5.2 P1 — service-role key injected into 8 `pull_request`-triggered workflows

Eight workflows inject `secrets.CASEPROOF_DEV_AUTH_ADMIN_KEY` into a job that checks out and executes PR-controlled code, guarded by `github.head_ref == '<branch name>'` over **18 branch names that all still exist on the remote**. The guard is *name-based*, not *content-based*.

Mitigations that are real: `github.repository == 'haytamAroui/caseproof'` + `head.repo.full_name == github.repository` (fork-blocking), `environment: caseproof-dev`, `permissions: contents: read`, `persist-credentials: false` in 6 of 8.

This **contradicts the repo's own runbook**, `docs/m1/REAL_DEV_AUTH_RUNBOOK.md:22`: *"Never expose this key to frontend, PR workflows, logs or external services."*

**Mitigating compliance:** AGENTS.md's specific prohibition (no PostgreSQL admin DSN / CA PEM / role-bypass secret in CI) **is respected** — the only `PGPASSWORD` is the disposable `caseproof_ephemeral_ci` service-container password.

### 5.3 CORRECTED — `required_approving_review_count: 0` is the adopted solo-maintainer policy, not a defect

**This section previously reported the zero-approval count as a finding and recommended changing it. That was wrong.** `docs/engineering/merge-policy.md` (adopted 23 October 2026) states that an independent approving reviewer is **not mandatory while this is a solo-maintainer repository**, because GitHub disallows approving one's own pull request; requiring one would lock the sole maintainer out of merging their own work. The policy also prescribes exactly the current settings: require `architecture` and `Disposable PostgreSQL concurrency and audit regression`, do not require approving reviews during the solo-maintainer phase, keep pull requests required, prevent force-push and deletion. Ruleset 25660385 matches that policy exactly.

The policy states the trigger for changing it: require independent approval **when additional maintainers join, when deployment or security risk warrants it, or before handling production customer data**. None of those conditions holds yet, so this is a future trigger, not a current finding.

**Residual, correctly stated:** `CONSTITUTION.md` C13 says *human approval is required* for schema-breaking changes, auth/RLS changes and production releases. The solo-maintainer policy satisfies that through the documented self-review plus mandatory CI, and it says so explicitly rather than silently. The genuine gap is narrower than the approval count: **23 of ~25 CI workflows are non-blocking**, so most of the acceptance suite can fail without preventing a merge. That is a coverage question, not an approval question, and it is the part worth attention.

### 5.4 P2 — three conflicting SEC-01..16 registers

See §4.1. A silent mis-mapping in a security gate: an auditor landing on the m5 file reads "SEC-01" as "Matter authorization" while the pilot gate means "Threat model and trust map".

### 5.5 P2 — receipt HMAC key shares custody with the Supabase admin key

`dossier_journey.py:213-219` derives the receipt key by domain separation from `CASEPROOF_DEV_AUTH_ADMIN_KEY` — the **same** secret as the Supabase admin key (`dev_live_entry.py:31`). Domain separation prevents cross-protocol reuse, but one compromise forges receipt attestations, and rotation breaks historical verification (no key ID in the manifest, no old-key path). Documented in ADR 0036:106-113 and **unresolved** — a pilot blocker.

The HMAC implementation itself is **correct**: domain-separated derivation, fail-closed on missing key (`dossier_journey.py:567-571`), constant-time `compare_digest` everywhere, payload-covered, publishable-key rejected.

### 5.6 P2 — hosted MCP is a safe building block but **not safe to expose**

`hosted_mcp_app.py` is well built (origin allowlist, strict bearer, per-request `HostContentGate`, mirrored-header validation). But `supabase_oauth_mcp_verifier.py:92-94` sets the resource audience to a **locally asserted** value — *"effective local MCP policy bindings, NOT claims minted by Supabase"* — weaker than ADR 0024's wording implies. The block on plain Supabase session tokens is host-policy dependent, not cryptographic. **And `create_hosted_mcp_app` is imported only by a test — it is not wired into any entrypoint.** Correct posture today; must not be flipped to public without amending the ADR or cryptographically binding the audience.

### 5.7 P3 — `__import__("os")` + fixed `/tmp` append path

`apps/api/signed_document_parse.py:203`: `if __import__("os").environ.get("CASEPROOF_OCR_DIAGNOSTICS") == "YES": open("/tmp/caseproof-ocr-diagnostic.txt", "a")`. Unnecessary obfuscation plus a world-writable fixed path (symlink-attack target) in a diagnostic branch. Content is non-sensitive (`page=<n> reason=<code>`); impact low, pattern should change.

### 5.8 Surfaces where the checks found nothing

Reported as "not surfaced by the checks performed" — see the evidentiary limit above.

| Surface | Result |
|---|---|
| SQL injection | **0** f-string/`%`/`.format()` SQL across `apps/ application/ infrastructure/ scripts/ domains/ packages/` — all psycopg uses `%s` placeholders; `caseproof` schema not client-writable |
| Command injection | **0** `subprocess(shell=True)` repo-wide; argv lists only; executables allowlisted (`pdf_ocr.py:133`); sandbox `--network none`; scrubbed child env; RLIMIT_AS/CPU/FSIZE/NOFILE |
| XXE | `safe_docx_xml.py:21-24` `forbid_dtd`/`forbid_entities`/`forbid_external` + depth/node caps; `minidom` only reached after validation |
| Zip bomb / traversal | `file_boundary.py:18-40` (≤128 entries, ≤8 MiB, ≤2 MiB/entry, ≤80× ratio, no symlink/encrypted/`..`/absolute); `private_filesystem_byte_store.py` uses `O_NOFOLLOW|O_DIRECTORY` segment-by-segment |
| Path traversal on asset routes | `/word-assets/{asset_path:path}` and `/dev/clearbrief/{asset}` use **exact allowlists**, no normalization |
| Authentication bypass | none surfaced; `UnavailableBearerVerifier` → **503, never allow**; signature verified only by remote Auth, never locally |
| Tenant isolation | all 80 SECURITY DEFINER functions pin `search_path` (**0 gaps**); all 15 RLS policies scope by `auth.uid()` + membership + grant |
| `eval`/`exec`/`pickle`/`yaml.load` | **0 hits** in product code |
| `sys.path` manipulation | 1 hit, test-only |
| Prompt injection | model output may only become a separately-labelled object (`model_notes.py:37`); injection text stays inert data |
| Supply chain | `uv.lock` (279 KB) + `package-lock.json` (130 KB) committed; `uv run --locked` + `npm ci` everywhere; **0** `curl\|bash`; frontend deps **exactly pinned**; 0 unpinned pip/npm |

---

## 6. Test suite

**2 322 Python test IDs** (1 360 `def test_` × parametrization) + **156 JS/TS** = **2 478** total. **4 skipped** (0.17 %), **0 xfail**, **0 `pytest.mark.skip`**, **0 `continue-on-error`**, **0 `if: false`** in CI.

| Category | Share | Notes |
|---|---|---|
| Real behaviour | **~78 %** | kernel/domain/application logic on real bytes |
| Testing the test-double | ~6 % | |
| **Tautological / grep-the-source** | **~7 %** | the weak tail |
| Meta / CI-shape / doc-shape | ~9 % | YAML assertions, JSON equality |

**~160 tests assert on literal source text** rather than behaviour — e.g. `test_p6_privacy_disclosure.py:8-15` (7 substring assertions on a `.tsx` file), `test_data_rights_enforcement.py:134-135` (greps `dev_live_entry.py`), `test_clearbrief_workspace.py:215-248` (**34** substring assertions on `workspace.js`), `test_architecture_freeze_v1.py:136` (the inert guard). These pass if the string exists *anywhere* in the file, including in a comment.

**`tests/adversarial/` has exactly ONE file** (464 lines, 91 IDs, 15 hand-labelled oracle cases). It is genuinely strong — metamorphic Unicode fuzz, stale-digest, hidden-contradiction, cross-tenant, chain-truncation, prompt-injection-as-inert-data — but **all against `InMemory*` implementations, never a real adapter**. No homoglyph/bidi/confusable attacks anywhere in the repo.

**Fixture reality:**
> **Only 2 binary document fixtures are committed** — `synthetic_invoice.pdf` (2 384 B, real PDF, 2 pages) and `synthetic_supplier.eml` (357 B). **Zero committed DOCX. Zero committed scanned images.**

All DOCX/PDF/scan bytes are **programmatically generated at test time** (`tests/fixtures/factory.py:37-181`, `visual_fidelity.py:26-79`, `dossier_journey.py:8-56`, `scripts/m0_real_format_fixtures.py:52-181`). The claim is **backed by real bytes**, but there is **no golden-binary regression corpus** — if a generator changes, the fixture changes with it.

Weakest layer: **`apps/worker` — 1 test file, 8 test IDs** for 3 modules including the lease/fence worker.

**Windows parity (measured directly):** `pytest --co` without a POSIX `resource` shim → **42 modules error at collection, 1 941 of 2 322 tests collected**. No `windows-latest` matrix row exists. The repo is Linux-only in practice; the owner works on Windows.

---

## 7. Code inventory by lifecycle state

**Do not delete on the basis of this table alone.** Reachability is a fact; obsolescence is a judgment that needs product intent.

### 7.1 Genuinely dead — no intent, no future use

`packages/evidence_kernel/domain/ports.py` (one grep hit) · `domains/construction/` (test/eval only) · `frontend/src/features/evidence/index.ts` port · `frontend/premium-audit.json` (stale absolute path) · `application/decision_ports.py` · `application/documents/finance.py` · `application/litigation/model_notes.py` · `application/litigation/visual_calibration.py` · `domains/disputes/docx_exhibit_page_policy.py` (parallel copy of an inline rule).

### 7.2 Intentionally dormant — gated by design, must be preserved

`application/security/deployment_assessment.py` (hard-codes `sec_01_16_approved: False`) · `application/litigation/review_cycle.py::ready_for_release()` (always `False` **by design** — "release authority is M4") · `application/extraction/pipeline.py:580` invariant (the proposal-only pipeline can never satisfy human review) · the 6 `contracts/v2_operation_matrix.json` operations · the rights-enforcement SQL gates (`_rights_enforcement_control`, disabled by default) · `infrastructure/execution/postgres_jobs.py` (real SQL, no live schema) · `application/review/memory.py` and `application/extraction/journal.py::MemoryJournal` (explicitly labelled test-only) · `infrastructure/persistence/m1_exhibit_memory.py` (explicitly labelled test-only).

### 7.3 Unreachable but plausibly future capability — do not delete without a product decision

`apps/api/requesty_extraction.py` (real LLM client, unwired) · `apps/api/postgres_case_repository.py` and `restricted_case_repository.py` (real SQL, possible non-PostgREST path) · `apps/api/hosted_mcp_app.py` (deliberately unmounted until its release gate passes) · `apps/api/contracts_v2.py` (contract definitions awaiting their moment) · `apps/api/hosted_mcp_oauth_boundary.py` · the `authenticated_*` composition layer · `apps/web/prototype/` (orphaned, unserved) · `apps/word_addin/demo_app.py` (synthetic demo server) · `frontend/scripts/p6-dependency-audit.mjs` (not wired to any npm script).

---

## 8. Consolidated findings by severity and class

**Ranking principle (v2):** severity is driven by **pilot-blocking consequence**, not by effort. Classes: **Security** (exploitable or credential custody) · **Truthfulness** (a machine-read or human-read artifact asserts something false) · **Completeness** (a required capability does not exist) · **Hygiene** (correctness/maintainability with no direct pilot consequence).

### P0

| # | Class | Finding | Evidence |
|---|---|---|---|
| **P0-1** | Security | Live service-role key + Supabase PAT + OpenAI key in an ungitignored `.env` inside a **PUBLIC** repo working tree. Rotate all three; add `.env`, `.env.*`, `*.log` to `.gitignore`. | §5.1 — verified |
| **P0-2** | Security | Service-role credential injected into 8 `pull_request`-triggered workflows, gated only by branch name, with all 18 branches live. Contradicts the repo's own runbook. | §5.2 — verified |
| **P0-3** | Truthfulness | `supabase/migrations/` **cannot be replayed in filename order** — `_phase4_reference_decisions` is created only outside the migration set; 7 migrations depend on it. `supabase db push` fails. The fix requires a **written design decision** (renumber vs. rewrite-dependents vs. first-class bootstrap), because Supabase records applied versions and renumbering invalidates the dev DB's history. | §3.5 — verified |
| **P0-4** | Truthfulness | The `/v2` contract freeze guard is **inert** — it checks `apps/api/main.py` (3 routes, never had `/v2`) while 66 `/v2` routes are mounted and the contract's global status string is false. Second defence (permission grants + `CaseAccessService`) prevents direct exploitation; the exposure is that a machine-read artifact lies. | §3.4 — verified |

### P1

| # | Class | Finding |
|---|---|---|
| **P1-1** | Completeness | **No production deployment target** for API, worker or add-in. Runnable locally; not productionizable. |
| **P1-2** | Evidence | **Live signed-browser acceptance never runs on `main`** — 22 workflows gated by `github.head_ref == '<branch>'`; 10 have 0 successes ever. |
| **P1-3** | Truthfulness | `required_approving_review_count: 0` **matches the adopted solo-maintainer policy** and is not a defect; the real residual is that **23 of ~25 CI checks are non-blocking**. See §5.3. |
| **P1-4** | Truthfulness | **Documentation lags the code by 13 merged PRs** and misstates the merge gate in three files. `STATUS.md` is the implementation-truth pointer and is stale. |
| **P1-5** | Truthfulness | **`MEMORY.md` states the superseded finance-first product** and is a first-class required read. |
| **P1-6** | Truthfulness | **Three conflicting SEC-01..16 registers.** |
| **P1-7** | Security | **Receipt HMAC key shares custody with the Supabase admin key**; no rotation path (ADR 0036, unresolved). |
| **P1-8** | Completeness | **33 of 72 API modules unreachable**; `apps/api/main.py` is a naming trap that misleads every reader and agent about tenancy, auth and persistence. |
| **P1-9** | Completeness | **`caseproof_m1_reader` DB role does not exist** — blocks the least-privilege runtime (issue #37) and gates SEC-04. |
| **P1-10** | Completeness | **All 16 SEC-01..16 pilot gates OPEN** — no independent security review, penetration test, incident plan, backup drill or erasure proof exists. |
| **P1-11** | Completeness | **The reviewer journey is not completable by a user** — no "run an explicit check" action, no job progress; §18 first-matter-and-check journey has a hole. |

### P2 — hygiene and quality

`.gitattributes` absent → `npm run lint` and `npm run contracts:check` fail on every Windows checkout (CRLF vs Prettier LF; generated TS verified byte-identical) · `pydantic` banned by `kernel/AGENTS.md:20` and ADR 0008:28 but **absent** from the kernel ban list · **dynamic-import bypass** (`getattr(importlib, "import_module")`, `sys.modules` injection) not detected, breaching `CONSTITUTION.md:38` · `domains/evidence_signals.py` outside every `RULES` root · **kernel public surface not frozen** (no `__all__`, no `py.typed`, empty `domain/__init__.py`) — the precondition for ADR 0019's reuse claim · ~160 grep-the-source tests · one adversarial test file · `apps/worker` has 8 test IDs · no committed binary DOCX/scan fixtures · `evals/` type-checked but never executed · **two DOCX paths disagree on tracked changes** (`engines.py:264-268` includes `w:ins` text; `docx_region_inventory.py:122-126` excludes the same parts) · **PNG/JPEG originals accepted by intake but never parsed** · `docker/ocr-worker.Dockerfile` is the production-default OCR image, unpinned (no digest, no apt pins, no `USER`) · `Pillow` declared with no import found · Actions tag-pinned, not SHA-pinned · no Python CVE scanning · no per-migration rollback artifact · 2 applied migrations with no repo file; 20 of 72 with no receipt · duplicate ADR `0020`, no index · OCR confidence never calibrated (`calibration_status: 'not_available'`) · `__import__("os")` + fixed `/tmp` path · ADR 0025 names subprocessors literally `"TBD"`.

---

## 9. Constitutional compliance

**26 enforceable clauses** (C01–C25 plus C09-A).

**COMPLIANT (21):** C01, C02, C03, C04, C05, C06, C07, C08, C09, C09-A, C10, C12, C14, C15, C17, C18, C19, C20, C21, C22, C23.
**PARTIAL (5):** C11 (no per-migration rollback artifacts), C13 (self-review is the documented substitute for an independent approval during the solo-maintainer phase; the policy is explicit about this), C16 (only 2 required checks; no release record artifact), C24 (`MEMORY.md` stale, `AGENTS.md` misstates the gate), C25 (no formal independent approval is possible while the repository has one maintainer).

The engineering discipline is genuinely high. The failures are **governance and operations**, not code logic.

---

## 10. Recommended sequence

**Do not rebuild CaseProof.** Secure, reconnect, verify and validate what exists; implement only what the pilot requires.

**Track A — containment (immediate, operational, not gated by the code freeze)**
1. Rotate `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ACCESS_TOKEN`, `OPENAI_API_KEY`; add `.env`, `.env.*`, `*.log` to `.gitignore`; add `.gitattributes` (`* text=auto eol=lf`).
2. Move all `CASEPROOF_DEV_AUTH_ADMIN_KEY` consumers out of `pull_request`-triggered execution; protect the `caseproof-dev` environment with required reviewers; retire the 18 stale remote branches; SHA-pin `actions/checkout`.

**Track B — integrity (engineering, bounded)**
3. Write the migration-repair design decision (renumber vs. rewrite-dependents vs. first-class bootstrap), then implement it with a **fresh-replay** CI job that runs the chain **in filename order**.
4. Provision `caseproof_m1_reader` as a least-privilege, non-BYPASSRLS, non-owner login.
5. Replace the `/v2` guard with a route inspection of the real composition root asserting the 6 named operations are absent; extend the kernel ban list (`pydantic`, `starlette`, DB drivers, HTTP clients) and close the dynamic-import bypass; add `domains/` root to the scanned roots; freeze the kernel's public surface.

**Track C — release assurance (governance)**
6. Refresh `STATUS.md` to the current head; correct `AGENTS.md`, `CLAUDE.md`, `ROADMAP.md`, `README.md`, `BLUEPRINT.md` (F6 + Storyteller decision), `MEMORY.md`; collapse the five competing task lists into one; resolve the duplicate ADR 0020 and add an index; designate one canonical SEC register.
7. Add the remaining CI workflows as required checks, and record the solo-maintainer merge policy next to the ruleset so the next reader does not have to re-derive it. Require independent approval only when the policy's own trigger is met: additional maintainers, deployment or security risk, or production customer data.
8. Replace the 22 branch-name gates with environment/scope gating so live acceptance **runs on `main`**; add `main` to the required checks; execute `evals/` in CI; commit a golden binary fixture set.
9. Derive a dedicated receipt key (`CASEPROOF_RECEIPT_KEY`) with a manifest key ID and retained verification keys (ADR 0036).

**Track D — product completion (only after B and C)**
10. Build the deployment target (API image + worker supervisor + TLS + rollback).
11. Implement the named missing capabilities: embedded DOCX/crop hyperlinks, the claim-review path, the organization-verified approver directory.
12. Frontend: "run an explicit check", the P10 data-disclosure page, an NL/FR catalog, and a locale-correct date/number format.

**Track E — independent validation (outside engineering)**
13. Adjudicated NL/FR corpus by a non-author; lawyer reviewer benchmark reporting the **rate of incorrect confirmation of unsupported claims**; real operational recovery drill; SEC-01..16 with accountable approvers.

**Do not:** add a second vertical, a DomainPack, or a generic EvidenceState — ADR 0018/0019 forbid it without a superseding ADR and evidence-led customer pull.

---

## 11. Method and limitations

**Executed:** FastAPI route enumeration of the real composition (95 mounted routes: 66 `/v2`, 21 `/dev`); exhaustive import scan of `packages/evidence_kernel`; `check_architecture.py` RULES-root coverage check; `pytest --collect-only` with and without a POSIX `resource` shim (2 322 IDs / 42 collection errors); `gh run list` across 59 workflows; `gh api repos/…/rulesets`; `git check-ignore` / `git ls-files` on `.env`; migration table-creation site search; CONSTITUTION clause enumeration (26); authority-document line/byte counts (3 580 lines / 400 KB); `caseproof_m1_reader` search across migrations and proposals (0 hits); `evals/` workflow-reference search.

**Could not verify:** live `caseproof-dev` catalog (Supabase MCP not connected — every LIVE/DEPLOYED claim is read from the repo's own receipts); GitHub environment protection rules; actual retention/backup/TLS behaviour (provider-side); `apps/web/review/` runtime (Linux-gated); any real Word-host behaviour; whether the 33 unmounted modules were intended for later wiring; whether the 18 stale remote branches carry branch-level protection; **production security, independent legal-document accuracy and reviewer effectiveness — none of which this artifact can establish.**

**CI reality at audit time:** `main` = 24 workflow runs, 23 success, 1 skipped, 0 failed. The single skip is the `workflow_dispatch`-only one-click E2E.

**No file was modified by this audit.**
