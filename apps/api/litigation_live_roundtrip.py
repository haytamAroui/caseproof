"""Development-only signed Supabase live-review adapter.

PostgREST verifies the JWT; the installed RPC derives auth.uid(), checks
CURRENT matter grants and performs the entire audit/review transaction. No
service key, caller-supplied actor/org, or synthetic identity is accepted here.
"""
from __future__ import annotations

import http.client
import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header
from pydantic import BaseModel, ConfigDict, Field

from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.litigation_evidence_app import _token

HOST = "ldwmocpxwskvhoojndrd.supabase.co"
RPC = "/rest/v1/rpc/caseproof_dev_live_review"
CORRECTION_RPC = "/rest/v1/rpc/caseproof_dev_correct_brief"


class LiveReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    observation_id: str = Field(min_length=1, max_length=160)
    request_id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
    expected_revision: int = Field(ge=0, le=255)
    disposition: str = Field(pattern=r"^(confirmed_candidate|dismissed|needs_information)$")
    rationale: str = Field(min_length=1, max_length=2000)


class LiveCorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_review_revision: int = Field(ge=1, le=255)
    before: str = Field(min_length=3, max_length=100)
    after: str = Field(min_length=3, max_length=100)
    request_id: str = Field(
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    )


class SignedLiveReview:
    def __init__(self, publishable_key: str):
        if not publishable_key.startswith("sb_publishable_"):
            raise ValueError("public development publishable key required")
        self._key = publishable_key

    def call(
        self, bearer: str, *, case_id: str, brief_version_id: str,
        action: str, **values: object,
    ) -> dict[str, Any]:
        if action not in {"check", "state", "review", "preview_correction", "commit_correction"}:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        try:
            case = str(UUID(case_id))
            version = str(UUID(brief_version_id))
        except ValueError:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
        if len(bearer) > 8192 or not bearer:
            raise AccessRejected(AccessFailure.AUTHENTICATION_REQUIRED)
        is_correction = action in {"preview_correction", "commit_correction"}
        rpc = CORRECTION_RPC if is_correction else RPC
        data = {
            "p_case": case, "p_version": version,
            "p_action": action.removesuffix("_correction") if is_correction else action,
            **values,
        }
        con = http.client.HTTPSConnection(HOST, timeout=12)
        try:
            con.request(
                "POST", rpc,
                json.dumps(data, separators=(",", ":")).encode("utf-8"),
                headers={
                    "apikey": self._key,
                    "Authorization": f"Bearer {bearer}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Cache-Control": "no-store",
                },
            )
            response = con.getresponse()
            status = response.status
            raw = response.read(262145)
        except (OSError, TimeoutError, http.client.HTTPException):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        finally:
            con.close()
        if len(raw) > 262144:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        if status in (400, 401, 403, 404, 409):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        if status != 200:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        expected_schema = (
            "dev-signed-draft-correction-v1"
            if is_correction else "caseproof-dev-signed-roundtrip-v1"
        )
        if not isinstance(result, dict) or result.get("schema") != expected_schema:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return result


def create_live_review_router(publishable_key: str | None) -> APIRouter:
    client = SignedLiveReview(publishable_key) if publishable_key else None
    router = APIRouter()
    base = "/dev/live/matters/{case_id}/briefs/{brief_version_id}"

    def invoke(
        authorization: str | None, case_id: str, brief_version_id: str,
        action: str, **values: object,
    ) -> dict[str, Any]:
        if client is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return client.call(
            _token(authorization), case_id=case_id,
            brief_version_id=brief_version_id, action=action, **values,
        )

    @router.post(base + "/check")
    def check(
        case_id: str, brief_version_id: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        return invoke(authorization, case_id, brief_version_id, "check")

    @router.get(base + "/reviews/{snapshot_hash}")
    def state(
        case_id: str, brief_version_id: str, snapshot_hash: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        if len(snapshot_hash) != 64 or any(c not in "0123456789abcdef" for c in snapshot_hash):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        return invoke(
            authorization, case_id, brief_version_id, "state",
            p_snapshot=snapshot_hash,
        )

    @router.post(base + "/reviews")
    def record(
        case_id: str, brief_version_id: str, body: LiveReviewRequest,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        return invoke(
            authorization, case_id, brief_version_id, "review",
            p_snapshot=body.snapshot_hash, p_request=body.request_id,
            p_expected=body.expected_revision, p_observation=body.observation_id,
            p_disposition=body.disposition, p_rationale=body.rationale,
        )

    @router.post(base + "/corrections/preview")
    def preview_correction(
        case_id: str, brief_version_id: str, body: LiveCorrectionRequest,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        return invoke(
            authorization, case_id, brief_version_id, "preview_correction",
            p_snapshot=body.snapshot_hash,
            p_expected_review=body.expected_review_revision,
            p_before=body.before, p_after=body.after,
        )

    @router.post(base + "/corrections/commit")
    def commit_correction(
        case_id: str, brief_version_id: str, body: LiveCorrectionRequest,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        return invoke(
            authorization, case_id, brief_version_id, "commit_correction",
            p_snapshot=body.snapshot_hash,
            p_expected_review=body.expected_review_revision,
            p_before=body.before, p_after=body.after,
            p_request=body.request_id,
        )

    return router
