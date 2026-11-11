"""Metadata-only pilot readiness CLI. Neither approval nor client-data permission."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from application.pilot_readiness import load_and_validate
from application.pilot_study import assess_private_file


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--register",
        type=Path,
        default=Path("docs/pilot/PILOT_EXTERNAL_GATE_REGISTER.json"),
    )
    parser.add_argument(
        "--private-study",
        type=str,
        default=None,
        help="Local permissioned metadata only. Never upload private study to CI.",
    )
    args = parser.parse_args()
    decision = load_and_validate(args.register)
    print(json.dumps(decision, sort_keys=True))
    if args.private_study is not None:
        # Only aggregated counts, no client references/IDs/people/document content.
        print(json.dumps(assess_private_file(args.private_study), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
