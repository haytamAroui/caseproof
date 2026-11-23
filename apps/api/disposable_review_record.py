"""Loopback/disposable review record port.

Same identity/authorization discipline as DisposableSignedBriefPublisher,
backed only by the disposable PostgreSQL stores. Never mounted in the main
API: it exists so the loopback development composition can export a genuine,
content-addressed record of the recorded state of a matter's working brief
(published head, recorded check runs, hash-chained human review events)
without any Supabase credential.

The record is a faithful transcript of recorded state, never a
reassessment: payload digests are recomputed and the review event hash
chain is replayed from the genesis hash, so a tampered row fails closed
instead of exporting. It approves nothing and files nothing.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from uuid import UUID

from application.litigation.matter_policy import MatterPermission, authorize_matter
from apps.api.access_control import VerifiedSubject
from apps.api.disposable_litigation_brief_graph import _canonical, _hash
from apps.api.disposable_litigation_review_ledger import ZERO_HASH, _digest
from apps.api.disposable_postgres_vault_ledger import Connection
from apps.api.disposable_signed_brief_publisher import working_brief_id
from apps.api.litigation_check_service import PrivateMatterAccess
from apps.api.signed_supabase_originals import PrivateStorageDenied

__all__ = ["DisposableSignedReviewRecord", "RecordConflict"]

_MAX_BEARER = 8192
_MAX_RUNS = 20
_MAX_EVENTS = 256
_ROLES = {"own_draft", "opponent_brief"}


class RecordConflict(ValueError):
    """Recorded state is missing, inconsistent or tampered."""


def _uuid(value: object) -> UUID:
    if not isinstance(value, (UUID, str)):
        raise RecordConflict("invalid stored identity")
    try:
        return UUID(str(value))
    except ValueError:
        raise RecordConflict("invalid stored identity") from None


class DisposableSignedReviewRecord:
    """PostgreSQL transcript adapter; no production wiring."""

    persistence = "disposable_postgres_only"

    def __init__(
        self,
        *,
        connect: Callable[[], Connection],
        verify_bearer: Callable[[str], VerifiedSubject],
        access_lookup: Callable[[str, str], PrivateMatterAccess | None],
    ) -> None:
        self._connect = connect
        self._verify = verify_bearer
        self._access = access_lookup

    def _authorize(self, bearer: str, case_id: str) -> tuple[UUID, UUID]:
        if (
            not isinstance(bearer, str)
            or not 0 < len(bearer) <= _MAX_BEARER
            or ("\r" in bearer or "\n" in bearer)
        ):
            raise PrivateStorageDenied("Missing or invalid signed identity")
        try:
            case = _uuid(case_id)
            subject = self._verify(bearer)
        except RecordConflict:
            raise PrivateStorageDenied("Missing or invalid signed identity") from None
        except Exception:
            raise PrivateStorageDenied("Missing or invalid signed identity") from None
        if not isinstance(subject, VerifiedSubject):
            raise PrivateStorageDenied("Missing or invalid signed identity")
        try:
            scope = self._access(subject.subject_id, case_id)
        except Exception:
            raise PrivateStorageDenied("Private matter unavailable") from None
        if not isinstance(scope, PrivateMatterAccess) or scope.case_id != case_id:
            raise PrivateStorageDenied("Private matter unavailable")
        try:
            decision = authorize_matter(
                actor_id=subject.subject_id,
                org_id=scope.org_id,
                case_id=case_id,
                action=MatterPermission.EVIDENCE_READ,
                membership=scope.member,
                grant=scope.grant,
            )
        except ValueError:
            raise PrivateStorageDenied("Private matter unavailable") from None
        if not decision.allowed:
            raise PrivateStorageDenied("Private matter unavailable")
        return _uuid(scope.org_id), case

    def record(self, *, bearer: str, case_id: str, document_role: str) -> dict[str, Any]:
        if document_role not in _ROLES:
            raise PrivateStorageDenied("Unknown document role")
        org, case = self._authorize(bearer, case_id)
        brief = working_brief_id(case_id, document_role)
        keys = (org, case, brief)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "select h.revision, v.version_id, v.graph_sha256, v.original_sha256, "
                "v.document_id, v.document_version_id, v.case_revision, v.exhibit_revision "
                "from caseproof._m2_brief_heads h "
                "join caseproof._m2_brief_versions v on v.org_id=h.org_id "
                "and v.case_id=h.case_id and v.brief_id=h.brief_id "
                "and v.version_id=h.version_id "
                "where h.org_id=%s and h.case_id=%s and h.brief_id=%s",
                keys,
            )
            heads = cur.fetchall()
            if len(heads) != 1 or type(heads[0][0]) is not int:
                raise PrivateStorageDenied("No published brief version")
            head = heads[0]
            (
                revision,
                version_id,
                graph_sha,
                original_sha,
                document_id,
                document_version_id,
                case_revision,
                exhibit_revision,
            ) = head
            cur.execute(
                "select snapshot_sha, payload_sha, payload, case_revision, "
                "exhibit_revision from caseproof._m2_check_runs "
                "where org_id=%s and case_id=%s and brief_version_id=%s "
                "order by snapshot_sha limit %s",
                (*keys[:2], str(version_id), _MAX_RUNS + 1),
            )
            runs = cur.fetchall()
            if len(runs) > _MAX_RUNS:
                raise RecordConflict("unbounded recorded check history")
            cur.execute(
                "select snapshot_sha, event_sha from caseproof._m2_review_heads "
                "where org_id=%s and case_id=%s",
                keys[:2],
            )
            review_heads = {str(row[0]): str(row[1]) for row in cur.fetchall()}
            cur.execute(
                "select snapshot_sha, revision, request_id, actor_id, event_sha, decision "
                "from caseproof._m2_review_events "
                "where org_id=%s and case_id=%s "
                "order by snapshot_sha, revision limit %s",
                (*keys[:2], _MAX_EVENTS + 1),
            )
            events = cur.fetchall()
            if len(events) > _MAX_EVENTS:
                raise RecordConflict("unbounded recorded review history")

        checks: list[dict[str, Any]] = []
        for snapshot_sha, payload_sha, payload, run_case_rev, run_exhibit_rev in runs:
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
                    "snapshot_sha256": str(snapshot_sha),
                    "payload_sha256": str(payload_sha),
                    "payload_sha256_verified": True,
                    "case_revision": run_case_rev,
                    "exhibit_revision": run_exhibit_rev,
                    "run": decoded,
                }
            )

        reviews: list[dict[str, Any]] = []
        by_snapshot: dict[str, list[tuple[object, ...]]] = {}
        for snapshot_sha, revision_no, request_id, actor_id, event_sha, raw_decision in events:
            by_snapshot.setdefault(str(snapshot_sha), []).append(
                (revision_no, str(request_id), str(actor_id), str(event_sha), raw_decision)
            )
        for snapshot_sha in sorted(by_snapshot):
            current = ZERO_HASH
            decisions: list[dict[str, Any]] = []
            rows = by_snapshot[snapshot_sha]
            for expected, (revision_no, request_id, actor_id, event_sha, raw) in enumerate(rows, 1):
                decision: Any = raw
                if isinstance(decision, str):
                    try:
                        decision = json.loads(decision)
                    except ValueError:
                        raise RecordConflict("unreadable recorded review event") from None
                if revision_no != expected or not isinstance(decision, dict):
                    raise RecordConflict("broken recorded review chain")
                actor = str(_uuid(actor_id))
                digest = _digest(
                    _canonical(
                        {
                            "run": snapshot_sha,
                            "revision": revision_no,
                            "request": str(_uuid(request_id)),
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
                        "request_id": str(_uuid(request_id)),
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
            "case_id": str(case),
            "document_role": document_role,
            "brief": {
                "brief_id": str(brief),
                "head_revision": revision,
                "head_version_id": str(version_id),
                "graph_sha256": str(graph_sha),
                "original_sha256": str(original_sha),
                "document_id": str(document_id),
                "document_version_id": str(document_version_id),
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
