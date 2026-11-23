"""Live SignedReviewRecord adapter over the pinned RPC surface.

The proposed caseproof_signed_review_record RPC (db/proposals, NOT applied)
authenticates the signed user, authorizes evidence read on the matter and
returns the RAW recorded rows (brief head, check runs, review heads/events),
bounded. It never recomputes digests in SQL: this adapter replays the review
hash chain and re-verifies every payload digest with the exact Python
canonicalization (review_record_assembly), failing closed on any tamper.
The Ed25519 installation signature is then applied with the service-held key
(sign_record_body): the private key stays service configuration, never
database or client. The offline verifier independently re-checks digest,
chain and signature; the record remains a transcript of recorded state,
never an approval or filing.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from apps.api.disposable_review_record import RecordConflict, sign_record_body
from apps.api.review_record_assembly import assemble_record_body
from apps.api.signed_supabase_originals import PrivateStorageDenied, PrivateStorageFailure

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_ALLOWED_ROLES = {"own_draft", "opponent_brief"}
_MAX_RESULT_BYTES = 600_000

RpcCaller = Callable[..., Any]

__all__ = ["LiveSignedReviewRecord"]


class LiveSignedReviewRecord:
    """SignedReviewRecord over the live signed RPC surface."""

    def __init__(
        self, *, call_rpc: RpcCaller, publishable_key: str, signing_key: bytes | None = None
    ) -> None:
        if not callable(call_rpc) or not isinstance(publishable_key, str):
            raise ValueError("invalid live record composition")
        if signing_key is not None and (type(signing_key) is not bytes or len(signing_key) != 32):
            raise ValueError("Ed25519 signing key must be 32 raw bytes")
        self._rpc = call_rpc
        self._key = publishable_key
        self._signing_key = signing_key

    def record(self, *, bearer: str, case_id: str, document_role: str) -> dict[str, object]:
        if type(case_id) is not str or not _UUID.fullmatch(case_id):
            raise ValueError("invalid case_id")
        if document_role not in _ALLOWED_ROLES:
            raise PrivateStorageDenied("Unknown document role")
        result = self._rpc(
            publishable_key=self._key, bearer=bearer,
            name="caseproof_signed_review_record",
            args={"p_case": case_id, "p_role": document_role},
        )
        if not isinstance(result, dict):
            raise PrivateStorageFailure("RPC result outside the signed contract")
        if result.get("ok") is not True:
            if result.get("error") == "denied":
                raise PrivateStorageDenied("Private record unavailable")
            raise PrivateStorageFailure("RPC result outside the signed contract")
        brief = result.get("brief")
        checks = result.get("checks")
        review_heads = result.get("review_heads")
        review_events = result.get("review_events")
        if (
            not isinstance(brief, dict)
            or not isinstance(checks, list)
            or not isinstance(review_heads, list)
            or not isinstance(review_events, list)
            or len(json.dumps(result, ensure_ascii=False, default=str)) > _MAX_RESULT_BYTES
        ):
            raise PrivateStorageFailure("RPC result outside the signed contract")
        try:
            body = assemble_record_body(
                case_id=case_id,
                document_role=document_role,
                brief=brief,
                check_rows=checks,
                review_head_rows=review_heads,
                review_event_rows=review_events,
            )
        except RecordConflict:
            raise PrivateStorageFailure("recorded state failed replay verification") from None
        if self._signing_key is None:
            return body
        body["receipt"] = sign_record_body(body, self._signing_key)
        return body
