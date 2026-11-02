"""Loopback workspace intake over installed signed journey/dossier authorities.

Four-original development contract: DOCX, UTF-8 inventory and two PDFs.
All containers/parsers/hashes are checked before registration or Storage writes.
Replay uses durable registration and fresh signed readback, never HTTP success alone.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import http.client
import json
from typing import Any, Literal
from uuid import UUID, uuid5

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from application.documents.file_boundary import DOCX, validate_original_container
from application.extraction.contracts import ExtractionError
from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.dossier_journey import DossierStore, IdentityConfirmation, InventoryReviewException
from apps.api.litigation_evidence_app import _token
from apps.api.litigation_live_journey import HOST, JourneyClient, MatterCreate, safe_original_filename
from apps.api.signed_document_parse import parse_verified_original
from apps.api.signed_supabase_originals import (
    PrivateStorageDenied,
    PrivateStorageExists,
    PrivateStorageFailure,
    PrivateStorageOutcomeUnknown,
)
from domains.disputes.reference_detection import detect_exhibit_references


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class IntakeFile(Contract):
    role: Literal["draft", "inventory", "exhibit"]
    filename: str = Field(min_length=1, max_length=128)
    media_type: Literal[
        "text/plain",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_length: int = Field(ge=1, le=5_242_880)
    content_base64: str = Field(min_length=1, max_length=6_990_600)


class IntakeCommand(Contract):
    request_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    files: list[IntakeFile] = Field(min_length=4, max_length=4)

    @model_validator(mode="after")
    def coherent(self) -> IntakeCommand:
        if str(UUID(self.request_id)) != self.request_id:
            raise ValueError("canonical request required")
        if (
            sorted(f.role for f in self.files) != ["draft", "exhibit", "exhibit", "inventory"]
            or len({f.filename for f in self.files}) != 4
            or sum(f.byte_length for f in self.files) > 12_000_000
        ):
            raise ValueError("one draft, one inventory and two uniquely named PDFs required")
        return self


class Organization(Contract):
    org_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    name: str = Field(min_length=1, max_length=160)


class OrganizationView(Contract):
    schema_version: Literal["caseproof-workspace-create-orgs-v1"] = Field(alias="schema")
    organizations: list[Organization] = Field(max_length=100)


class CreatedMatter(Contract):
    schema_version: Literal["caseproof-workspace-created-v1"] = Field(alias="schema")
    case_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    request_id: str = Field(pattern=r"^[0-9a-f-]{36}$")


class SourceView(Contract):
    role: Literal["draft", "inventory", "exhibit"]
    filename: str = Field(min_length=1, max_length=128)
    document_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    version_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_length: int = Field(ge=1, le=20_971_520)
    media_type: str = Field(max_length=100)
    page_count: int | None = Field(default=None, ge=0, le=200)
    processing: Literal["preserved", "text_extracted", "partial", "unavailable"]
    readback: Literal["verified", "unknown", "integrity_mismatch"] = "unknown"


class IntakeView(Contract):
    schema_version: Literal["caseproof-workspace-intake-v1"] = Field(alias="schema")
    case_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    bundle_signature: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    brief_id: str | None = Field(default=None, pattern=r"^[0-9a-f-]{36}$")
    sources: list[SourceView] = Field(max_length=32)
    entries: list[IdentityConfirmation] = Field(max_length=512)
    exceptions: list[InventoryReviewException] = Field(default_factory=list, max_length=64)
    confirmation_id: str | None = Field(default=None, max_length=128)
    inventory_complete: bool
    readback_complete: bool


def preflight(command: IntakeCommand) -> list[bytes]:
    originals = []
    for source in command.files:
        try:
            safe_original_filename(source.filename)
            raw = base64.b64decode(source.content_base64, validate=True)
            if len(raw) != source.byte_length or hashlib.sha256(raw).hexdigest() != source.sha256:
                raise ValueError("digest/size mismatch")
            expected = {"draft": DOCX, "inventory": "text/plain", "exhibit": "application/pdf"}[source.role]
            if source.media_type != expected:
                raise ValueError("role/media mismatch")
            validate_original_container(raw, expected)
            if source.role == "inventory":
                if len(raw) > 1_048_576 or "\x00" in raw.decode("utf-8"):
                    raise ValueError("invalid inventory")
                candidates = detect_exhibit_references(raw.decode("utf-8"), region="inventory")
                identities = {
                    ("stuk" if r.label.startswith("stuk") else "piece", r.number) for r in candidates
                }
                if len(identities) > 512:
                    raise HTTPException(
                        422,
                        "Inventory supports at most 512 distinct Stuk/Pièce identities; no files written.",
                    )
            else:
                parse_verified_original(
                    document_id="preflight", version_id="preflight", data=raw, media_type=expected
                )
        except (ValueError, UnicodeError, binascii.Error, ExtractionError):
            raise HTTPException(
                422, "An original failed size, digest, filename or format validation; no files written."
            ) from None
        originals.append(raw)
    return originals


class WorkspaceIntake:
    def __init__(self, client: JourneyClient, store: DossierStore):
        self.client, self.store = client, store

    def register(
        self, bearer: str, case: str, request: str, metadata: list[dict[str, Any]]
    ) -> dict[str, Any]:
        con = http.client.HTTPSConnection(HOST, timeout=30)
        try:
            con.request(
                "POST",
                "/rest/v1/rpc/caseproof_dev_register_bundle",
                json.dumps({"p_case": str(UUID(case)), "p_request": request, "p_sources": metadata}).encode(),
                {
                    "apikey": self.client._key,
                    "Authorization": "Bearer " + bearer,
                    "Content-Type": "application/json",
                    "Cache-Control": "no-store",
                },
            )
            response = con.getresponse()
            status, raw = response.status, response.read(32769)
        except (OSError, TimeoutError, http.client.HTTPException):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        finally:
            con.close()
        if status == 409:
            raise HTTPException(409, "Registration conflicts with the current bundle; reopen sources.")
        if status in (400, 401, 403, 404):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        if status != 200 or len(raw) > 32768:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            result = json.loads(raw)
            if result["case_id"] != case or len(result["sources"]) != len(metadata):
                raise ValueError("scope mismatch")
            docs, versions = set(), set()
            for row, supplied in zip(result["sources"], metadata, strict=True):
                if any(row[k] != v for k, v in supplied.items()):
                    raise ValueError("metadata mismatch")
                for key in ("document_id", "version_id"):
                    if str(UUID(row[key])) != row[key] or UUID(row[key]).int == 0:
                        raise ValueError("identity invalid")
                docs.add(row["document_id"])
                versions.add(row["version_id"])
            if len(docs) != 4 or len(versions) != 4:
                raise ValueError("duplicate identity")
        except (ValueError, TypeError, KeyError):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        return dict(result)

    def reserve(self, bearer: str, case: str, command: IntakeCommand) -> IntakeView:
        self.client.call(bearer, "state", case_id=case)
        preflight(command)
        metadata = [f.model_dump(exclude={"content_base64"}) for f in command.files]
        request = str(uuid5(UUID(case), json.dumps(metadata, sort_keys=True, separators=(",", ":"))))
        rows = self.register(bearer, case, request, metadata)["sources"]
        return IntakeView(
            schema="caseproof-workspace-intake-v1",
            case_id=case,
            sources=[SourceView(**r, processing="unavailable") for r in rows],
            entries=[],
            inventory_complete=False,
            readback_complete=False,
        )

    def upload(self, bearer: str, case: str, command: IntakeCommand) -> IntakeView:
        # Permission read before expensive parsing; the SQL/Storage also reauthorize writes.
        self.client.call(bearer, "state", case_id=case)
        originals = preflight(command)
        metadata = [f.model_dump(exclude={"content_base64"}) for f in command.files]
        registered = self.register(
            bearer,
            case,
            str(uuid5(UUID(case), json.dumps(metadata, sort_keys=True, separators=(",", ":")))),
            metadata,
        )
        try:
            # Validate all server refs and organization bindings before the first object write.
            refs = [
                self.client.library.source(
                    bearer=bearer, case_id=case, document_id=r["document_id"], version_id=r["version_id"]
                )
                for r in registered["sources"]
            ]
            if len({ref.org_id for ref, _ in refs}) != 1:
                raise ValueError("cross organization bundle")
            for (ref, length), row in zip(refs, registered["sources"], strict=True):
                if (
                    ref.sha256_hex != row["sha256"]
                    or length != row["byte_length"]
                    or ref.content_type != row["media_type"]
                ):
                    raise ValueError("registered original differs")
            for row, raw in zip(registered["sources"], originals, strict=True):
                params = dict(
                    bearer=bearer, case_id=case, document_id=row["document_id"], version_id=row["version_id"]
                )
                try:
                    existing = self.client.library.read(**params)
                except PrivateStorageDenied:
                    # Missing and masked are deliberately indistinguishable.
                    # Only the signed write policy may authorize a new object.
                    existing = None
                if existing is not None:
                    if existing != raw:
                        raise ValueError("existing original differs")
                    continue
                try:
                    self.client.library.put_once(data=raw, **params)
                except (PrivateStorageDenied, PrivateStorageExists, PrivateStorageOutcomeUnknown):
                    pass  # Only fresh signed readback below establishes completion.
                readback = self.client.library.read(**params)
                if readback != raw:
                    raise ValueError("readback differs")
        except (PrivateStorageFailure, ValueError):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        result = self.context(bearer, case)
        if not result.readback_complete:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return result

    def context(self, bearer: str, case: str) -> IntakeView:
        # State handles empty matters. Bundle context is read only once a bundle exists.
        self.client.call(bearer, "state", case_id=case)
        con = http.client.HTTPSConnection(HOST, timeout=15)
        try:
            con.request(
                "GET",
                "/rest/v1/caseproof_private_source_versions?select=version_id&case_id=eq."
                + str(UUID(case))
                + "&limit=1",
                headers={
                    "apikey": self.client._key,
                    "Authorization": "Bearer " + bearer,
                    "Cache-Control": "no-store",
                },
            )
            response = con.getresponse()
            status, raw = response.status, response.read(8193)
        except (OSError, TimeoutError, http.client.HTTPException):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        finally:
            con.close()
        if status != 200 or len(raw) > 8192:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            rows = json.loads(raw)
            if not isinstance(rows, list):
                raise ValueError("invalid source state")
        except (ValueError, UnicodeError):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        if not rows:
            return IntakeView(
                schema="caseproof-workspace-intake-v1",
                case_id=case,
                sources=[],
                entries=[],
                inventory_complete=False,
                readback_complete=False,
            )
        context = self.store.rpc(bearer, case, "context")
        try:
            sources, originals = self.store.sources(bearer, case)
        except AccessRejected:
            # A partial transfer is not absence and must not be called complete.
            # Reauthorize the manifest after failure; this does not recover bytes.
            self.client.call(bearer, "state", case_id=case)
            pending = self.client.bundle_manifest(bearer, case)["sources"]
            # Each state is independently established through a fresh signed read.
            # Missing and masked Storage objects remain indistinguishable.
            partial = []
            for row in pending:
                try:
                    raw = self.client.library.read(
                        bearer=bearer,
                        case_id=case,
                        document_id=row["document_id"],
                        version_id=row["version_id"],
                    )
                except PrivateStorageFailure:
                    readback = "unknown"
                else:
                    readback = (
                        "verified"
                        if len(raw) == row["byte_length"] and hashlib.sha256(raw).hexdigest() == row["sha256"]
                        else "integrity_mismatch"
                    )
                partial.append(
                    SourceView(
                        **{
                            k: row[k]
                            for k in (
                                "role",
                                "filename",
                                "document_id",
                                "version_id",
                                "sha256",
                                "byte_length",
                                "media_type",
                            )
                        },
                        processing="unavailable",
                        readback=readback,
                    )
                )
            return IntakeView(
                schema="caseproof-workspace-intake-v1",
                case_id=case,
                bundle_signature=context["bundle_signature"],
                sources=partial,
                entries=[],
                inventory_complete=False,
                readback_complete=False,
            )
        inventory = next((s for s in sources if s["role"] == "inventory"), None)
        confirmation = context.get("confirmation")
        payload = confirmation["payload"] if confirmation else {}
        entries = payload.get("entries", [])
        if not confirmation and inventory:
            refs = detect_exhibit_references(
                originals[inventory["version_id"]].decode("utf-8"), region="inventory"
            )
            entries = [
                {
                    "label": "stuk" if r.label.startswith("stuk") else "piece",
                    "number": r.number,
                    "source_version_id": None,
                    "pages": [],
                }
                for r in refs
            ]
            entries = list({(e["label"], e["number"]): e for e in entries}.values())
        projected = []
        for row in sources:
            partial = bool(row.get("image_only_pages") or row.get("parse_error"))
            projected.append(
                SourceView(
                    **{
                        k: row[k]
                        for k in (
                            "role",
                            "filename",
                            "document_id",
                            "version_id",
                            "sha256",
                            "byte_length",
                            "media_type",
                        )
                    },
                    page_count=row.get("page_count"),
                    processing="unavailable"
                    if row.get("parse_error")
                    else "partial"
                    if partial
                    else "text_extracted"
                    if row["role"] == "exhibit"
                    else "preserved",
                    readback="verified",
                )
            )
        current = self.store.rpc(bearer, case, "context")
        if current != context:
            raise HTTPException(409, "Intake changed during readback; refresh sources.")
        return IntakeView(
            schema="caseproof-workspace-intake-v1",
            case_id=case,
            bundle_signature=context["bundle_signature"],
            brief_id=next((s["version_id"] for s in sources if s["role"] == "draft"), None),
            sources=projected,
            entries=entries,
            exceptions=payload.get("exceptions", []),
            confirmation_id=confirmation["request_id"] if confirmation else None,
            inventory_complete=bool(payload.get("inventory_complete") and not payload.get("exceptions")),
            readback_complete=True,
        )


def create_workspace_intake_router(service: WorkspaceIntake | None) -> APIRouter:
    router = APIRouter()

    def active(header: str | None) -> tuple[WorkspaceIntake, str]:
        if service is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return service, _token(header)

    @router.get("/v2/workspace/intake/organizations")
    def organizations(authorization: str | None = Header(default=None)) -> OrganizationView:
        s, bearer = active(authorization)
        result = s.client.call_create_organizations(bearer)
        return OrganizationView(
            schema="caseproof-workspace-create-orgs-v1",
            organizations=[Organization(**r) for r in result["organizations"]],
        )

    @router.post("/v2/workspace/intake/matters")
    def create(body: MatterCreate, authorization: str | None = Header(default=None)) -> CreatedMatter:
        s, bearer = active(authorization)
        result = s.client.call(
            bearer,
            "create",
            request_id=str(body.request_id),
            data={"org_id": str(body.org_id), "name": body.name},
        )
        return CreatedMatter(
            schema="caseproof-workspace-created-v1",
            case_id=result["case_id"],
            request_id=str(body.request_id),
        )

    @router.get("/v2/workspace/intake/matters/{case_id}")
    def context(case_id: UUID, authorization: str | None = Header(default=None)) -> IntakeView:
        s, bearer = active(authorization)
        return s.context(bearer, str(case_id))

    @router.post("/v2/workspace/intake/matters/{case_id}/reservations")
    def reserve(
        case_id: UUID, body: IntakeCommand, authorization: str | None = Header(default=None)
    ) -> IntakeView:
        s, bearer = active(authorization)
        return s.reserve(bearer, str(case_id), body)

    @router.post("/v2/workspace/intake/matters/{case_id}/sources")
    def upload(
        case_id: UUID, body: IntakeCommand, authorization: str | None = Header(default=None)
    ) -> IntakeView:
        s, bearer = active(authorization)
        return s.upload(bearer, str(case_id), body)

    return router
