"""Reap exact-owned development runs older than four hours."""
from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta

from scripts.m05_registry import stale_runs
from scripts.teardown_test_run import teardown


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--older-than-hours", type=int, default=4)
    args = parser.parse_args()
    if args.older_than_hours < 4:
        raise RuntimeError("minimum stale age is four hours")
    key = os.environ["CASEPROOF_DEV_AUTH_ADMIN_KEY"]
    cutoff = (datetime.now(UTC) - timedelta(hours=args.older_than_hours)).isoformat()
    runs = stale_runs(key, cutoff)
    failed = 0
    for run_id in runs:
        try:
            teardown(run_id, key)
        except Exception as exc:
            failed += 1
            print(f"REAPER_RUN_FAILED:{type(exc).__name__}", file=sys.stderr)
    if failed:
        raise RuntimeError(f"{failed} owned stale runs not cleaned")
    print(f"M05_REAPER_OK: processed {len(runs)} stale runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
