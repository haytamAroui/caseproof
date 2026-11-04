"""Signed, snapshot-bound DOCX candidate editor.

This API never persists, activates, authorizes or releases edited documents.
It is separate from reviewed finding correction and only returns a local
candidate for an explicitly authorized user with access to the current brief.
"""
from __future__ import annotations

import hashlib
import json
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
from apps.api.signed_supabase_originals import (
    PrivateStorageExists,
    PrivateStorageOutcomeUnknown,
)
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



UUID_V4 = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"


class EditorReviewBody(EditorCandidateBody):
    review_request_id: str = Field(pattern=UUID_V4)
    rationale: str = Field(min_length=10, max_length=2000)


class EditorCommitBody(EditorCandidateBody):
    review_request_id: str = Field(pattern=UUID_V4)
    request_id: str = Field(pattern=UUID_V4)


def editor_command_sha256(case_id: str, brief_id: str, body: EditorCandidateBody) -> str:
    """Full command fingerprint; no incidental request ID can weaken replay."""
    fields = body.model_dump(exclude={"review_request_id", "request_id", "rationale"})
    payload = json.dumps(
        {"case": case_id, "brief": brief_id, **fields},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


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


    @router.post(base + "/review")
    def save_document_review(
        case_id: str, brief_id: str, body: EditorReviewBody,
        authorization: str | None = Header(default=None),
        if_match: str | None = Header(default=None),
        idempotency_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        if idempotency_key != body.review_request_id:
            raise HTTPException(422, "document review request ID mismatch")
        derivative, digest = candidate(
            case_id, brief_id, body, authorization, if_match
        )
        s, bearer, _ = bound(
            case_id, brief_id, body.snapshot_hash, authorization
        )
        fingerprint = editor_command_sha256(case_id, brief_id, body)
        response = s.revisions.editor_review(
            bearer, case_id, brief_id, body.snapshot_hash,
            body.review_request_id,
            {
                "original_sha256": body.original_sha256,
                "command_sha256": fingerprint,
                "candidate_sha256": digest,
                "rationale": body.rationale,
            },
        )
        if (
            response.get("state") != "reviewed"
            or response.get("review_request_id") != body.review_request_id
            or response.get("command_sha256") != fingerprint
            or response.get("candidate_sha256") != digest
            or len(derivative) > 5_242_880
        ):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return {
            "schema": "caseproof-document-editor-review-v1",
            "review_request_id": body.review_request_id,
            "command_sha256": fingerprint,
            "candidate_sha256": digest,
            "persisted": True,
            "activated": False,
            "requires_separate_commit": True,
        }

    def authoritative_status(
        s: DossierStore, bearer: str, case_id: str, brief_id: str,
        body: EditorCommitBody,
    ) -> tuple[dict[str, Any], str]:
        fingerprint = editor_command_sha256(case_id, brief_id, body)
        status = s.revisions.reserve(
            bearer, case_id, body.request_id, "status",
            {"command_sha256": fingerprint},
        )
        if status.get("state") not in ("absent", "reserved", "active"):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        if status.get("state") != "absent" and (
            status.get("command_sha256") != fingerprint
            or status.get("parent_version_id") != brief_id
            or status.get("parent_snapshot_hash") != body.snapshot_hash
            or status.get("reference_id") != "doc-edit:" + body.review_request_id
        ):
            raise HTTPException(409, "document edit replay conflicts with operation")
        return status, fingerprint

    @router.post(base + "/status")
    def document_edit_status(
        case_id: str, brief_id: str, body: EditorCommitBody,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        if store is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        bearer = _token(authorization)
        status, _ = authoritative_status(store, bearer, case_id, brief_id, body)
        return {
            "schema": "caseproof-document-editor-status-v1",
            "state": status["state"],
            "version_id": status.get("version_id") if status["state"] == "active" else None,
            "committed": status["state"] == "active",
            "requires_recheck": status["state"] in ("reserved", "active"),
        }

    @router.post(base + "/commit")
    def commit_document_edit(
        case_id: str, brief_id: str, body: EditorCommitBody,
        authorization: str | None = Header(default=None),
        if_match: str | None = Header(default=None),
        idempotency_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        if store is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        if if_match != "snapshot_id:" + body.snapshot_hash:
            raise HTTPException(412, "snapshot precondition required")
        if idempotency_key != body.request_id:
            raise HTTPException(422, "durable edit request ID mismatch")
        s = store
        bearer = _token(authorization)
        status, fingerprint = authoritative_status(
            s, bearer, case_id, brief_id, body
        )
        if status["state"] == "active":
            return {
                "schema": "caseproof-document-editor-commit-v1",
                "state": "active", "version_id": status["version_id"],
                "committed": True, "requires_recheck": True,
                "reconciled": True,
            }
        if status["state"] == "absent":
            derivative, digest = candidate(
                case_id, brief_id, body, authorization, if_match
            )
        else:
            original = s.client.library.read(
                bearer=bearer, case_id=case_id,
                document_id=status["document_id"], version_id=brief_id,
            )
            if hashlib.sha256(original).hexdigest() != body.original_sha256:
                raise HTTPException(412, "reserved source changed")
            try:
                if body.edits:
                    derivative = edit_document_text(
                        original, expected_sha256=body.original_sha256,
                        edits=[DocumentTextEdit(**edit.model_dump()) for edit in body.edits],
                        author=actor_name(s, bearer), timestamp=body.timestamp,
                    )
                else:
                    derivative = decide_document_revisions(
                        original, expected_sha256=body.original_sha256,
                        decisions=[
                            DocumentRevisionDecision(**choice.model_dump())
                            for choice in body.decisions
                        ],
                    )
            except ValueError:
                raise HTTPException(422, "stale reserved document edit") from None
            digest = hashlib.sha256(derivative).hexdigest()
        reserved = s.revisions.editor_reserve(
            bearer, case_id, brief_id, body.snapshot_hash,
            body.request_id, body.review_request_id,
            {
                "original_sha256": body.original_sha256,
                "command_sha256": fingerprint,
                "candidate_sha256": digest,
                "byte_length": len(derivative),
            },
        )
        if (
            reserved.get("parent_version_id") != brief_id
            or reserved.get("parent_snapshot_hash") != body.snapshot_hash
            or reserved.get("reference_id") != "doc-edit:" + body.review_request_id
            or reserved.get("command_sha256") != fingerprint
            or reserved.get("original_sha256") != digest
            or reserved.get("byte_length") != len(derivative)
        ):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        params = {
            "bearer": bearer, "case_id": case_id,
            "document_id": reserved["document_id"],
            "version_id": reserved["version_id"],
        }
        try:
            s.client.library.put_once(data=derivative, **params)
        except (PrivateStorageExists, PrivateStorageOutcomeUnknown):
            pass
        readback = s.client.library.read(**params)
        if len(readback) != len(derivative) or hashlib.sha256(readback).hexdigest() != digest:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        activated = s.revisions.activate(
            bearer, case_id, body.request_id, digest, len(readback)
        )
        if activated.get("state") != "active" or activated.get("version_id") != reserved["version_id"]:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return {
            "schema": "caseproof-document-editor-commit-v1",
            "state": "active", "version_id": activated["version_id"],
            "committed": True, "requires_recheck": True,
            "reconciled": False,
        }

    return router
