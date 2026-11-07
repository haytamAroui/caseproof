"""Offline pilot-evidence preflight. Metadata only; never authorizes client data.

The input is an *untrusted register*. Human identity, signatures, permission to
test, professional-secrecy compliance and production controls cannot be
established from a JSON file or synthetic CI.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED_GATES = (
    "D01", "T61", "T70", "T72", "T73",
    "T74", "T75", "T76", "T78", "T79",
)
STATES = frozenset({"OPEN", "EVIDENCED", "APPROVED", "BLOCKED"})
SCHEMA = "caseproof-pilot-external-gates-v1"


class PilotEvidenceError(ValueError):
    """Untrusted, incomplete or contradictory approval metadata."""


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 1024


def validate_register(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != SCHEMA:
        raise PilotEvidenceError("unknown pilot gate schema")
    if set(record) != {"schema", "build_sha", "environment", "data_class", "gates"}:
        raise PilotEvidenceError("unknown or missing register fields")
    if not all(_text(record[k]) for k in ("build_sha", "environment", "data_class")):
        raise PilotEvidenceError("build, environment and data class required")
    if not isinstance(record["gates"], dict) or set(record["gates"]) != set(REQUIRED_GATES):
        raise PilotEvidenceError("complete exact mandatory gate set required")
    outstanding: list[str] = []
    approvals_for_owner_review: list[str] = []
    for gate in REQUIRED_GATES:
        value = record["gates"][gate]
        if not isinstance(value, dict) or set(value) != {
            "status", "owner_role", "reviewer", "reviewed_at",
            "evidence_ref", "independent_receipt_sha256",
        }:
            raise PilotEvidenceError("gate metadata incomplete: " + gate)
        if not isinstance(value["status"], str) or value["status"] not in STATES:
            raise PilotEvidenceError("unknown gate status: " + gate)
        if not _text(value["owner_role"]):
            raise PilotEvidenceError("named accountable role missing: " + gate)
        fields = ("reviewer", "reviewed_at", "evidence_ref", "independent_receipt_sha256")
        if value["status"] == "APPROVED":
            if not all(_text(value[k]) for k in fields):
                raise PilotEvidenceError("approval claims must cite external receipt: " + gate)
            sha = value["independent_receipt_sha256"]
            if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
                raise PilotEvidenceError("receipt digest invalid: " + gate)
            approvals_for_owner_review.append(gate)
        else:
            outstanding.append(gate)
    return {
        "schema": "caseproof-pilot-preflight-v1",
        "build_sha": record["build_sha"],
        "environment": record["environment"],
        "gates_requiring_external_review": outstanding,
        "claimed_approvals_not_cryptographically_verified": approvals_for_owner_review,
        "ready_for_human_final_decision": not outstanding,
        "machine_approves_pilot": False,
        "machine_authorizes_client_data": False,
    }


def load_and_validate(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if not raw or len(raw) > 128_000:
        raise PilotEvidenceError("bounded metadata file required")
    try:
        value = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise PilotEvidenceError("invalid metadata JSON") from exc
    return validate_register(value)
