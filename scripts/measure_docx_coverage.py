"""Roadmap task 6: measure what the Word reader sees and omits on DOCX files.

Runs the existing fail-closed region inventory (docx_region_inventory) over a
directory of .docx files and writes one measurement report: per-file regions
by kind and status, omission classes with their fail-closed reasons, and an
aggregate. The report always states which corpus kind it measured:

- synthetic: generated control files; validates the harness counts what it
  claims to count. NEVER presented as real Belgian acceptance.
- real: representative actual briefs; the measurement that feeds the task 7
  decision and sizes task 8.

Usage:
    uv run --locked python -m scripts.measure_docx_coverage \
        --dir PATH --corpus-kind synthetic|real [--out report.json]

Prints a Markdown summary; --out also writes the JSON report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict
from zipfile import ZipFile

from infrastructure.parsers.docx_region_inventory import inventory_docx_regions

HARNESS_VERSION = "caseproof-docx-coverage-measurement-v1"
OMISSION_KINDS = (
    "COMMENT_EXCLUDED",
    "HIDDEN_TEXT_EXCLUDED",
    "STRUCTURED_CONTENT",
    "UNKNOWN_WORD_PART",
)


class RegionRow(TypedDict):
    part: str
    kind: str
    status: str
    reason: str
    part_bytes: int | None


class FileRow(TypedDict):
    file: str
    sha256: str
    bytes: int
    coverage_unknown: bool
    fail_closed_reason: str | None
    regions: list[RegionRow]
    has_comments: bool
    has_tracked_revisions: bool
    has_hidden_text: bool
    has_structured_content: bool


class Aggregate(TypedDict):
    regions_by_kind: dict[str, int]
    regions_by_status: dict[str, int]
    fail_closed_reasons: dict[str, int]
    files_with_comments: int
    files_with_tracked_revisions: int
    files_coverage_unknown: int


class Report(TypedDict):
    harness_version: str
    corpus_kind: str
    measured_at: str
    directory: str
    file_count: int
    files: list[FileRow]
    aggregate: Aggregate


def _part_sizes(path: Path) -> dict[str, int]:
    try:
        with ZipFile(path) as archive:
            return {info.filename: info.file_size for info in archive.infolist()}
    except OSError:
        return {}


def measure_file(path: Path) -> FileRow:
    payload = path.read_bytes()
    coverage = inventory_docx_regions(payload)
    sizes = _part_sizes(path)
    regions: list[RegionRow] = [
        {
            "part": region.part,
            "kind": region.kind,
            "status": str(region.status),
            "reason": region.reason,
            "part_bytes": sizes.get(region.part),
        }
        for region in coverage.regions
    ]
    return {
        "file": path.name,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "coverage_unknown": coverage.coverage_unknown,
        "fail_closed_reason": coverage.reason,
        "regions": regions,
        "has_comments": any(r["kind"] == "COMMENT_EXCLUDED" for r in regions),
        "has_tracked_revisions": any(r["status"] == "REVISION_STATE_UNRESOLVED" for r in regions),
        "has_hidden_text": any(r["kind"] == "HIDDEN_TEXT_EXCLUDED" for r in regions),
        "has_structured_content": any(r["kind"] == "STRUCTURED_CONTENT" for r in regions),
    }


def build_report(directory: Path, corpus_kind: str) -> Report:
    files = sorted(directory.glob("*.docx"))
    measured = [measure_file(path) for path in files]
    kind_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    for entry in measured:
        for region in entry["regions"]:
            kind_counts[region["kind"]] += 1
            status_counts[region["status"]] += 1
        if entry["fail_closed_reason"]:
            reason_counts[entry["fail_closed_reason"]] += 1
    return {
        "harness_version": HARNESS_VERSION,
        "corpus_kind": corpus_kind,
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "directory": str(directory),
        "file_count": len(measured),
        "files": measured,
        "aggregate": {
            "regions_by_kind": dict(sorted(kind_counts.items())),
            "regions_by_status": dict(sorted(status_counts.items())),
            "fail_closed_reasons": dict(sorted(reason_counts.items())),
            "files_with_comments": sum(1 for e in measured if e["has_comments"]),
            "files_with_tracked_revisions": sum(1 for e in measured if e["has_tracked_revisions"]),
            "files_coverage_unknown": sum(1 for e in measured if e["coverage_unknown"]),
        },
    }


def render_markdown(report: Report) -> str:
    aggregate = report["aggregate"]
    lines = [
        f"# Word reader coverage measurement ({report['corpus_kind']} corpus)",
        "",
        f"Harness {report['harness_version']}, measured at {report['measured_at']}, "
        f"{report['file_count']} file(s).",
        "",
        "This report states what the reader SEES and what it OMITS per file. "
        + ("Synthetic control corpus: harness validation only, NOT Belgian acceptance."
           if report["corpus_kind"] == "synthetic"
           else "Real corpus: feeds the pilot decision (task 7) and sizes task 8."),
        "",
        "## Aggregate",
        "",
        "```json",
        json.dumps(aggregate, indent=2, sort_keys=True),
        "```",
        "",
        "## Per file",
        "",
        "| file | coverage_unknown | regions | omissions |",
        "| --- | --- | --- | --- |",
    ]
    for entry in report["files"]:
        omissions = sorted({r["kind"] for r in entry["regions"]
                            if r["kind"] in OMISSION_KINDS or r["status"] == "REVISION_STATE_UNRESOLVED"})
        lines.append(
            f"| {entry['file']} | {entry['coverage_unknown']} | {len(entry['regions'])} "
            f"| {', '.join(omissions) if omissions else '(none declared)'} |"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True, type=Path, help="directory of .docx files")
    parser.add_argument("--corpus-kind", required=True, choices=("synthetic", "real"))
    parser.add_argument("--out", type=Path, default=None, help="optional JSON report path")
    args = parser.parse_args(argv)
    if not args.dir.is_dir():
        print(f"not a directory: {args.dir}", file=sys.stderr)
        return 2
    report = build_report(args.dir, args.corpus_kind)
    if args.out:
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
