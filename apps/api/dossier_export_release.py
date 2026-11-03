"""Bounded, version-bound reviewed delivery. A release is not a legal certificate."""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
from typing import Any, cast
from uuid import UUID

from docx import Document
from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from application.litigation.report_projection import canonical as canonical_report
from application.litigation.report_projection import render_dossier_export
from apps.api.access_control import AccessFailure, AccessRejected
from infrastructure.parsers.dossier_docx_export import annotated_docx

HEX64 = r"^[0-9a-f]{64}$"
FORMATS = ("json", "markdown", "docx")
LIMITS = {"json": 2_000_000, "markdown": 2_000_000, "docx": 5_242_880}
MEDIA = {
    "json": "application/json",
    "markdown": "text/markdown; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class ReleaseCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    release_id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
    snapshot_hash: str = Field(pattern=HEX64)


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _checked_artifacts(report: dict[str, Any], original: bytes) -> dict[str, bytes]:
    """One frozen source report generates all formats without machine reassessment."""
    try:
        artifacts = {
            "json": render_dossier_export(report, "json").encode("utf-8"),
            "markdown": render_dossier_export(report, "markdown").encode("utf-8"),
            "docx": annotated_docx(original, report),
        }
    except (ValueError, KeyError, TypeError):
        raise HTTPException(422, "unsupported export structure; no release created") from None
    for kind, raw in artifacts.items():
        if not 0 < len(raw) <= LIMITS[kind]:
            raise HTTPException(422, "export exceeds supported size; no release created")
    # Independent parsing of actual output; a ZIP signature is not a DOCX proof.
    try:
        Document(io.BytesIO(artifacts["docx"]))
    except (ValueError, OSError, KeyError, TypeError):
        raise HTTPException(422, "generated DOCX cannot be reopened") from None
    return artifacts


def release_manifest(report: dict[str, Any], artifacts: dict[str, bytes]) -> dict[str, Any]:
    """No general VERIFIED flag: scopes, abstentions and decisions remain separate."""
    sources = report.get("sources")
    decisions = report.get("human_decisions")
    if not isinstance(sources, list) or not sources or not isinstance(decisions, list):
        raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
    selected = []
    for row in sources:
        if not isinstance(row, dict):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        selected.append({
            "version_id": row["version_id"],
            "sha256": row["sha256"],
            "role": row["role"],
        })
    if not all(isinstance(d, dict) and isinstance(d.get("request_id"), str) for d in decisions):
        raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
    return {
        "schema": "caseproof-reviewed-release-v1",
        "case_id": report["case_id"],
        "brief_id": report["brief_id"],
        "snapshot_hash": report["snapshot_hash"],
        "bundle_signature": report["bundle_signature"],
        "confirmation_id": report.get("confirmation_id"),
        "sources": selected,
        "coverage": report["coverage"],
        "finding_count": len(report["findings"]),
        "review_count": len(decisions),
        "review_request_ids": [d["request_id"] for d in decisions],
        "review_sha256": _hash(canonical_report(decisions).encode()),
        "artifacts": {
            kind: {"sha256": _hash(raw), "byte_length": len(raw), "media_type": MEDIA[kind]}
            for kind, raw in artifacts.items()
        },
        "limitations": [
            "Machine checks are not semantic legal support or filing approval.",
            "Unchecked, incomplete and OCR-unreliable regions remain explicitly unresolved.",
            "This release is a frozen historical artifact, not a statement of currentness.",
        ],
    }


def create_release_router(store: Any) -> APIRouter:
    """Always authenticate via the existing signed host and scoped release RPC."""
    from apps.api.dossier_journey import canonical, read_dossier_report
    from apps.api.litigation_evidence_app import _token

    router = APIRouter()
    base = "/v2/matters/{case_id}/briefs/{brief_id}/dossier/releases"

    def active(header: str | None) -> str:
        if store is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return _token(header)

    def check_id(value: str) -> str:
        try:
            uid = UUID(value)
        except ValueError:
            raise HTTPException(422, "invalid release identity") from None
        if str(uid) != value:
            raise HTTPException(422, "invalid release identity")
        return value

    @router.get(base + "/preview")
    def preview(case_id: str, brief_id: str, snapshot_hash: str,
                authorization: str | None = Header(default=None)) -> dict[str, Any]:
        bearer = active(authorization)
        if len(snapshot_hash) != 64 or any(ch not in "0123456789abcdef" for ch in snapshot_hash):
            raise HTTPException(422, "invalid snapshot")
        if store.current_draft_version(bearer, case_id) != brief_id:
            raise HTTPException(409, "historical draft cannot be released as current")
        report, _ = read_dossier_report(store, bearer, case_id, brief_id, snapshot_hash, decisions=True)
        status = store.export_rpc(bearer, case_id, "authorize", None, {})
        if not status.get("authorized"):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        return {
            "schema": "caseproof-release-preview-v1",
            "case_id": case_id, "brief_id": brief_id, "snapshot_hash": snapshot_hash,
            "finding_count": len(report["findings"]),
            "review_count": len(report["human_decisions"]),
            "coverage": report["coverage"],
            "formats": list(FORMATS),
            "release_ready": len(report["human_decisions"]) > 0,
            "limitations": ["Human review is not a legal certificate.", "Scope and abstentions remain visible."],
        }

    @router.post(base)
    def release(case_id: str, brief_id: str, body: ReleaseCommand,
                authorization: str | None = Header(default=None)) -> dict[str, Any]:
        bearer = active(authorization)
        # Check idempotent recovery FIRST. This path must not generate new bytes
        # after an acknowledged or lost-response release.
        existing = store.export_rpc(bearer, case_id, "status", str(body.release_id), {})
        if existing.get("state") == "released":
            if existing.get("snapshot_hash") != body.snapshot_hash or existing.get("brief_id") != brief_id:
                raise HTTPException(409, "release request identity already belongs to another snapshot")
            return cast(dict[str, Any], existing)
        if existing.get("state") != "absent":
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        if store.current_draft_version(bearer, case_id) != brief_id:
            raise HTTPException(409, "superseded draft cannot be released as current")
        report, original = read_dossier_report(
            store, bearer, case_id, brief_id, body.snapshot_hash, decisions=True
        )
        if not report["human_decisions"]:
            raise HTTPException(409, "persisted human review required for reviewed release")
        artifacts = _checked_artifacts(report, original)
        manifest = release_manifest(report, artifacts)
        manifest["release_id"] = str(body.release_id)
        manifest["manifest_sha256"] = _hash(canonical(manifest).encode())
        # The existing server-only snapshot receipt key attests the entire
        # released manifest. The browser never supplies signing authority.
        manifest["server_receipt"] = store.receipt(manifest)
        payload = {
            "manifest": manifest,
            "human_decisions": report["human_decisions"],
            "contents": {kind: base64.b64encode(raw).decode("ascii") for kind, raw in artifacts.items()},
        }
        result = store.export_rpc(bearer, case_id, "release", str(body.release_id), payload)
        if result.get("state") != "released" or result.get("manifest") != manifest:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return cast(dict[str, Any], result)

    @router.get(base)
    def list_releases(case_id: str, brief_id: str,
                      authorization: str | None = Header(default=None)) -> dict[str, Any]:
        bearer = active(authorization)
        result = store.export_rpc(bearer, case_id, "list", None, {"brief_id": brief_id})
        if not isinstance(result.get("releases"), list):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return cast(dict[str, Any], result)

    @router.get(base + "/{release_id}")
    def status(case_id: str, brief_id: str, release_id: str,
               authorization: str | None = Header(default=None)) -> dict[str, Any]:
        bearer = active(authorization)
        result = store.export_rpc(bearer, case_id, "status", check_id(release_id), {})
        if result.get("state") == "absent":
            return cast(dict[str, Any], result)
        if result.get("state") != "released" or result.get("brief_id") != brief_id:
            raise HTTPException(404, "release not found")
        manifest = result.get("manifest")
        if not isinstance(manifest, dict):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        receipt = manifest.get("server_receipt")
        unsigned = {k: v for k, v in manifest.items() if k != "server_receipt"}
        if not isinstance(receipt, str) or not hmac.compare_digest(receipt, store.receipt(unsigned)):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return cast(dict[str, Any], result)

    @router.get(base + "/{release_id}/artifacts/{kind}")
    def artifact(case_id: str, brief_id: str, release_id: str, kind: str,
                 authorization: str | None = Header(default=None)) -> Response:
        if kind not in FORMATS:
            raise HTTPException(404, "unsupported release format")
        bearer = active(authorization)
        record = store.export_rpc(bearer, case_id, "artifact", check_id(release_id), {"format": kind})
        manifest = record.get("manifest")
        if not isinstance(manifest, dict) or manifest.get("brief_id") != brief_id:
            raise HTTPException(404, "release not found")
        receipt = manifest.get("server_receipt")
        unsigned = {k: v for k, v in manifest.items() if k != "server_receipt"}
        if not isinstance(receipt, str) or not hmac.compare_digest(receipt, store.receipt(unsigned)):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        info = manifest.get("artifacts", {}).get(kind, {})
        try:
            raw = base64.b64decode(record["content_base64"], validate=True)
        except (KeyError, ValueError):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        if (not 0 < len(raw) <= LIMITS[kind] or len(raw) != info.get("byte_length")
                or _hash(raw) != info.get("sha256")):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return Response(raw, media_type=MEDIA[kind], headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f"attachment; filename=caseproof-reviewed-{release_id}.{kind if kind != 'markdown' else 'md'}",
            "X-CaseProof-Export-SHA256": info["sha256"],
            "X-CaseProof-Export-Size": str(len(raw)),
            "X-CaseProof-Snapshot": manifest["snapshot_hash"],
        })

    return router
