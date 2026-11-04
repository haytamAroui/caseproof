"""Offline DOCX editing harness for controlled local/synthetic acceptance.

This CLI neither authenticates against CaseProof nor writes to its source store.
It emits a candidate DOCX for manual review, never an activated draft.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from infrastructure.parsers.docx_structured_editing import (
    DocumentRevisionDecision,
    DocumentTextEdit,
    decide_document_revisions,
    edit_document_text,
    list_document_blocks,
    list_document_revisions,
)


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema") != "caseproof-docx-local-edit-plan-v1":
        raise ValueError("unsupported local editing plan")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("inspect", "edit", "review"))
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--list-targets", action="store_true")
    parser.add_argument("--list-revisions", action="store_true")
    parser.add_argument("--include-text", action="store_true")
    args = parser.parse_args()
    source = args.input.resolve(strict=True)
    original = source.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    if args.mode == "inspect":
        blocks = list_document_blocks(original)
        kinds: dict[str, int] = {}
        for block in blocks:
            kinds[block.kind] = kinds.get(block.kind, 0) + 1
        payload = {
            "schema": "caseproof-docx-local-inspection-v1",
            "source_sha256": digest,
            "paragraph_counts": kinds,
            "editable_plain_text_blocks": sum(b.editable for b in blocks),
            "limitations": "No review authority, tracking acceptance or CaseProof activation",
        }
        if args.list_targets:
            payload["targets"] = [
                {
                    "part": b.part,
                    "paragraph_index": b.paragraph_index,
                    "kind": b.kind,
                    "expected_text_sha256": b.text_sha256,
                    "editable": b.editable,
                    **({"before": b.text} if args.include_text else {}),
                }
                for b in blocks
            ]
        if args.list_revisions:
            payload["revisions"] = [
                {
                    "part": r.part, "revision_id": r.revision_id,
                    "kind": r.kind, "author": r.author,
                    "timestamp": r.timestamp,
                    "text_sha256": r.text_sha256,
                }
                for r in list_document_revisions(original)
            ]
        print(json.dumps(payload, sort_keys=True))
        return 0
    if args.output is None or args.plan is None:
        parser.error("--output and --plan are required for changes")
    output = args.output.resolve()
    if output == source or output.exists():
        raise ValueError("never overwrite an original or existing output")
    command = _json(args.plan)
    if command.get("source_sha256") != digest:
        raise ValueError("local plan does not bind to source bytes")
    if args.mode == "edit":
        raw = command.get("edits")
        if not isinstance(raw, list) or not raw:
            raise ValueError("missing edit operations")
        edits = []
        for entry in raw:
            if not isinstance(entry, dict) or set(entry) != {
                "part", "paragraph_index", "expected_text_sha256", "before", "after", "track_changes"
            }:
                raise ValueError("invalid edit fields")
            edits.append(DocumentTextEdit(**entry))
        candidate = edit_document_text(
            original, expected_sha256=digest, edits=edits,
            author=command["author"], timestamp=command["timestamp"],
        )
    else:
        raw = command.get("decisions")
        if not isinstance(raw, list) or not raw:
            raise ValueError("missing revision decisions")
        decisions = []
        for entry in raw:
            if not isinstance(entry, dict) or set(entry) != {"part", "revision_id", "action"}:
                raise ValueError("invalid review fields")
            decisions.append(DocumentRevisionDecision(**entry))
        candidate = decide_document_revisions(
            original, expected_sha256=digest, decisions=decisions,
        )
    # A local file write is not a CaseProof reviewed commit. Persist a new file
    # exclusively; never truncate an existing output or original.
    with output.open("xb") as file:
        file.write(candidate)
    print(json.dumps({
        "schema": "caseproof-docx-local-candidate-v1",
        "source_sha256": digest,
        "candidate_sha256": hashlib.sha256(candidate).hexdigest(),
        "candidate_bytes": len(candidate),
        "activated": False,
        "requires_human_review_and_recheck": True,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
