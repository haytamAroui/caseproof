"""Verify a draft pack using trusted repository code; never extracts or executes ZIP files."""

import argparse
import json
from pathlib import Path

from application.dossiers.pack import MAX_PACK_BYTES, verify_pack


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack", type=Path)
    parser.add_argument("--expected-manifest")
    args = parser.parse_args()
    try:
        with args.pack.open("rb") as stream:
            raw = stream.read(MAX_PACK_BYTES + 1)
        print(json.dumps(verify_pack(raw, expected_manifest=args.expected_manifest), indent=2))
    except (ValueError, KeyError, TypeError, OSError):
        raise SystemExit("Pack verification failed; do not trust or open its contents.") from None


if __name__ == "__main__":
    main()
