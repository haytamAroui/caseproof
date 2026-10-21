# ExceptionDesk — coding-agent instructions

Read `CONSTITUTION.md`, `README.md`, `docs/ROADMAP.md`, and `docs/architecture/EXCEPTIONDESK_HEXAGONAL.md` before coding. Existing `docs/reference/` contains historical CaseProof research, not the current product definition.

**Product:** one app, finance-first. Dispute dossiers are a second workflow, not a second startup. Do not build insurance, trade-finance, general legal AI or a plugin marketplace without a decision record.

**Boundaries:** `packages.evidence_kernel` imports neither `domains` nor frameworks/ORM/LLM clients; `domains.finance` imports kernel primitives; adapters depend inward. Kernel facts are immutable. Reconciliation emits findings; it does not mutate source facts or assert that a mismatch proves wrongdoing. Source verification, corroboration and reviewer disposition are independent.

**Working procedure:** choose one vertical slice, write deterministic tests, report exact tests run and limitations. For substantial changes create `docs/tasks/<ID>.md`. No claims of tests passing without executing them. Do not merge/deploy/change production or contact customers without explicit approval. Preserve privacy, tenancy and evidence immutability invariants.

**Run now:** `python -m unittest discover -s tests -v` (Python 3.11+). No infrastructure is required for the initial domain tests.

Existing `CLAUDE.md` and specialist instructions are subordinate to this current product definition where they refer to the old CaseProof-only MVP.
