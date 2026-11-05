"""Native Microsoft Word DOCX candidate workflow.

Word itself supplies the full editing UI, including shape/textbox layout,
comments, formatting and existing tracked revisions. CaseProof accepts only
a bounded validated candidate bound to an immutable source snapshot. The
candidate is neither evidence nor a reviewed version until a separate human
review receipt and an atomically reserved, readback-verified activation exist.
"""
from __future__ import annotations

import hashlib
import io
import json
from typing import Any, Callable
from zipfile import ZipFile

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.litigation_evidence_app import _token
from apps.api.signed_supabase_originals import PrivateStorageExists, PrivateStorageOutcomeUnknown
from infrastructure.parsers.dossier_docx_export import _validate_derivative_package

SHA = r"^[0-9a-f]{64}$"
UUID = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
MAX_DOCX = 5_242_880
DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class NativeCandidateBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    snapshot_hash: str = Field(pattern=SHA)
    original_sha256: str = Field(pattern=SHA)
    candidate_sha256: str = Field(pattern=SHA)
    byte_length: int = Field(ge=1, le=MAX_DOCX)

    @model_validator(mode="after")
    def changed(self) -> NativeCandidateBinding:
        if self.original_sha256 == self.candidate_sha256:
            raise ValueError("an unchanged source is not an edit")
        return self


class NativeReviewBody(NativeCandidateBinding):
    review_request_id: str = Field(pattern=UUID)
    rationale: str = Field(min_length=10, max_length=2000)

    @model_validator(mode="after")
    def human_rationale(self) -> NativeReviewBody:
        if len(self.rationale.strip()) < 10:
            raise ValueError("a substantive human review is required")
        return self


class NativeCommitBody(NativeCandidateBinding):
    review_request_id: str = Field(pattern=UUID)
    request_id: str = Field(pattern=UUID)


def native_fingerprint(case_id: str, brief_id: str, binding: NativeCandidateBinding) -> str:
    """Content-bound and route-bound; excludes human rationale and retry UUIDs."""
    value = json.dumps({
        "schema": "caseproof-native-word-draft-v1",
        "case_id": case_id, "brief_version_id": brief_id,
        "snapshot_hash": binding.snapshot_hash,
        "original_sha256": binding.original_sha256,
        "candidate_sha256": binding.candidate_sha256,
        "byte_length": binding.byte_length,
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_native_headers(
    snapshot_hash: str | None, original_sha256: str | None,
    candidate_sha256: str | None, byte_length: int | None,
    *, review_request_id: str | None = None, request_id: str | None = None,
) -> NativeCandidateBinding | NativeCommitBody:
    data: dict[str, Any] = {
        "snapshot_hash": snapshot_hash, "original_sha256": original_sha256,
        "candidate_sha256": candidate_sha256, "byte_length": byte_length,
    }
    if review_request_id is not None or request_id is not None:
        data.update(review_request_id=review_request_id, request_id=request_id)
    try:
        return NativeCommitBody.model_validate(data) if "request_id" in data else NativeCandidateBinding.model_validate(data)
    except ValidationError:
        raise HTTPException(422, "invalid native Word candidate binding") from None


async def limited_docx_body(request: Request, expected_bytes: int) -> bytes:
    if request.headers.get("content-type") != DOCX_MEDIA:
        raise HTTPException(415, "native Word candidate must be DOCX bytes")
    if expected_bytes < 1 or expected_bytes > MAX_DOCX:
        raise HTTPException(422, "invalid candidate size")
    chunks: list[bytes] = []
    size = 0
    async for piece in request.stream():
        size += len(piece)
        if size > expected_bytes or size > MAX_DOCX:
            raise HTTPException(413, "DOCX candidate exceeds declared bounded size")
        chunks.append(piece)
    if size != expected_bytes:
        raise HTTPException(422, "DOCX candidate byte length mismatch")
    return b"".join(chunks)


def validate_native_candidate(original: bytes, candidate: bytes, binding: NativeCandidateBinding) -> dict[str, Any]:
    if hashlib.sha256(original).hexdigest() != binding.original_sha256:
        raise HTTPException(412, "source bytes changed")
    if len(candidate) != binding.byte_length or hashlib.sha256(candidate).hexdigest() != binding.candidate_sha256:
        raise HTTPException(422, "DOCX candidate byte integrity mismatch")
    try:
        _validate_derivative_package(candidate)
        with ZipFile(io.BytesIO(original)) as old, ZipFile(io.BytesIO(candidate)) as new:
            original_parts = set(old.namelist())
            edited_parts = set(new.namelist())
            names = original_parts | edited_parts
            changed = sum(
                1 for part in names
                if part not in original_parts or part not in edited_parts
                or old.read(part) != new.read(part)
            )
            lost = len(original_parts - edited_parts)
    except (OSError, ValueError, RuntimeError):
        raise HTTPException(422, "unsafe or unsupported Word document candidate") from None
    if changed == 0:
        raise HTTPException(422, "no document package changes to review")
    return {
        "changed_package_parts": changed, "removed_package_parts": lost,
        "fidelity": "requires_manual_word_and_caseproof_review",
        "evidence_status": "unverified", "activated": False,
    }


def create_native_word_router(
    store: Any,
    bound: Callable[[str, str, str, str | None], tuple[Any, str, bytes]],
) -> APIRouter:
    router = APIRouter()
    base = "/v2/matters/{case_id}/briefs/{brief_id}/dossier/editor/native"

    def signed_status(
        s: Any, bearer: str, case_id: str, brief_id: str, body: NativeCommitBody,
    ) -> tuple[dict[str, Any], str]:
        fingerprint = native_fingerprint(case_id, brief_id, body)
        status = s.revisions.editor_status(
            bearer, case_id, body.request_id, body.review_request_id, fingerprint,
        )
        if status.get("state") not in ("absent", "reserved", "active"):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        if status["state"] != "absent" and (
            status.get("command_sha256") != fingerprint
            or status.get("parent_version_id") != brief_id
            or status.get("parent_snapshot_hash") != body.snapshot_hash
            or status.get("reference_id") != "doc-edit:" + body.review_request_id
            or status.get("original_sha256") != body.candidate_sha256
            or status.get("byte_length") != body.byte_length
        ):
            raise HTTPException(409, "native Word operation replay conflict")
        return status, fingerprint

    @router.post(base + "/preview")
    async def preview(
        case_id: str, brief_id: str, request: Request,
        authorization: str | None = Header(default=None),
        if_match: str | None = Header(default=None),
        x_caseproof_snapshot_hash: str | None = Header(default=None),
        x_caseproof_original_sha256: str | None = Header(default=None),
        x_caseproof_candidate_sha256: str | None = Header(default=None),
        x_caseproof_byte_length: int | None = Header(default=None),
    ) -> dict[str, Any]:
        binding = parse_native_headers(
            x_caseproof_snapshot_hash, x_caseproof_original_sha256,
            x_caseproof_candidate_sha256, x_caseproof_byte_length,
        )
        if if_match != "snapshot_id:" + binding.snapshot_hash:
            raise HTTPException(412, "original snapshot precondition required")
        _, _, original = bound(case_id, brief_id, binding.snapshot_hash, authorization)
        candidate = await limited_docx_body(request, binding.byte_length)
        assessment = validate_native_candidate(original, candidate, binding)
        return {
            "schema": "caseproof-native-docx-preview-v1",
            "brief_version_id": brief_id,
            **binding.model_dump(),
            "command_sha256": native_fingerprint(case_id, brief_id, binding),
            **assessment,
        }

    @router.post(base + "/review")
    def review(
        case_id: str, brief_id: str, body: NativeReviewBody,
        authorization: str | None = Header(default=None),
        if_match: str | None = Header(default=None),
        idempotency_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        if if_match != "snapshot_id:" + body.snapshot_hash:
            raise HTTPException(412, "snapshot precondition required")
        if idempotency_key != body.review_request_id:
            raise HTTPException(422, "review request ID mismatch")
        s, bearer, original = bound(case_id, brief_id, body.snapshot_hash, authorization)
        if hashlib.sha256(original).hexdigest() != body.original_sha256:
            raise HTTPException(412, "original DOCX bytes changed")
        fingerprint = native_fingerprint(case_id, brief_id, body)
        result = s.revisions.editor_review(
            bearer, case_id, brief_id, body.snapshot_hash,
            body.review_request_id,
            {"original_sha256": body.original_sha256,
             "command_sha256": fingerprint,
             "candidate_sha256": body.candidate_sha256,
             "rationale": body.rationale},
        )
        if (result.get("state") != "reviewed"
            or result.get("review_request_id") != body.review_request_id
            or result.get("command_sha256") != fingerprint
            or result.get("candidate_sha256") != body.candidate_sha256):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return {
            "schema": "caseproof-native-docx-review-v1",
            "review_request_id": body.review_request_id,
            "candidate_sha256": body.candidate_sha256,
            "command_sha256": fingerprint,
            "saved": True, "activated": False,
        }

    @router.post(base + "/status")
    def status(
        case_id: str, brief_id: str, body: NativeCommitBody,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        if store is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        bearer = _token(authorization)
        row, _ = signed_status(store, bearer, case_id, brief_id, body)
        return {
            "schema": "caseproof-native-docx-status-v1",
            "state": row["state"],
            "version_id": row.get("version_id") if row["state"] == "active" else None,
        }

    @router.post(base + "/commit")
    async def commit(
        case_id: str, brief_id: str, request: Request,
        authorization: str | None = Header(default=None),
        if_match: str | None = Header(default=None),
        idempotency_key: str | None = Header(default=None),
        x_caseproof_snapshot_hash: str | None = Header(default=None),
        x_caseproof_original_sha256: str | None = Header(default=None),
        x_caseproof_candidate_sha256: str | None = Header(default=None),
        x_caseproof_byte_length: int | None = Header(default=None),
        x_caseproof_review_request_id: str | None = Header(default=None),
    ) -> dict[str, Any]:
        body = parse_native_headers(
            x_caseproof_snapshot_hash, x_caseproof_original_sha256,
            x_caseproof_candidate_sha256, x_caseproof_byte_length,
            review_request_id=x_caseproof_review_request_id,
            request_id=idempotency_key,
        )
        if not isinstance(body, NativeCommitBody):
            raise HTTPException(422, "invalid signed commit identity")
        if if_match != "snapshot_id:" + body.snapshot_hash:
            raise HTTPException(412, "source precondition required")
        if store is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        bearer = _token(authorization)
        previous, fingerprint = signed_status(store, bearer, case_id, brief_id, body)
        if previous["state"] == "active":
            return {
                "schema": "caseproof-native-docx-commit-v1",
                "state": "active", "version_id": previous["version_id"],
                "reconciled": True, "requires_recheck": True,
            }
        # Even retries must verify the identical candidate bytes before
        # sending another storage write; byte hashes are independent of IDs.
        candidate = await limited_docx_body(request, body.byte_length)
        if previous["state"] == "absent":
            s, _, original = bound(case_id, brief_id, body.snapshot_hash, authorization)
        else:
            s = store
            original = s.client.library.read(
                bearer=bearer, case_id=case_id,
                document_id=previous["document_id"], version_id=brief_id,
            )
        validate_native_candidate(original, candidate, body)
        reserved = s.revisions.editor_reserve(
            bearer, case_id, brief_id, body.snapshot_hash,
            body.request_id, body.review_request_id,
            {"original_sha256": body.original_sha256,
             "command_sha256": fingerprint,
             "candidate_sha256": body.candidate_sha256,
             "byte_length": body.byte_length},
        )
        if (reserved.get("parent_version_id") != brief_id
            or reserved.get("parent_snapshot_hash") != body.snapshot_hash
            or reserved.get("reference_id") != "doc-edit:" + body.review_request_id
            or reserved.get("command_sha256") != fingerprint
            or reserved.get("original_sha256") != body.candidate_sha256
            or reserved.get("byte_length") != body.byte_length):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        params = dict(
            bearer=bearer, case_id=case_id,
            document_id=reserved["document_id"], version_id=reserved["version_id"],
        )
        try:
            s.client.library.put_once(data=candidate, **params)
        except (PrivateStorageExists, PrivateStorageOutcomeUnknown):
            pass
        readback = s.client.library.read(**params)
        if (len(readback) != body.byte_length
            or hashlib.sha256(readback).hexdigest() != body.candidate_sha256):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        active = s.revisions.editor_activate(
            bearer, case_id, body.request_id, body.review_request_id,
            body.candidate_sha256, body.byte_length,
        )
        if active.get("state") != "active" or active.get("version_id") != reserved["version_id"]:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return {
            "schema": "caseproof-native-docx-commit-v1",
            "state": "active", "version_id": reserved["version_id"],
            "reconciled": False, "requires_recheck": True,
        }

    return router
