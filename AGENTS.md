# ExceptionDesk / CaseProof — coding-agent instructions

Read `CONSTITUTION.md`, `MEMORY.md`, `docs/STATUS.md`, `docs/ROADMAP.md`, `docs/standards/database-v1.md` when working with data, and the nearest `AGENTS.md`/ADR before changes. **Git and CI are authoritative**; memory is a checked snapshot.

**Product:** finance-first ExceptionDesk for supplier invoice vs purchase order exception resolution; CaseProof dispute dossiers later. Never silently rename the product, copy AZComply code/data, or introduce unrelated sectors.

**Architecture:** the pure `packages.evidence_kernel` must not import `domains`, FastAPI, ORM or LLM SDKs. `domains.finance` consumes the kernel, adapters depend inward. Quoted source text ≠ semantic support ≠ source authenticity ≠ independently authorized human approval. `Decimal` for money.

**Workflow:** smallest testable vertical slice, independently review security/evidence/tenant changes, record actual branch + CI + test outcomes, and update `docs/STATUS.md` after material milestones. No production upload, migration, secret, external customer data or user action without separately authorized safeguards. Do not claim a prototype is deployed.

## Cloud-first verification (Constitution C25)

- Markdown-only edits: review changed-file scope and links; no Python test claim required.
- Executable code, SQL proposal, workflow/config or dependencies: required real cloud-runner CI (locked pytest, architecture checks, affected Ruff/mypy, actual disposable PostgreSQL/adversarial tests) before merge.
- CI is **available** on `main` as of 2026-10-22, but confirm every new HEAD. The intentional negative-control PR #4 failed specifically on forbidden finance→kernel import; **never merge it**.
- **Owner-controlled branch protection is NOT verified**: GitHub rulesets endpoint returned none and branch protection query was inaccessible. `CONSTITUTION.md` C13/C16/C25 and [issue #5](https://github.com/haytamAroui/caseproof/issues/5) remain gates. Do not claim that CI success alone establishes enforced merge protection. No autonomous production deployment or override of review controls.

## Runtime security boundaries

- `/v1/claims` is an **in-memory development adapter** with caller-chosen tenant header, not customer-safe authentication.
- S2-004 transaction/audit, S2-008 evidence graph, S2-009 Vault ledger have tested disposable SQL proposals; **not live production migrations**, even though source changes merged.
- S2-006/S2-007 Auth adapters and protected manual workflows do not prove end-to-end genuine Auth → least-privilege database-role binding until genuinely executed with authorized test accounts.
- `/v2` review/promotion is not mounted. No mock or CLI-injected claim authorizes consequential decisions.
- Private document bytes, verified object versions, source availability and human approvals are separate production gates.

## Delivery format

After each task: implemented paths and commit, exact CI/test evidence, risk and permission impact, untouched environments, unresolved gates, review findings and next customer-outcome-driven slice. Do not reproduce customer documents or tokens in logs.
