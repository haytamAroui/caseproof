"""Live SignedBriefPublisher adapter over pinned PostgREST RPCs.

Targets the proposed signed-workbench RPC surface (migration NOT applied;
see docs proposal 2026-11-23). Each RPC is security definer and remains the
write gate: this adapter validates caller input, forwards exact bounded
arguments and strictly validates the structured result. Business outcomes
are payload-contractual, never inferred from HTTP status beyond denial:

    {"ok": true, ...result fields...}
    {"ok": false, "error": "denied" | "invalid" | "stale_revision"
                          | "duplicate_version" | "conflict"}

denied maps to masked PrivateStorageDenied; invalid/stale/duplicate/
conflict map to ValueError (immutable graph conflict), matching the port
contract. The mapping page space rules (real physical inventory, explicit
unpaginated marker, out-of-inventory rejection) are enforced server side by
the RPC; this adapter only guarantees the arguments are well-formed and the
result honestly shaped.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from apps.api.litigation_development_app import (
    SignedDocumentRegistration,
    SignedDocumentSummary,
    SignedDocumentVersionSummary,
    SignedExhibitConfirmation,
    SignedPublishOutcome,
)
from apps.api.signed_supabase_originals import PrivateStorageDenied, PrivateStorageFailure

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MEDIA_TYPES = {
    "application/pdf",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_MAPPING_KEYS = {"pdf_page", "printed_page", "bundle_page"}
_MAX_MAPPINGS = 512
_MAX_PAGE = 100_000
_MEDIA_MAX_BYTES = 3 * 1024 * 1024

RpcCaller = Callable[..., Any]

__all__ = ["LiveSignedBriefPublisher"]


def _uuid(value: object, field_name: str) -> str:
    if type(value) is not str or not _UUID.fullmatch(value):
        raise ValueError(f"invalid {field_name}")
    return value


def _response_uuid(value: object) -> str:
    if type(value) is not str or not _UUID.fullmatch(value):
        raise PrivateStorageFailure("RPC result outside the signed contract")
    return value


def _response_int(value: object, *, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise PrivateStorageFailure("RPC result outside the signed contract")
    return value


def _int(value: object, field_name: str, *, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"invalid {field_name}")
    return value


def _validated_mappings(page_mappings: object) -> list[dict[str, int]] | None:
    if page_mappings is None:
        return None
    if not isinstance(page_mappings, (list, tuple)) or not 1 <= len(page_mappings) <= _MAX_MAPPINGS:
        raise ValueError("invalid exhibit declaration")
    seen: set[int] = set()
    out: list[dict[str, int]] = []
    for mapping in page_mappings:
        if not isinstance(mapping, dict) or set(mapping) - _MAPPING_KEYS or "pdf_page" not in mapping:
            raise ValueError("invalid exhibit declaration")
        pdf = mapping["pdf_page"]
        if type(pdf) is not int or not 1 <= pdf <= _MAX_PAGE or pdf in seen:
            raise ValueError("invalid exhibit declaration")
        row = {"pdf_page": pdf}
        for key in ("printed_page", "bundle_page"):
            value = mapping.get(key)
            if value is not None:
                if type(value) is not int or not 1 <= value <= _MAX_PAGE:
                    raise ValueError("invalid exhibit declaration")
                row[key] = value
        seen.add(pdf)
        out.append(row)
    return out


class LiveSignedBriefPublisher:
    """SignedBriefPublisher over the live signed RPC surface."""

    def __init__(self, *, call_rpc: RpcCaller, publishable_key: str) -> None:
        if not callable(call_rpc) or not isinstance(publishable_key, str):
            raise ValueError("invalid live publisher composition")
        self._rpc = call_rpc
        self._key = publishable_key

    def _call(self, bearer: str, name: str, args: dict[str, Any]) -> dict[str, Any]:
        result = self._rpc(publishable_key=self._key, bearer=bearer, name=name, args=args)
        if not isinstance(result, dict) or type(result.get("ok")) is not bool:
            raise PrivateStorageFailure("RPC result outside the signed contract")
        if result["ok"] is not True:
            error = result.get("error")
            if error == "denied":
                raise PrivateStorageDenied("Private source unavailable")
            if error in {"invalid", "stale_revision", "duplicate_version", "conflict"}:
                raise ValueError("immutable graph conflict")
            raise PrivateStorageFailure("RPC result outside the signed contract")
        return result

    def list_documents(self, *, bearer: str, case_id: str) -> tuple[SignedDocumentSummary, ...]:
        result = self._call(bearer, "caseproof_signed_list_documents",
                            {"p_case": _uuid(case_id, "case_id")})
        documents = result.get("documents")
        if not isinstance(documents, list) or len(documents) > 512:
            raise PrivateStorageFailure("RPC result outside the signed contract")
        summaries = []
        for document in documents:
            if not isinstance(document, dict):
                raise PrivateStorageFailure("RPC result outside the signed contract")
            versions_raw = document.get("versions")
            if not isinstance(versions_raw, list) or len(versions_raw) > 64:
                raise PrivateStorageFailure("RPC result outside the signed contract")
            versions = []
            for version in versions_raw:
                if not isinstance(version, dict):
                    raise PrivateStorageFailure("RPC result outside the signed contract")
                media_type = version.get("media_type")
                sha256_hex = version.get("sha256_hex")
                if (
                    type(media_type) is not str or media_type not in _MEDIA_TYPES
                    or type(sha256_hex) is not str or not _SHA256.fullmatch(sha256_hex)
                ):
                    raise PrivateStorageFailure("RPC result outside the signed contract")
                versions.append(SignedDocumentVersionSummary(
                    version_id=_response_uuid(version.get("version_id")),
                    version_number=_response_int(version.get("version_number"), low=1, high=1_000_000),
                    media_type=media_type,
                    byte_length=_response_int(version.get("byte_length"), low=1, high=_MEDIA_MAX_BYTES),
                    sha256_hex=sha256_hex,
                ))
            label = document.get("label")
            if type(label) is not str or not 0 < len(label) <= 200:
                raise PrivateStorageFailure("RPC result outside the signed contract")
            summaries.append(SignedDocumentSummary(
                document_id=_response_uuid(document.get("document_id")),
                label=label,
                versions=tuple(versions),
            ))
        return tuple(summaries)

    def register_source_version(
        self,
        *,
        bearer: str,
        case_id: str,
        label: str,
        media_type: str,
        byte_length: int,
        sha256_hex: str,
    ) -> SignedDocumentRegistration:
        if (
            type(label) is not str or not 0 < len(label.strip()) <= 200
            or "\r" in label or "\n" in label
            or media_type not in _MEDIA_TYPES
            or type(byte_length) is not int or not 0 < byte_length <= _MEDIA_MAX_BYTES
            or type(sha256_hex) is not str or not _SHA256.fullmatch(sha256_hex)
        ):
            raise ValueError("invalid source declaration")
        result = self._call(bearer, "caseproof_signed_register_source", {
            "p_case": _uuid(case_id, "case_id"),
            "p_label": label,
            "p_media_type": media_type,
            "p_byte_length": byte_length,
            "p_sha256": sha256_hex,
        })
        return SignedDocumentRegistration(
            document_id=_response_uuid(result.get("document_id")),
            version_id=_response_uuid(result.get("version_id")),
        )

    def confirm_exhibit(
        self,
        *,
        bearer: str,
        case_id: str,
        document_id: str,
        version_id: str,
        display_label: str,
        page_mappings: object = None,
    ) -> SignedExhibitConfirmation:
        if (
            type(display_label) is not str or not 0 < len(display_label.strip()) <= 200
            or "\r" in display_label or "\n" in display_label
        ):
            raise ValueError("invalid exhibit declaration")
        mappings = _validated_mappings(page_mappings)
        args: dict[str, Any] = {
            "p_case": _uuid(case_id, "case_id"),
            "p_document": _uuid(document_id, "document_id"),
            "p_version": _uuid(version_id, "version_id"),
            "p_label": display_label,
        }
        if mappings is not None:
            args["p_page_mappings"] = mappings
        result = self._call(bearer, "caseproof_signed_confirm_exhibit", args)
        return SignedExhibitConfirmation(
            exhibit_id=_response_uuid(result.get("exhibit_id")),
            exhibit_revision=_response_int(result.get("exhibit_revision"), low=0, high=1_000_000),
        )

    def publish_uploaded(
        self,
        *,
        bearer: str,
        case_id: str,
        document_id: str,
        version_id: str,
        document_role: str,
        expected_revision: int,
    ) -> SignedPublishOutcome:
        if document_role not in {"own_draft", "opponent_brief"}:
            raise ValueError("invalid document role")
        result = self._call(bearer, "caseproof_signed_publish_uploaded", {
            "p_case": _uuid(case_id, "case_id"),
            "p_document": _uuid(document_id, "document_id"),
            "p_version": _uuid(version_id, "version_id"),
            "p_role": document_role,
            "p_expected_revision": _int(expected_revision, "expected_revision",
                                        low=0, high=1_000_000),
        })
        return SignedPublishOutcome(
            brief_id=_response_uuid(result.get("brief_id")),
            brief_version_id=_response_uuid(result.get("brief_version_id")),
            published_revision=_response_int(result.get("published_revision"), low=0, high=1_000_000),
        )
