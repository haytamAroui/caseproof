"""S2-008a2: typed, fail-closed metadata codec for KRN-102 evidence locators.

This is NOT a production repository, SQL authorizer, source vault, parser,
citation resolver, or /v2 route. Stored JSONB is untrusted until decoded into
strict kernel types AND checked against a server-chosen exact source/representation
identity. Even a byte-hash match does not establish origin, semantics, completeness
or permission for approval. Source bytes and genuine Auth are separate gates.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from packages.evidence_kernel.domain.anchors import (
    JSON_BASIS,
    PDF_BASIS,
    SHEET_BASIS,
    TEXT_BASIS,
    EvidenceAnchor,
    Locator,
    PdfLayout,
    PdfRegion,
    SheetRange,
    StructuredField,
    StructuredLayout,
    TextSpan,
    WorkbookLayout,
)

LOCATOR_SCHEMA_VERSION = "krn102-locator-v1"
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_A1 = re.compile(r"([A-Z]+)([1-9][0-9]*)(?::([A-Z]+)([1-9][0-9]*))?\Z")
_PROJECTION_KEYS = frozenset({
    "org_id", "case_id", "kernel_anchor_id", "kernel_document_id",
    "kernel_version_id", "kernel_representation_id",
    "source_sha256_hex", "representation_sha256_hex",
    "locator_kind", "locator_schema_version", "locator",
})


class StoredLocatorError(ValueError):
    """Untrusted persisted locator must not be used or silently repaired."""


def _shape(value: object, required: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != required or any(
        type(key) is not str for key in value
    ):
        raise StoredLocatorError("unsupported stored locator keys or shape")
    return value


def _integer(value: object, label: str) -> int:
    if type(value) is not int:
        raise StoredLocatorError(f"{label} must be an exact integer")
    return value


def _text(value: object, label: str) -> str:
    if type(value) is not str or not value.strip() or len(value) > 256:
        raise StoredLocatorError(f"{label} must be bounded nonempty text")
    return value


def _decimal(value: object, label: str) -> Decimal:
    if type(value) is not str or not re.fullmatch(
        r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", value
    ) or len(value) > 64:
        raise StoredLocatorError(f"{label} must be canonical finite Decimal text")
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise StoredLocatorError(f"{label} is not a valid finite decimal") from exc


def _sha(value: object, label: str) -> str:
    if type(value) is not str or not _SHA.fullmatch(value):
        raise StoredLocatorError(f"{label} must be SHA-256 hex")
    return value


def _pairs_unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, item in pairs:
        if name in result:
            raise StoredLocatorError("duplicate persisted JSON key")
        result[name] = item
    return result


def _bad_constant(_: str) -> None:
    raise StoredLocatorError("nonfinite JSON is not supported")


def _parse_json(value: object) -> dict[str, object]:
    if type(value) is str:
        if len(value.encode("utf-8")) > 8192:
            raise StoredLocatorError("oversized persisted locator")
        try:
            value = json.loads(
                value, object_pairs_hook=_pairs_unique, parse_constant=_bad_constant
            )
        except (ValueError, UnicodeError) as exc:
            raise StoredLocatorError("invalid persisted locator JSON") from exc
    if type(value) is not dict:
        raise StoredLocatorError("persisted JSONB locator must be an object")
    # DB adapters may return a decoded dict. We still enforce all nested types.
    try:
        size = len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (ValueError, TypeError, UnicodeError) as exc:
        raise StoredLocatorError("unsupported stored JSONB value") from exc
    if size > 8192:
        raise StoredLocatorError("oversized persisted locator")
    return value


def encode_locator(locator: Locator) -> tuple[str, str, dict[str, object]]:
    """Canonical JSONB-ready value. Decimals remain strings, never floats."""
    if isinstance(locator, TextSpan):
        kind = "text_span"
        payload: dict[str, object] = {
            "start": locator.start, "end": locator.end,
            "encoding": locator.encoding, "normalization": locator.normalization,
        }
    elif isinstance(locator, PdfRegion):
        kind = "pdf_region"
        payload = {
            "page_index": locator.page_index,
            "x0": format(locator.x0, "f"), "y0": format(locator.y0, "f"),
            "x1": format(locator.x1, "f"), "y1": format(locator.y1, "f"),
            "page_width": format(locator.page_width, "f"),
            "page_height": format(locator.page_height, "f"),
            "rotation": locator.rotation,
            "coordinate_system": locator.coordinate_system,
        }
    elif isinstance(locator, SheetRange):
        kind = "sheet_range"
        payload = {
            "sheet_id": locator.sheet_id,
            "a1_range": locator.a1_range,
            "table_id": locator.table_id,
        }
    elif isinstance(locator, StructuredField):
        kind = "structured_field"
        payload = {"schema_id": locator.schema_id, "path": list(locator.path)}
    else:
        raise StoredLocatorError("unsupported kernel locator class")
    return kind, LOCATOR_SCHEMA_VERSION, payload


def decode_locator(kind: object, version: object, payload: object) -> Locator:
    """Strict versioned DB decoder; unknown/partial/mutated data fails closed."""
    if version != LOCATOR_SCHEMA_VERSION:
        raise StoredLocatorError("unrecognized locator schema version")
    obj = _parse_json(payload)
    try:
        if kind == "text_span":
            d = _shape(obj, {"start", "end", "encoding", "normalization"})
            return TextSpan(
                start=_integer(d["start"], "start"),
                end=_integer(d["end"], "end"),
                encoding=d["encoding"],  # type: ignore[arg-type]
                normalization=d["normalization"],  # type: ignore[arg-type]
            )
        if kind == "pdf_region":
            d = _shape(obj, {
                "page_index", "x0", "y0", "x1", "y1", "page_width",
                "page_height", "rotation", "coordinate_system",
            })
            return PdfRegion(
                page_index=_integer(d["page_index"], "page_index"),
                x0=_decimal(d["x0"], "x0"), y0=_decimal(d["y0"], "y0"),
                x1=_decimal(d["x1"], "x1"), y1=_decimal(d["y1"], "y1"),
                page_width=_decimal(d["page_width"], "page_width"),
                page_height=_decimal(d["page_height"], "page_height"),
                rotation=_integer(d["rotation"], "rotation"),
                coordinate_system=d["coordinate_system"],  # type: ignore[arg-type]
            )
        if kind == "sheet_range":
            d = _shape(obj, {"sheet_id", "a1_range", "table_id"})
            if d["table_id"] is not None:
                _text(d["table_id"], "table_id")
            return SheetRange(
                sheet_id=_text(d["sheet_id"], "sheet_id"),
                a1_range=_text(d["a1_range"], "a1_range"),
                table_id=d["table_id"],  # type: ignore[arg-type]
            )
        if kind == "structured_field":
            d = _shape(obj, {"schema_id", "path"})
            path = d["path"]
            if type(path) is not list or len(path) > 128:
                raise StoredLocatorError("structured path must be a bounded array")
            segments: list[str | int] = []
            for part in path:
                if type(part) is str:
                    segments.append(_text(part, "path key"))
                elif type(part) is int and part >= 0:
                    segments.append(part)
                else:
                    raise StoredLocatorError("invalid structured path segment")
            return StructuredField(
                schema_id=_text(d["schema_id"], "schema_id"),
                path=tuple(segments),
            )
    except (ValueError, TypeError) as exc:
        raise StoredLocatorError("invalid typed locator constraints") from exc
    raise StoredLocatorError("unknown persisted locator kind")


@dataclass(frozen=True, slots=True)
class ExpectedEvidenceParent:
    """Server-selected DB scope/identity, NOT authenticated by constructing it."""

    org_id: UUID
    case_id: UUID
    document_id: str
    version_id: str
    representation_id: str
    source_sha256_hex: str
    representation_sha256_hex: str

    def __post_init__(self) -> None:
        for field in ("org_id", "case_id"):
            value = getattr(self, field)
            if not isinstance(value, UUID) or value.int == 0:
                raise StoredLocatorError("trusted parent UUID required")
        for field in ("document_id", "version_id", "representation_id"):
            _text(getattr(self, field), field)
        _sha(self.source_sha256_hex, "source digest")
        _sha(self.representation_sha256_hex, "representation digest")


def encode_anchor_projection(
    anchor: EvidenceAnchor, parent: ExpectedEvidenceParent,
) -> dict[str, object]:
    """Prepare typed adapter data; does NOT write, authorize or establish bytes."""
    if (anchor.document_id, anchor.version_id, anchor.representation_id,
        anchor.source_sha256_hex, anchor.representation_sha256_hex) != (
        parent.document_id, parent.version_id, parent.representation_id,
        parent.source_sha256_hex, parent.representation_sha256_hex
    ):
        raise StoredLocatorError("anchor differs from expected immutable parent")
    kind, version, locator = encode_locator(anchor.locator)
    return {
        "org_id": str(parent.org_id), "case_id": str(parent.case_id),
        "kernel_anchor_id": anchor.anchor_id,
        "kernel_document_id": anchor.document_id,
        "kernel_version_id": anchor.version_id,
        "kernel_representation_id": anchor.representation_id,
        "source_sha256_hex": anchor.source_sha256_hex,
        "representation_sha256_hex": anchor.representation_sha256_hex,
        "locator_kind": kind,
        "locator_schema_version": version,
        "locator": locator,
    }


def decode_anchor_projection(
    row: Mapping[str, object], parent: ExpectedEvidenceParent,
) -> EvidenceAnchor:
    """Rehydrate only the exact server-authorized projection for one parent.

    Callers MUST resolve parent via a trusted membership-scoped DB query;
    constructing ExpectedEvidenceParent from the same untrusted row defeats
    the identity check. This is a metadata contract, not citation resolution.
    """
    if not isinstance(row, Mapping) or set(row.keys()) != _PROJECTION_KEYS:
        raise StoredLocatorError("unsupported evidence projection")
    if row["org_id"] != str(parent.org_id) or row["case_id"] != str(parent.case_id):
        raise StoredLocatorError("foreign tenant or case")
    if (
        row["kernel_document_id"], row["kernel_version_id"],
        row["kernel_representation_id"], row["source_sha256_hex"],
        row["representation_sha256_hex"],
    ) != (
        parent.document_id, parent.version_id, parent.representation_id,
        parent.source_sha256_hex, parent.representation_sha256_hex,
    ):
        raise StoredLocatorError("stale/cross-version evidence projection")
    anchor_id = _text(row["kernel_anchor_id"], "kernel_anchor_id")
    return EvidenceAnchor(
        anchor_id=anchor_id,
        document_id=parent.document_id,
        version_id=parent.version_id,
        source_sha256_hex=parent.source_sha256_hex,
        representation_id=parent.representation_id,
        representation_sha256_hex=parent.representation_sha256_hex,
        locator=decode_locator(
            row["locator_kind"], row["locator_schema_version"], row["locator"],
        ),
    )


def _a1_end(value: str) -> tuple[int, int]:
    m = _A1.fullmatch(value)
    if m is None:
        raise StoredLocatorError("unsupported A1 range")
    col, r1, col2, r2 = m.groups()
    end_col = col2 or col
    end_row = int(r2 or r1)
    n = 0
    for ch in end_col:
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return end_row, n


def validate_against_verified_bytes(
    anchor: EvidenceAnchor,
    *,
    source_bytes: bytes,
    representation_bytes: bytes,
    coordinate_basis: str,
    trusted_layout: PdfLayout | WorkbookLayout | StructuredLayout | None = None,
) -> None:
    """Fail closed unless caller supplies exact byte-matched source+representation.

    Checks exact byte hashes and locator existence. PDF/sheet geometry requires
    independently trusted parser layout (this function cannot authenticate it).
    Never interpret successful return as evidence truth or promotion approval.
    """
    if not isinstance(source_bytes, bytes) or not isinstance(representation_bytes, bytes):
        raise StoredLocatorError("independently acquired exact bytes required")
    if (
        hashlib.sha256(source_bytes).hexdigest() != anchor.source_sha256_hex
        or hashlib.sha256(representation_bytes).hexdigest()
        != anchor.representation_sha256_hex
    ):
        raise StoredLocatorError("source or representation byte digest mismatch")
    locator = anchor.locator
    expected_basis = (
        TEXT_BASIS if isinstance(locator, TextSpan)
        else PDF_BASIS if isinstance(locator, PdfRegion)
        else SHEET_BASIS if isinstance(locator, SheetRange)
        else JSON_BASIS
    )
    if coordinate_basis != expected_basis:
        raise StoredLocatorError("coordinate basis does not match exact representation")
    if isinstance(locator, TextSpan):
        try:
            value = representation_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise StoredLocatorError("representation is not UTF-8") from exc
        if locator.normalization != "none" and not unicodedata.is_normalized(
            locator.normalization, value
        ):
            raise StoredLocatorError("normalization basis has drifted")
        if locator.end > len(value):
            raise StoredLocatorError("text locator outside Unicode code-point bounds")
        return
    if isinstance(locator, PdfRegion):
        if not isinstance(trusted_layout, PdfLayout):
            raise StoredLocatorError("trusted PDF layout required")
        if locator.page_index >= len(trusted_layout.pages):
            raise StoredLocatorError("PDF physical page missing")
        page = trusted_layout.pages[locator.page_index]
        if (page.width, page.height, page.rotation) != (
            locator.page_width, locator.page_height, locator.rotation
        ):
            raise StoredLocatorError("PDF page geometry differs from stored anchor")
        return
    if isinstance(locator, SheetRange):
        if not isinstance(trusted_layout, WorkbookLayout):
            raise StoredLocatorError("trusted workbook layout required")
        sheet = next((s for s in trusted_layout.sheets if s.sheet_id == locator.sheet_id), None)
        if sheet is None:
            raise StoredLocatorError("spreadsheet stable sheet ID unavailable")
        row, col = _a1_end(locator.a1_range)
        if row > sheet.max_row or col > sheet.max_column:
            raise StoredLocatorError("sheet range exceeds trusted bounds")
        if locator.table_id is not None and locator.table_id not in sheet.table_ids:
            raise StoredLocatorError("spreadsheet table ID unavailable")
        return
    if not isinstance(locator, StructuredField) or not isinstance(trusted_layout, StructuredLayout):
        raise StoredLocatorError("trusted structured layout required")
    if trusted_layout.schema_id != locator.schema_id:
        raise StoredLocatorError("structured schema differs from source")
    try:
        document: Any = json.loads(
            representation_bytes.decode("utf-8"),
            object_pairs_hook=_pairs_unique,
            parse_constant=_bad_constant,
        )
    except (ValueError, UnicodeDecodeError) as exc:
        raise StoredLocatorError("invalid structured representation JSON") from exc
    for part in locator.path:
        if type(part) is int:
            if not isinstance(document, list) or part >= len(document):
                raise StoredLocatorError("JSON array coordinate unavailable")
            document = document[part]
        else:
            if not isinstance(document, dict) or part not in document:
                raise StoredLocatorError("JSON field coordinate unavailable")
            document = document[part]
