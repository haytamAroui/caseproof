"""Signed-user HTTPS transport for immutable originals in CaseProof-dev.

Supabase Auth issues the bearer. Storage enforces exact case/document/version
scope through reviewed storage.objects policies; no service role, owner DB key,
tenant header, upsert or signed URL. All errors are sanitized. This is a
transport, not an ingestion/ledger approval service.
"""
from __future__ import annotations

import hashlib
import http.client
import re
from dataclasses import dataclass, field
from urllib.parse import quote
from uuid import UUID

BUCKET = "caseproof-originals-dev"
PROJECT_REF = "ldwmocpxwskvhoojndrd"
MAX_BYTES = 20 * 1024 * 1024
MIME = frozenset({
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "image/png",
    "image/jpeg",
})
DIGEST = re.compile(r"^[0-9a-f]{64}$")
API_KEY = re.compile(r"^sb_publishable_[A-Za-z0-9_-]+$")


class PrivateStorageFailure(RuntimeError):
    """No backend response bodies/identities/paths in exception messages."""


class PrivateStorageDenied(PrivateStorageFailure):
    pass


class PrivateStorageExists(PrivateStorageFailure):
    pass


class PrivateStorageOutcomeUnknown(PrivateStorageFailure):
    pass


class PrivateStorageIntegrityError(PrivateStorageFailure):
    pass


@dataclass(frozen=True, slots=True)
class OriginalRef:
    org_id: UUID
    case_id: UUID
    document_id: UUID
    version_id: UUID
    sha256_hex: str
    content_type: str

    def __post_init__(self) -> None:
        for field_name in ("org_id", "case_id", "document_id", "version_id"):
            if not isinstance(getattr(self, field_name), UUID):
                raise ValueError("Exact UUID original reference required")
        if not isinstance(self.sha256_hex, str) or not DIGEST.fullmatch(self.sha256_hex):
            raise ValueError("Canonical SHA-256 required")
        if self.content_type not in MIME:
            raise ValueError("Unsupported original MIME")

    @property
    def path(self) -> str:
        return "/".join((
            str(self.org_id), str(self.case_id),
            str(self.document_id), str(self.version_id), self.sha256_hex,
        ))


@dataclass(frozen=True, slots=True)
class SignedOriginalsStorage:
    publishable_key: str = field(repr=False)
    timeout_seconds: float = 12.0

    def __post_init__(self) -> None:
        if not isinstance(self.publishable_key, str) or not API_KEY.fullmatch(
            self.publishable_key
        ):
            raise ValueError("Use a Supabase publishable key, never a service key")
        if not 0.1 <= self.timeout_seconds <= 30.0:
            raise ValueError("Invalid storage timeout")

    def _request(
        self, method: str, ref: OriginalRef, bearer: str, payload: bytes | None,
    ) -> tuple[int, bytes]:
        if (
            not isinstance(bearer, str) or not bearer or len(bearer) > 8192
            or any(ch in bearer for ch in "\r\n")
            or method not in ("POST", "GET")
        ):
            raise ValueError("Invalid signed-user Storage request")
        prefix = "/storage/v1/object/authenticated/" if method == "GET" else "/storage/v1/object/"
        path = prefix + BUCKET + "/" + quote(ref.path, safe="/")
        conn = http.client.HTTPSConnection(
            PROJECT_REF + ".supabase.co", timeout=self.timeout_seconds,
        )
        headers = {
            "apikey": self.publishable_key,
            "Authorization": "Bearer " + bearer,
            "Cache-Control": "no-store",
            "Accept": "application/octet-stream",
        }
        if method == "POST":
            headers["Content-Type"] = ref.content_type
            headers["x-upsert"] = "false"
        try:
            conn.request(method, path, body=payload, headers=headers)
            response = conn.getresponse()
            status = response.status
            raw = response.read(MAX_BYTES + 1)
        except (OSError, TimeoutError, http.client.HTTPException):
            raise PrivateStorageOutcomeUnknown("Storage network outcome unknown") from None
        finally:
            conn.close()
        if len(raw) > MAX_BYTES:
            raise PrivateStorageFailure("Oversized Storage response")
        return status, raw

    def put_once(self, ref: OriginalRef, bearer: str, payload: bytes) -> None:
        if not isinstance(payload, bytes) or not 0 < len(payload) <= MAX_BYTES:
            raise ValueError("Original size outside allowed bounds")
        if hashlib.sha256(payload).hexdigest() != ref.sha256_hex:
            raise PrivateStorageIntegrityError("Original SHA-256 mismatch")
        status, _ = self._request("POST", ref, bearer, payload)
        if status in (200, 201):
            return
        if status == 409:
            raise PrivateStorageExists("Original already exists; no overwrite") from None
        if status in (400, 401, 403, 404, 422):
            raise PrivateStorageDenied("Storage rejected private original") from None
        raise PrivateStorageOutcomeUnknown("Storage write outcome unverified") from None

    def get_verified(self, ref: OriginalRef, bearer: str) -> bytes:
        status, body = self._request("GET", ref, bearer, None)
        if status in (400, 401, 403, 404):
            raise PrivateStorageDenied("Original unavailable to signed user") from None
        if status != 200:
            raise PrivateStorageOutcomeUnknown("Storage read outcome unverified") from None
        if not 0 < len(body) <= MAX_BYTES:
            raise PrivateStorageIntegrityError("Empty or oversized original") from None
        if hashlib.sha256(body).hexdigest() != ref.sha256_hex:
            raise PrivateStorageIntegrityError("Stored original checksum mismatch") from None
        return body
