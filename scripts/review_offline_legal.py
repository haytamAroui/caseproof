"""Record local decisions on an offline legal review, or recheck a corrected Word. No network."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from apps.api.offline_review import recheck, record_decisions


def _write(path: Path, raw: bytes, checkpoint: str, scope: str) -> None:
    with path.open("xb") as handle:
        handle.write(raw)
    print(json.dumps({"output": str(path), "review_sha256": checkpoint, "scope": scope,
                      "attribution": "local_unauthenticated_label_not_lawyer_identity"}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    decide = commands.add_parser("decide", help="Add a decision to one finding; writes a new review")
    decide.add_argument("review", type=Path)
    decide.add_argument("--checkpoint", required=True, help="SHA-256 kept separately from the export")
    decide.add_argument("--finding", type=int, required=True, help="Finding number from 0")
    decide.add_argument("--action", choices=("confirm", "qualify", "reject", "waive"), required=True)
    decide.add_argument("--reason", default="")
    decide.add_argument("--label", required=True, help="Local reviewer label, not an authenticated identity")
    decide.add_argument("--output", type=Path, required=True)
    again = commands.add_parser("recheck", help="Check a corrected Word against the earlier review")
    again.add_argument("docx", type=Path)
    again.add_argument("--corpus", type=Path, required=True)
    again.add_argument("--previous", type=Path, required=True)
    again.add_argument("--exhibits", type=Path, help="Same exhibit directory as the first check")
    again.add_argument("--conditions", type=Path, help="Same conditions.toml as the first check")
    again.add_argument("--checkpoint", required=True)
    again.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "decide":
        raw, cp = record_decisions(pack=args.review.read_bytes(), checkpoint=args.checkpoint, decisions=[
            {"reference_index": args.finding, "action": args.action, "reason": args.reason,
             "reviewer_label": args.label}])
        _write(args.output, raw, cp, "local_decision_not_filing_approval")
    else:
        raw, cp = recheck(docx=args.docx, corpus=args.corpus, prior_pack=args.previous.read_bytes(),
                          prior_checkpoint=args.checkpoint, exhibits=args.exhibits,
                          conditions=args.conditions)
        _write(args.output, raw, cp, "legal_reference_slice_only")


if __name__ == "__main__":
    main()
