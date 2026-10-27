"""One verified Supabase JWT → private PostgREST source version → Storage bytes.

No server-owner database connection. Metadata is resolved from installed
security_invoker view, not trusted from client-supplied tenant/hash/path.
Storage checks the same actor's actual JWT and the current matter grant.
"""
from __future__ import annotations

import http.client
import json
from dataclasses import dataclass, field
from uuid import UUID

from apps.api.signed_supabase_originals import (
    MAX_BYTES,
    MIME,
    OriginalRef,
    PrivateStorageDenied,
    PrivateStorageFailure,
    PrivateStorageIntegrityError,
    PrivateStorageOutcomeUnknown,
    SignedOriginalsStorage,
)

PROJECT_HOST = "ldwmocpxwskvhoojndrd.supabase.co"
MAX_METADATA_BYTES = 8192


def _uuid(raw: object) -> UUID:
    if not isinstance(raw, str):
        raise PrivateStorageDenied("Masked or malformed source identifier")
    try:
        value = UUID(raw)
    except (TypeError, AttributeError, ValueError):
        raise PrivateStorageDenied("Masked or malformed source identifier") from None
    if str(value) != raw or value.int == 0:
        raise PrivateStorageDenied("Masked or malformed source identifier")
    return value


@dataclass(frozen=True, slots=True)
class SignedSourceLibrary:
    storage: SignedOriginalsStorage
    timeout_seconds: float = 12.0
    _key: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_key", self.storage.publishable_key)
        if not 0.1 <= self.timeout_seconds <= 30.0:
            raise ValueError("Invalid signed source lookup timeout")

    def source(
        self, *, bearer: str, case_id: str, document_id: str, version_id: str,
    ) -> tuple[OriginalRef, int]:
        requested = (_uuid(case_id), _uuid(document_id), _uuid(version_id))
        if not isinstance(bearer, str) or not 0 < len(bearer) <= 8192 or (
            "\r" in bearer or "\n" in bearer
        ):
            raise PrivateStorageDenied("Missing or invalid signed identity")
        # Inputs are canonical UUIDs, never URL-embedded untrusted fragments.
        path = (
            "/rest/v1/caseproof_private_source_versions?"
            "select=org_id,case_id,document_id,version_id,"
            "original_sha256_hex,byte_length,media_type"
            f"&case_id=eq.{case_id}&document_id=eq.{document_id}"
            f"&version_id=eq.{version_id}&limit=2"
        )
        conn = http.client.HTTPSConnection(PROJECT_HOST, timeout=self.timeout_seconds)
        try:
            conn.request(
                "GET", path,
                headers={
                    "apikey": self._key,
                    "Authorization": "Bearer " + bearer,
                    "Accept": "application/json",
                    "Cache-Control": "no-store",
                },
            )
            response = conn.getresponse()
            status, raw = response.status, response.read(MAX_METADATA_BYTES + 1)
        except (OSError, TimeoutError, http.client.HTTPException):
            raise PrivateStorageOutcomeUnknown("Private source lookup unavailable") from None
        finally:
            conn.close()
        if status in (400, 401, 403, 404):
            raise PrivateStorageDenied("Private source unavailable") from None
        if status != 200 or len(raw) > MAX_METADATA_BYTES:
            raise PrivateStorageOutcomeUnknown("Private source lookup incomplete") from None
        try:
            rows = json.loads(raw.decode("utf-8"))
        except (UnicodeError, ValueError):
            raise PrivateStorageOutcomeUnknown("Invalid signed source metadata") from None
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise PrivateStorageDenied("Source version not uniquely authorized") from None
        obj: dict[str, object] = rows[0]
        try:
            org_id = _uuid(obj["org_id"])
            refs = tuple(_uuid(obj[k]) for k in ("case_id", "document_id", "version_id"))
            digest = obj["original_sha256_hex"]
            mime = obj["media_type"]
            length = obj["byte_length"]
            if refs != requested or type(length) is not int or not 0 < length <= MAX_BYTES:
                raise ValueError("Nonmatching version or unsafe size")
            if not isinstance(digest, str) or not isinstance(mime, str) or mime not in MIME:
                raise ValueError("Unsafe content metadata")
            ref = OriginalRef(org_id, *refs, digest, mime)
        except (KeyError, TypeError, ValueError):
            raise PrivateStorageIntegrityError("Private source metadata inconsistent") from None
        return ref, length

    def read(
        self, *, bearer: str, case_id: str, document_id: str, version_id: str,
    ) -> bytes:
        ref, length = self.source(
            bearer=bearer, case_id=case_id,
            document_id=document_id, version_id=version_id,
        )
        data = self.storage.get_verified(ref, bearer)
        if len(data) != length:
            raise PrivateStorageIntegrityError("Original byte length mismatch")
        # Requery the signed invoker view after the remote Storage read to
        # reject revocation/version metadata drift across the two requests.
        current, current_length = self.source(
            bearer=bearer, case_id=case_id,
            document_id=document_id, version_id=version_id,
        )
        if ref != current or length != current_length:
            raise PrivateStorageFailure("Private source changed during read")
        return data

    def put_once(
        self, *, bearer: str, case_id: str, document_id: str,
        version_id: str, data: bytes,
    ) -> None:
        ref, length = self.source(
            bearer=bearer, case_id=case_id,
            document_id=document_id, version_id=version_id,
        )
        if not isinstance(data, bytes) or len(data) != length:
            raise PrivateStorageIntegrityError("Original length mismatch") from None
        self.storage.put_once(ref, bearer, data)
        # Always verify real bytes after writing, not just the Storage 200.
        if self.read(
            bearer=bearer, case_id=case_id,
            document_id=document_id, version_id=version_id,
        ) != data:
            raise PrivateStorageIntegrityError("Original readback mismatch") from None
