# Stage 0: Evidence Kernel engineering baseline

Status: implementation in progress. CI runner, locked dependencies, and complete branch checks remain unverified.

## Scope

- Python 3.11+ with pyproject.toml and uv dependency locking.
- Pure Python evidence domain, independent of sectors, HTTP, databases and SDKs.
- Source verification, corroboration and reviewer decisions are independent states.
- Authenticated tenant scope belongs to application adapters; untrusted tenant headers are not authorization.
- No database schema, migrations, production release or external customer actions in this stage.

## Verification commands

Run from the repository root in an internet-enabled isolated cloud workspace:

```sh
uv lock --python 3.11
uv sync --locked --group dev --python 3.11
uv run --locked python scripts/check_architecture.py
uv run --locked python -m compileall -q packages apps domains
uv run --locked pytest -q
uv run --locked ruff check .
uv run --locked mypy packages/evidence_kernel
```

The architecture script uses only the standard library and can be run independently when dependencies are unavailable. Such a check does not substitute for locked tests.

## Acceptance criteria

1. A committed uv.lock is reproducible in an isolated cloud runner.
2. Architecture checks and a negative-control forbidden-import test pass.
3. Full branch unit, security and API contract tests pass.
4. Ruff and mypy pass or any explicitly approved exceptions are documented.
5. Human review and protected branch settings are verified before merge.
6. The verification report includes source commit, environment, commands and exit statuses.

## Current blockers

GitHub Actions is failing before executing job steps. A complete branch test run and lockfile have not been obtained. Therefore Stage 0 is not yet operationally complete and no merge readiness is claimed.

See docs/quality/CLOUD_FALLBACK_VERIFICATION.md and docs/CLOUD_DEPENDENCY_BOOTSTRAP.md.
