"""Frozen-reference source inspection, using the existing receipt/grant boundary."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from fastapi import APIRouter, Header, HTTPException, Response

from application.litigation.viewer_contract import ViewerContext
from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.litigation_evidence_app import _token
from apps.api.signed_supabase_originals import PrivateStorageFailure

if TYPE_CHECKING:
    from apps.api.dossier_journey import DossierStore


def create_dossier_viewer_router(store: DossierStore | None) -> APIRouter:
    router = APIRouter()
    base = "/v2/matters/{case_id}/briefs/{brief_id}/dossier/snapshots/{snapshot}/references/{reference_id}/viewer"

    def source(
        token: str, case: str, brief: str, snapshot: str, reference: str
    ) -> tuple[ViewerContext, bytes]:
        if store is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        # Reopen verifies current grants, source set, snapshot SHA and server HMAC.
        report, _ = store.reopen(token, case, brief, snapshot)
        finding = next((f for f in report["findings"] if f["reference_id"] == reference), None)
        if finding is None:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        version = finding.get("version_id")
        recorded = next((s for s in report.get("sources", []) if s["version_id"] == version), None)
        if not recorded or recorded.get("media_type") != "application/pdf":
            raise HTTPException(422, "This finding has no bound PDF source")
        if finding.get("source_sha256") != recorded.get("sha256"):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        if not 0 < recorded.get("byte_length", 0) <= 20_000_000:
            raise HTTPException(413, "Viewer source budget exceeded")
        try:
            raw = store.client.library.read(
                bearer=token, case_id=case, document_id=recorded["document_id"], version_id=version
            )
        except PrivateStorageFailure:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
        if len(raw) != recorded["byte_length"] or hashlib.sha256(raw).hexdigest() != recorded["sha256"]:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        if not raw.startswith(b"%PDF-"):
            raise HTTPException(422, "Viewer source is not a supported PDF")
        page = finding.get("pdf_page") if finding.get("page_mapping") == "mapped" else None
        if page is not None and (type(page) is not int or not 1 <= page <= 200):
            raise HTTPException(422, "Viewer physical page is unsupported")
        regions = finding.get("visual_assessment", {}).get("regions", [])
        view = ViewerContext.model_validate(
            {
                "schema": "caseproof-viewer-v1",
                "case_id": case,
                "brief_id": brief,
                "snapshot_hash": snapshot,
                "reference_id": reference,
                "version_id": version,
                "original_sha256": recorded["sha256"],
                "byte_length": len(raw),
                "page_mapping": finding["page_mapping"],
                "pdf_page": page,
                "legacy_region_count": len(regions),
                "geometry_policy": "derived_pdf_text_only_legacy_raster_not_projected",
            }
        )
        return view, raw

    @router.get(base, response_model=ViewerContext, response_model_by_alias=True)
    def context(
        case_id: str,
        brief_id: str,
        snapshot: str,
        reference_id: str,
        authorization: str | None = Header(default=None),
    ) -> ViewerContext:
        return source(_token(authorization), case_id, brief_id, snapshot, reference_id)[0]

    @router.get(base + "/original")
    def original(
        case_id: str,
        brief_id: str,
        snapshot: str,
        reference_id: str,
        authorization: str | None = Header(default=None),
    ) -> Response:
        view, raw = source(_token(authorization), case_id, brief_id, snapshot, reference_id)
        return Response(
            raw,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=caseproof-viewer-source.pdf",
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "X-CaseProof-Snapshot": view.snapshot_hash,
                "X-CaseProof-Original-SHA256": view.original_sha256,
            },
        )

    return router
