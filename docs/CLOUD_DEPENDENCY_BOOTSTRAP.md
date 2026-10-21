# Cloud dependency bootstrap — ExceptionDesk

## Problem
The initial repository has no `uv.lock`. Running `uv run --locked` before generating the lockfile cannot work. Dependencies do not have to be preinstalled before locking; `uv lock` resolves them from the configured package registry and writes the lockfile.

## One-time bootstrap (trusted cloud runner with PyPI access)
1. Review `pyproject.toml`, including Python support range and the `dev` dependency group. Ensure `ruff` and `mypy` are in the dev group alongside `pytest` and `httpx`.
2. Install a pinned `uv` version (initially 0.10.0, subject to review).
3. Run `uv lock` (network access is required for uncached packages). Do not use `--offline` unless the full dependency metadata is cached.
4. Run `uv sync --locked --group dev`.
5. Run `uv run --locked ruff check .`, `uv run --locked mypy packages/evidence_kernel`, `uv run --locked pytest -q`, and `uv run --locked python scripts/check_architecture.py`.
6. Commit `pyproject.toml` and `uv.lock` together to the feature branch only after lock generation and actual checks are recorded. Review failures instead of suppressing them.

## Every subsequent cloud CI run
Run `uv sync --locked --group dev` before the test commands. Never regenerate `uv.lock` implicitly during ordinary CI. Missing/stale lockfile is a CI failure. Use an isolated runner with package-registry access; cache accelerates installs but is not a correctness prerequisite.

## Scope and security
No secrets are required to resolve public Python dependencies. Do not embed credentials in lockfiles. Do not deploy or merge based only on successful dependency installation. Existing code and security checks remain mandatory.

## Observed environment limitation (2026-10-21)
`uv` 0.10.0 is installed. `uv lock --offline` fails because FastAPI metadata is not cached; `uv lock` fails because DNS for pypi.org is unavailable. No lockfile was generated. Do not fabricate one from installed package versions.
