"""Development-only ClearBrief reviewer endpoints: no production mount.

No review can be submitted using a client-supplied actor, org, checked payload,
source text or release flag. Requests contain only a stable idempotency key,
the reviewed observation/snapshot and a disposition proposal.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Header
from pydantic import BaseModel, ConfigDict, Field

from application.litigation.unified_review import ReviewDisposition
from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.litigation_evidence_app import _token
from apps.api.litigation_review_workspace import ReviewCommand, SignedReviewWorkspace


class ReviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    observation_id: str = Field(min_length=1, max_length=160)
    request_id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
    expected_revision: int = Field(ge=0, le=256)
    disposition: Literal["confirmed_candidate", "dismissed", "needs_information"]
    rationale: str = Field(min_length=1, max_length=2000)


def create_clearbrief_review_router(service: SignedReviewWorkspace | None = None) -> APIRouter:
    router = APIRouter()
    base = "/v2/matters/{case_id}/briefs/{brief_version_id}/review"

    @router.get(base)
    def review_state(
        case_id: str, brief_version_id: str,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        if service is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return service.state(
            bearer=_token(authorization),
            case_id=case_id, brief_version_id=brief_version_id,
        )

    @router.post(base)
    def record_review(
        case_id: str, brief_version_id: str, body: ReviewBody,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        if service is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        if not body.rationale.strip():
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        return service.record(
            bearer=_token(authorization),
            case_id=case_id, brief_version_id=brief_version_id,
            command=ReviewCommand(
                snapshot_hash=body.snapshot_hash,
                observation_id=body.observation_id,
                request_id=UUID(body.request_id),
                expected_revision=body.expected_revision,
                disposition=ReviewDisposition(body.disposition),
                rationale=body.rationale,
            ),
        )

    return router
