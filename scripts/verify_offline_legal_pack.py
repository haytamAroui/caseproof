"""Cold verification of a legal-review slice exported by the workbench.

No network, database or installed corpus is needed. The checkpoint must come
from a separate trusted channel. It detects changes, not legal correctness.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from application.litigation.offline_legal_pack import verify_legal_pack


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    body = verify_legal_pack(args.pack.read_bytes(), expected_sha256=args.expected_sha256)
    print(json.dumps({"integrity": "checkpoint_matched_and_legal_checks_replayed",
                      "corpus_pack_sha256": body["corpus_pack_sha256"],
                      "references": [{"status": r["status"], "reason": r["reason"],
                                      "version": r["corpus_version"]} for r in body["references"]],
                      "scope": "legal_reference_slice_only", "applicability": "not_assessed"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
