"""Recover ONLY explicitly enumerated PR202-owned failed synthetic CI runs.

Uses official GoTrue Admin deletion and the existing protected, run-scoped
fixture cleanup; never guesses resource ownership or deletes unrelated data.
"""
from __future__ import annotations

import os
from uuid import UUID

from scripts.m05_registry import call, rows
from scripts.teardown_test_run import teardown


def main() -> int:
    if os.environ.get("GITHUB_REPOSITORY") != "haytamAroui/caseproof":
        raise RuntimeError("RIGHTS_RECOVERY_PROTECTED_REPOSITORY_REQUIRED")
    key = os.environ["CASEPROOF_DEV_AUTH_ADMIN_KEY"]
    raw = os.environ.get("CASEPROOF_RIGHTS_RECOVERY_RUN_IDS", "")
    runs = [str(UUID(x)) for x in raw.split(",") if x]
    if len(runs) > 5 or len(set(runs)) != len(runs):
        raise RuntimeError("RIGHTS_RECOVERY_RUN_ALLOWLIST_INVALID")
    for run in runs:
        entries = rows(key, run)
        if not entries:
            continue
        roots = [e for e in entries if e["resource_type"] == "run" and e["resource_id"] == run]
        matters = [e for e in entries if e["resource_type"] == "matter" and e["state"] == "CREATED"]
        owner = [e for e in entries if e["resource_type"] == "auth_user"
                 and e["resource_id"].startswith("owner:")
                 and e["state"] == "CREATED" and "@" not in e["resource_id"]]
        if len(roots) != 1 or len(matters) != 1 or len(owner) != 1:
            raise RuntimeError("RIGHTS_RECOVERY_UNVERIFIED_TEST_SCOPE")
        # These are exact-owned runs created by the PR202 signed test.
        teardown(run, key)
        if call(key, "verify", run) is not True:
            raise RuntimeError("RIGHTS_RECOVERY_RESIDUAL_FOUND")
        print("RIGHTS_PREVIOUS_SIGNED_FIXTURE_RECOVERED", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
