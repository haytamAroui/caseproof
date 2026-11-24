"""Shared assembly of a completed review record from RAW recorded rows.

Both record ports converge here: the disposable adapter reads the rows with
direct SQL, the live adapter receives the same raw rows from the
caseproof_signed_review_record RPC. In every case the digests are recomputed
and the review hash chain is replayed HERE, in Python, with the exact
canonicalization that produced the recorded digests: a tampered row fails
closed no matter which backend served it. The record approves nothing and
files nothing; it is a faithful transcript of recorded state.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from apps.api.disposable_litigation_brief_graph import _canonical, _hash
from apps.api.disposable_litigation_review_ledger import ZERO_HASH, _digest

__all__ = ["RecordConflict", "assemble_record_body"]


class RecordConflict(ValueError):
    """Recorded state is missing, inconsistent or tampered."""

_MAX_RUNS = 20
_MAX_EVENTS = 256
_SHA256 = "0123456789abcdef"


def _uuid(value: object) -> UUID:
    if not isinstance(value, (UUID, str)):
        raise RecordConflict("invalid stored identity")
    try:
        return UUID(str(value))
    except ValueError:
        raise RecordConflict("invalid stored identity") from None


def _sha(value: object) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(ch not in _SHA256 for ch in value)
    ):
        raise RecordConflict("invalid stored digest")
    return value


def _counted(value: object, limit: int) -> list[Any]:
    if not isinstance(value, list) or len(value) > limit:
        raise RecordConflict("unbounded recorded history")
    return value


def assemble_record_body(
    *,
    case_id: str,
    document_role: str,
    brief: dict[str, Any],
    check_rows: list[Any],
    review_head_rows: list[Any],
    review_event_rows: list[Any],
) -> dict[str, Any]:
    """Replay and assemble the completed record, or raise RecordConflict."""
    case = str(_uuid(case_id))
    if document_role not in {"own_draft", "opponent_brief"}:
        raise RecordConflict("unknown document role")
    try:
        head_revision = brief["head_revision"]
        version_id = str(_uuid(brief["version_id"]))
        graph_sha = _sha(brief["graph_sha256"])
        original_sha = _sha(brief["original_sha256"])
        document_id = str(_uuid(brief["document_id"]))
        document_version_id = str(_uuid(brief["document_version_id"]))
        case_revision = brief["case_revision"]
        exhibit_revision = brief["exhibit_revision"]
    except (KeyError, TypeError):
        raise RecordConflict("recorded brief head incomplete") from None
    if (
        type(head_revision) is not int
        or head_revision < 1
        or type(case_revision) is not int
        or type(exhibit_revision) is not int
    ):
        raise RecordConflict("recorded brief head incomplete")

    checks: list[dict[str, Any]] = []
    for row in _counted(check_rows, _MAX_RUNS):
        try:
            snapshot_sha = _sha(row["snapshot_sha256"])
            payload_sha = _sha(row["payload_sha256"])
            payload = row["payload"]
            run_case_rev = row["case_revision"]
            run_exhibit_rev = row["exhibit_revision"]
        except (KeyError, TypeError):
            raise RecordConflict("recorded check row incomplete") from None
        if (
            not isinstance(payload, str)
            or _digest(payload) != payload_sha
            or type(run_case_rev) is not int
            or type(run_exhibit_rev) is not int
        ):
            raise RecordConflict("recorded check payload digest mismatch")
        try:
            decoded = json.loads(payload)
        except ValueError:
            raise RecordConflict("recorded check payload unreadable") from None
        checks.append(
            {
                "snapshot_sha256": snapshot_sha,
                "payload_sha256": payload_sha,
                "payload_sha256_verified": True,
                "case_revision": run_case_rev,
                "exhibit_revision": run_exhibit_rev,
                "run": decoded,
            }
        )

    review_heads: dict[str, str] = {}
    for row in _counted(review_head_rows, _MAX_EVENTS):
        try:
            review_heads[_sha(row["snapshot_sha256"])] = _sha(row["event_sha256"])
        except (KeyError, TypeError):
            raise RecordConflict("recorded review head incomplete") from None

    by_snapshot: dict[str, list[dict[str, Any]]] = {}
    for row in _counted(review_event_rows, _MAX_EVENTS):
        if not isinstance(row, dict):
            raise RecordConflict("recorded review event incomplete")
        try:
            by_snapshot.setdefault(_sha(row["snapshot_sha256"]), []).append(row)
        except (KeyError, TypeError):
            raise RecordConflict("recorded review event incomplete") from None

    reviews: list[dict[str, Any]] = []
    for snapshot_sha in sorted(by_snapshot):
        current = ZERO_HASH
        decisions: list[dict[str, Any]] = []
        rows = sorted(by_snapshot[snapshot_sha], key=lambda r: r.get("revision") or 0)
        for expected, row in enumerate(rows, 1):
            try:
                revision_no = row["revision"]
                request_id = str(_uuid(row["request_id"]))
                actor = str(_uuid(row["actor_id"]))
                event_sha = _sha(row["event_sha256"])
                raw = row["decision"]
            except (KeyError, TypeError):
                raise RecordConflict("recorded review event incomplete") from None
            decision: Any = raw
            if isinstance(decision, str):
                try:
                    decision = json.loads(decision)
                except ValueError:
                    raise RecordConflict("unreadable recorded review event") from None
            if revision_no != expected or not isinstance(decision, dict):
                raise RecordConflict("broken recorded review chain")
            digest = _digest(
                _canonical(
                    {
                        "run": snapshot_sha,
                        "revision": revision_no,
                        "request": request_id,
                        "actor": actor,
                        "previous_sha": current,
                        "decision": decision,
                    }
                )
            )
            if digest != event_sha or decision.get("actor_id") != actor:
                raise RecordConflict("tampered recorded review event")
            decisions.append(
                {
                    "revision": revision_no,
                    "request_id": request_id,
                    "actor_id": actor,
                    "event_sha256": event_sha,
                    "decision": decision,
                }
            )
            current = digest
        head_sha = review_heads.get(snapshot_sha)
        if head_sha is None or head_sha != current:
            raise RecordConflict("recorded review head mismatch")
        reviews.append(
            {
                "snapshot_sha256": snapshot_sha,
                "head_sha256": head_sha,
                "chain_verified": True,
                "decisions": decisions,
            }
        )

    body: dict[str, Any] = {
        "schema": "caseproof-review-record-v1",
        "case_id": case,
        "document_role": document_role,
        "brief": {
            "brief_id": str(brief.get("brief_id", "")),
            "head_revision": head_revision,
            "head_version_id": version_id,
            "graph_sha256": graph_sha,
            "original_sha256": original_sha,
            "document_id": document_id,
            "document_version_id": document_version_id,
            "case_revision": case_revision,
            "exhibit_revision": exhibit_revision,
        },
        "checks": checks,
        "reviews": reviews,
        "note": (
            "Transcript of recorded development state. Digests recomputed; "
            "review hash chain replayed. Not a legal approval or filing."
        ),
    }
    body["record_sha256"] = _hash(body)
    return body
