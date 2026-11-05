"""Private two-reviewer pilot results evaluator; no files or source text in output."""
from __future__ import annotations

import json
from statistics import median
from typing import Any

SCHEMA = "caseproof-practitioner-study-v1"
MODES = ("manual", "caseproof")


class StudyEvidenceError(ValueError):
    """Refuse misleading or incomplete observations."""


def _count(value: Any) -> bool:
    return type(value) is int and value >= 0


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 96


def assess_study(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != SCHEMA:
        raise StudyEvidenceError("unknown study schema")
    if set(record) != {"schema", "data_class", "build_sha", "dossiers", "sessions"}:
        raise StudyEvidenceError("study must use a metadata-only contract")
    if not isinstance(record["data_class"], str) or record["data_class"] not in {
        "synthetic", "authorized_pilot"
    }:
        raise StudyEvidenceError("unknown authorization class")
    if not _identifier(record["build_sha"]):
        raise StudyEvidenceError("build identifier required")
    dossiers = record["dossiers"]
    sessions = record["sessions"]
    if not isinstance(dossiers, list) or not 3 <= len(dossiers) <= 5:
        raise StudyEvidenceError("three to five permissioned dossiers required")
    if not isinstance(sessions, list) or len(sessions) != 2 * len(dossiers):
        raise StudyEvidenceError("one manual and one assisted session per dossier required")

    facts = {}
    for dossier in dossiers:
        if not isinstance(dossier, dict) or set(dossier) != {
            "code", "input_sha256", "rights_ref", "gold_receipt_ref",
            "gold_label_reviewer_codes", "gold_references", "gold_errors",
            "contains_scan",
        }:
            raise StudyEvidenceError("dossier evidence incomplete")
        code = dossier["code"]
        if not _identifier(code) or code in facts:
            raise StudyEvidenceError("duplicate or invalid dossier code")
        if not all(_identifier(dossier[k]) for k in ("rights_ref", "gold_receipt_ref")):
            raise StudyEvidenceError("rights and independent gold evidence required")
        digest = dossier["input_sha256"]
        if not isinstance(digest, str) or len(digest) != 64 or any(
            c not in "0123456789abcdef" for c in digest
        ):
            raise StudyEvidenceError("immutable input digest missing")
        reviewers = dossier["gold_label_reviewer_codes"]
        if not isinstance(reviewers, list) or len(reviewers) != 2 or not all(
            _identifier(v) for v in reviewers
        ) or len(set(reviewers)) != 2:
            raise StudyEvidenceError("two independent gold reviewers required")
        if not _count(dossier["gold_references"]) or dossier["gold_references"] == 0:
            raise StudyEvidenceError("nonzero gold denominator required")
        if not _count(dossier["gold_errors"]) or dossier["gold_errors"] > dossier["gold_references"]:
            raise StudyEvidenceError("gold error count invalid")
        if type(dossier["contains_scan"]) is not bool:
            raise StudyEvidenceError("scan coverage must be explicit")
        facts[code] = dossier
    if not any(d["contains_scan"] for d in dossiers):
        raise StudyEvidenceError("pilot needs at least one scanned exhibit")

    seen = set()
    reviewers_by_mode = {mode: set() for mode in MODES}
    reviewers = set()
    measures = {mode: [] for mode in MODES}
    for row in sessions:
        if not isinstance(row, dict) or set(row) != {
            "dossier_code", "reviewer_code", "mode", "seconds",
            "caught_gold_errors", "false_verified", "abstentions",
            "wrong_source_or_page",
        }:
            raise StudyEvidenceError("session metadata incomplete")
        code = row["dossier_code"]
        mode = row["mode"]
        reviewer = row["reviewer_code"]
        if (not _identifier(code) or code not in facts or
            not isinstance(mode, str) or mode not in MODES or
            not _identifier(reviewer)):
            raise StudyEvidenceError("unrecognized reviewer, condition or dossier")
        if reviewer in facts[code]["gold_label_reviewer_codes"]:
            raise StudyEvidenceError("a trial reviewer cannot adjudicate own gold labels")
        identity = (code, mode)
        if identity in seen:
            raise StudyEvidenceError("duplicate condition or missing counterbalanced case")
        seen.add(identity)
        reviewers_by_mode[mode].add(reviewer)
        reviewers.add(reviewer)
        if (type(row["seconds"]) is not int or row["seconds"] <= 0 or
            not all(_count(row[k]) for k in (
                "caught_gold_errors", "false_verified", "abstentions", "wrong_source_or_page"
            ))):
            raise StudyEvidenceError("positive timing and nonnegative counts required")
        if (row["caught_gold_errors"] > facts[code]["gold_errors"] or
            any(row[k] > facts[code]["gold_references"] for k in (
                "false_verified", "abstentions", "wrong_source_or_page"
            ))):
            raise StudyEvidenceError("observation exceeds independent denominator")
        measures[mode].append(row)

    if len(reviewers) != 2 or any(reviewers_by_mode[mode] != reviewers for mode in MODES):
        raise StudyEvidenceError("same two independent trial reviewers must experience both modes")
    for code in facts:
        pair = [row for row in sessions if row["dossier_code"] == code]
        if len({row["reviewer_code"] for row in pair}) != 2:
            raise StudyEvidenceError("one trial reviewer cannot see both conditions for a dossier")

    denominator = sum(d["gold_errors"] for d in dossiers)
    reference_total = sum(d["gold_references"] for d in dossiers)
    outcomes: dict[str, Any] = {}
    for mode in MODES:
        rows = measures[mode]
        caught = sum(r["caught_gold_errors"] for r in rows)
        outcomes[mode] = {
            "gold_error_denominator": denominator,
            "caught_gold_errors": caught,
            "error_recall": round(caught / denominator, 4) if denominator else None,
            "gold_reference_denominator": reference_total,
            "false_verified": sum(r["false_verified"] for r in rows),
            "abstentions": sum(r["abstentions"] for r in rows),
            "wrong_source_or_page": sum(r["wrong_source_or_page"] for r in rows),
            "median_seconds": median(r["seconds"] for r in rows),
        }
    return {
        "schema": "caseproof-practitioner-measurement-v1",
        "data_class": record["data_class"],
        "dossier_count": len(dossiers),
        "reviewer_count": 2,
        "conditions": outcomes,
        "external_practitioner_approval_verified": False,
        "pilot_approved": False,
    }


def assess_private_file(path: str) -> dict[str, Any]:
    from pathlib import Path

    raw = Path(path).read_bytes()
    if not raw or len(raw) > 256_000:
        raise StudyEvidenceError("bounded private metadata required")
    try:
        data = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise StudyEvidenceError("invalid private study JSON") from exc
    return assess_study(data)
