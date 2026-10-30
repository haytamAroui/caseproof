"""M0.5 stale-run reaper (fail closed until protected ledger access is wired).

No destructive operation is permitted from a guessed email prefix or age alone.
Each run must be resolved through the protected database ownership ledger and
reconciled against exact resource IDs before deletion.
"""
from __future__ import annotations

import argparse
import sys
from datetime import timedelta


STALE_AFTER = timedelta(hours=4)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--older-than-hours", type=int, default=4)
    args = parser.parse_args()
    if args.older_than_hours < 4:
        print("REAPER_REFUSED: minimum age is four hours", file=sys.stderr)
        return 2
    # Intentionally refuse until the same exact-owned cleanup engine is
    # available for both the protected acceptance and scheduled recovery.
    print("REAPER_BLOCKED: durable ledger read and scoped teardown not wired", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
