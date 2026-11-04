"""Signed dossier orchestration; original bytes and current grants on every request."""

from __future__ import annotations

import base64
import hashlib
import hmac
import http.client
import io
import json
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from pypdf import PdfReader, PdfWriter

from application.extraction.contracts import ExtractionError
from application.litigation.dossier_contracts import add_report_contract, assess_fidelity, quotation_context
from application.litigation.regional_fidelity import select_visual_assessment
from application.litigation.report_projection import render_dossier_export
from application.litigation.workspace_contract import DraftExcerptView, ReviewLedgerView
from apps.api.access_control import AccessFailure, AccessRejected, IdentityServiceUnavailable, InvalidBearer
from apps.api.dossier_draft_revisions import DraftRevisionClient, stale_snapshot_conflict
from apps.api.litigation_evidence_app import _token
from apps.api.litigation_headless_verification import DecisionBody
from apps.api.litigation_live_journey import HOST, JourneyClient
from apps.api.signed_document_parse import parse_verified_original
from apps.api.signed_supabase_originals import (
    PrivateStorageExists,
    PrivateStorageFailure,
    PrivateStorageOutcomeUnknown,
)
from domains.disputes.dossier_verification import build_findings
from domains.disputes.exhibit_identity import InventoryStatus
from domains.disputes.page_labels import PAGE_LABEL_PATTERN
from domains.disputes.reference_detection import detect_exhibit_references
from infrastructure.parsers.docx_correction_anchor import bound_locator, correction_anchor
from infrastructure.parsers.docx_reference_discovery import discover_docx_references
from infrastructure.parsers.docx_text_regions import extract_docx_text_regions
from infrastructure.parsers.dossier_docx_export import annotated_docx, corrected_docx_preview
from infrastructure.parsers.pdf_ocr import OCRUnavailable
from infrastructure.parsers.pdf_visual_fidelity import PDFVisualFidelity


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class PageConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    space: Literal["printed", "bundle"]
    label: str = Field(min_length=1, max_length=12, pattern=PAGE_LABEL_PATTERN)
    pdf_page: int = Field(ge=1, le=64)
    rationale: str = Field(min_length=3, max_length=500)


class IdentityConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    label: Literal["stuk", "piece"]
    number: str = Field(pattern=r"^\d{1,4}(?:bis|ter)?$")
    source_version_id: str | None = None
    pages: list[PageConfirmation] = Field(default_factory=list, max_length=128)


class InventoryReviewException(BaseModel):
    """Versioned, source-anchored human observation, not a verified identity."""

    model_config = ConfigDict(extra="forbid", strict=True)
    version: Literal[1] = 1
    kind: Literal["detector_miss", "unsupported_notation"]
    citation: str = Field(min_length=3, max_length=200)
    rationale: str = Field(min_length=5, max_length=500)
    review_state: Literal["review_needed"] = "review_needed"


class InventoryConfirmation(BaseModel):
    # Generated JSON Schema must reject the same unsafe complete+pending state
    # as the Python model validator. Unique human citation pairs still need
    # application validation; JSON Schema cannot express composite uniqueness.
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        json_schema_extra={
            "allOf": [
                {
                    "if": {"properties": {"inventory_complete": {"const": True}}},
                    "then": {"properties": {"exceptions": {"maxItems": 0}}},
                }
            ]
        },
    )
    bundle_signature: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_id: str
    inventory_complete: bool
    entries: list[IdentityConfirmation] = Field(max_length=512)
    exceptions: list[InventoryReviewException] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def guard_exceptions(self) -> InventoryConfirmation:
        if self.exceptions and self.inventory_complete:
            raise ValueError("pending inventory exceptions cannot be declared complete")
        if len({(e.kind, e.citation) for e in self.exceptions}) != len(self.exceptions):
            raise ValueError("duplicate pending inventory exception")
        return self


class VerificationOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    draft_language: Literal["nl", "fr", "en", "de"] | None = None
    source_languages: dict[str, Literal["nl", "fr", "en", "de"]] = Field(default_factory=dict, max_length=32)


class DocxLocatorIdentity(BaseModel):
    """Version-bound identity for an exact editable DOCX paragraph."""

    model_config = ConfigDict(extra="forbid", strict=True)
    exact_text: str = Field(min_length=1, max_length=4000)
    prefix: str = Field(max_length=4000)
    suffix: str = Field(max_length=4000)
    occurrence_index: int = Field(ge=0, le=100000)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    paragraph_id: str | None = Field(default=None, pattern=r"^[0-9A-Fa-f]{8}$")
    source_version_id: str = Field(min_length=1, max_length=256)


class CorrectionPreviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    locator_identity: DocxLocatorIdentity | None = None

    @model_validator(mode="after")
    def check_locator_correspondence(self) -> CorrectionPreviewBody:
        if self.locator_identity is not None and self.locator_identity.exact_text != self.before:
            raise ValueError("locator exact text differs from correction before text")
        return self
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    original_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reference_id: str = Field(min_length=1, max_length=256)
    paragraph_index: int = Field(ge=0, le=100000)
    before: str = Field(min_length=1, max_length=4000)
    after: str = Field(max_length=4000)


class StaleDossierConflict(HTTPException):
    def __init__(self) -> None:
        super().__init__(409, "snapshot is stale")


def reopen_for_mutation(
    store: DossierStore, bearer: str, case: str, brief: str, snapshot: str
) -> tuple[dict[str, Any], bytes]:
    try:
        return store.reopen(bearer, case, brief, snapshot)
    except HTTPException as exc:
        if exc.status_code == 409:
            raise HTTPException(412, "snapshot is stale") from None
        raise


def validate_correction_target(
    original: bytes, finding: dict[str, Any], brief: str, command: CorrectionPreviewBody
) -> None:
    identity = command.locator_identity
    if command.before != finding.get("literal") or (identity is not None and identity.source_version_id != brief):
        raise ValueError("correction does not match reference anchor")
    target = {**finding, "locator_identity": identity.model_dump() if identity is not None else None}
    if correction_anchor(original, target) != command.paragraph_index:
        raise ValueError("correction does not match reference anchor")


class CorrectionCommitBody(CorrectionPreviewBody):
    request_id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


class CropBatchBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    region_ids: list[str] = Field(min_length=1, max_length=96)


class VisualDecisionBody(DecisionBody):
    reviewed_region_ids: list[str] = Field(default_factory=list, max_length=96)


class DossierStore:
    def __init__(self, key: str, receipt_secret: str | None = None):
        self.key = key
        self.client = JourneyClient(key)
        self.revisions = DraftRevisionClient(key, receipt_secret)
        self.visual = PDFVisualFidelity()
        # Domain-separated receipt key, never the public client key. No key is
        # serialized, logged, persisted in source, or accepted from HTTP.
        self.receipt_key = (
            hmac.digest(receipt_secret.encode(), b"caseproof:dossier-receipt:v1", "sha256")
            if receipt_secret
            and len(receipt_secret) >= 32
            and not receipt_secret.startswith("sb_publishable_")
            else None
        )

    def rpc(self, bearer: str, case: str, action: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        con = http.client.HTTPSConnection(HOST, timeout=30)
        try:
            function = {
                "read": "caseproof_dossier_snapshot_read",
                "historical_read": "caseproof_dossier_historical_read",
            }.get(action, "caseproof_dossier")
            params = (
                {"p_case": case, "p_snapshot": (data or {}).get("snapshot_hash")}
                if action in {"read", "historical_read"}
                else {"p_case": case, "p_action": action, "p_data": data or {}}
            )
            con.request(
                "POST",
                "/rest/v1/rpc/" + function,
                canonical(params).encode(),
                {
                    "apikey": self.key,
                    "Authorization": "Bearer " + bearer,
                    "Content-Type": "application/json",
                    "Cache-Control": "no-store",
                },
            )
            res = con.getresponse()
            status, raw = res.status, res.read(4_000_001)
        except (OSError, TimeoutError, http.client.HTTPException):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        finally:
            con.close()
        if status in (400, 401, 403, 404):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        if status == 409:
            if stale_snapshot_conflict(raw):
                if action == "review":
                    raise HTTPException(412, "snapshot is stale")
                raise StaleDossierConflict()
            raise HTTPException(409, "stale dossier or idempotency conflict")
        if status != 200 or len(raw) > 4_000_000:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        if not isinstance(result, dict):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return result

    def export_rpc(
        self, bearer: str, case: str, action: str, release_id: str | None,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Signed reads; only trusted backend may persist a signed release."""
        if action not in {"authorize", "release", "status", "list", "artifact"}:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        payload: dict[str, Any] = {
            "p_case": case, "p_action": action,
            "p_export": release_id, "p_data": data,
        }
        if action == "release":
            # The API has already checked the signed report. A separate fresh
            # Auth /user lookup pins the actor before trusted PostgreSQL write.
            # No browser may invoke release RPC as service_role.
            key = self.revisions.trusted_key
            if not key:
                raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
            try:
                actor = self.revisions.verifier.verify_bearer(bearer)
            except InvalidBearer:
                raise AccessRejected(AccessFailure.AUTHENTICATION_REQUIRED) from None
            except IdentityServiceUnavailable:
                raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
            payload["p_actor"] = actor.subject_id
            headers = {
                "apikey": key, "Content-Type": "application/json",
                "Cache-Control": "no-store",
            }
            if key.startswith("eyJ"):
                headers["Authorization"] = "Bearer " + key
        else:
            headers = {
                "apikey": self.key, "Authorization": "Bearer " + bearer,
                "Content-Type": "application/json", "Cache-Control": "no-store",
            }
        con = http.client.HTTPSConnection(HOST, timeout=60)
        try:
            con.request(
                "POST", "/rest/v1/rpc/caseproof_dossier_export_release",
                canonical(payload).encode(), headers,
            )
            response = con.getresponse()
            status, raw = response.status, response.read(16_000_001)
        except (OSError, TimeoutError, http.client.HTTPException):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        finally:
            con.close()
        if status in (400, 401, 403, 404):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        if status == 409:
            raise HTTPException(409, "stale release or idempotency conflict")
        if status != 200 or len(raw) > 16_000_000:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        if not isinstance(result, dict):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return result

    def correction_status(
        self, bearer: str, case: str, brief: str, command: CorrectionCommitBody
    ) -> dict[str, Any]:
        """Read durable operation status without repeating a consequential write."""
        values = command.model_dump(exclude={"request_id"})
        if command.locator_identity is None:
            values.pop("locator_identity")
        digest = hashlib.sha256(canonical({"case": case, "brief": brief, **values}).encode()).hexdigest()
        status = self.revisions.reserve(
            bearer, case, command.request_id, "status", {"command_sha256": digest}
        )
        state = status.get("state")
        if state not in ("absent", "reserved", "active"):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        if state in ("reserved", "active") and (
            status.get("parent_snapshot_hash") != command.snapshot_hash
            or status.get("reference_id") != command.reference_id
            or status.get("parent_version_id") != brief
        ):
            raise HTTPException(409, "correction operation differs from command")
        if state == "active":
            return {"state": "active", "version_id": status["version_id"],
                    "committed": True, "requires_recheck": True}
        return {"state": state, "committed": False, "requires_recheck": state == "reserved"}

    def correction_review_receipt(
        self, bearer: str, case: str, brief: str, snapshot: str, reference: str
    ) -> dict[str, Any]:
        """Signed read of an actor-specific persisted review; never trust a browser claim."""
        report = self.frozen_report(bearer, case, brief, snapshot)
        if not any(f.get("reference_id") == reference for f in report.get("findings", [])):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        try:
            actor = self.revisions.verifier.verify_bearer(bearer).subject_id
        except InvalidBearer:
            raise AccessRejected(AccessFailure.AUTHENTICATION_REQUIRED) from None
        except IdentityServiceUnavailable:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        ledger = self.rpc(bearer, case, "decisions", {"snapshot_hash": snapshot})
        rows = ledger.get("decisions")
        if not isinstance(rows, list):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        matching = [
            row for row in rows
            if isinstance(row, dict)
            and row.get("reference_id") == reference
            and row.get("reviewer_id") == actor
            and isinstance(row.get("request_id"), str)
            and isinstance(row.get("timestamp"), str)
        ]
        if not matching:
            raise HTTPException(409, "persisted actor review required before correction")
        receipt = matching[-1]
        return {
            "schema": "caseproof-correction-review-receipt-v1",
            "brief_version_id": brief,
            "snapshot_hash": snapshot,
            "reference_id": reference,
            "reviewer_id": actor,
            "review_request_id": receipt["request_id"],
        }

    def commit_correction(
        self, bearer: str, case: str, brief: str, command: CorrectionCommitBody
    ) -> dict[str, Any]:
        values = command.model_dump(exclude={"request_id"})
        if command.locator_identity is None:
            values.pop("locator_identity")
        command_sha = hashlib.sha256(canonical({"case": case, "brief": brief, **values}).encode()).hexdigest()
        existing = self.revisions.reserve(
            bearer, case, command.request_id, "status", {"command_sha256": command_sha}
        )
        if existing.get("state") in ("reserved", "active") and (
            existing.get("parent_snapshot_hash") != command.snapshot_hash
            or existing.get("reference_id") != command.reference_id
            or existing.get("parent_version_id") != brief
        ):
            raise HTTPException(409, "correction reservation differs from command")
        if existing.get("state") == "active":
            return {**existing, "committed": True, "requires_recheck": True}
        if existing.get("state") == "absent":
            # The reserve RPC independently enforces the same actor/snapshot/reference
            # predicate transactionally. This API gate prevents bypassing the review
            # receipt even if the browser sends a direct commit.
            try:
                self.correction_review_receipt(bearer, case, brief, command.snapshot_hash, command.reference_id)
            except StaleDossierConflict:
                raise HTTPException(412, "snapshot is stale") from None
            report, original = reopen_for_mutation(self, bearer, case, brief, command.snapshot_hash)
            if report["snapshot_hash"] != command.snapshot_hash:
                raise HTTPException(412, "snapshot is stale")
            finding = next((f for f in report["findings"] if f["reference_id"] == command.reference_id), None)
            if finding is None:
                raise HTTPException(422, "unknown correction reference")
        elif existing.get("state") == "reserved":
            report = self.frozen_report(bearer, case, brief, command.snapshot_hash)
            finding = next((f for f in report["findings"] if f["reference_id"] == command.reference_id), None)
            if finding is None:
                raise HTTPException(422, "unknown correction reference")
            original = self.client.library.read(
                bearer=bearer, case_id=case, document_id=existing["document_id"], version_id=brief
            )
        else:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            validate_correction_target(original, finding, brief, command)
            derivative = corrected_docx_preview(
                original,
                expected_sha256=command.original_sha256,
                paragraph_index=command.paragraph_index,
                before=command.before,
                after=command.after,
            )
        except ValueError:
            raise HTTPException(422, "unsupported or stale correction range") from None
        digest = hashlib.sha256(derivative).hexdigest()
        reserved = self.revisions.reserve(
            bearer,
            case,
            command.request_id,
            "reserve",
            {
                "command_sha256": command_sha,
                "snapshot_hash": command.snapshot_hash,
                "parent_version_id": brief,
                "parent_sha256": command.original_sha256,
                "reference_id": command.reference_id,
                "sha256": digest,
                "byte_length": len(derivative),
            },
        )
        if (
            reserved.get("parent_version_id") != brief
            or reserved.get("parent_snapshot_hash") != command.snapshot_hash
            or reserved.get("reference_id") != command.reference_id
            or reserved.get("original_sha256") != digest
            or reserved.get("byte_length") != len(derivative)
        ):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        params = {
            "bearer": bearer,
            "case_id": case,
            "document_id": reserved["document_id"],
            "version_id": reserved["version_id"],
        }
        try:
            self.client.library.put_once(data=derivative, **params)
        except (PrivateStorageExists, PrivateStorageOutcomeUnknown):
            pass  # Only the following fresh signed readback can reconcile the write.
        readback = self.client.library.read(**params)
        if len(readback) != len(derivative) or hashlib.sha256(readback).hexdigest() != digest:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        activated = self.revisions.activate(bearer, case, command.request_id, digest, len(readback))
        if activated.get("state") != "active" or activated.get("version_id") != reserved["version_id"]:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return {**activated, "committed": True, "requires_recheck": True}

    def current_draft_version(self, bearer: str, case: str) -> str:
        """Authoritative currently active draft from the signed, scoped manifest."""
        manifest = self.client.bundle_manifest(bearer, case)
        entries = manifest.get("sources") if isinstance(manifest, dict) else None
        if not isinstance(entries, list):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        drafts = [row.get("version_id") for row in entries if isinstance(row, dict) and row.get("role") == "draft"]
        if len(drafts) != 1 or not isinstance(drafts[0], str):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return drafts[0]

    def receipt(self, payload: dict[str, Any]) -> str:
        key = getattr(self, "receipt_key", None)
        if not key:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return hmac.new(key, canonical(payload).encode(), hashlib.sha256).hexdigest()

    def frozen_report(
        self, bearer: str, case: str, brief: str, snapshot: str, *, historical: bool = False
    ) -> dict[str, Any]:
        stored = self.rpc(
            bearer, case, "historical_read" if historical else "read", {"snapshot_hash": snapshot}
        )
        serialized = stored.get("serialized")
        if not isinstance(serialized, str) or hashlib.sha256(serialized.encode()).hexdigest() != snapshot:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            report = json.loads(serialized)
        except (ValueError, UnicodeError):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        if not isinstance(report, dict):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        attestation = report.pop("server_receipt", None)
        expected = self.receipt(report)
        if (
            not isinstance(attestation, str)
            or len(attestation) != 64
            or any(c not in "0123456789abcdef" for c in attestation)
            or not hmac.compare_digest(expected, attestation)
        ):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        report["server_receipt"] = attestation
        if report.get("case_id") != case or report.get("brief_id") != brief:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        report["snapshot_hash"] = snapshot
        return report

    def reopen(self, bearer: str, case: str, brief: str, snapshot: str) -> tuple[dict[str, Any], bytes]:
        report, originals = self.reopen_originals(bearer, case, brief, snapshot)
        return report, originals[brief]

    def reopen_originals(
        self, bearer: str, case: str, brief: str, snapshot: str
    ) -> tuple[dict[str, Any], dict[str, bytes]]:
        """Request-local verified originals; never a cross-request source cache."""
        report = self.frozen_report(bearer, case, brief, snapshot)
        sources, originals = self.sources(bearer, case, inspect_pdf=False)
        current = {(s["version_id"], s["sha256"]) for s in sources}
        recorded = {(s["version_id"], s["sha256"]) for s in report.get("sources", [])}
        if not recorded or recorded != current:
            raise HTTPException(409, "source snapshot changed")
        report["snapshot_hash"] = snapshot
        return report, originals

    def sources(
        self, bearer: str, case: str, *, inspect_pdf: bool = True
    ) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
        manifest = self.client.bundle_manifest(bearer, case)["sources"]
        originals = {}
        sources = []
        for item in manifest:
            row = dict(item)
            try:
                raw = self.client.library.read(
                    bearer=bearer, case_id=case, document_id=row["document_id"], version_id=row["version_id"]
                )
            except PrivateStorageFailure:
                raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
            if len(raw) != row["byte_length"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
                raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
            originals[row["version_id"]] = raw
            if inspect_pdf and row["media_type"] == "application/pdf":
                try:
                    _, manifest = parse_verified_original(
                        document_id=row["document_id"],
                        version_id=row["version_id"],
                        data=raw,
                        media_type=row["media_type"],
                    )
                    row["page_count"] = len(manifest["pages"])
                    row["image_only_pages"] = [
                        p["pdf_page"] for p in manifest["pages"] if p["status"] == "needs_ocr"
                    ]
                    row["image_only"] = len(row["image_only_pages"]) == row["page_count"]
                except ExtractionError:
                    row["page_count"] = 0
                    row["parse_error"] = "unreadable_or_unsupported_pdf"
            sources.append(row)
        return sources, originals

    def load(
        self, bearer: str, case: str, brief: str, *, language_context: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any], bytes]:
        context = self.rpc(bearer, case, "context")
        sources, originals = self.sources(bearer, case)
        drafts = [s for s in sources if s["role"] == "draft" and s["version_id"] == brief]
        if len(drafts) != 1:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        languages = language_context or {"draft_language": None, "source_languages": {}}
        if set(languages.get("source_languages", {})) - {
            s["version_id"] for s in sources if s["role"] == "exhibit"
        }:
            raise HTTPException(422, "language source outside authorized bundle")
        raw = originals[brief]
        discovery = discover_docx_references(raw)
        regions = {r.part: r.text for r in extract_docx_text_regions(raw).regions}
        confirmation = context.get("confirmation")
        inventory = next((x for x in sources if x["role"] == "inventory"), None)
        inventory_readable = False
        inventory_identities: set[tuple[str, str]] = set()
        if inventory is not None:
            try:
                inventory_text = originals[inventory["version_id"]].decode("utf-8")
                inventory_identities = {
                    ("stuk" if r.label.startswith("stuk") else "piece", r.number)
                    for r in detect_exhibit_references(inventory_text, region="inventory")
                }
                inventory_readable = True
            except UnicodeError:
                inventory["parse_error"] = "unreadable_utf8_inventory"
        if confirmation:
            supplied = confirmation["payload"]["entries"]
            supplied_identities = {(e["label"], e["number"]) for e in supplied}
            # Never infer absence from an omitted confirmation row. Inventory
            # bytes, not client JSON, establish known inventory membership.
            normalized = [e for e in supplied if (e["label"], e["number"]) in inventory_identities]
            normalized += [
                {"label": label, "number": number, "source_version_id": None, "pages": []}
                for label, number in sorted(inventory_identities - supplied_identities)
            ]
            confirmation = {
                **confirmation,
                "payload": {
                    **confirmation["payload"],
                    "entries": normalized,
                    "inventory_complete": bool(
                        inventory_readable
                        and confirmation["payload"]["inventory_complete"]
                        and supplied_identities == inventory_identities
                        and not confirmation["payload"].get("exceptions")
                    ),
                },
            }
        inventory_status = (
            InventoryStatus.MISSING
            if inventory is None
            else InventoryStatus.UNPARSEABLE
            if not inventory_readable
            else InventoryStatus.UNCONFIRMED
            if not confirmation
            else InventoryStatus.CONFIRMED_COMPLETE
            if confirmation["payload"]["inventory_complete"]
            else InventoryStatus.INCOMPLETE
        )
        if confirmation:
            initial = build_findings(
                discovery, regions, sources, confirmation, inventory_status=inventory_status
            )
            # Only retrieve stored geometry for explicitly mapped physical pages.
            for source in sources:
                pages = {
                    p["pdf_page"]
                    for e in confirmation["payload"]["entries"]
                    if e.get("source_version_id") == source["version_id"]
                    for p in e["pages"]
                }
                # Resolve actual referenced physical pages independently of the
                # whole-file text status, including scanned pages in mixed PDFs.
                pages.update(
                    f["pdf_page"]
                    for f in initial["findings"]
                    if f["version_id"] == source["version_id"] and f["pdf_page"] is not None
                )
                geometry = {}
                for page in sorted(pages):
                    try:
                        ref, payload = self.client.read_geometry(bearer, source["version_id"], page)
                    except AccessRejected as error:
                        if error.http_status == 503:
                            raise
                        continue
                    words = payload.get("words", [])
                    if (
                        ref.original_sha256 == source["sha256"]
                        and isinstance(words, list)
                        and words
                        and isinstance(words[0], dict)
                    ):
                        w = words[0]
                        geometry[str(page)] = {
                            "crop": {
                                "page_number": page,
                                **{k: w[k] for k in ("left", "top", "width", "height")},
                                "geometry_sha256": ref.geometry_sha256,
                            }
                        }
                source["geometry"] = geometry
        found = build_findings(discovery, regions, sources, confirmation, inventory_status=inventory_status)
        # Both text-layer PDFs and scans take the visual path. Inputs come only
        # from verified private originals; unavailable engines never count as pass.
        visual_pages: dict[tuple[str, int], dict[str, Any]] = {}
        visual_budget = 4
        for finding in found["findings"]:
            version, page_number = finding["version_id"], finding["pdf_page"]
            tail = regions.get(finding["region"], "")[finding["offsets"]["end"] :]
            finding.update(
                quotation_context(
                    tail,
                    draft_language=languages.get("draft_language"),
                    source_language=languages.get("source_languages", {}).get(version),
                )
            )
            if version is None or page_number is None:
                finding["visual_assessment"] = select_visual_assessment(None, finding["quoted_text"])
                assess_fidelity(finding, None)
                continue
            key = (version, page_number)
            if key not in visual_pages:
                source = next(s for s in sources if s["version_id"] == version)
                try:
                    if len(visual_pages) >= visual_budget:
                        raise OCRUnavailable("visual_page_budget_exceeded")
                    visual_pages[key] = getattr(self, "visual", PDFVisualFidelity()).inspect(
                        originals[version], original_sha256=source["sha256"], page_number=page_number
                    )
                except OCRUnavailable as error:
                    visual_pages[key] = {"error": str(error)}
            assessment = select_visual_assessment(visual_pages[key], finding["quoted_text"])
            finding["visual_assessment"] = assessment
            assess_fidelity(finding, visual_pages[key])
            # Identity/pinpoint remain independently checked; visual conflict
            # never changes exhibit identity or claims human semantic support.
        found["coverage"]["visual_pages_attempted"] = len(visual_pages)
        found["coverage"]["visual_pages_completed"] = sum(not p.get("error") for p in visual_pages.values())
        found["coverage"]["visual_findings_not_assessed"] = sum(
            f["visual_assessment"]["state"] == "not_assessed" for f in found["findings"]
        )
        report = {
            "schema": "caseproof-dossier-v1",
            "case_id": case,
            "brief_id": brief,
            "bundle_signature": context["bundle_signature"],
            "confirmation_id": confirmation["request_id"] if confirmation else None,
            "inventory_confirmation": {
                k: confirmation.get(k) for k in ("request_id", "reviewer_id", "timestamp")
            }
            if confirmation
            else None,
            "sources": sources,
            "visual_pages": {v + ":" + str(p): data for (v, p), data in visual_pages.items()},
            **found,
            "professional_certificate": False,
            "filing_status": "not_assessed",
        }
        report["coverage"]["unprocessed_sources"] = sum(bool(s.get("parse_error")) for s in sources)
        report["coverage"]["inventory_exceptions_pending"] = (
            len(confirmation["payload"].get("exceptions", [])) if confirmation else 0
        )
        add_report_contract(report, discovery.region_manifest, languages)
        report["server_receipt"] = self.receipt(report)
        serialized = canonical(report)
        if len(serialized.encode()) > 1_900_000:
            raise HTTPException(422, "visual snapshot budget exceeded; reduce assessed pages")
        report["snapshot_hash"] = hashlib.sha256(serialized.encode()).hexdigest()
        self.rpc(
            bearer, case, "snapshot", {"serialized": serialized, "snapshot_hash": report["snapshot_hash"]}
        )
        return report, raw


def read_dossier_report(
    store: DossierStore,
    bearer: str,
    case: str,
    brief: str,
    snapshot: str | None = None,
    *,
    decisions: bool = False,
) -> tuple[dict[str, Any], bytes]:
    report, original = (
        store.reopen(bearer, case, brief, snapshot) if snapshot else store.load(bearer, case, brief)
    )
    if (
        report.get("schema") != "caseproof-dossier-v1"
        or not report.get("snapshot_hash")
        or (snapshot is not None and report["snapshot_hash"] != snapshot)
    ):
        raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
    if decisions:
        rows = store.rpc(bearer, case, "decisions", {"snapshot_hash": report["snapshot_hash"]})
        if not isinstance(rows.get("decisions"), list):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        report = {**report, "human_decisions": rows["decisions"]}
    return report, original


def create_dossier_router(store: DossierStore | None) -> APIRouter:
    router = APIRouter()
    base = "/v2/matters/{case_id}/briefs/{brief_id}/dossier"

    def active(header: str | None) -> tuple[DossierStore, str]:
        if store is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return store, _token(header)

    @router.get(base)
    def dossier(
        case_id: str,
        brief_id: str,
        snapshot_hash: str | None = None,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        s, bearer = active(authorization)
        return read_dossier_report(s, bearer, case_id, brief_id, snapshot_hash)[0]

    @router.get(base + "/history/{snapshot_hash}")
    def historical_dossier(
        case_id: str, brief_id: str, snapshot_hash: str, authorization: str | None = Header(default=None)
    ) -> dict[str, Any]:
        s, bearer = active(authorization)
        if len(snapshot_hash) != 64 or any(c not in "0123456789abcdef" for c in snapshot_hash):
            raise HTTPException(422, "invalid snapshot identity")
        report = s.frozen_report(bearer, case_id, brief_id, snapshot_hash, historical=True)
        return {
            "mode": "historical_read_only",
            "currentness": "not_asserted",
            "source_availability": "not_assessed",
            "report": report,
        }

    @router.get(base + "/history/{snapshot_hash}/comparison")
    def compare_frozen_findings(
        case_id: str, brief_id: str, snapshot_hash: str,
        current_brief_id: str, current_snapshot_hash: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        from application.litigation.finding_drift import explain_finding_drift

        s, bearer = active(authorization)
        for digest in (snapshot_hash, current_snapshot_hash):
            if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise HTTPException(422, "invalid snapshot identity")
        for version in (brief_id, current_brief_id):
            try:
                if str(UUID(version)) != version:
                    raise ValueError
            except ValueError:
                raise HTTPException(422, "invalid draft version") from None
        old = s.frozen_report(bearer, case_id, brief_id, snapshot_hash, historical=True)
        new = s.frozen_report(bearer, case_id, current_brief_id,
                              current_snapshot_hash, historical=True)
        if (old.get('brief_id') != brief_id or old.get('snapshot_hash') != snapshot_hash
                or new.get('brief_id') != current_brief_id
                or new.get('snapshot_hash') != current_snapshot_hash):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            return explain_finding_drift(old, new)
        except ValueError:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None

    @router.get(base + "/history/{snapshot_hash}/sources/{version_id}/original")
    def historical_original(
        case_id: str,
        brief_id: str,
        snapshot_hash: str,
        version_id: str,
        authorization: str | None = Header(default=None),
    ) -> Response:
        s, bearer = active(authorization)
        if len(snapshot_hash) != 64 or any(c not in "0123456789abcdef" for c in snapshot_hash):
            raise HTTPException(422, "invalid snapshot identity")
        report = s.frozen_report(bearer, case_id, brief_id, snapshot_hash, historical=True)
        matches = [row for row in report.get("sources", []) if row.get("version_id") == version_id]
        if len(matches) != 1:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        row = matches[0]
        try:
            raw = s.client.library.read(
                bearer=bearer, case_id=case_id, document_id=row["document_id"], version_id=version_id
            )
        except PrivateStorageFailure:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
        if len(raw) != row["byte_length"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return Response(
            raw,
            media_type="application/octet-stream",
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Content-Disposition": "attachment; filename=caseproof-historical-original",
                "X-CaseProof-Snapshot": snapshot_hash,
                "X-CaseProof-Original-SHA256": row["sha256"],
            },
        )

    @router.post(base + "/checks")
    def check_with_languages(
        case_id: str,
        brief_id: str,
        body: VerificationOptions,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        s, bearer = active(authorization)
        return s.load(bearer, case_id, brief_id, language_context=body.model_dump())[0]

    @router.get(base + "/snapshots/{snapshot_hash}/references/{reference_id}/correction-anchor")
    def correction_anchor_route(
        case_id: str, brief_id: str, snapshot_hash: str, reference_id: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        s, bearer = active(authorization)
        report, original = s.reopen(bearer, case_id, brief_id, snapshot_hash)
        finding = next((f for f in report["findings"] if f["reference_id"] == reference_id), None)
        if finding is None:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        try:
            index = correction_anchor(original, finding)
            locator = bound_locator(original, finding, brief_id)
        except ValueError:
            raise HTTPException(422, "unsupported or ambiguous correction anchor") from None
        return {"snapshot_hash": snapshot_hash, "brief_version_id": brief_id,
                "reference_id": reference_id, "original_sha256": hashlib.sha256(original).hexdigest(),
                "paragraph_index": index, "before": finding["literal"], "locator_identity": locator}

    @router.get(base + "/snapshots/{snapshot_hash}/references/{reference_id}/correction-operations")
    def correction_operations(
        case_id: str, brief_id: str, snapshot_hash: str, reference_id: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        s, bearer = active(authorization)
        report = s.frozen_report(bearer, case_id, brief_id, snapshot_hash, historical=True)
        if not any(f["reference_id"] == reference_id for f in report["findings"]):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        result = s.revisions.recovery(bearer, case_id, brief_id, snapshot_hash, reference_id)
        if not isinstance(result.get("operations"), list) or len(result["operations"]) > 20:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return {**result, "current_draft_version_id": s.current_draft_version(bearer, case_id)}

    @router.get(base + "/corrections/review-receipt")
    def correction_review_receipt(
        case_id: str, brief_id: str, snapshot_hash: str, reference_id: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        s, bearer = active(authorization)
        if len(snapshot_hash) != 64 or any(c not in "0123456789abcdef" for c in snapshot_hash):
            raise HTTPException(422, "invalid snapshot")
        if not 1 <= len(reference_id) <= 256:
            raise HTTPException(422, "invalid reference")
        return s.correction_review_receipt(bearer, case_id, brief_id, snapshot_hash, reference_id)

    @router.post(base + "/corrections/preview")
    def correction_preview(
        case_id: str,
        brief_id: str,
        body: CorrectionPreviewBody,
        authorization: str | None = Header(default=None),
        if_match: str | None = Header(default=None),
    ) -> dict[str, Any]:
        s, bearer = active(authorization)
        if if_match != "snapshot_id:" + body.snapshot_hash:
            raise HTTPException(412, "snapshot precondition required")
        report, original = reopen_for_mutation(s, bearer, case_id, brief_id, body.snapshot_hash)
        if report["snapshot_hash"] != body.snapshot_hash:
            raise HTTPException(412, "snapshot is stale")
        finding = next((f for f in report["findings"] if f["reference_id"] == body.reference_id), None)
        if finding is None:
            raise HTTPException(422, "unknown correction reference")
        try:
            validate_correction_target(original, finding, brief_id, body)
            derivative = corrected_docx_preview(
                original,
                expected_sha256=body.original_sha256,
                paragraph_index=body.paragraph_index,
                before=body.before,
                after=body.after,
            )
        except ValueError:
            raise HTTPException(422, "unsupported or stale correction range") from None
        return {
            "schema": "caseproof-docx-correction-preview-v1",
            "reference_id": body.reference_id,
            "paragraph_index": body.paragraph_index,
            "before": body.before,
            "after": body.after,
            "brief_version_id": brief_id,
            "snapshot_hash": body.snapshot_hash,
            "committed": False,
            "requires_new_draft_version": True,
            "requires_recheck": True,
            "invalidates_snapshot_hash": body.snapshot_hash,
            "original_sha256": body.original_sha256,
            "derivative_sha256": hashlib.sha256(derivative).hexdigest(),
            "derivative_byte_length": len(derivative),
        }

    @router.post(base + "/corrections/status")
    def correction_status(
        case_id: str,
        brief_id: str,
        body: CorrectionCommitBody,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        s, bearer = active(authorization)
        return s.correction_status(bearer, case_id, brief_id, body)

    @router.post(base + "/corrections/commit")
    def correction_commit(
        case_id: str,
        brief_id: str,
        body: CorrectionCommitBody,
        authorization: str | None = Header(default=None),
        if_match: str | None = Header(default=None),
        idempotency_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        s, bearer = active(authorization)
        if if_match != "snapshot_id:" + body.snapshot_hash:
            raise HTTPException(412, "snapshot precondition required")
        if idempotency_key != body.request_id:
            raise HTTPException(422, "idempotency key must match durable correction request")
        return s.commit_correction(bearer, case_id, brief_id, body)

    @router.post(base + "/recheck")
    def recheck(
        case_id: str, brief_id: str, authorization: str | None = Header(default=None)
    ) -> dict[str, Any]:
        s, bearer = active(authorization)
        # The requested version must be current, not merely an accessible historical
        # derivative. Check again after processing to fence concurrent activation.
        if s.current_draft_version(bearer, case_id) != brief_id:
            raise HTTPException(409, "superseded draft cannot be rechecked")
        report = s.load(bearer, case_id, brief_id)[0]
        if report.get("brief_id") != brief_id or s.current_draft_version(bearer, case_id) != brief_id:
            raise HTTPException(409, "draft superseded during recheck")
        return report

    @router.post(base + "/confirmation")
    def confirm(
        case_id: str,
        brief_id: str,
        body: InventoryConfirmation,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        s, bearer = active(authorization)
        try:
            UUID(body.request_id)
            sources, originals = s.sources(bearer, case_id)
            if not any(x["role"] == "draft" and x["version_id"] == brief_id for x in sources):
                raise ValueError("draft outside preserved matter")
            inventory = [x for x in sources if x["role"] == "inventory"]
            if len(inventory) != 1:
                raise ValueError("missing inventory")
            inventory_text = originals[inventory[0]["version_id"]].decode("utf-8")
            refs = detect_exhibit_references(inventory_text, region="inventory")
            for exception in body.exceptions:
                if exception.citation not in inventory_text:
                    raise ValueError("inventory exception not anchored in original")
            identities = {("stuk" if r.label.startswith("stuk") else "piece", r.number) for r in refs}
            for entry in body.entries:
                if (entry.label, entry.number) not in identities:
                    raise ValueError("identity absent from preserved inventory")
                matches = [
                    x
                    for x in sources
                    if x["version_id"] == entry.source_version_id and x["role"] == "exhibit"
                ]
                if entry.source_version_id is not None and len(matches) != 1:
                    raise ValueError("source outside bundle")
                if entry.pages and (
                    not matches or any(p.pdf_page > matches[0].get("page_count", 0) for p in entry.pages)
                ):
                    raise ValueError("page outside preserved source")
        except (ValueError, UnicodeError):
            raise HTTPException(422, "invalid inventory/source/page confirmation") from None
        if body.inventory_complete and {(e.label, e.number) for e in body.entries} != identities:
            raise HTTPException(
                422, "complete inventory confirmation must include every discovered inventory identity"
            )
        payload = body.model_dump(exclude={"bundle_signature", "request_id"})
        return s.rpc(
            bearer,
            case_id,
            "confirm",
            {"bundle_signature": body.bundle_signature, "request_id": body.request_id, "payload": payload},
        )

    @router.get(base + "/reviews", response_model=ReviewLedgerView, response_model_by_alias=True)
    def review_ledger(
        case_id: str,
        brief_id: str,
        snapshot_hash: str,
        authorization: str | None = Header(default=None),
    ) -> ReviewLedgerView:
        s, bearer = active(authorization)
        # A current review is never authorized by a historical snapshot alone.
        report, _ = s.reopen(bearer, case_id, brief_id, snapshot_hash)
        rows = s.rpc(bearer, case_id, "decisions", {"snapshot_hash": snapshot_hash})
        if not isinstance(rows.get("decisions"), list):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            result = ReviewLedgerView.model_validate({
                "schema": "caseproof-review-ledger-v1",
                "case_id": case_id,
                "brief_id": brief_id,
                "snapshot_hash": report["snapshot_hash"],
                "decisions": rows["decisions"],
            })
            references = {f["reference_id"] for f in report["findings"]}
            if any(decision.reference_id not in references for decision in result.decisions):
                raise ValueError("Orphan review")
        except (ValidationError, ValueError, KeyError):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        return result

    @router.get(
        base + "/snapshots/{snapshot_hash}/references/{reference_id}/draft-context",
        response_model=DraftExcerptView,
        response_model_by_alias=True,
    )
    def draft_context(
        case_id: str, brief_id: str, snapshot_hash: str, reference_id: str,
        authorization: str | None = Header(default=None),
    ) -> DraftExcerptView:
        s, bearer = active(authorization)
        report, original = s.reopen(bearer, case_id, brief_id, snapshot_hash)
        finding = next((f for f in report["findings"] if f["reference_id"] == reference_id), None)
        if finding is None:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        text_by_part = {r.part: r.text for r in extract_docx_text_regions(original).regions}
        region = finding.get("region")
        offsets = finding.get("offsets")
        literal = finding.get("literal")
        excerpt = ""
        start = end = 0
        available = False
        if (
            isinstance(region, str)
            and region in text_by_part
            and isinstance(offsets, dict)
            and type(offsets.get("start")) is int
            and type(offsets.get("end")) is int
            and isinstance(literal, str)
        ):
            source_text = text_by_part[region]
            a, b = offsets["start"], offsets["end"]
            if 0 <= a < b <= len(source_text) and source_text[a:b] == literal:
                left = max(0, a - 750)
                right = min(len(source_text), b + 750)
                if right - left <= 2400:
                    excerpt = source_text[left:right]
                    start, end = a - left, b - left
                    available = True
        return DraftExcerptView(
            schema="caseproof-draft-excerpt-v1",
            case_id=case_id, brief_id=brief_id, snapshot_hash=snapshot_hash,
            reference_id=reference_id, original_sha256=hashlib.sha256(original).hexdigest(),
            available=available, region=region if available else None,
            excerpt=excerpt, selection_start=start, selection_end=end,
            reason=None if available else "unsupported_or_ambiguous_anchor",
        )

    @router.post(base + "/reviews")
    def review(
        case_id: str,
        brief_id: str,
        body: VisualDecisionBody,
        authorization: str | None = Header(default=None),
        if_match: str | None = Header(default=None),
        idempotency_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        s, bearer = active(authorization)
        if if_match != "snapshot_id:" + body.snapshot_hash:
            raise HTTPException(412, "snapshot precondition required")
        if idempotency_key != str(body.request_id):
            raise HTTPException(422, "idempotency key must match durable review request")
        report, _ = reopen_for_mutation(s, bearer, case_id, brief_id, body.snapshot_hash)
        finding = next((f for f in report["findings"] if f["reference_id"] == body.reference_id), None)
        if report["snapshot_hash"] != body.snapshot_hash:
            raise HTTPException(412, "snapshot is stale")
        if finding is None:
            raise HTTPException(409, "stale or unknown finding")
        if body.decision == "CONFIRMED_SUPPORTED" and finding["technical_check"] != "checked":
            raise HTTPException(409, "resolve identity and pinpoint before confirming support")
        required = {r["region_id"] for r in finding.get("visual_assessment", {}).get("regions", [])}
        if set(body.reviewed_region_ids) != required:
            raise HTTPException(409, "inspect and explicitly confirm every selected visual region")
        payload = body.model_dump(mode="json")
        return s.rpc(bearer, case_id, "review", payload)

    @router.get(base + "/export")
    def export(
        case_id: str,
        brief_id: str,
        format: Literal["json", "markdown", "docx"] = "json",
        snapshot_hash: str | None = None,
        authorization: str | None = Header(default=None),
    ) -> Response:
        s, bearer = active(authorization)
        report, original = read_dossier_report(s, bearer, case_id, brief_id, snapshot_hash, decisions=True)
        headers = {"X-CaseProof-Snapshot": report["snapshot_hash"], "Cache-Control": "no-store"}
        if format == "docx":
            try:
                data = annotated_docx(original, report)
            except ValueError:
                raise HTTPException(422, "draft cannot be annotated") from None
            return Response(
                data,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={
                    **headers,
                    "X-CaseProof-Export-SHA256": hashlib.sha256(data).hexdigest(),
                    "X-Content-Type-Options": "nosniff",
                    "Content-Disposition": "attachment; filename=caseproof-annotated.docx",
                },
            )
        content = render_dossier_export(report, format)
        headers.update(
            {
                "X-CaseProof-Export-SHA256": hashlib.sha256(content.encode()).hexdigest(),
                "X-Content-Type-Options": "nosniff",
            }
        )
        return Response(
            content,
            media_type=("text/markdown" if format == "markdown" else "application/json"),
            headers=headers,
        )

    def frozen_regions(
        s: DossierStore, bearer: str, case: str, brief: str, snapshot: str
    ) -> list[dict[str, Any]]:
        # The guarded read RPC checks current membership/grants, retention,
        # bundle and inventory freshness in one transaction. A frozen PNG does
        # not require re-downloading/re-parsing every original on every request.
        report = s.frozen_report(bearer, case, brief, snapshot)
        return [
            r
            for page in report.get("visual_pages", {}).values()
            for r in [*page.get("regions", []), *([page["page_context"]] if page.get("page_context") else [])]
        ]

    @router.post(base + "/snapshots/{snapshot_hash}/crops")
    def visual_crop_batch(
        case_id: str,
        brief_id: str,
        snapshot_hash: str,
        body: CropBatchBody,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        s, bearer = active(authorization)
        if len(set(body.region_ids)) != len(body.region_ids) or any(
            len(r) != 64 or any(c not in "0123456789abcdef" for c in r) for r in body.region_ids
        ):
            raise HTTPException(422, "bounded unique crop identities required")
        regions = frozen_regions(s, bearer, case_id, brief_id, snapshot_hash)
        crops = []
        for identity in body.region_ids:
            selected = [r for r in regions if r["region_id"] == identity]
            if len(selected) != 1:
                raise HTTPException(404, "visual region unavailable")
            region = selected[0]
            png = base64.b64decode(region["crop_base64"], validate=True)
            if hashlib.sha256(png).hexdigest() != region["crop_sha256"]:
                raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
            crops.append(
                {k: region[k] for k in ("region_id", "crop_sha256", "original_sha256", "crop_base64")}
            )
        return {
            "snapshot_hash": snapshot_hash,
            "crops": crops,
            "source_availability": "verified_at_snapshot_creation",
        }

    @router.get(base + "/snapshots/{snapshot_hash}/regions/{region_id}/crop")
    def visual_crop(
        case_id: str,
        brief_id: str,
        snapshot_hash: str,
        region_id: str,
        authorization: str | None = Header(default=None),
    ) -> Response:
        s, bearer = active(authorization)
        matches = [
            r
            for r in frozen_regions(s, bearer, case_id, brief_id, snapshot_hash)
            if r["region_id"] == region_id
        ]
        if len(matches) != 1:
            raise HTTPException(404, "visual region unavailable")
        region = matches[0]
        try:
            png = base64.b64decode(region["crop_base64"], validate=True)
        except (ValueError, KeyError):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        if hashlib.sha256(png).hexdigest() != region["crop_sha256"]:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return Response(
            png,
            media_type="image/png",
            headers={
                "Cache-Control": "no-store",
                "X-CaseProof-Crop-SHA256": region["crop_sha256"],
                "X-CaseProof-Original-SHA256": region["original_sha256"],
                "X-CaseProof-Snapshot": snapshot_hash,
                "X-CaseProof-Original-Availability": "verified_at_snapshot_creation",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @router.get(base + "/sources/{version_id}/original")
    def original(
        case_id: str, brief_id: str, version_id: str, authorization: str | None = Header(default=None),
        snapshot_hash: str | None = None,
    ) -> Response:
        s, bearer = active(authorization)
        if snapshot_hash is not None:
            if len(snapshot_hash) != 64 or any(c not in "0123456789abcdef" for c in snapshot_hash):
                raise HTTPException(422, "invalid snapshot identity")
            report, files = s.reopen_originals(bearer, case_id, brief_id, snapshot_hash)
            matches = [row for row in report.get("sources", []) if row.get("version_id") == version_id]
            if len(matches) != 1:
                raise AccessRejected(AccessFailure.RESOURCE_MASKED)
            source = matches[0]
            raw = files.get(version_id)
            if (not isinstance(raw, bytes) or len(raw) != source.get("byte_length")
                    or hashlib.sha256(raw).hexdigest() != source.get("sha256")):
                raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
            return Response(raw, media_type="application/octet-stream", headers={
                "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                "Content-Disposition": "attachment; filename=caseproof-original",
                "X-CaseProof-Snapshot": snapshot_hash,
                "X-CaseProof-Original-SHA256": source["sha256"],
            })
        sources, files = s.sources(bearer, case_id)
        if not any(x["role"] == "draft" and x["version_id"] == brief_id for x in sources):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        source = next((x for x in sources if x["version_id"] == version_id), None)
        if source is None:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        return Response(
            files[version_id],
            media_type="application/octet-stream",
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Content-Disposition": "attachment; filename=caseproof-original",
                "X-CaseProof-Original-SHA256": source["sha256"],
            },
        )

    @router.get(base + "/sources/{version_id}/pages/{page_number}")
    def page(
        case_id: str,
        brief_id: str,
        version_id: str,
        page_number: int,
        authorization: str | None = Header(default=None),
    ) -> Response:
        s, bearer = active(authorization)
        sources, files = s.sources(bearer, case_id)
        if not any(x["role"] == "draft" and x["version_id"] == brief_id for x in sources):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        source = next((x for x in sources if x["version_id"] == version_id), None)
        if not source or not 1 <= page_number <= source.get("page_count", 0):
            raise HTTPException(404, "source page unavailable")
        writer = PdfWriter()
        writer.add_page(PdfReader(io.BytesIO(files[version_id])).pages[page_number - 1])
        out = io.BytesIO()
        writer.write(out)
        return Response(
            out.getvalue(),
            media_type="application/pdf",
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "X-CaseProof-Original-SHA256": source["sha256"],
                "X-CaseProof-PDF-Page": str(page_number),
            },
        )

    from apps.api.docx_editor_api import create_document_editor_router
    from apps.api.dossier_export_release import create_release_router

    router.include_router(create_release_router(store))
    router.include_router(create_document_editor_router(store))
    return router
