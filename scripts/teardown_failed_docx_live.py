"""One-time exact-owned cleanup of the failed 5-Nov synthetic DOCX test run.

The run's Storage is already empty and its owned dossier was deleted by the
protected Postgres cleanup RPC after guard remediation. This completes only
its remaining GoTrue users and M0.5 ownership ledger via the usual admin API.
No production/user matters or unregistered identities are touched.
"""
from __future__ import annotations

import os
from datetime import datetime

from scripts.m05_registry import rows, stale_runs
from scripts.teardown_test_run import teardown

START = datetime.fromisoformat("2026-11-05T08:36:00+00:00")
END = datetime.fromisoformat("2026-11-05T08:40:00+00:00")


def main() -> None:
    key = os.environ["CASEPROOF_DEV_AUTH_ADMIN_KEY"]
    candidates = []
    for run in stale_runs(key, END.isoformat()):
        entries = rows(key, run)
        roots = [r for r in entries if r["resource_type"] == "run" and r["resource_id"] == run]
        if len(roots) != 1:
            continue
        created = datetime.fromisoformat(roots[0]["created_at"].replace("Z", "+00:00"))
        if not START <= created < END:
            continue
        kinds = [r["resource_type"] for r in entries]
        if (kinds.count("run") != 1 or kinds.count("matter") != 1
            or kinds.count("storage_file") != 0 or kinds.count("auth_user") != 3):
            raise RuntimeError("M05_DOCX_OLD_RUN_OWNERSHIP_SHAPE_UNEXPECTED")
        owners = [
            r for r in entries
            if r["resource_type"] == "auth_user" and r["resource_id"].startswith("owner:")
            and "@" not in r["resource_id"]
        ]
        if len(owners) != 1:
            raise RuntimeError("M05_DOCX_OLD_RUN_OWNER_NOT_UNIQUE")
        candidates.append(run)
    if len(candidates) != 1:
        raise RuntimeError("M05_DOCX_EXPECTED_EXACTLY_ONE_OLD_OWNED_RUN")
    teardown(candidates[0], key)
    if rows(key, candidates[0]):
        raise RuntimeError("M05_DOCX_OLD_OWNERSHIP_STILL_PRESENT")
    print("M05_DOCX_OLDER_FAILED_RUN_AUTH_AND_LEDGER_EMPTY_VERIFIED", flush=True)


if __name__ == "__main__":
    main()
