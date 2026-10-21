# Stage 0 — Engineering foundation (independent execution)

Status: **Stage 0 implementation complete within the owner's deferred CI/lockfile scope; full-branch verification outstanding**.
Owner direction (2026-10-21): defer GitHub Actions and uv.lock work. Neither is a prerequisite for continuing Stage 0 implementation. This is not an exemption from tests, security review or merge gates.

## Delivered

- Binding constitution and architecture rules; sector-neutral kernel boundary.
- Python project and dependency declarations in pyproject.toml.
- Architecture checker and positive/negative regression tests.
- Independent verification entrypoint: `python scripts/verify_stage0.py`.
- Source/claim, persistence and API boundary ADRs (0006 and 0007).
- Versioned API surface contract `contracts/kernel-api.v1.json` and drift/security tests `tests/test_kernel_api_contract_v1.py`.
- Git hooks run Python architecture and pytest without `uv.lock`.
- Test matrix, cloud fallback policy, database standards and scoped agent instructions.
- Feature-branch development only. No migrations, production tenant auth, customer documents, merge or deployment.

## Run without GitHub Actions or uv.lock

From the exact branch checkout with Python 3.11+ and declared development dependencies already installed:

```sh
python scripts/verify_stage0.py
```

The script runs the architecture guard, compilation, full pytest, Ruff and mypy; it reports missing tools as **BLOCKED** and exits nonzero. It does not pretend that dependency locking has succeeded.

To run individual checks:

```sh
python scripts/check_architecture.py
python -m compileall -q packages domains apps
python -m pytest -q
python -m ruff check .
python -m mypy packages/evidence_kernel
```

## Evidence collected (2026-10-21)

In a separate cloud workspace, the *previously prepared Stage 0–3 review ZIP* (not a checkout of the latest GitHub branch) ran its test files with **17 passed in 0.46 seconds**, exit 0. Python compilation of `packages` and `apps` exited 0. This is patch-level evidence only. Ruff and mypy were not available there. No claim is made that the latest branch passed.

## Deferred / merge-blocking items

- `uv.lock` and reproducible locked installation: deferred at owner request.
- GitHub Actions runner availability: deferred at owner request.
- Full checkout `python scripts/verify_stage0.py` run: outstanding.
- Ruff, mypy, execution of newly added API contract tests, negative-control execution and tenant security checks: outstanding until independently run.
- Required branch protection and human review: unverified.

**Stage 0 implementation may continue and Stage 1 can be developed in parallel. No merge or release is authorized until all applicable gates pass.**

See `docs/quality/CLOUD_FALLBACK_VERIFICATION.md`, `docs/adr/0006-kernel-api-contracts.md` and `docs/adr/0007-kernel-persistence-boundary.md`.
