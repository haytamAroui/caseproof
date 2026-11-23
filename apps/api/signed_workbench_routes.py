"""Development-only SIGNED routes for check, review and correction preview.

These routes reach the signed adapters (LiveMatterCheckStore, the signed review
ledger) through a per-request workbench factory bound to ONE verified bearer
(assemble_request_workbench in production composition; a labeled fake auth and
transport rig in tests). Nothing here is mounted in production, writes live
data on its own, or accepts a client actor, org, checked payload or source text.

Vocabulary: a "candidate difference" is a deterministic comparison of typed
values inside one verified source passage. It is never a legal conclusion,
never proof that the brief is wrong, and never an approval.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from typing import Annotated, Any, Protocol
from uuid import UUID

from fastapi import APIRouter, Header
from pydantic import BaseModel, ConfigDict, Field

from application.litigation.review_cycle import CorrectionProposal, preview_correction
from application.litigation.unified_review import ReviewDisposition
from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.litigation_check_service import AuthorizedLitigationChecker
from apps.api.litigation_evidence_app import _token
from apps.api.litigation_review_app import ReviewBody
from apps.api.litigation_review_workspace import ReviewCommand, SignedReviewWorkspace

__all__ = ["create_signed_workbench_router"]

_NOTE = (
    "Candidate differences compare typed values in one verified source passage. "
    "They are not legal conclusions, not approval and not a filing decision."
)


class _Workbench(Protocol):
    checker: AuthorizedLitigationChecker
    workspace: SignedReviewWorkspace
    store: Any


class CorrectionPreviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    observation_id: str = Field(min_length=1, max_length=160)
    # Optional: when omitted the exact text must occur exactly once in the
    # current verified representation, otherwise the preview abstains (409).
    start: int | None = Field(default=None, ge=0, le=120_000)
    end: int | None = Field(default=None, ge=1, le=120_000)
    before: str = Field(min_length=1, max_length=4000)
    after: str = Field(min_length=1, max_length=4000)
    rationale: str = Field(min_length=1, max_length=2000)


def create_signed_workbench_router(
    factory: Callable[[str], _Workbench] | None,
) -> APIRouter:
    router = APIRouter()
    base = "/dev/signed/matters/{case_id}/briefs/{brief_version_id}"

    def bench(authorization: str | None) -> tuple[str, _Workbench]:
        if factory is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        bearer = _token(authorization)
        try:
            return bearer, factory(bearer)
        except ValueError:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None

    @router.get(base + "/check")
    @router.post(base + "/check")
    def signed_check(
        case_id: str, brief_version_id: str,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        bearer, wb = bench(authorization)
        run = wb.checker.check(bearer=bearer, case_id=case_id, brief_version_id=brief_version_id)
        return {"schema": "caseproof-signed-check-v1", "note": _NOTE, **asdict(run)}

    @router.get(base + "/review")
    def signed_review_state(
        case_id: str, brief_version_id: str,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        bearer, wb = bench(authorization)
        return wb.workspace.state(
            bearer=bearer, case_id=case_id, brief_version_id=brief_version_id)

    @router.post(base + "/review")
    def signed_review_record(
        case_id: str, brief_version_id: str, body: ReviewBody,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        bearer, wb = bench(authorization)
        if not body.rationale.strip():
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        return wb.workspace.record(
            bearer=bearer, case_id=case_id, brief_version_id=brief_version_id,
            command=ReviewCommand(
                snapshot_hash=body.snapshot_hash, observation_id=body.observation_id,
                request_id=UUID(body.request_id), expected_revision=body.expected_revision,
                disposition=ReviewDisposition(body.disposition), rationale=body.rationale,
            ),
        )

    @router.post(base + "/correction-preview")
    def signed_correction_preview(
        case_id: str, brief_version_id: str, body: CorrectionPreviewBody,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        """Pure bounded preview against the CURRENT verified representation.

        Persisting is a separate, explicit step: upload the corrected file
        through the signed upload route, publish it as a new brief version,
        then re-check that new version. This route writes nothing.
        """
        bearer, wb = bench(authorization)
        subject = wb.checker._verified(bearer)
        scope = wb.checker._scope(subject, case_id)
        try:
            bundle = wb.store.load_bundle(
                case_id=case_id, brief_version_id=brief_version_id, access=scope)
        except Exception:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        run = wb.checker.check(
            bearer=bearer, case_id=case_id, brief_version_id=brief_version_id)
        if run.snapshot_hash != body.snapshot_hash:
            raise AccessRejected(AccessFailure.STALE_SNAPSHOT)
        text = bundle.representation.text
        start, end = body.start, body.end
        if start is None or end is None:
            if text.count(body.before) != 1:
                raise AccessRejected(AccessFailure.STALE_SNAPSHOT)
            start = text.index(body.before)
            end = start + len(body.before)
        try:
            proposal = CorrectionProposal(
                body.observation_id, subject.subject_id, run.snapshot_hash,
                brief_version_id, run.representation_sha256, start, end,
                body.before, body.after, body.rationale)
            preview = preview_correction(
                run=run, text=text, proposal=proposal)
        except Exception:
            # Changed range, unknown observation or stale text: never guess.
            raise AccessRejected(AccessFailure.STALE_SNAPSHOT) from None
        return {
            "schema": "caseproof-signed-correction-preview-v1",
            "brief_version_id": brief_version_id,
            "invalidates_check_hash": preview.invalidates_check_hash,
            "old_text_sha256": preview.old_text_sha256,
            "proposed_text_sha256": preview.proposed_text_sha256,
            "proposed_text": preview.proposed_text,
            "requires_new_brief_version": True,
            "persisted": False,
            "note": _NOTE,
        }

    return router


