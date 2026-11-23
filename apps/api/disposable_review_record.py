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

from collections.abc import Callable
from typing import Any
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from application.litigation.matter_policy import MatterPermission, authorize_matter
from apps.api.access_control import VerifiedSubject
from apps.api.disposable_litigation_brief_graph import _canonical
from apps.api.disposable_postgres_vault_ledger import Connection
from apps.api.disposable_signed_brief_publisher import working_brief_id
from apps.api.litigation_check_service import PrivateMatterAccess
from apps.api.review_record_assembly import RecordConflict, assemble_record_body
from apps.api.signed_supabase_originals import PrivateStorageDenied

__all__ = ["DisposableSignedReviewRecord", "RecordConflict", "SIGNATURE_DOMAIN", "sign_record_body"]

SIGNATURE_DOMAIN = "caseproof-review-record-signature-v1"


def sign_record_body(body: dict[str, Any], signing_key: bytes) -> dict[str, str]:
    """Ed25519 receipt over the domain-separated canonical completed record.

    Binds the record (record_sha256 included) to the holder of signing_key.
    This is an installation signature: it proves production by a key holder
    and integrity since signing, never a personal, legal or eIDAS signature.
    The private key is configuration-held; only the public key is exported.
    """
    if type(signing_key) is not bytes or len(signing_key) != 32:
        raise RecordConflict("Ed25519 signing key must be 32 raw bytes")
    if body.get("schema") != "caseproof-review-record-v1" or "record_sha256" not in body:
        raise RecordConflict("only a completed review record can be signed")
    private = Ed25519PrivateKey.from_private_bytes(signing_key)
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    signed_doc = {"domain": SIGNATURE_DOMAIN, "record": body}
    signature = private.sign(_canonical(signed_doc).encode("utf-8"))
    return {
        "scheme": "ed25519",
        "domain": SIGNATURE_DOMAIN,
        "public_key": public.hex(),
        "signature": signature.hex(),
    }

_MAX_BEARER = 8192
_MAX_RUNS = 20
_MAX_EVENTS = 256
_ROLES = {"own_draft", "opponent_brief"}


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
        signing_key: bytes | None = None,
    ) -> None:
        self._connect = connect
        self._verify = verify_bearer
        self._access = access_lookup
        if signing_key is not None and (type(signing_key) is not bytes or len(signing_key) != 32):
            raise RecordConflict("Ed25519 signing key must be 32 raw bytes")
        self._signing_key = signing_key

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
            review_head_rows = [
                {"snapshot_sha256": str(row[0]), "event_sha256": str(row[1])}
                for row in cur.fetchall()
            ]
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

        check_rows = [
            {
                "snapshot_sha256": str(snapshot_sha),
                "payload_sha256": str(payload_sha),
                "payload": payload,
                "case_revision": run_case_rev,
                "exhibit_revision": run_exhibit_rev,
            }
            for snapshot_sha, payload_sha, payload, run_case_rev, run_exhibit_rev in runs
        ]
        event_rows = [
            {
                "snapshot_sha256": str(snapshot_sha),
                "revision": revision_no,
                "request_id": str(request_id),
                "actor_id": str(actor_id),
                "event_sha256": str(event_sha),
                "decision": raw_decision,
            }
            for snapshot_sha, revision_no, request_id, actor_id, event_sha, raw_decision in events
        ]
        # Same replay and assembly as the live adapter: one code path, one
        # canonicalization, fail-closed on tamper from either backend.
        body = assemble_record_body(
            case_id=str(case),
            document_role=document_role,
            brief={
                "brief_id": str(brief),
                "head_revision": revision,
                "version_id": str(version_id),
                "graph_sha256": str(graph_sha),
                "original_sha256": str(original_sha),
                "document_id": str(document_id),
                "document_version_id": str(document_version_id),
                "case_revision": case_revision,
                "exhibit_revision": exhibit_revision,
            },
            check_rows=check_rows,
            review_head_rows=review_head_rows,
            review_event_rows=event_rows,
        )
        if self._signing_key is not None:
            body["receipt"] = sign_record_body(body, self._signing_key)
        return body
