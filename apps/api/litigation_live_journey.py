"""Development-only real signed matter -> original TXT -> immutable ingest -> brief.

All ordinary mutations use signed JWT and publishable key. TXT promotion
instead uses loopback server verification of GoTrue and actual Storage bytes,
then a service-only SQL function. Clients cannot self-certify original text.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import http.client
import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header
from pydantic import BaseModel, ConfigDict, Field

from apps.api.access_control import (
    AccessFailure, AccessRejected, IdentityServiceUnavailable, InvalidBearer,
)
from apps.api.litigation_evidence_app import _token
from apps.api.signed_supabase_originals import (
    PrivateStorageExists,
    PrivateStorageFailure,
    SignedOriginalsStorage,
)
from apps.api.signed_supabase_source_library import SignedSourceLibrary
from apps.api.supabase_auth_verifier import HttpsSupabaseUserLookup, SupabaseAuthUserVerifier

HOST = "ldwmocpxwskvhoojndrd.supabase.co"
MAX_TXT = 1024 * 1024
MAX_RPC_RESPONSE = 2 * 1024 * 1024


def _uuid(value: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError:
        raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
    if str(parsed) != value:
        raise AccessRejected(AccessFailure.RESOURCE_MASKED)
    return value


class MatterCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    org_id: UUID
    name: str = Field(min_length=1, max_length=160)
    request_id: UUID


class OriginalRegister(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(min_length=1, max_length=128)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_length: int = Field(ge=1, le=MAX_TXT)
    media_type: str = Field(pattern=r"^text/plain$")
    request_id: UUID


class OriginalUpload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_base64: str = Field(min_length=1, max_length=1400000)


class AuthoredBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_version_id: UUID
    text: str = Field(min_length=1, max_length=8000)
    quote: str = Field(min_length=3, max_length=100)
    request_id: UUID


class JourneyClient:
    def __init__(self, publishable_key: str, trusted_ingest_key: str | None = None):
        if not publishable_key.startswith("sb_publishable_"):
            raise ValueError("development publishable key required")
        self._key = publishable_key
        if trusted_ingest_key is not None and not (
            trusted_ingest_key.startswith('sb_secret_') or trusted_ingest_key.startswith('eyJ')
        ):
            raise ValueError('protected development admin key required')
        self._trusted_ingest_key = trusted_ingest_key
        self._verifier = (
            SupabaseAuthUserVerifier(
                "ldwmocpxwskvhoojndrd",
                HttpsSupabaseUserLookup("ldwmocpxwskvhoojndrd", publishable_key),
            ) if trusted_ingest_key is not None else None
        )
        self.library = SignedSourceLibrary(SignedOriginalsStorage(publishable_key))

    def call(
        self, bearer: str, action: str, *,
        case_id: str | None = None,
        request_id: str | None = None,
        data: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        if action not in {"create", "register", "brief", "state"}:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        body: dict[str, object] = {"p_action": action, "p_data": data or {}}
        if case_id is not None:
            body["p_case"] = _uuid(case_id)
        if request_id is not None:
            body["p_request"] = _uuid(request_id)
        con = http.client.HTTPSConnection(HOST, timeout=20)
        try:
            con.request(
                "POST", "/rest/v1/rpc/caseproof_dev_journey",
                body=json.dumps(body, separators=(",", ":")).encode("utf-8"),
                headers={
                    "apikey": self._key,
                    "Authorization": "Bearer " + bearer,
                    "Content-Type": "application/json",
                    "Cache-Control": "no-store",
                },
            )
            response = con.getresponse()
            status, raw = response.status, response.read(MAX_RPC_RESPONSE + 1)
        except (OSError, TimeoutError, http.client.HTTPException):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        finally:
            con.close()
        if status in (400, 401, 403, 404, 409, 422):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        if status != 200 or len(raw) > MAX_RPC_RESPONSE:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            result = json.loads(raw)
        except (UnicodeError, ValueError):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        if not isinstance(result, dict):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return result

    def call_create_organizations(self, bearer: str) -> dict[str, Any]:
        con = http.client.HTTPSConnection(HOST, timeout=12)
        try:
            con.request(
                "POST", "/rest/v1/rpc/caseproof_dev_journey_organizations",
                body=b"{}", headers={
                    "apikey": self._key, "Authorization": "Bearer " + bearer,
                    "Content-Type": "application/json", "Cache-Control": "no-store",
                },
            )
            response = con.getresponse()
            status, raw = response.status, response.read(16385)
        except (OSError, TimeoutError, http.client.HTTPException):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        finally:
            con.close()
        if status in (400, 401, 403, 404):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        if status != 200 or len(raw) > 16384:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            result = json.loads(raw)
        except (UnicodeError, ValueError):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        if not isinstance(result, dict) or result.get("schema") != "caseproof-dev-create-orgs-v1":
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return result

    def upload(
        self, bearer: str, case_id: str, doc_id: str, version_id: str, content: str,
    ) -> dict[str, object]:
        try:
            encoded = content.encode("ascii")
            if len(encoded) > 1400000:
                raise ValueError("oversize")
            data = base64.b64decode(encoded, validate=True)
        except (UnicodeError, ValueError, binascii.Error):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
        if not 0 < len(data) <= MAX_TXT:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        digest = hashlib.sha256(data).hexdigest()
        try:
            source, size = self.library.source(
                bearer=bearer, case_id=_uuid(case_id),
                document_id=_uuid(doc_id), version_id=_uuid(version_id),
            )
            if source.sha256_hex != digest or size != len(data) or source.content_type != "text/plain":
                raise AccessRejected(AccessFailure.RESOURCE_MASKED)
            try:
                self.library.put_once(
                    bearer=bearer, case_id=case_id, document_id=doc_id,
                    version_id=version_id, data=data,
                )
            except PrivateStorageExists:
                if self.library.read(
                    bearer=bearer, case_id=case_id,
                    document_id=doc_id, version_id=version_id,
                ) != data:
                    raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
        except PrivateStorageFailure:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
        return {"document_id": doc_id, "version_id": version_id, "sha256": digest, "verified": True}

    def ingest(
        self, bearer: str, case_id: str, doc_id: str, version_id: str, request_id: str,
    ) -> dict[str, Any]:
        try:
            raw = self.library.read(
                bearer=bearer, case_id=_uuid(case_id),
                document_id=_uuid(doc_id), version_id=_uuid(version_id),
            )
            if not raw or len(raw) > MAX_TXT:
                raise AccessRejected(AccessFailure.RESOURCE_MASKED)
            raw.decode("utf-8", errors="strict")
        except (PrivateStorageFailure, UnicodeError):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
        # Only trusted loopback API may promote a verified source. The actor
        # is established by GoTrue, NEVER accepted from request JSON.
        if self._trusted_ingest_key is None or self._verifier is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            actor = self._verifier.verify_bearer(bearer)
        except InvalidBearer:
            raise AccessRejected(AccessFailure.AUTHENTICATION_REQUIRED) from None
        except IdentityServiceUnavailable:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        data = {
            "p_actor": _uuid(actor.subject_id),
            "p_case": _uuid(case_id),
            "p_request": _uuid(request_id),
            "p_document": _uuid(doc_id),
            "p_version": _uuid(version_id),
            "p_content_base64": base64.b64encode(raw).decode("ascii"),
        }
        admin = self._trusted_ingest_key
        headers = {
            "apikey": admin, "Content-Type": "application/json",
            "Cache-Control": "no-store",
        }
        if admin.startswith("eyJ"):
            headers["Authorization"] = "Bearer " + admin
        con = http.client.HTTPSConnection(HOST, timeout=20)
        try:
            con.request(
                "POST", "/rest/v1/rpc/caseproof_dev_ingest_verified",
                body=json.dumps(data, separators=(",", ":")).encode("utf-8"),
                headers=headers,
            )
            response = con.getresponse()
            status, body = response.status, response.read(MAX_RPC_RESPONSE + 1)
        except (OSError, TimeoutError, http.client.HTTPException):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        finally:
            con.close()
        if status in (400, 401, 403, 404, 409, 422):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        if status != 200 or len(body) > MAX_RPC_RESPONSE:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            result = json.loads(body)
        except (UnicodeError, ValueError):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        if not isinstance(result, dict):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return result


def create_live_journey_router(
    publishable_key: str | None, trusted_ingest_key: str | None = None,
) -> APIRouter:
    router = APIRouter()
    client = JourneyClient(publishable_key, trusted_ingest_key) if publishable_key else None

    def active(authorization: str | None) -> tuple[JourneyClient, str]:
        if client is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return client, _token(authorization)

    @router.get("/dev/live/create-organizations")
    def create_organizations(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        c, bearer = active(authorization)
        return c.call_create_organizations(bearer)

    @router.post("/dev/live/matters")
    def create(body: MatterCreate, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        c, bearer = active(authorization)
        return c.call(bearer, "create", request_id=str(body.request_id),
                      data={"org_id": str(body.org_id), "name": body.name})

    @router.post("/dev/live/matters/{case_id}/sources")
    def register(case_id: str, body: OriginalRegister,
                 authorization: str | None = Header(default=None)) -> dict[str, Any]:
        c, bearer = active(authorization)
        return c.call(bearer, "register", case_id=case_id, request_id=str(body.request_id),
                      data=body.model_dump(mode="json", exclude={"request_id"}))

    @router.post("/dev/live/matters/{case_id}/sources/{document_id}/{version_id}/upload")
    def upload(case_id: str, document_id: str, version_id: str, body: OriginalUpload,
               authorization: str | None = Header(default=None)) -> dict[str, object]:
        c, bearer = active(authorization)
        return c.upload(bearer, case_id, document_id, version_id, body.content_base64)

    @router.post("/dev/live/matters/{case_id}/sources/{document_id}/{version_id}/ingest")
    def ingest(case_id: str, document_id: str, version_id: str, request_id: UUID,
               authorization: str | None = Header(default=None)) -> dict[str, Any]:
        c, bearer = active(authorization)
        return c.ingest(bearer, case_id, document_id, version_id, str(request_id))

    @router.post("/dev/live/matters/{case_id}/briefs")
    def brief(case_id: str, body: AuthoredBrief,
              authorization: str | None = Header(default=None)) -> dict[str, Any]:
        c, bearer = active(authorization)
        return c.call(bearer, "brief", case_id=case_id, request_id=str(body.request_id),
                      data=body.model_dump(mode="json", exclude={"request_id"}))

    @router.get("/dev/live/matters/{case_id}/state")
    def state(case_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        c, bearer = active(authorization)
        return c.call(bearer, "state", case_id=case_id)

    return router
