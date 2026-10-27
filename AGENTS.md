# ExceptionDesk / CaseProof — coding-agent instructions

Read `CONSTITUTION.md`, [accepted architecture ADR 0011](docs/adr/0011-architecture-freeze-and-first-finance-slice.md), `MEMORY.md`, `docs/STATUS.md`, `docs/ROADMAP.md`, `docs/standards/database-v1.md` when working with data, and the nearest `AGENTS.md`/ADR before changes. **Git and CI are authoritative**; memory is a checked snapshot.

**Product:** finance-first ExceptionDesk for supplier invoice vs purchase order exception resolution; CaseProof dispute dossiers later. Never silently rename the product, copy AZComply code/data, or introduce unrelated sectors.

**Architecture:** the pure `packages.evidence_kernel` must not import `domains`, FastAPI, ORM or LLM SDKs. `domains.finance` consumes the kernel, adapters depend inward. Quoted source text ≠ semantic support ≠ source authenticity ≠ independently authorized human approval. `Decimal` for money.

**Workflow:** prioritize a complete synthetic invoice/PO reviewer journey in parallel with real Auth/Vault/review security gates. Frozen [action catalog](contracts/action_catalog.v1.json) distinguishes installed request scopes from uninstalled approval scopes, and [baseline](contracts/architecture_baseline_v1.json) names exact `sheet_range`/decimal-string PDF contract. Do not introduce DomainPack or generic EvidenceState without a superseding ADR. Smallest testable vertical slice, independently review security/evidence/tenant changes, record actual branch + CI + test outcomes, and update `docs/STATUS.md` after material milestones. No production upload, migration, secret, external customer data or user action without separately authorized safeguards. Do not claim a prototype is deployed.

## Cloud-first verification (Constitution C25)

- Markdown-only edits: review changed-file scope and links; no Python test claim required.
- Executable code, SQL proposal, workflow/config or dependencies: required real cloud-runner CI (locked pytest, architecture checks, affected Ruff/mypy, actual disposable PostgreSQL/adversarial tests) before merge.
- CI is **available** on `main` as of 2026-10-22, but confirm every new HEAD. The intentional negative-control PR #4 failed specifically on forbidden finance→kernel import; **never merge it**.
- **Owner-controlled branch protection is NOT verified**: GitHub rulesets endpoint returned none and branch protection query was inaccessible. `CONSTITUTION.md` C13/C16/C25 and [issue #5](https://github.com/haytamAroui/caseproof/issues/5) remain gates. Do not claim that CI success alone establishes enforced merge protection. No autonomous production deployment or override of review controls.

## CaseProof Supabase dev access (owner direction, 2026-10-27)

- For **live** `caseproof-dev` database work, use the **connected Supabase MCP**: `list_migrations`, `list_tables`, `execute_sql` for read-only verification, `get_advisors`, and `apply_migration` only for separately approved/reviewed migrations. Always pin project `ldwmocpxwskvhoojndrd`; never assume AZComply's project.
- **Do not add or request PostgreSQL administrator DSNs, database passwords, CA PEM environment secrets, owner logins, or role-bypass credentials in GitHub Actions to replace Supabase MCP.** Use GitHub CI for disposable isolated PostgreSQL, automated code tests and the existing separately protected Supabase Auth smoke where appropriate.
- MCP `execute_sql` is generally privileged; its catalog checks or manual `request.jwt.claim.sub` simulation are **not** genuine signed-user live-RLS acceptance. Do not claim that they are. An eventual live Auth→actual Postgres acceptance needs a designed, independently reviewed least-privilege runtime, not an admin secret workaround.
- Do not create Auth identities by inserting into `auth.users` with SQL. The existing protected Auth API workflow may create temporary users and must delete them in a `finally` cleanup. Never expose credential values in repo, actions logs, files or chat.
- Record what the MCP **actually verified** versus pending signed-user tests, grant issuance/revocation audits, private Storage, human security review and production approval. The read-only audit is `scripts/m1_live_mcp_readonly_audit.sql`; [receipt](docs/m1/MCP_LIVE_RLS_AUDIT_2026-10-27.md).
- **Development migration completion rule (owner direction, 27 October 2026):** When a PR changing `supabase/migrations/*.sql` is merged, do not stop at GitHub green CI. In the **same active development task**, compare `list_migrations` against `main`, use connected **Supabase MCP `apply_migration`** for unapplied, explicitly approved **caseproof-dev** migrations, then `list_migrations`, read-only catalog queries, role-grant/RLS inspection and `get_advisors`. Record the generated migration version and the exact deployed SQL in `supabase/migrations/` so repo and database match. If a migration is blocked or fails, report the exact blocker and keep the milestone open. Do not apply automatically to production or silently bypass owner review. This is an agent workflow rule, **not** an unattended background GitHub event trigger.

## Runtime security boundaries

- `/v1/claims` is an **in-memory development adapter** with caller-chosen tenant header, not customer-safe authentication.
- S2-004 transaction/audit, S2-008 evidence graph, S2-009 Vault ledger have tested disposable SQL proposals; **not live production migrations**, even though source changes merged.
- S2-006/S2-007 Auth adapters and protected manual workflows do not prove end-to-end genuine Auth → least-privilege database-role binding until genuinely executed with authorized test accounts.
- `/v2` review/promotion is not mounted. No mock or CLI-injected claim authorizes consequential decisions.
- Private document bytes, verified object versions, source availability and human approvals are separate production gates.

## Delivery format

After each task: implemented paths and commit, exact CI/test evidence, risk and permission impact, untouched environments, unresolved gates, review findings and next customer-outcome-driven slice. Do not reproduce customer documents or tokens in logs.
