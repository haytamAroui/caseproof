"""Bounded, version-bound reviewed delivery. A release is not a legal certificate."""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import re
from typing import Any, cast
from urllib.parse import quote
from uuid import UUID

from docx import Document
from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from application.litigation.report_projection import canonical as canonical_report
from application.litigation.report_projection import render_dossier_export
from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.release_completeness import release_policy
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
    acknowledge_partial: bool = False


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


def _validate_frozen_report(report: dict[str, Any]) -> None:
    """Reject invalid backend data before preview or artifact creation."""
    sources = report.get("sources")
    decisions = report.get("human_decisions")
    findings = report.get("findings")
    if (
        not all(isinstance(report.get(key), str) and report[key] for key in
                ("case_id", "brief_id", "snapshot_hash", "bundle_signature"))
        or not isinstance(report.get("coverage"), dict)
        or not isinstance(sources, list) or not sources
        or not isinstance(decisions, list) or not isinstance(findings, list)
        or not all(isinstance(finding, dict) for finding in findings)
    ):
        raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
    for row in sources:
        if not isinstance(row, dict) or not all(
            isinstance(row.get(key), str) and row[key] for key in ("version_id", "sha256", "role")
        ):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
    if any(re.fullmatch(HEX64, row["sha256"]) is None for row in sources):
        raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
    if len({row["version_id"] for row in sources}) != len(sources):
        raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
    if not all(isinstance(d, dict) and isinstance(d.get("request_id"), str) for d in decisions):
        raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
    for finding in findings:
        if not isinstance(finding.get("reference_id"), str) or not finding["reference_id"]:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        if finding.get("version_id") is not None and not isinstance(finding["version_id"], str):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        visual = finding.get("visual_assessment", {})
        if (not isinstance(visual, dict) or not isinstance(visual.get("regions", []), list)
                or not all(isinstance(region, dict) for region in visual.get("regions", []))):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)


def release_manifest(report: dict[str, Any], artifacts: dict[str, bytes]) -> dict[str, Any]:
    """No general VERIFIED flag: scopes, abstentions and decisions remain separate."""
    _validate_frozen_report(report)
    policy = release_policy(report)
    if not policy["can_release"]:
        raise HTTPException(409, "no applicable reviewed finding; no release created")
    sources = report["sources"]
    decisions = report["human_decisions"]
    selected = []
    for row in sources:
        selected.append({
            "version_id": row["version_id"],
            "sha256": row["sha256"],
            "role": row["role"],
        })
    # Link destination paths are derived exclusively from frozen source IDs and
    # the selected finding, not from external URL fields or caller input.
    source_by_id = {
        row["version_id"]: row for row in selected
        if row["role"] in {"exhibit", "draft", "inventory"}
    }
    case_path = quote(str(report["case_id"]), safe="")
    brief_path = quote(str(report["brief_id"]), safe="")
    snapshot_path = quote(str(report["snapshot_hash"]), safe="")
    original_base = (
        f"/v2/matters/{case_path}/briefs/{brief_path}/dossier"
        f"/history/{snapshot_path}/sources"
    )
    source_links = [{
        "version_id": row["version_id"],
        "role": row["role"],
        "sha256": row["sha256"],
        "original_path": f"{original_base}/{quote(str(row['version_id']), safe='')}/original",
    } for row in selected]
    reference_links = []
    for finding in report["findings"]:
        reference = finding.get("reference_id")
        version = finding.get("version_id")
        if not reference or not version or version not in source_by_id:
            continue
        page = finding.get("pdf_page")
        mapped = finding.get("page_mapping") == "mapped"
        physical = page if mapped and type(page) is int and page > 0 else None
        reference_links.append({
            "reference_id": reference,
            "source_version_id": version,
            "original_sha256": source_by_id[version]["sha256"],
            "pdf_page": physical,
            "viewer_path": (
                f"/matters/{case_path}/briefs/{brief_path}"
                f"?snapshot={snapshot_path}&finding={quote(reference, safe='')}"
            ),
            "page_space": "physical_pdf_page" if physical is not None else "unmapped",
        })
    return {
        "schema": "caseproof-reviewed-release-v1",
        "case_id": report["case_id"],
        "brief_id": report["brief_id"],
        "snapshot_hash": report["snapshot_hash"],
        "bundle_signature": report["bundle_signature"],
        "confirmation_id": report.get("confirmation_id"),
        "sources": selected,
        "source_links": source_links,
        "reference_links": reference_links,
        "coverage": report["coverage"],
        "finding_count": len(report["findings"]),
        "review_count": len(decisions),
        "release_policy": policy,
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
            "Review completeness counts detected findings, not semantic validity, OCR or full-document coverage.",
            *(
                ["PARTIAL REVIEW: unreviewed detected findings remain; explicit reviewer acknowledgement required."]
                if policy["scope"] == "partial" else []
            ),
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

    def checked_manifest(
        raw: Any, case: str, brief: str, release_id: str
    ) -> dict[str, Any]:
        """All replay, list, status and binary reads recheck the server receipt."""
        if not isinstance(raw, dict):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        if (
            raw.get("schema") != "caseproof-reviewed-release-v1"
            or raw.get("case_id") != case
            or raw.get("brief_id") != brief
            or raw.get("release_id") != release_id
            or not isinstance(raw.get("snapshot_hash"), str)
            or len(raw["snapshot_hash"]) != 64
        ):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        # Old v1 receipts have no completeness field. Never infer historical
        # completeness or rewrite their signed manifests or artifact bytes.
        if "release_policy" in raw:
            p = raw["release_policy"]
            if (
                not isinstance(p, dict) or p.get("version") != 1
                or p.get("scope") not in ("partial", "complete")
                or type(p.get("total_findings")) is not int
                or type(p.get("reviewed_findings")) is not int
                or type(p.get("unreviewed_findings")) is not int
                or p["total_findings"] != raw.get("finding_count")
                or p["reviewed_findings"] < 1
                or p["reviewed_findings"] + p["unreviewed_findings"] != p["total_findings"]
                or p.get("review_complete") is not (p["scope"] == "complete")
                or (p["unreviewed_findings"] == 0) != (p["scope"] == "complete")
            ):
                raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        receipt = raw.get("server_receipt")
        unsigned = {key: value for key, value in raw.items() if key != "server_receipt"}
        claimed_hash = unsigned.get("manifest_sha256")
        unsigned_without_hash = {
            key: value for key, value in unsigned.items()
            if key != "manifest_sha256"
        }
        if (
            not isinstance(receipt, str)
            or not isinstance(claimed_hash, str)
            or len(receipt) != 64
            or len(claimed_hash) != 64
            or not hmac.compare_digest(claimed_hash, _hash(canonical(unsigned_without_hash).encode()))
            or not hmac.compare_digest(receipt, store.receipt(unsigned))
        ):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return raw

    @router.get(base + "/preview")
    def preview(case_id: str, brief_id: str, snapshot_hash: str,
                authorization: str | None = Header(default=None)) -> dict[str, Any]:
        bearer = active(authorization)
        if len(snapshot_hash) != 64 or any(ch not in "0123456789abcdef" for ch in snapshot_hash):
            raise HTTPException(422, "invalid snapshot")
        if store.current_draft_version(bearer, case_id) != brief_id:
            raise HTTPException(409, "historical draft cannot be released as current")
        report, _ = read_dossier_report(store, bearer, case_id, brief_id, snapshot_hash, decisions=True)
        _validate_frozen_report(report)
        status = store.export_rpc(bearer, case_id, "authorize", None, {})
        if not status.get("authorized"):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        policy = release_policy(report)
        return {
            "schema": "caseproof-release-preview-v1",
            "case_id": case_id, "brief_id": brief_id, "snapshot_hash": snapshot_hash,
            "finding_count": len(report["findings"]),
            "review_count": len(report["human_decisions"]),
            "coverage": report["coverage"],
            "formats": list(FORMATS),
            "release_ready": policy["can_release"],
            "can_release": policy["can_release"],
            "release_policy": policy,
            "currentness": "current",
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
            validated = checked_manifest(
                existing.get("manifest"), case_id, brief_id, str(body.release_id)
            )
            if validated["snapshot_hash"] != body.snapshot_hash:
                raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
            return cast(dict[str, Any], existing)
        if existing.get("state") != "absent":
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        if store.current_draft_version(bearer, case_id) != brief_id:
            raise HTTPException(409, "superseded draft cannot be released as current")
        report, original = read_dossier_report(
            store, bearer, case_id, brief_id, body.snapshot_hash, decisions=True
        )
        _validate_frozen_report(report)
        policy = release_policy(report)
        if not policy["can_release"]:
            raise HTTPException(409, "at least one applicable persisted finding review required")
        if policy["scope"] == "partial" and not body.acknowledge_partial:
            raise HTTPException(409, "partial release requires explicit acknowledgement")
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
        for entry in result["releases"]:
            if not isinstance(entry, dict) or entry.get("state") != "released":
                raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
            if entry.get("brief_id") != brief_id:
                raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
            identity = entry.get("release_id")
            if not isinstance(identity, str):
                raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
            validated = checked_manifest(entry.get("manifest"), case_id, brief_id, identity)
            if entry.get("snapshot_hash") != validated["snapshot_hash"]:
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
        validated = checked_manifest(result.get("manifest"), case_id, brief_id, release_id)
        if result.get("snapshot_hash") != validated["snapshot_hash"]:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return cast(dict[str, Any], result)

    @router.get(base + "/{release_id}/artifacts/{kind}")
    def artifact(case_id: str, brief_id: str, release_id: str, kind: str,
                 authorization: str | None = Header(default=None)) -> Response:
        if kind not in FORMATS:
            raise HTTPException(404, "unsupported release format")
        bearer = active(authorization)
        record = store.export_rpc(bearer, case_id, "artifact", check_id(release_id), {"format": kind})
        manifest = checked_manifest(record.get("manifest"), case_id, brief_id, release_id)
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
