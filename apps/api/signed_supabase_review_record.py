"""Live SignedReviewRecord adapter over the pinned RPC surface.

The proposed caseproof_signed_review_record RPC (migration NOT applied)
replays the recorded digests and the review hash chain server side under
security definer and returns the completed record body. This adapter
validates the body shape, then applies the Ed25519 installation signature
with the service-held key (sign_record_body): the private key stays service
configuration, never database or client. The offline verifier independently
re-checks digest, chain and signature; this adapter does not reassess
content, and the record remains a transcript of recorded state, never an
approval or filing.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from apps.api.disposable_review_record import sign_record_body
from apps.api.signed_supabase_originals import PrivateStorageDenied, PrivateStorageFailure

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_ROLES = {"own_draft", "opponent_brief"}
_MAX_BODY_BYTES = 200_000

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
        if result.get("ok") is False:
            if result.get("error") == "denied":
                raise PrivateStorageDenied("Private record unavailable")
            raise ValueError("inconsistent recorded state")
        body = result.get("record")
        if (
            not isinstance(body, dict)
            or body.get("schema") != "caseproof-review-record-v1"
            or type(body.get("record_sha256")) is not str
            or not _SHA256.fullmatch(body["record_sha256"])
            or len(str(body)) > _MAX_BODY_BYTES
        ):
            raise PrivateStorageFailure("RPC result outside the signed contract")
        if self._signing_key is None:
            return body
        body["receipt"] = sign_record_body(body, self._signing_key)
        return body
