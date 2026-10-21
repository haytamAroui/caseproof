# Kernel development when GitHub Actions is unavailable

**Decision (2026-10-21):** Runner outages must not prevent feature-branch development. They **do** prevent merging or releasing changes whose required verification is incomplete. This is a verification fallback, not a waiver of tests or tenant/security review.

## Independent cloud workspace fallback

1. Obtain the exact feature-branch source and dependencies in a trusted isolated cloud workspace (Codespaces, a hosted CI runner outside GitHub Actions, or the current execution workspace).
2. Record interpreter and installed package versions. Install declared dependencies using the package registry when accessible. When no lockfile exists and the registry is unavailable, execute tests against available dependencies but label the result **non-reproducible**.
3. Execute `python -m pytest -q`, `python scripts/check_architecture.py`, `python -m compileall -q packages apps`, and where available `ruff check .` and `mypy packages/evidence_kernel`. Report exact exit status and tests. Never call unavailable checks passed.
4. Commit work to a feature branch with its verification report, even if some checks remain blocked. Do not merge/deploy until all mandatory checks pass.
5. Once an internet-enabled runner is available, execute `uv lock`, commit `uv.lock`, run `uv sync --locked --group dev` and all required checks. Preserve the lockfile for all later work.
6. Keep the GitHub Actions bootstrap workflow manually triggered during runner outage to avoid repetitive pre-step failures. GitHub Actions is optional for development commits, not a substitute for merge gates.

## Current independently observed test evidence
- Workspace: cloud Python 3.13 environment, 2026-10-21.
- Source: previously prepared Stage 0–3 Evidence Kernel review ZIP, **not yet a GitHub branch commit**.
- Command: `PYTHONPATH=. pytest -q tests/test_kernel_contract_v1.py tests/test_workflow_v1.py tests/test_kernel_api.py tests/test_openapi_contract.py`.
- Result: **17 passed in 0.44s**, exit code 0.
- Available packages: FastAPI 0.128.2, pytest 9.0.2, HTTPX 0.28.1.
- Ruff and mypy unavailable; no `uv.lock`; offline `uv lock` failed because FastAPI metadata was not cached; GitHub cloning and PyPI were blocked by DNS. **No full-repository architecture check or locked dependency run was verified.**

This is evidence of a tested patch, **not** a merge-ready release.
