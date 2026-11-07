"""Prepare local, blinded CaseProof P1 reviewer packets or score completed trials.

No network calls, no applicant identification, no auto-generated legal labels.
Evidence is read from a bounded, rights-cleared local fixture directory.
Never use unreviewed real client data or claim this authenticates reviewers.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from application.litigation.reviewer_benchmark import (
    SUBMISSIONS_SCHEMA,
    BenchmarkInvalid,
    make_blinded_packets,
    score_completed_trial,
    validate_cases,
)

MAX_SOURCE_BYTES = 20 * 1024 * 1024


def _read_json(path: Path) -> dict[str, Any]:
    value: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BenchmarkInvalid("root must be a JSON object")
    return value


def verify_source_bytes(cases: list[dict[str, Any]], source_root: Path) -> None:
    """Check real PDF bytes + digest + physical page; not legal or OCR verification."""
    root = source_root.resolve(strict=True)
    for case in cases:
        relative = Path(case["source_pdf"])
        if relative.is_absolute() or ".." in relative.parts or relative.suffix.lower() != ".pdf":
            raise BenchmarkInvalid("PDF must be a relative local path inside source root")
        try:
            target = (root / relative).resolve(strict=True)
            if not target.is_relative_to(root):
                raise BenchmarkInvalid("PDF escaped authorized source root")
            if target.stat().st_size > MAX_SOURCE_BYTES:
                raise BenchmarkInvalid("PDF exceeds bounded evidence limit")
            data = target.read_bytes()
            if not data.startswith(b"%PDF-"):
                raise BenchmarkInvalid("source is not a PDF")
            if hashlib.sha256(data).hexdigest() != case["source_sha256"]:
                raise BenchmarkInvalid("source version SHA256 mismatch")
            reader = PdfReader(io.BytesIO(data), strict=True)
            if reader.is_encrypted:
                raise BenchmarkInvalid("encrypted PDF must be reviewed separately")
            if case["physical_pdf_page"] > len(reader.pages):
                raise BenchmarkInvalid("physical PDF page outside real original")
        except (OSError, ValueError, KeyError) as error:
            if isinstance(error, BenchmarkInvalid):
                raise
            raise BenchmarkInvalid("source cannot be independently read and pinned") from error


def _exclusive_json(destination: Path, value: object) -> None:
    data = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(destination, flags, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)


def prepare(
    *,
    cases_path: Path,
    reviewers_path: Path,
    source_root: Path,
    seed: str,
    destination: Path,
) -> dict[str, Any]:
    case_file = _read_json(cases_path)
    cases = case_file.get("cases")
    if not isinstance(cases, list) or any(not isinstance(c, dict) for c in cases):
        raise BenchmarkInvalid("case manifest must contain case records")
    validate_cases(cases)
    reviewer_file = _read_json(reviewers_path)
    reviewers = reviewer_file.get("reviewer_languages")
    if not isinstance(reviewers, dict):
        raise BenchmarkInvalid("reviewers file requires reviewer_languages")
    verify_source_bytes(cases, source_root)
    packets, manifest = make_blinded_packets(cases, reviewers, seed=seed)
    # We intentionally do not copy original PDFs or author labels into packets.
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    packet_dir = destination / "participant_packets"
    packet_dir.mkdir(mode=0o700)
    template_dir = destination / "empty_submissions"
    template_dir.mkdir(mode=0o700)
    _exclusive_json(destination / "private_assignments.json", manifest)
    for index, packet in enumerate(packets, start=1):
        name = f"reviewer-{index:02d}.json"
        _exclusive_json(packet_dir / name, packet)
        blank = {
            "schema": SUBMISSIONS_SCHEMA,
            "status": "EMPTY_TEMPLATE_NOT_A_HUMAN_RESULT",
            "decisions": [
                {
                    "assignment_id": row["assignment_id"],
                    "reviewer_id": packet["reviewer_id"],
                    "case_ref": row["case_ref"],
                    "condition": packet["condition"],
                    "source_version_id": row["source_version_id"],
                    "source_sha256": row["source_sha256"],
                    "physical_pdf_page": row["physical_pdf_page"],
                    "decision": None,
                    "elapsed_ms": None,
                    "inspected_original": False,
                    "rationale": "",
                    "confidence": None,
                    "warning_helpful": None,
                }
                for row in packet["cases"]
            ],
        }
        _exclusive_json(template_dir / name, blank)
    return {
        "schema": "caseproof-p1-preparation-receipt-v1",
        "participants": len(packets),
        "assignments": len(manifest["assignments"]),
        "balanced_for_descriptive_arm_comparison":
            manifest["balanced_for_descriptive_arm_comparison"],
        "source_pdf_digest_and_page_verified": True,
        "human_results_collected": False,
        "gold_labels_verified": False,
        "genuine_user_review_completed": False,
        "output": str(destination),
        "notice": "Local synthetic/rights-cleared evidence only; no legal or identity attestation.",
    }


def score(
    *,
    assignments_path: Path,
    gold_path: Path,
    submissions_path: Path,
    destination: Path,
) -> dict[str, Any]:
    result = score_completed_trial(
        _read_json(assignments_path),
        _read_json(gold_path),
        _read_json(submissions_path),
    )
    _exclusive_json(destination, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="command", required=True)
    prep = modes.add_parser("prepare", help="Verify originals and create blinded local packets")
    prep.add_argument("--cases", type=Path, required=True)
    prep.add_argument("--reviewers", type=Path, required=True)
    prep.add_argument("--source-root", type=Path, required=True)
    prep.add_argument("--seed", required=True)
    prep.add_argument("--out", type=Path, required=True)
    evaluation = modes.add_parser("score", help="Score complete external human submissions only")
    evaluation.add_argument("--assignments", type=Path, required=True)
    evaluation.add_argument("--gold", type=Path, required=True)
    evaluation.add_argument("--submissions", type=Path, required=True)
    evaluation.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(
            cases_path=args.cases, reviewers_path=args.reviewers,
            source_root=args.source_root, seed=args.seed, destination=args.out,
        )
    else:
        result = score(
            assignments_path=args.assignments,
            gold_path=args.gold,
            submissions_path=args.submissions,
            destination=args.out,
        )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
