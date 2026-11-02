"""Frozen-reference source inspection, using the existing receipt/grant boundary."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from fastapi import APIRouter, Header, HTTPException, Response

from application.litigation.viewer_contract import RasterOverlay, ViewerContext
from pydantic import ValidationError
from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.litigation_evidence_app import _token
from apps.api.signed_supabase_originals import PrivateStorageFailure

if TYPE_CHECKING:
    from apps.api.dossier_journey import DossierStore


def create_dossier_viewer_router(store: DossierStore | None) -> APIRouter:
    router = APIRouter()
    base = "/v2/matters/{case_id}/briefs/{brief_id}/dossier/snapshots/{snapshot}/references/{reference_id}/viewer"
    history = "/v2/matters/{case_id}/briefs/{brief_id}/dossier/history/{snapshot}/references/{reference_id}/viewer"

    def source(
        token: str, case: str, brief: str, snapshot: str, reference: str,
        *, historical: bool = False,
    ) -> tuple[ViewerContext, bytes, dict, dict]:
        if store is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        # Current reads retain SQL freshness checks. Historical reads use a
        # distinct read-only grant and never consult today's bundle manifest.
        if historical:
            report = store.frozen_report(token, case, brief, snapshot, historical=True)
            originals: dict[str, bytes] = {}
        else:
            report, originals = store.reopen_originals(token, case, brief, snapshot)
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
            raw = (store.client.library.read(
                bearer=token, case_id=case, document_id=recorded["document_id"], version_id=version
            ) if historical else originals[version])
            current, current_length = store.client.library.source(
                bearer=token, case_id=case, document_id=recorded["document_id"], version_id=version
            )
            if current.sha256_hex != recorded["sha256"] or current_length != len(raw):
                raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        except (PrivateStorageFailure, KeyError):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
        if len(raw) != recorded["byte_length"] or hashlib.sha256(raw).hexdigest() != recorded["sha256"]:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        if not raw.startswith(b"%PDF-"):
            raise HTTPException(422, "Viewer source is not a supported PDF")
        page = finding.get("pdf_page") if finding.get("page_mapping") == "mapped" else None
        if finding.get("page_mapping") == "mapped" and page is None:
            raise HTTPException(422, "Mapped viewer page is missing")
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
        return view, raw, report, finding

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
        view, raw, _, _ = source(_token(authorization), case_id, brief_id, snapshot, reference_id)
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


    @router.get(history, response_model=ViewerContext, response_model_by_alias=True)
    def historical_context(case_id: str, brief_id: str, snapshot: str, reference_id: str,
                           authorization: str | None = Header(default=None)) -> ViewerContext:
        return source(_token(authorization), case_id, brief_id, snapshot, reference_id, historical=True)[0]

    def historical_bytes(token: str, case_id: str, brief_id: str, snapshot: str,
                         reference_id: str) -> Response:
        view, raw, _, _ = source(token, case_id, brief_id, snapshot, reference_id, historical=True)
        return Response(raw, media_type="application/pdf", headers={
            "Content-Disposition": "attachment; filename=caseproof-historical-source.pdf",
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "X-CaseProof-Snapshot": view.snapshot_hash,
            "X-CaseProof-Original-SHA256": view.original_sha256,
        })

    @router.get(history + "/original")
    def historical_original(case_id: str, brief_id: str, snapshot: str, reference_id: str,
                            authorization: str | None = Header(default=None)) -> Response:
        return historical_bytes(_token(authorization), case_id, brief_id, snapshot, reference_id)

    def raster_regions(token: str, case_id: str, brief_id: str, snapshot: str,
                       reference_id: str, *, historical: bool = False) -> dict:
        # A region can be shown only if this same signed user can presently
        # reopen the exact bytes; a frozen crop is insufficient authorization.
        view, _, report, finding = source(token, case_id, brief_id, snapshot,
                                          reference_id, historical=historical)
        key = f"{view.version_id}:{view.pdf_page}"
        page = report.get("visual_pages", {}).get(key, {})
        rows = page.get("regions", []) if isinstance(page, dict) else []
        if not isinstance(rows, list) or len(rows) > 96:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        supported: list[dict] = []
        unassessed = 0
        for row in rows:
            if not isinstance(row, dict):
                unassessed += 1
                continue
            provenance = row.get("raster_provenance")
            if not isinstance(provenance, dict):
                unassessed += 1
                continue
            try:
                projected = RasterOverlay.model_validate({
                    "region_id": row["region_id"],
                    "original_sha256": row["original_sha256"],
                    "page_number": row["page_number"],
                    "bbox": tuple(row["bbox"]),
                    "image_size": tuple(row["image_size"]),
                    "crop_box": tuple(provenance["crop_box"]),
                    "rotation": provenance["rotation"],
                    "user_unit": provenance["user_unit"],
                    "cropbox_rasterized": provenance["cropbox_rasterized"],
                })
                if (projected.original_sha256 != view.original_sha256
                        or projected.page_number != view.pdf_page
                        or finding.get("source_sha256") != view.original_sha256):
                    raise ValueError("region/source mismatch")
            except (ValidationError, KeyError, TypeError, ValueError):
                unassessed += 1
                continue
            supported.append(projected.model_dump(mode="json"))
        return {"schema": "caseproof-raster-overlays-v1", "snapshot_hash": snapshot,
                "original_sha256": view.original_sha256,
                "source_version_id": view.version_id,
                "regions": supported, "unassessed_region_count": unassessed,
                "interpretation": "navigation_only_never_a_verdict"}

    @router.get(base + "/regions")
    def regions(case_id: str, brief_id: str, snapshot: str, reference_id: str,
                authorization: str | None = Header(default=None)) -> dict:
        return raster_regions(_token(authorization), case_id, brief_id, snapshot, reference_id)

    @router.get(history + "/regions")
    def historical_regions(case_id: str, brief_id: str, snapshot: str, reference_id: str,
                           authorization: str | None = Header(default=None)) -> dict:
        return raster_regions(_token(authorization), case_id, brief_id, snapshot,
                              reference_id, historical=True)

    return router
