# ExceptionDesk — coding-agent instructions

Read `CONSTITUTION.md`, `README.md`, `docs/ROADMAP.md`, and `docs/architecture/EXCEPTIONDESK_HEXAGONAL.md` before coding. Existing `docs/reference/` contains historical CaseProof research, not the current product definition.

**Product:** one app, finance-first. Dispute dossiers are a second workflow, not a second startup. Do not build insurance, trade-finance, general legal AI or a plugin marketplace without a decision record.

**Boundaries:** `packages.evidence_kernel` imports neither `domains` nor frameworks/ORM/LLM clients; `domains.finance` imports kernel primitives; adapters depend inward. Kernel facts are immutable. Reconciliation emits findings; it does not mutate source facts or assert that a mismatch proves wrongdoing. Source verification, corroboration and reviewer disposition are independent.

**Working procedure:** choose one vertical slice, write deterministic tests, report exact tests run and limitations. For substantial changes create `docs/tasks/<ID>.md`. No claims of tests passing without executing them. Do not merge/deploy/change production or contact customers without explicit approval. Preserve privacy, tenancy and evidence immutability invariants.

## Cloud-first verification (binding C25)

- **Markdown-only changes:** Review file scope, Markdown content and links; commit to feature branches without Python tests. Do not claim merge readiness.
- **Code, configuration, dependencies or migrations:** Require actual cloud-runner results (GitHub Actions or isolated cloud runner) for locked pytest, architecture checks, and affected Ruff, mypy, contract and security tests. Pushing a feature branch to trigger CI is allowed; missing or failing checks block merging.
- **CI unavailable:** Do not bypass implementation verification; report the blocker and prepare a patch or use an alternative verified cloud runner.
- **No autonomous merge/deploy.** Preserve all requirements of CONSTITUTION.md, including C12–C16, C21, C24 and C25.

## Mandatory database standard

Before any database-related task (SQL, ORM, migrations, repository adapters, RLS, Supabase membership/storage metadata, indexes or data-access API), **read `docs/standards/database-v1.md`** and relevant ADRs. If absent, stop and request the standard. Stage 0 is design-only: do not implement database schemas or migrations without separate approval.

**Run now:** `python -m unittest discover -s tests -v` (Python 3.11+). No infrastructure is required for the initial domain tests.

Existing `CLAUDE.md` and specialist instructions are subordinate to this current product definition where they refer to the old CaseProof-only MVP.

## Stage 1 trust contracts (mandatory design rules)
- A finding promoted beyond candidate must bind to an immutable versioned, resolvable typed evidence anchor. Citation resolution, content fidelity, semantic support and sufficiency are separate checks. Never equate exact quote matching with truth.
- Coverage must track scoped requirements, source inventory, processing/exclusion, unresolved issues and completion policy. A PROCESSED flag alone is not proof of complete investigation.
- Approved conclusions require an authorized decision and passing policy gates. A documented exception disposition may accept business risk but MUST NOT relabel contradictory or insufficient evidence as verified.
- Persisted evidence/decision changes must atomically record their audit event; in-memory Stage 1 prototypes have no durability guarantee. See ADRs 0008 and 0009.
- Pydantic belongs at I/O boundaries; keep the domain framework-independent. No autonomous promotion, no model confidence as an approval criterion.
