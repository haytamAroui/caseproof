"""Headless Phase 4 API; signed matter adapter owns sources and durable review state.

No browser, service-role token, or untrusted client-supplied source manifest.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, Protocol
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.litigation_evidence_app import _token
from infrastructure.parsers.docx_reference_discovery import discover_docx_references


class HeadlessMatterStore(Protocol):
    """Adapter MUST authorize bearer and case on every call and persist decisions."""
    def original_docx(self, *, bearer: str, case_id: str, brief_id: str) -> bytes: ...
    def manifest(self, *, bearer: str, case_id: str) -> list[dict[str, Any]]: ...
    def record(self, *, bearer: str, case_id: str, brief_id: str,
               reference_id: str, snapshot_hash: str, request_id: UUID,
               decision: str, rationale: str) -> dict[str, Any]: ...
    def decisions(self, *, bearer: str, case_id: str, brief_id: str,
                  snapshot_hash: str) -> list[dict[str, Any]]: ...


class DecisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    reference_id: str = Field(min_length=1, max_length=100)
    request_id: UUID
    decision: Literal["CONFIRMED_SUPPORTED", "CONFIRMED_QUALIFIED", "CONFIRMED_CONTRADICTED"]
    rationale: str = Field(min_length=1, max_length=2000)

    @field_validator("request_id", mode="before")
    @classmethod
    def parse_request_id(cls, value: object) -> UUID:
        if type(value) is not str:
            raise ValueError("request_id must be a UUID string")
        return UUID(value)




def discover(payload: bytes, manifest: list[dict[str, Any]]) -> dict[str, Any]:
    if len(payload) > 15_000_000:
        raise ValueError("DOCX exceeds size limit")
    result = discover_docx_references(payload)
    findings: list[dict[str, Any]] = []
    for index, ref in enumerate(result.references):
        matches = [x for x in manifest if str(x.get("number", "")) == ref.number
                   and x.get("label", "").casefold().startswith("stuk" if ref.label.startswith("stuk") else "pi")]
        source = matches[0] if len(matches) == 1 else None
        identity = ("resolved" if source and source.get("source_id") and source.get("version_id")
                    else "source_missing" if source else "not_in_inventory")
        # DOCX reference offsets are not a verified PDF or printed-page mapping.
        findings.append({
            "reference_id": f"ref-{index:04d}", "literal": ref.raw,
            "number": ref.number, "region": ref.region,
            "offsets": {"start": ref.start, "end": ref.end},
            "identity": identity, "source_id": source.get("source_id") if source else None,
            "version_id": source.get("version_id") if source else None,
            "source_sha256": source.get("source_sha256") if source else None,
            "page_mapping": "pdf_page_verified" if source and source.get("ocr_crop") else "page_unmapped",
            "pdf_page": source["ocr_crop"]["page_number"] if source and source.get("ocr_crop") else None,
            "printed_page": None, "bundle_page": None,
            "fidelity": "not_assessed", "support": "not_assessed",
            "ocr_crop": source.get("ocr_crop") if source else None,
            "ocr_uncertainty": source.get("ocr_uncertainty", "not_assessed") if source else "not_assessed",
            "ambiguous_manifest": len(matches) > 1,
        })
    return {
        "schema": "caseproof-headless-discovery-v1",
        "canonical_verification": False,
        "legacy_discovery": True,
        "text_coverage_complete": result.text_coverage_complete,
        "recognition_coverage_complete": result.coverage_complete,
        "unscanned_parts": list(result.unscanned_parts),
        "findings": findings,
    }


def load_snapshot(store: HeadlessMatterStore | None, bearer: str,
                  case_id: str, brief_id: str) -> dict[str, Any]:
    """Authorized, hash-bound discovery snapshot shared by the HTTP and MCP adapters."""
    if store is None:
        raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
    original = store.original_docx(bearer=bearer, case_id=case_id, brief_id=brief_id)
    manifest = store.manifest(bearer=bearer, case_id=case_id)
    result = discover(original, manifest)
    result["case_id"] = case_id
    result["brief_id"] = brief_id
    result["original_sha256"] = hashlib.sha256(original).hexdigest()
    result["snapshot_hash"] = hashlib.sha256(json.dumps(
        result, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return result


def export_report(store: HeadlessMatterStore | None, bearer: str, case_id: str,
                  brief_id: str, fmt: Literal["json", "markdown"]) -> tuple[str, str]:
    """Return (media_type, body) for the current snapshot and its human decisions."""
    snapshot = load_snapshot(store, bearer, case_id, brief_id)
    assert store is not None
    decisions = store.decisions(bearer=bearer, case_id=case_id, brief_id=brief_id,
                                snapshot_hash=snapshot["snapshot_hash"])
    report = {**snapshot, "human_decisions": decisions,
              "filing_status": "not_assessed", "professional_certificate": False}
    if fmt == "json":
        return "application/json", json.dumps(report, ensure_ascii=False, sort_keys=True)
    lines = ["# CaseProof verification report", "",
             f"Snapshot: `{snapshot['snapshot_hash']}`", "",
             "Unverified identity, page mappings and OCR remain not assessed.", ""]
    for finding in snapshot["findings"]:
        lines.append(f"- {finding['reference_id']}: {finding['literal']} — {finding['identity']}, {finding['page_mapping']}")
    lines += ["", "## Human decisions"]
    for decision in decisions:
        lines.append(f"- {decision['reference_id']}: {decision['decision']} — {decision['rationale']}")
    return "text/markdown", "\n".join(lines) + "\n"


def create_headless_review_router(store: HeadlessMatterStore | None = None) -> APIRouter:
    router = APIRouter()
    base = "/v2/matters/{case_id}/briefs/{brief_id}/verification"

    def load(bearer: str, case_id: str, brief_id: str) -> dict[str, Any]:
        return load_snapshot(store, bearer, case_id, brief_id)

    @router.get(base + "/discovery")
    def discovery(case_id: str, brief_id: str,
                  authorization: str | None = Header(default=None)) -> dict[str, Any]:
        return load(_token(authorization), case_id, brief_id)

    @router.post(base + "/reviews")
    def review(case_id: str, brief_id: str, body: DecisionBody,
               authorization: str | None = Header(default=None)) -> dict[str, Any]:
        bearer = _token(authorization)
        snapshot = load(bearer, case_id, brief_id)
        if snapshot["snapshot_hash"] != body.snapshot_hash or not any(
            f["reference_id"] == body.reference_id for f in snapshot["findings"]
        ):
            raise HTTPException(409, "stale or unknown reference")
        assert store is not None
        return store.record(bearer=bearer, case_id=case_id, brief_id=brief_id,
                            reference_id=body.reference_id, snapshot_hash=body.snapshot_hash,
                            request_id=body.request_id, decision=body.decision,
                            rationale=body.rationale)

    @router.get(base + "/export")
    def export(case_id: str, brief_id: str,
               format: Literal["json", "markdown"] = "json",
               authorization: str | None = Header(default=None)) -> Response:
        media_type, body = export_report(store, _token(authorization), case_id, brief_id, format)
        return Response(body, media_type=media_type)

    return router
