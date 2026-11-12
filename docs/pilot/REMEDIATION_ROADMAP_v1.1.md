# CaseProof — Remediation Roadmap v1.1

**Remediation required before a real-client pilot**
**Status:** proposed, bounded remediation exception — **not** authorization to open PRs, merge code, or start another broad feature phase.
**Base:** `docs/audits/DEEP_CODEBASE_AUDIT_2026-11-11_v2.md` (codebase assessment) and its review.
**Related:** `docs/pilot/P5_P6_ACCEPTANCE_MATRIX.md` · `docs/security/PILOT_DATA_SECURITY_GATE.md` · `docs/pilot/PILOT_CAPACITY_PROFILE.md`
**Supersedes:** remediation roadmap v1.0.

> **Operational security actions are not gated by the code freeze.** Emergency credential rotation, `.gitignore`/`.gitattributes` hardening and removal of privileged credentials from untrusted-PR execution are authorized as operational security actions and should not wait for a feature release. They require no feature design, no new ADR and no product decision.

---

## 0. Amendment log (v1.0 → v1.1)

Nine amendments applied. Each is traceable to a verified finding.

| ID | Change | Basis |
|---|---|---|
| **D1** | **Three foreign marketing image links removed.** The v1.0 draft of Phase 4 embedded three OpenAI-hosted image assets whose alt-text names three **legal-tech competitor products**. They are not CaseProof assets, and they placed third-party product names inside the project's own roadmap. `AGENTS.md:15` requires independent clearance for public naming and first-to-market claims; a grep of `docs/` for those vendor names returned zero hits before this draft, and zero hits after it — the removal is therefore complete and is recorded here without re-introducing the names. | Verified: 0 vendor-name hits in `docs/` before and after |
| **D2** | **"Preserve the approved Storyteller layout" replaced by an explicit decision task (UX-01).** Storyteller is **not** recorded as approved: `frontend/BLUEPRINT.md` contains **0 occurrences** of "Storyteller" or "cockpit" despite §1 declaring itself the single UI authority, and `docs/STORYTELLER_DESIGN_AUDIT.md` is referenced from none of `AGENTS.md`/`CLAUDE.md`/`MEMORY.md`. Phase 4 is built on this vocabulary, so it must be settled before Phase 4 starts. | Verified |
| **E1** | **Phase 2B now names the migration-repair design decision** and states that fresh-install repair and historical version reconciliation are **one coupled problem**, not two sequential tasks. Three candidate options are enumerated; the chosen option requires a written ADR. | Supabase records applied versions; renumbering invalidates dev history |
| **E2** | **New task DB-03 — provision `caseproof_m1_reader`.** The role has **0 occurrences** across `supabase/migrations/` and `db/proposals/`, while `apps/api/signed_private_matter_reader.py:108-146` asserts it exists, is non-superuser, non-BYPASSRLS, owns no tables and holds no write privileges. `docs/m1/LIVE_DEV_PRIVATE_MIGRATION_RECEIPT_2026-10-27.md:15,26` records it absent and names provisioning as the next action. It blocks the least-privilege runtime (issue #37) and gates **SEC-04**. | Verified: 0 grep hits in migrations + proposals |
| **E3** | **Phase 4 acceptance criterion now states its execution environment**, and **`.gitattributes` moves into Phase 1.** `infrastructure/parsers/limited.py:27` hard-fails off Linux; `pdf_ocr.py:13` / `worker.py:7` do an unconditional POSIX-only `import resource`, breaking collection of **42 of 186** test modules on Windows (measured: `pytest --co` → `42 errors … 1941 tests collected`). A pilot workflow the owner cannot personally exercise must be labelled as CI-executed. | Verified by direct measurement |
| **E4** | **New CI task CI-04 — execute the evaluation harness.** `scripts/run_topology_comparison.py` appears in CI **only as a mypy argument** (`kernel-boundary.yml:65`) and `scripts/run_document_evaluation` has **0** workflow references, while the corpus *validator* runs in 3 places. The default run yields `proposals: 0, label_recall: 0.0` — the current eval measures the safety rail, not extraction quality. | Verified |
| **E5** | **New task QA-01 — resolve the DOCX tracked-changes divergence before golden fixtures exist.** `infrastructure/parsers/engines.py:264-268` extracts `w:ins` text with a warning; `docx_region_inventory.py:122-126` and `docx_text_regions.py:55-57` **exclude** the same parts as `REVISION_STATE_UNRESOLVED`. Phase 5's tracked-change fixtures would freeze whichever behaviour they happened to capture. | Verified |
| **E6** | **Two additions.** (a) **QA-02** — PNG/JPEG originals are accepted by intake (`apps/api/signed_supabase_originals.py:25-26`) but **never parsed** (`engines.py:311-323` has no image branch; `signed_document_parse.py:24` sets `BINARY_MEDIA = {pdf, docx}`), so an uploaded image is stored, hashed and silently ignored. (b) **UX-02** — rename or deprecate `apps/api/main.py`, which still teaches every reader and agent the wrong thing about tenancy, auth and persistence. | Verified |
| **G1** | **New task ARCH-04 — freeze the kernel's public surface.** The kernel has no `__all__`, no `py.typed`, an empty `domain/__init__.py`, a dead `domain/ports.py`, and the only contract-freeze test pins four locator kind names. ADR 0019's reuse claim depends on a kernel whose exported names are pinned; this is the cheapest reuse insurance available and is not housekeeping. | Verified |
| **G2** | **New task OPS-02 — approve the pilot capacity envelope.** `application/capacity_envelope.py:21` reads `"approval": "development_only_not_pilot_approved"`; the docstring states *"NOT a pilot capacity approval."* A bounded pilot needs an approved envelope, and Phase 5's capacity measurement depends on one. | Verified |
| — | **Sequencing refinement.** GOV-01…GOV-04 now run as a **parallel track from day one** — the docs will go stale during Phases 1–2 regardless, and Phase 3's exit criterion (a green release candidate whose important tests actually executed) is a better definition of truth than any document statement. | — |

---

## 1. Roadmap overview

| Phase | Severity | Scope |
|---|---|---|
| **01** | P0 | Immediate security containment — secrets, privileged CI, access boundaries |
| **02** | P0 | Architecture and database integrity — migrations, contracts, boundaries, least-privilege role |
| **03** | P1 | Governance and reliable CI — review protection, live acceptance, authoritative documentation |
| **04** | P1 | Complete the pilot workflow — reviewer journey, essential frontend gaps, deployment |
| **05** | P1 | Independent verification — real fixtures, adversarial evaluation, human study |
| **06** | Gate | Controlled pilot release — SEC-01…16, restore tests, firm approval |

**We should not rebuild CaseProof.** The evidence kernel, legal verification logic, secure intake, reviewer workspace and export mechanisms already provide a substantial foundation. The priority is to **secure, reconnect, verify and validate what already exists**, then implement only the missing capabilities required for a complete pilot workflow.

**Tracked in parallel:** GOV-01 → GOV-04 (documentation reconciliation) start immediately and run alongside Phases 1–2.

---

## 2. Phase 1 — Immediate security containment (P0)

The audit identifies credentials in an untracked `.env` and privileged credentials reachable from some pull-request workflows. **This is an exposure risk, not evidence that credentials have been publicly leaked.** Treat it as an exposure risk: rotate, then verify.

| Task | Required fix | Evidence of closure |
|---|---|---|
| **SEC-FIX-01** | Rotate the exposed-at-risk Supabase service-role, Supabase access and OpenAI credentials. Inspect git history, CI logs and workflow artifacts for actual exposure before assuming none occurred. | Rotation receipts; `git log --all -- .env` empty; log scan result |
| **SEC-FIX-02** | Protect `.env`, local overrides and logs via `.gitignore` (`.env`, `.env.*`, `*.log`), **plus `.gitattributes` (`* text=auto eol=lf`)** — the latter currently makes `npm run lint` and `npm run contracts:check` fail on every Windows checkout. Add secret scanning and pre-commit controls. | `git check-ignore --no-index .env` returns a rule; `npm run lint` + `npm run contracts:check` pass on Windows |
| **SEC-FIX-03** | Remove privileged live-test secrets from PR-controlled execution. Sensitive tests run only through protected, explicitly authorized execution. | No `pull_request`-triggered workflow references `CASEPROOF_DEV_AUTH_ADMIN_KEY` |
| **SEC-FIX-04** | Review and retire stale privileged workflow entry points and the 18 stale remote branches they are keyed to, **after preserving required evidence** (prior run records, receipts). | Remote branch list reconciled against workflow `head_ref` guards; prior runs retained |
| **SEC-FIX-05** | Restrict CI secrets to minimum necessary permissions; review GitHub environment protections for `caseproof-dev` (required reviewers, wait timer, branch restriction). | Environment protection screenshot/export; secret usage inventory |
| **SEC-FIX-06** | SHA-pin the GitHub Actions used by any workflow that holds a service-role credential (currently tag-pinned, including two `actions/checkout@v4` users). | Pinned-SHA manifest |

**Acceptance:** no untrusted PR code can access administrative credentials; no sensitive local configuration is accidentally publishable; rotations and access checks have evidence.

---

## 3. Phase 2 — Architecture and database integrity (P0)

### 3.1 Migration replay and historical reconciliation — **one coupled problem**

`_phase4_reference_decisions` is created outside the ordered migration directory (`supabase/phase4_reviewed/caseproof_phase4_signed_reference_review.sql:2`), yet 7 migrations / 20 references depend on it — including a DDL trigger (`20261030155817_matter_retention.sql:94`) and a PL/pgSQL `%rowtype` validated at function-creation time (`20261030161844_complete_dossier_journey.sql:32`). `supabase db push` against the repo directory fails. CI hides this by reordering (`scripts/verify_retention_disposable.py:80-89`).

**The coupling (E1):** Supabase applies migrations in filename order and **records the applied version**. Therefore a repaired chain for fresh installs and a reconciliation map for the existing dev DB must be designed **together** — renumbering to place the phase4 table creation early invalidates the dev database's recorded history.

| Task | Required fix | Evidence of closure |
|---|---|---|
| **DB-01** | **Write the migration-repair design decision as an ADR.** Choose explicitly between: **(a)** rewrite the dependent migrations to remove the hard dependency (trigger + `%rowtype`), preserving applied history; **(b)** renumber the chain and ship a version-reconciliation map for the dev DB; **(c)** make the phase4 bootstrap a first-class, named, integrity-checked pre-migration step. Option (c) is only acceptable if the ordering is explicit and checked — an unnamed ordering step *is* the hidden sequence this phase exists to eliminate. | ADR with the chosen option and its consequences for applied history |
| **DB-02** | Implement DB-01, and add a CI job that replays the **complete chain in filename order** against a disposable PostgreSQL instance. The job must not reorder or defer any file. | Fresh-replay CI job green on an unmodified chain |
| **DB-03** | **Provision `caseproof_m1_reader`** as a least-privilege, non-owner, non-BYPASSRLS, non-login-to-browser application role with exactly the 5 protected tables it may read and no write privileges — matching the assertions already in `apps/api/signed_private_matter_reader.py:108-146`. Record the grants in a migration. Closes issue #37 and **SEC-04**. | Migration in `supabase/migrations/`; role inspection receipt; the existing reader assertions pass against the live role |
| **DB-04** | Reconcile historical migration IDs and deployed SQL: record the generated version for the 2 drifted files, bring the 2 applied-but-absent migrations (`20261105081249`, `20261105100916`) into `supabase/migrations/`, and produce install receipts for the 20 migrations that currently have none. | Every repo migration has a version + install receipt; every applied migration has a repo file |
| **DB-05** | Explicit handling of out-of-band SQL: declare which SQL is expected to be applied out of band, how it is verified, and how it is prevented from being silently omitted. | Written policy + CI check that fails on undeclared out-of-band dependencies |
| **DB-06** | Extend migration integrity checks across the **complete** active chain — currently 6 of 72 are byte-compared and the job asserts only `>= 35` files exist. | CI job compares all 72 against their recorded digest |
| **DB-07** | Tested recovery or rollback procedure per migration, satisfying `CONSTITUTION.md` C11 ("every migration has … rollback/recovery analysis"). | Per-migration rollback artifact + tested restore path |

**Do not simply append a later migration and claim the problem is solved:** that will not repair earlier migrations that already fail during a fresh replay.

### 3.2 API contract guard

The current test checks `apps/api/main.py`, which contains only `/health`, `/v1/claims` and `/v1/claims/{claim_id}` and **has never had a `/v2` route** — so the assertion cannot fail regardless of what the product does.

| Task | Required fix | Evidence of closure |
|---|---|---|
| **ARCH-01** | Replace the text grep with a **route inspection of the real FastAPI application** (`create_litigation_development_app()`), asserting the **six named contract operations** are absent: `/v2/evidence-anchors`, `/v2/findings`, `/v2/findings/{id}/evidence`, `/v2/cases/{id}/coverage`, `/v2/cases/{id}/promotion`, `/v2/cases/{id}/exception-dispositions`. **Do not** ban legitimate existing `/v2` routes — 66 are correctly mounted and authorised. | Negative test proves a deliberately prohibited route is detected in the real composition |
| **ARCH-02** | Correct `contracts/v2_operation_matrix.json` so its `status` string and its prose describe the **actual** state (the 6 proposed operations unmounted; 66 other `/v2` product routes live). A machine-read artifact must not assert a false state. | Contract text matches measured route table; CI asserts the contract against the live route inventory |

### 3.3 Kernel boundary protection

| Task | Required fix | Evidence of closure |
|---|---|---|
| **ARCH-03** | Expand boundary checks: add the missing forbidden imports (`pydantic` — already banned by `packages/evidence_kernel/AGENTS.md:20` and ADR 0008:28 but absent from the ban list — plus `starlette`, DB drivers, HTTP clients, cloud SDKs); close the **dynamic-import bypass** (`getattr(importlib, "import_module")`, `sys.modules` injection, `eval`/`exec`), which `CONSTITUTION.md:38` explicitly prohibits; add the unscanned `domains/` root files to the scanned set. | Negative tests fail when each forbidden dependency or bypass is introduced |
| **ARCH-04** | **Freeze the kernel's public surface**: per-module `__all__`, `py.typed`, a populated `domain/__init__.py`, and a compatibility test pinning the exported names. ADR 0019's reuse claim depends on this — a kernel whose exported names are not pinned breaks silently for a second consumer. | Compatibility test fails on removal or rename of any exported kernel name |
| **ARCH-05** | Preserve the reusable kernel's independence from FastAPI, Supabase, LLM SDKs and litigation-specific rules. `Decimal` for geometry; no `float`; no sector terminology inside the kernel. | Existing kernel rules hold; boundary tests green |

**Phase 2 acceptance:** a clean database can be recreated **without a custom hidden SQL sequence**; the real API route guard catches deliberately prohibited routes; architecture negative tests fail when forbidden dependencies are introduced; the least-privilege reader role exists and is verified.

---

## 4. Phase 3 — Governance, documentation and trustworthy CI (P1)

The audit found the codebase is ahead of its documentation, and the required merge checks are too narrow.

| Task | Required outcome | Evidence of closure |
|---|---|---|
| **GOV-01** | Make `docs/STATUS.md` accurately reflect merged capabilities through PR #211, including the rights ledger, release acknowledgement, paraphrase guard, blinded reviewer benchmark, source-identity hardening, duplicate-pinpoint fail-closed, claim candidates and statute parser. | STATUS.md references each merged PR and its evidence |
| **GOV-02** | Correct `ROADMAP.md`, `MEMORY.md`, `AGENTS.md`, `CLAUDE.md`, `README.md` and `frontend/BLUEPRINT.md`. Specifically: `MEMORY.md:9` must stop naming the superseded finance-first product; `AGENTS.md:22` / `STATUS.md:316` / `CLAUDE.md:9` must stop claiming branch protection is unverified; `BLUEPRINT.md:284` must reflect F6 as shipped. | Each stale statement corrected at its source |
| **GOV-03** | Establish **one** authoritative implementation tracker; archive the four competing lists (`ROADMAP.md` delivery sequence, `CASEPROOF_AGENT_MASTER_TODO.md`, root `AGENT_MASTER_TODO.md`, `CASEPROOF_FINAL_WORKFLOW_V4.md`, `CASEPROOF_DECISION_CATALOGUE_AUDIT_2026-11-10.md`) to clearly-marked archive status. Resolve the duplicate ADR `0020` and add `docs/adr/README.md`. | One tracker; four archives labelled; ADR index present |
| **GOV-04** | Use **one canonical SEC-01…16 register** (`docs/security/PILOT_DATA_SECURITY_GATE.md`), with the m5 register and the STATUS.md variant rewritten as explicit cross-references. | One register; no competing ID space |
| **GOV-05** | Require **independent PR approval** (`required_approving_review_count: 1`, `require_code_owner_review: true`) and add an appropriate set of stable, risk-based CI checks as required status checks. | Ruleset reflects the requirement; both required contexts succeed on every main run |
| **CI-01** | Replace obsolete **branch-name gates** (`github.head_ref == '<branch>'`, 22 workflows) with controlled release-acceptance execution keyed to environment/scope, so acceptance runs on the release candidate rather than on a feature branch that may be deleted. | Live-acceptance workflows execute on `main` and on release candidates |
| **CI-02** | Execute signed-browser, rights enforcement, authorization and recovery acceptance **on the release candidate**. | Required checks execute and pass; no skipped critical acceptance |
| **CI-03** | Add Python dependency vulnerability scanning (`pip-audit` or equivalent), pin the OCR container image by digest, and add the missing rollback-analysis artefacts. | Scanning job green; image digest pinned |
| **CI-04** | **Execute the evaluation harness in CI** — `scripts/run_document_evaluation` currently has 0 workflow references, and `scripts/run_topology_comparison.py` appears only as a mypy argument. The corpus validator already runs; the evaluation itself does not. | Evaluation job green and its reported metrics recorded in the release candidate artifact |
| **CI-05** | Ensure a green release-candidate build means the important security, database and real-workflow tests **actually executed and passed**, rather than merely being skipped. | Release-candidate artifact lists every executed job and its result |

**Phase 3 acceptance:** a green release-candidate build is evidence, not decoration.

---

## 5. Phase 4 — Complete the minimum usable product (P1)

Only the capabilities necessary for the first Belgian litigation workflow.

### 5.1 Reviewer journey

1. **Explicit verification execution.** Add the missing **Run Check** action, job progress, cancellation/recovery behaviour and explicit verification results. The reviewer must know what has and has not been checked. *(The §18 first-matter-and-check journey is currently not completable by a user.)*
2. **Complete claim-review journey.** Connect extracted claim → exact source anchor → evidence display → human decision → source-linked receipt → coverage-aware export.

### 5.2 Essential Belgian-market UX

3. **NL/FR interface localisation**, clear uncertainty states, the retention/data disclosure page (`/matters/:caseId/data`), and required source navigation.
4. **UX-01 — decide the Storyteller question before building on it.** `frontend/BLUEPRINT.md` contains zero occurrences of "Storyteller" or "cockpit" despite §1 declaring itself the single UI authority. Either adopt Storyteller into the blueprint (making it authoritative, with the 141 `cockpit-*` CSS classes and `PrimaryNavigation.tsx:8` reconciled against it) or drop the term. **This is a decision, not an implementation detail** — Phase 4 is built on this vocabulary.
5. **UX-02 — rename or deprecate `apps/api/main.py`.** It is not the application; it is an 89-line development demo with a caller-controlled `X-Tenant-Id` header. Anyone reading it first draws the wrong conclusion about tenancy, authentication and persistence. One-line change, bundled with ARCH-01.

### 5.3 Data-format correctness (must precede golden fixtures)

6. **QA-01 — resolve the DOCX tracked-changes divergence.** `infrastructure/parsers/engines.py:264-268` extracts `w:ins` text with a warning; `docx_region_inventory.py:122-126` and `docx_text_regions.py:55-57` exclude the same parts as `REVISION_STATE_UNRESOLVED`. Two paths disagree on the same file. Decide which is authoritative **before** Phase 5 creates tracked-change fixtures, or the golden corpus freezes an accident.
7. **QA-02 — close the PNG/JPEG intake gap.** Storage accepts `image/png`/`image/jpeg` (`signed_supabase_originals.py:25-26`) but no parser handles images (`engines.py:311-323`; `signed_document_parse.py:24` sets `BINARY_MEDIA = {pdf, docx}`). An uploaded image is stored, hashed and silently ignored. Either reject unsupported originals explicitly at intake or label them stored-only in the product surface.

### 5.4 Operations

8. A reproducible API/worker deployment, verified worker supervision, properly managed TLS and signing keys, and tested restart/recovery behaviour.

The audit's proposed DOCX/crop hyperlinks and stronger approval provenance should be resolved **against the actual pilot requirements**. They should not automatically become mandatory features without establishing that no safe existing workflow satisfies the same requirement.

**Phase 4 acceptance:** a new reviewer can complete a synthetic NL/FR dossier from intake through reviewed export and reopening, without manually calling developer scripts or APIs — **executed on the CI/Linux environment** (the parser worker is Linux-only by construction: `infrastructure/parsers/limited.py:27`).

**Out of scope for this phase:** hosted MCP, a second commercial vertical, and speculative kernel generalization.

---

## 6. Phase 5 — Independent verification and human validation (P1)

This is where CaseProof moves from *the software passed tests* to *the verification process is demonstrably reliable*.

| Verification track | Required evidence |
|---|---|
| **Golden documents** | Fixed, independently controlled DOCX, scanned PDF, mixed page-size and tracked-change fixtures. **Today only two binary document fixtures are committed** (`synthetic_invoice.pdf`, 2 384 B; `synthetic_supplier.eml`, 357 B) — zero DOCX, zero scanned images. Everything else is regenerated at test time by the generator that also computes the expected hashes, so there is no golden-byte regression corpus. |
| **Kernel adversarial tests** | Wrong page, duplicate quotation, source-version mismatch, qualifier changes, OCR errors and conflicting evidence. Extend beyond the current single adversarial file (464 lines, 91 IDs, all against `InMemory*` implementations) to cover a real adapter. |
| **Real adapter tests** | Genuine authorization, cross-matter refusal, worker crashes, retries, revocation and source readback — including the `caseproof_m1_reader` path from DB-03. |
| **Evaluations** | Executed NL/FR corpus with **independent adjudication**, not only author-supplied labels (`evals/litigation/m0_corpus_v3.json` carries `label_status: author_supplied_unadjudicated`, `independent_gold: false`). |
| **Human reviewer study** | Lawyers evaluate seeded unsupported claims **without receiving the answer key**. |
| **Operational capacity** | Full-journey measurements within documented dossier limits. **OPS-02 — approve the pilot capacity envelope first:** `application/capacity_envelope.py:21` currently reads `"approval": "development_only_not_pilot_approved"`. |
| **Security evidence** | Independent security review of the privileged `SECURITY DEFINER` RPCs, roles and grants; independent pen test; incident plan; backup-restore drill. |

**The human study should specifically report the rate at which reviewers incorrectly confirm unsupported claims. Precision or recall of the engine alone is insufficient.** The engine's error rate is not the harm function; the harm is a lawyer confirming a claim the evidence does not support.

---

## 7. Phase 6 — Controlled pilot release (Gate)

Two separate gates.

**Operational gate:** all applicable controls in the canonical **SEC-01…16 security checklist** must have evidence and the required accountable approvals — security assessment, professional secrecy, retention, approved processing location, incident handling and backup restoration.

**Customer validation gate:** obtain permissioned dossiers, observed reviewer workflows and feedback from the intended Belgian legal users. **Engineering CI cannot substitute for these activities.**

Until both are satisfied, CaseProof stays restricted to synthetic or suitably rights-cleared material. No free trial on client documents without separate permissions and SEC-01…16 acceptance.

---

## 8. Recommended implementation batches

Rather than opening 15–20 small PRs, group the authorized engineering work into four coherent batches.

| Batch | Scope | Exit criterion |
|---|---|---|
| **R1 — Security** | SEC-FIX-01…06: secret containment and rotation, workflow isolation, least privilege, credential controls, secret scanning, `.gitattributes` | Security review passed; no untrusted PR code can reach administrative credentials |
| **R2 — Integrity** | DB-01…07 + ARCH-01…05: migration design decision + replay, `caseproof_m1_reader`, historical reconciliation, real-API contract guard, kernel boundaries and public surface | Fresh DB replay green in filename order; negative tests fail on forbidden dependencies; reader role verified |
| **R3 — Release assurance** | GOV-01…05 + CI-01…05: branch protection, authoritative docs, executed live CI, evaluation harness, golden fixtures, capacity approval | Verified release candidate whose important tests actually executed |
| **R4 — Pilot-critical completion** | QA-01…02, UX-01…02, reviewer journey, NL/FR localisation, P10 disclosure page, deployment, receipts and recovery | Complete synthetic end-to-end journey, CI-executed |

**Independent assessment and pilot approval happen after these batches; they are not additional PRs that can be declared complete through CI.**

**Recommendation:** authorize **R1** and **R2** as tightly bounded security/integrity remediation exceptions first. **Do not start R4** until the repository's security, migrations and release evidence are trustworthy.

---

## 9. What we should NOT spend time building now

Do not make these pilot prerequisites without specific evidence of need:

- Removing all 33 reported unreachable API modules. *(Reachability is a fact; obsolescence is a judgment. Several are intentionally dormant — the release-completeness gate, the rights-enforcement SQL gates, the proposal-only pipeline invariant — and several are plausible future capability: `requesty_extraction.py`, the Postgres `CaseAccessRepository` implementations, `hosted_mcp_app.py`, `contracts_v2.py`. Delete only what is genuinely dead, which is a much smaller set.)*
- Implementing hosted MCP or an expanded Word add-in.
- Supporting a new finance, construction or compliance vertical.
- Creating a generic plugin framework or universal evidence state.
- Adding more AI models to the deterministic verification path.
- Redesigning the already established frontend from scratch.

Dead-code cleanup, Windows development ergonomics, OCR confidence calibration and supplementary DOCX features can be assessed separately, with security-sensitive exceptions prioritised where necessary.

---

## 10. Final release gates

**Pilot release readiness checklist — 0/6 confirmed**

| | Gate | Requirement |
|---|---|---|
| ☐ | **Security containment confirmed** | Credentials rotated or formally risk-assessed; privileged PR execution removed |
| ☐ | **Architecture and database reproducible** | Fresh replay and verified contract boundaries |
| ☐ | **Release candidate CI actually passes** | Required checks executed; no skipped critical acceptance |
| ☐ | **Complete synthetic reviewer journey** | Intake, check, review, correction, recheck, export, reopen |
| ☐ | **Independent engine and reviewer validation** | Adjudicated corpus and observed human results |
| ☐ | **Pilot security and firm approvals** | Applicable SEC controls approved with accountable evidence |

This checklist starts unconfirmed. **Checking an item is a tracking action, not evidence that a release gate has passed.**

---

## 11. Out of scope

Preserved from ADR 0018 / ADR 0019 and the current freeze:

- A second commercial vertical or a new sector — requires customer pull, technical fit, measured benefit, commercial commitment **and** an explicit owner scope decision via a superseding ADR.
- DomainPack or a generic EvidenceState.
- Hosted MCP production exposure, public OAuth issuance, and any durable consent registry.
- Word as a mandatory launch channel.
- Speculative kernel generalisation — the kernel stays a separate long-term asset with frozen public contracts, and nothing in this roadmap requires it to become a framework.

**The target is not another large codebase. It is a reproducible, secure and independently verified CaseProof workflow, while preserving the reusable evidence kernel as a separate long-term asset.**
