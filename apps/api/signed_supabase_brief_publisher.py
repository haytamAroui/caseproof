"""Live SignedBriefPublisher adapter over pinned PostgREST RPCs.

Targets the proposed signed-workbench RPC surface (migration NOT applied;
see docs proposal 2026-11-23). Each RPC is security definer and remains the
write gate: this adapter validates caller input, forwards exact bounded
arguments and strictly validates the structured result. Business outcomes
are payload-contractual, never inferred from HTTP status beyond denial:

    {"ok": true, ...result fields...}
    {"ok": false, "error": "denied" | "invalid" | "stale_revision"
                          | "duplicate_version" | "conflict"}

denied/forbidden map to masked PrivateStorageDenied; invalid/stale/
duplicate/conflict map to ValueError (immutable graph conflict), matching
the port contract.

confirm is raw-read + build + CAS: the adapter reads the register head via
caseproof_signed_exhibit_register, re-validates every stored entry, builds
the append-only register with the domain canonical serializer (byte-
identical to the rest of the system), then calls the write RPC with the
expected revision, the exact payload TEXT and its sha256. publish forwards
the service-computed artifacts (representation, references, assertions,
graph) derived from a verified readback; the RPC independently enforces
the full contract server side (digests verified at write via core sha256,
representation byte-identical to the trusted registry, references resolved
against the confirmed register, CAS), so this adapter never trusts client
input and the write RPC never trusts the service's computation either.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from application.litigation.exhibit_confirmation import serialized_entries
from apps.api.litigation_development_app import (
    SignedDocumentRegistration,
    SignedDocumentSummary,
    SignedDocumentVersionSummary,
    SignedExhibitConfirmation,
    SignedPublishOutcome,
)
from apps.api.signed_supabase_originals import PrivateStorageDenied, PrivateStorageFailure
from domains.disputes.exhibits import ExhibitEntry, ExhibitPage

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


def _parse_entry(raw: object) -> ExhibitEntry:
    """Re-validate one register entry from the raw read before re-serialization."""
    if not isinstance(raw, dict) or set(raw) != {
        "exhibit_id", "display_label", "aliases", "confirmed", "manual_inclusion", "pages"
    }:
        raise PrivateStorageFailure("RPC result outside the signed contract")
    aliases = raw["aliases"]
    pages = raw["pages"]
    if (
        type(raw["exhibit_id"]) is not str
        or type(raw["display_label"]) is not str
        or not isinstance(aliases, list) or len(aliases) > 64
        or any(type(a) is not str for a in aliases)
        or type(raw["confirmed"]) is not bool
        or type(raw["manual_inclusion"]) is not bool
        or not isinstance(pages, list) or not 1 <= len(pages) <= 100_000
    ):
        raise PrivateStorageFailure("RPC result outside the signed contract")
    parsed_pages = []
    for page in pages:
        if not isinstance(page, dict) or set(page) != {
            "source_id", "version_id", "pdf_page", "printed_page", "bundle_page"
        }:
            raise PrivateStorageFailure("RPC result outside the signed contract")
        for key in ("pdf_page", "printed_page", "bundle_page"):
            value = page[key]
            if value is not None and (type(value) is not int or not 1 <= value <= _MAX_PAGE):
                raise PrivateStorageFailure("RPC result outside the signed contract")
        try:
            parsed_pages.append(ExhibitPage(
                page["source_id"], page["version_id"],
                pdf_page=page["pdf_page"], printed_page=page["printed_page"],
                bundle_page=page["bundle_page"],
            ))
        except (TypeError, ValueError):
            raise PrivateStorageFailure("RPC result outside the signed contract") from None
    try:
        return ExhibitEntry(
            raw["exhibit_id"], raw["display_label"], tuple(parsed_pages),
            aliases=tuple(aliases), confirmed=raw["confirmed"],
            manual_inclusion=raw["manual_inclusion"],
        )
    except (TypeError, ValueError):
        raise PrivateStorageFailure("RPC result outside the signed contract") from None


def _build_pages(
    document_id: str, version_id: str,
    mappings: list[dict[str, int]] | None, page_count: int | None,
) -> tuple[ExhibitPage, ...]:
    """Physical inventory only; mappings annotate real pages, never invent any."""
    if mappings is None:
        if page_count is None:
            return (ExhibitPage(document_id, version_id),)
        return tuple(
            ExhibitPage(document_id, version_id, pdf_page=page)
            for page in range(1, page_count + 1)
        )
    if page_count is None or any(m["pdf_page"] > page_count for m in mappings):
        raise ValueError("invalid exhibit declaration")
    merged = {m["pdf_page"]: (m.get("printed_page"), m.get("bundle_page")) for m in mappings}
    return tuple(
        ExhibitPage(
            document_id, version_id, pdf_page=page,
            printed_page=merged[page][0] if page in merged else None,
            bundle_page=merged[page][1] if page in merged else None,
        )
        for page in range(1, page_count + 1)
    )


def _working_brief_id(case_id: str, document_role: str) -> str:
    """Deterministic working brief id; the RPC recomputes it and rejects drift."""
    raw = bytearray(
        hashlib.sha256(f"caseproof-working-brief:{document_role}:{case_id}".encode()).digest()[:16]
    )
    raw[6] = (raw[6] & 0x0F) | 0x40
    raw[8] = (raw[8] & 0x3F) | 0x80
    import uuid as _uuid_module
    return str(_uuid_module.UUID(bytes=bytes(raw)))


def _validated_references(references: object) -> list[dict[str, Any]]:
    if not isinstance(references, list) or len(references) > 512:
        raise ValueError("invalid publish declaration")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for reference in references:
        if (
            not isinstance(reference, dict)
            or set(reference) - {"reference_id", "exhibit_label", "exact_quote", "pdf_page"}
            or not {"reference_id", "exhibit_label", "exact_quote"} <= set(reference)
            or type(reference["reference_id"]) is not str
            or not 1 <= len(reference["reference_id"]) <= 128
            or reference["reference_id"] in seen
            or type(reference["exhibit_label"]) is not str
            or not 1 <= len(reference["exhibit_label"]) <= 160
            or type(reference["exact_quote"]) is not str
            or not 1 <= len(reference["exact_quote"]) <= 4000
        ):
            raise ValueError("invalid publish declaration")
        pdf_page = reference.get("pdf_page")
        if pdf_page is not None and (type(pdf_page) is not int or not 1 <= pdf_page <= _MAX_PAGE):
            raise ValueError("invalid publish declaration")
        seen.add(reference["reference_id"])
        out.append(dict(reference))
    return out


def _validated_assertions(assertions: object, reference_ids: set[str]) -> list[dict[str, Any]]:
    if not isinstance(assertions, list) or len(assertions) > 2048:
        raise ValueError("invalid publish declaration")
    out: list[dict[str, Any]] = []
    for assertion in assertions:
        if (
            not isinstance(assertion, dict)
            or set(assertion) != {
                "claim_id", "reference_id", "text_start", "text_end", "assertion_text",
                "kind", "fact_role", "language", "source_language",
            }
            or type(assertion["claim_id"]) is not str
            or not 1 <= len(assertion["claim_id"]) <= 160
            or assertion["reference_id"] not in reference_ids
            or type(assertion["text_start"]) is not int or assertion["text_start"] < 0
            or type(assertion["text_end"]) is not int
            or assertion["text_end"] <= assertion["text_start"]
            or type(assertion["assertion_text"]) is not str
            or len(assertion["assertion_text"]) > 8000
            or assertion["kind"] not in {"money", "date"}
            or assertion["fact_role"] not in {"payment", "due", "delivery", "invoice"}
            or assertion["language"] not in {"nl", "fr", "en"}
            or assertion["source_language"] not in {"nl", "fr", "en"}
        ):
            raise ValueError("invalid publish declaration")
        out.append(dict(assertion))
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
            if error in {"denied", "forbidden"}:
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
        read = self._call(bearer, "caseproof_signed_exhibit_register", {
            "p_case": _uuid(case_id, "case_id"),
            "p_version": _uuid(version_id, "version_id"),
        })
        revision = _response_int(read.get("register_revision"), low=0, high=1_000_000)
        media_type = read.get("media_type")
        if type(media_type) is not str or media_type not in _MEDIA_TYPES:
            raise PrivateStorageFailure("RPC result outside the signed contract")
        page_count = read.get("page_count")
        if media_type == "application/pdf":
            if type(page_count) is not int or not 1 <= page_count <= _MAX_PAGE:
                raise PrivateStorageFailure("RPC result outside the signed contract")
        else:
            page_count = None
        payload = read.get("payload")
        if payload is None:
            if revision != 0:
                raise PrivateStorageFailure("RPC result outside the signed contract")
            entries: tuple[ExhibitEntry, ...] = ()
        else:
            if not isinstance(payload, dict) or revision < 1:
                raise PrivateStorageFailure("RPC result outside the signed contract")
            entries_raw = payload.get("entries")
            if not isinstance(entries_raw, list) or len(entries_raw) > 512:
                raise PrivateStorageFailure("RPC result outside the signed contract")
            entries = tuple(_parse_entry(raw) for raw in entries_raw)
        if len(entries) >= 512:
            raise ValueError("invalid exhibit declaration")
        pages = _build_pages(
            _uuid(document_id, "document_id"), _uuid(version_id, "version_id"),
            mappings, page_count)
        exhibit_id = "piece-" + uuid4().hex[:12]
        augmented = entries + (
            ExhibitEntry(exhibit_id, display_label.strip(), pages, confirmed=True),
        )
        payload_text = serialized_entries(augmented).decode("utf-8")
        result = self._call(bearer, "caseproof_signed_confirm_exhibit", {
            "p_case": _uuid(case_id, "case_id"),
            "p_document": _uuid(document_id, "document_id"),
            "p_version": _uuid(version_id, "version_id"),
            "p_request": str(uuid4()),
            "p_expected": revision,
            "p_payload": payload_text,
            "p_sha": hashlib.sha256(payload_text.encode("utf-8")).hexdigest(),
        })
        if type(result.get("replay")) is not bool:
            raise PrivateStorageFailure("RPC result outside the signed contract")
        return SignedExhibitConfirmation(
            exhibit_id=exhibit_id,
            exhibit_revision=_response_int(result.get("exhibit_revision"), low=1, high=1_000_000),
        )

    def publish_uploaded(
        self,
        *,
        bearer: str,
        case_id: str,
        document_id: str,
        version_id: str,
        intent_id: str,
        document_role: str,
        expected_revision: int,
        brief_version_id: str,
        request_id: str,
        representation: str,
        representation_sha256: str,
        parser_id: str,
        references: object,
        assertions: object,
        graph_text: str,
        graph_sha256: str,
    ) -> SignedPublishOutcome:
        """Publish a service-computed brief version through the signed RPC.

        The artifacts (representation, references, assertions, graph) MUST be
        derived by the service from a verified readback of the original; the
        RPC independently enforces coherence against the trusted registry and
        both digests at write time, so a direct authenticated caller cannot
        publish content the verifier never derived.
        """
        if document_role not in {"own_draft", "opponent_brief"}:
            raise ValueError("invalid document role")
        if (
            type(representation) is not str
            or not 0 < len(representation.encode("utf-8")) <= 480_000
            or type(representation_sha256) is not str
            or not _SHA256.fullmatch(representation_sha256)
            or hashlib.sha256(representation.encode("utf-8")).hexdigest()
            != representation_sha256
            or type(parser_id) is not str or not 1 <= len(parser_id) <= 64
            or type(graph_text) is not str or len(graph_text) > 200_000
            or type(graph_sha256) is not str or not _SHA256.fullmatch(graph_sha256)
            or hashlib.sha256(graph_text.encode("utf-8")).hexdigest() != graph_sha256
        ):
            raise ValueError("invalid publish declaration")
        refs = _validated_references(references)
        asserts = _validated_assertions(assertions, {r["reference_id"] for r in refs})
        brief_id = _working_brief_id(_uuid(case_id, "case_id"), document_role)
        result = self._call(bearer, "caseproof_signed_publish_uploaded", {
            "p_case": _uuid(case_id, "case_id"),
            "p_brief": brief_id,
            "p_version": _uuid(brief_version_id, "brief_version_id"),
            "p_request": _uuid(request_id, "request_id"),
            "p_expected": _int(expected_revision, "expected_revision", low=0, high=1_000_000),
            "p_document": _uuid(document_id, "document_id"),
            "p_document_version": _uuid(version_id, "version_id"),
            "p_intent": _uuid(intent_id, "intent_id"),
            "p_role": document_role,
            "p_representation": representation,
            "p_representation_sha": representation_sha256,
            "p_parser_id": parser_id,
            "p_references": refs,
            "p_assertions": asserts,
            "p_graph_text": graph_text,
            "p_graph_sha": graph_sha256,
        })
        if type(result.get("replay")) is not bool:
            raise PrivateStorageFailure("RPC result outside the signed contract")
        return SignedPublishOutcome(
            brief_id=brief_id,
            brief_version_id=_uuid(brief_version_id, "brief_version_id"),
            published_revision=_response_int(result.get("revision"), low=1, high=1_000_000),
        )
