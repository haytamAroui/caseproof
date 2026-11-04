"""Signed, snapshot-bound DOCX candidate editor.

This API never persists, activates, authorizes or releases edited documents.
It is separate from reviewed finding correction and only returns a local
candidate for an explicitly authorized user with access to the current brief.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.api.access_control import (
    AccessFailure,
    AccessRejected,
    IdentityServiceUnavailable,
    InvalidBearer,
)
from apps.api.litigation_evidence_app import _token
from infrastructure.parsers.docx_structured_editing import (
    DocumentRevisionDecision,
    DocumentTextEdit,
    decide_document_revisions,
    edit_document_text,
    list_document_blocks,
    list_document_revisions,
)

if TYPE_CHECKING:
    from apps.api.dossier_journey import DossierStore

SHA = r"^[0-9a-f]{64}$"
PART = r"^word/(?:document|header[0-9]+|footer[0-9]+|footnotes|endnotes)\.xml$"


class EditorTextEdit(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    part: str = Field(pattern=PART)
    paragraph_index: int = Field(ge=0, le=2999)
    expected_text_sha256: str = Field(pattern=SHA)
    before: str = Field(min_length=1, max_length=20000)
    after: str = Field(max_length=20000)
    track_changes: bool = True


class EditorRevisionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    part: str = Field(pattern=PART)
    revision_id: int = Field(ge=0, le=2000000000)
    action: Literal["accept", "reject"]


class EditorCandidateBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    snapshot_hash: str = Field(pattern=SHA)
    original_sha256: str = Field(pattern=SHA)
    timestamp: str = Field(pattern=r"^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00$")
    edits: list[EditorTextEdit] = Field(default_factory=list, max_length=40)
    decisions: list[EditorRevisionDecision] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def require_one_operation_mode(self) -> EditorCandidateBody:
        if bool(self.edits) == bool(self.decisions):
            raise ValueError("exactly one of edits or decisions is required")
        if self.edits and len({(e.part, e.paragraph_index) for e in self.edits}) != len(self.edits):
            raise ValueError("duplicate editor target")
        if self.decisions and len({(d.part, d.revision_id) for d in self.decisions}) != len(self.decisions):
            raise ValueError("duplicate revision target")
        try:
            date = datetime.fromisoformat(self.timestamp)
            offset = date.utcoffset()
            if offset is None or offset.total_seconds() != 0:
                raise ValueError
        except ValueError:
            raise ValueError("invalid timestamp") from None
        return self


def create_document_editor_router(store: DossierStore | None) -> APIRouter:
    router = APIRouter()
    base = "/v2/matters/{case_id}/briefs/{brief_id}/dossier/editor"

    def bound(
        case_id: str, brief_id: str, snapshot: str, authorization: str | None
    ) -> tuple[DossierStore, str, bytes]:
        if store is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        bearer = _token(authorization)
        if not re.fullmatch(SHA, snapshot):
            raise HTTPException(422, "invalid source snapshot")
        if store.current_draft_version(bearer, case_id) != brief_id:
            raise HTTPException(409, "superseded draft is read-only")
        report, original = store.reopen(bearer, case_id, brief_id, snapshot)
        if report.get("snapshot_hash") != snapshot or report.get("brief_id") != brief_id:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        if store.current_draft_version(bearer, case_id) != brief_id:
            raise HTTPException(412, "draft superseded during editor authorization")
        return store, bearer, original

    def actor_name(store: DossierStore, bearer: str) -> str:
        """Author is always resolved from the signed server identity, not JSON."""
        try:
            actor = store.revisions.verifier.verify_bearer(bearer).subject_id
        except InvalidBearer:
            raise AccessRejected(AccessFailure.AUTHENTICATION_REQUIRED) from None
        except IdentityServiceUnavailable:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        if not actor or len(actor) > 104:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return "CaseProof reviewer " + actor

    @router.get(base + "/blocks")
    def editor_blocks(
        case_id: str,
        brief_id: str,
        snapshot_hash: str,
        offset: int = 0,
        limit: int = 20,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        if offset < 0 or offset > 3000 or limit < 1 or limit > 20:
            raise HTTPException(422, "invalid editor page")
        _, _, original = bound(case_id, brief_id, snapshot_hash, authorization)
        try:
            blocks = list_document_blocks(original)
            selected = blocks[offset:offset + limit]
        except ValueError:
            raise HTTPException(422, "unsupported or oversized DOCX") from None
        return {
            "schema": "caseproof-docx-editor-blocks-v1",
            "brief_version_id": brief_id,
            "snapshot_hash": snapshot_hash,
            "original_sha256": hashlib.sha256(original).hexdigest(),
            "total": len(blocks),
            "offset": offset,
            "has_more": offset + limit < len(blocks),
            "editable_count": sum(block.editable for block in blocks),
            "blocks": [
                {
                    "part": b.part,
                    "paragraph_index": b.paragraph_index,
                    "kind": b.kind,
                    "text": b.text,
                    "text_sha256": b.text_sha256,
                    "editable": b.editable,
                }
                for b in selected
            ],
            "committed": False,
        }

    @router.get(base + "/revisions")
    def editor_revisions(
        case_id: str,
        brief_id: str,
        snapshot_hash: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _, _, original = bound(case_id, brief_id, snapshot_hash, authorization)
        try:
            revisions = list_document_revisions(original)
        except ValueError:
            raise HTTPException(422, "unsupported Word revisions") from None
        return {
            "schema": "caseproof-docx-editor-revisions-v1",
            "brief_version_id": brief_id,
            "snapshot_hash": snapshot_hash,
            "original_sha256": hashlib.sha256(original).hexdigest(),
            "revisions": [
                {
                    "part": r.part,
                    "revision_id": r.revision_id,
                    "kind": r.kind,
                    "author": r.author,
                    "timestamp": r.timestamp,
                    "text_sha256": r.text_sha256,
                }
                for r in revisions
            ],
        }

    def candidate(
        case_id: str, brief_id: str, body: EditorCandidateBody,
        authorization: str | None, if_match: str | None,
    ) -> tuple[bytes, str]:
        if if_match != "snapshot_id:" + body.snapshot_hash:
            raise HTTPException(412, "snapshot precondition required")
        s, bearer, original = bound(case_id, brief_id, body.snapshot_hash, authorization)
        if hashlib.sha256(original).hexdigest() != body.original_sha256:
            raise HTTPException(412, "original bytes changed")
        try:
            if body.edits:
                derivative = edit_document_text(
                    original,
                    expected_sha256=body.original_sha256,
                    edits=[DocumentTextEdit(**edit.model_dump()) for edit in body.edits],
                    author=actor_name(s, bearer),
                    timestamp=body.timestamp,
                )
            else:
                derivative = decide_document_revisions(
                    original,
                    expected_sha256=body.original_sha256,
                    decisions=[
                        DocumentRevisionDecision(**decision.model_dump())
                        for decision in body.decisions
                    ],
                )
        except ValueError:
            raise HTTPException(422, "unsupported, stale or ambiguous document edit") from None
        # Fence a concurrent new-version activation after expensive OOXML work.
        if s.current_draft_version(bearer, case_id) != brief_id:
            raise HTTPException(412, "draft superseded during edit")
        return derivative, hashlib.sha256(derivative).hexdigest()

    @router.post(base + "/preview")
    def editor_preview(
        case_id: str, brief_id: str, body: EditorCandidateBody,
        authorization: str | None = Header(default=None),
        if_match: str | None = Header(default=None),
    ) -> dict[str, Any]:
        derivative, digest = candidate(case_id, brief_id, body, authorization, if_match)
        return {
            "schema": "caseproof-docx-editor-preview-v1",
            "brief_version_id": brief_id,
            "snapshot_hash": body.snapshot_hash,
            "original_sha256": body.original_sha256,
            "derivative_sha256": digest,
            "derivative_byte_length": len(derivative),
            "operations_count": len(body.edits) + len(body.decisions),
            "committed": False,
            "activated": False,
            "requires_document_scoped_review_and_import": True,
            "requires_recheck": True,
        }

    @router.post(base + "/candidate")
    def editor_candidate(
        case_id: str, brief_id: str, body: EditorCandidateBody,
        authorization: str | None = Header(default=None),
        if_match: str | None = Header(default=None),
    ) -> Response:
        derivative, digest = candidate(case_id, brief_id, body, authorization, if_match)
        return Response(
            derivative,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Content-Disposition": "attachment; filename=caseproof-uncommitted-edited-candidate.docx",
                "X-CaseProof-Snapshot": body.snapshot_hash,
                "X-CaseProof-Edit-Candidate-SHA256": digest,
                "X-CaseProof-Original-SHA256": body.original_sha256,
            },
        )

    return router
