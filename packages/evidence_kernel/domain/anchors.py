"""KRN-102: typed, representation-bound citation locators.

Citation resolution means only that a location exists in an exact versioned
representation. It does NOT verify a quoted value, the assertion's semantic
support, authenticity, completeness, factual truth, or legal effect.

PDF and workbook bounds rely on layout manifests supplied by a trusted parser
adapter. This in-memory reference does NOT parse PDF or workbook source bytes.
The tenant scope must originate at an authenticated application boundary.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from threading import RLock
from typing import Any, Literal

from packages.evidence_kernel.domain.source_versions import (
    InMemorySourceRegistry,
    SourceRecordConflict,
    SourceRecordNotFound,
)

TEXT_BASIS = "unicode_codepoint_zero_based_half_open"
PDF_BASIS = "pdf_points_unrotated_bottom_left"
SHEET_BASIS = "spreadsheet_a1_sheet_id"
JSON_BASIS = "json_path_v1"
_A1 = re.compile(r"([A-Z]+)([1-9][0-9]*)(?::([A-Z]+)([1-9][0-9]*))?\Z")
_NORMAL_FORMS = {"none", "NFC", "NFD", "NFKC", "NFKD"}


class AnchorError(ValueError):
    """Invalid typed locator or unresolved representation contents."""


class AnchorResolutionError(AnchorError):
    """The exact typed locator cannot be resolved; do not remap implicitly."""


def _required(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise AnchorError(f"{name} required")


def _sha(value: object, name: str) -> None:
    if (not isinstance(value, str) or len(value) != 64
            or any(c not in "0123456789abcdef" for c in value)):
        raise AnchorError(f"{name} must be lowercase SHA-256 hex")


def _nonnegative(value: object, name: str) -> None:
    if type(value) is not int or value < 0:
        raise AnchorError(f"{name} must be a nonnegative integer")


def _positive(value: object, name: str) -> None:
    if type(value) is not int or value < 1:
        raise AnchorError(f"{name} must be a positive integer")


def _size(value: object, name: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
        raise AnchorError(f"{name} must be a positive finite Decimal")


def _rotation(value: object) -> None:
    if type(value) is not int or value not in {0, 90, 180, 270}:
        raise AnchorError("rotation must be one of 0, 90, 180, 270")


def _point(value: object, name: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise AnchorError(f"{name} must be a nonnegative finite Decimal")


@dataclass(frozen=True, slots=True)
class TextSpan:
    start: int
    end: int
    encoding: Literal["utf-8"] = "utf-8"
    normalization: Literal["none", "NFC", "NFD", "NFKC", "NFKD"] = "none"

    def __post_init__(self) -> None:
        _nonnegative(self.start, "start")
        _nonnegative(self.end, "end")
        if self.end <= self.start:
            raise AnchorError("text span must be nonempty and half-open")
        if self.encoding != "utf-8" or self.normalization not in _NORMAL_FORMS:
            raise AnchorError("unsupported text encoding or normalization")


@dataclass(frozen=True, slots=True)
class PdfRegion:
    page_index: int
    x0: Decimal
    y0: Decimal
    x1: Decimal
    y1: Decimal
    page_width: Decimal
    page_height: Decimal
    rotation: int
    coordinate_system: Literal["pdf_points_unrotated_bottom_left"] = PDF_BASIS

    def __post_init__(self) -> None:
        _nonnegative(self.page_index, "physical page index")
        for name in ("x0", "y0", "x1", "y1"):
            _point(getattr(self, name), name)
        _size(self.page_width, "page_width")
        _size(self.page_height, "page_height")
        _rotation(self.rotation)
        if self.coordinate_system != PDF_BASIS:
            raise AnchorError("unsupported PDF coordinate system")
        if not (self.x0 < self.x1 <= self.page_width
                and self.y0 < self.y1 <= self.page_height):
            raise AnchorError("PDF region is out of page bounds")


def _column_number(letters: str) -> int:
    value = 0
    for char in letters:
        value = value * 26 + (ord(char) - ord("A") + 1)
    return value


def _a1_bounds(a1_range: str) -> tuple[int, int, int, int]:
    _required(a1_range, "A1 range")
    if len(a1_range) > 64:
        raise AnchorError("A1 range exceeds supported length")
    match = _A1.fullmatch(a1_range)
    if match is None:
        raise AnchorError("A1 range must be uppercase cells such as A1:B4")
    col1, row1, col2, row2 = match.groups()
    c1, r1 = _column_number(col1), int(row1)
    c2, r2 = _column_number(col2 or col1), int(row2 or row1)
    if r2 < r1 or c2 < c1:
        raise AnchorError("A1 range bounds are reversed")
    return r1, c1, r2, c2


@dataclass(frozen=True, slots=True)
class SheetRange:
    sheet_id: str
    a1_range: str
    table_id: str | None = None

    def __post_init__(self) -> None:
        _required(self.sheet_id, "sheet_id")
        _a1_bounds(self.a1_range)
        if self.table_id is not None:
            _required(self.table_id, "table_id")


@dataclass(frozen=True, slots=True)
class StructuredField:
    schema_id: str
    path: tuple[str | int, ...]

    def __post_init__(self) -> None:
        _required(self.schema_id, "schema_id")
        if not isinstance(self.path, tuple) or not self.path:
            raise AnchorError("structured field requires a nonempty typed path")
        for segment in self.path:
            if type(segment) is int:
                _nonnegative(segment, "array index")
            elif isinstance(segment, str):
                _required(segment, "object field")
            else:
                raise AnchorError("path segments must be string keys or integer indices")


Locator = TextSpan | PdfRegion | SheetRange | StructuredField


@dataclass(frozen=True, slots=True)
class EvidenceAnchor:
    anchor_id: str
    document_id: str
    version_id: str
    source_sha256_hex: str
    representation_id: str
    representation_sha256_hex: str
    locator: Locator

    def __post_init__(self) -> None:
        for name in ("anchor_id", "document_id", "version_id", "representation_id"):
            _required(getattr(self, name), name)
        _sha(self.source_sha256_hex, "source_sha256_hex")
        _sha(self.representation_sha256_hex, "representation_sha256_hex")
        if not isinstance(self.locator, (TextSpan, PdfRegion, SheetRange, StructuredField)):
            raise AnchorError("locator must be a supported typed variant")


@dataclass(frozen=True, slots=True)
class PdfPage:
    page_index: int
    width: Decimal
    height: Decimal
    rotation: int

    def __post_init__(self) -> None:
        _nonnegative(self.page_index, "physical page index")
        _size(self.width, "page width")
        _size(self.height, "page height")
        _rotation(self.rotation)


@dataclass(frozen=True, slots=True)
class PdfLayout:
    pages: tuple[PdfPage, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.pages, tuple) or not self.pages:
            raise AnchorError("PDF layout requires pages")
        if tuple(p.page_index for p in self.pages) != tuple(range(len(self.pages))):
            raise AnchorError("PDF page manifest must be contiguous from physical page zero")


@dataclass(frozen=True, slots=True)
class WorkbookSheet:
    sheet_id: str
    max_row: int
    max_column: int
    table_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _required(self.sheet_id, "sheet_id")
        _positive(self.max_row, "max_row")
        _positive(self.max_column, "max_column")
        if not isinstance(self.table_ids, tuple):
            raise AnchorError("table IDs must be immutable")
        for name in self.table_ids:
            _required(name, "table_id")
        if len(set(self.table_ids)) != len(self.table_ids):
            raise AnchorError("duplicate table identifiers")


@dataclass(frozen=True, slots=True)
class WorkbookLayout:
    sheets: tuple[WorkbookSheet, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.sheets, tuple) or not self.sheets:
            raise AnchorError("workbook layout requires sheets")
        if len({sheet.sheet_id for sheet in self.sheets}) != len(self.sheets):
            raise AnchorError("ambiguous sheet identifier")


@dataclass(frozen=True, slots=True)
class StructuredLayout:
    schema_id: str

    def __post_init__(self) -> None:
        _required(self.schema_id, "schema_id")


LocatorLayout = PdfLayout | WorkbookLayout | StructuredLayout


@dataclass(frozen=True, slots=True)
class LayoutManifest:
    document_id: str
    version_id: str
    representation_id: str
    representation_sha256_hex: str
    layout: LocatorLayout

    def __post_init__(self) -> None:
        for name in ("document_id", "version_id", "representation_id"):
            _required(getattr(self, name), name)
        _sha(self.representation_sha256_hex, "representation_sha256_hex")
        if not isinstance(self.layout, (PdfLayout, WorkbookLayout, StructuredLayout)):
            raise AnchorError("unsupported layout metadata")


@dataclass(frozen=True, slots=True)
class ResolvedAnchor:
    """Location resolution only; extracted content is not a verified claim."""

    anchor: EvidenceAnchor
    value: Any = field(repr=False, default=None)


def _json_unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise AnchorResolutionError("ambiguous duplicate JSON object key")
        result[key] = value
    return result


def _invalid_json_constant(value: str) -> None:
    raise AnchorResolutionError(f"invalid JSON constant: {value}")


@dataclass
class AnchorResolver:
    """In-memory deterministic resolver. The layout register caller is trusted.

    Registration of a layout is a parser-adapter assertion, NOT an independent
    PDF/spreadsheet parser or authenticity check.
    """

    sources: InMemorySourceRegistry
    _manifests: dict[tuple[str, str], LayoutManifest] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    def register_layout(self, tenant_scope: str, manifest: LayoutManifest) -> None:
        representation = self.sources.get_representation_for_source(
            tenant_scope, manifest.document_id, manifest.version_id, manifest.representation_id
        )
        if representation.sha256_hex != manifest.representation_sha256_hex:
            raise AnchorResolutionError("layout representation digest mismatch")
        expected_basis = {
            PdfLayout: PDF_BASIS,
            WorkbookLayout: SHEET_BASIS,
            StructuredLayout: JSON_BASIS,
        }[type(manifest.layout)]
        if representation.coordinate_convention != expected_basis:
            raise AnchorResolutionError("layout coordinate convention mismatch")
        key = (tenant_scope, manifest.representation_id)
        with self._lock:
            if key in self._manifests:
                raise SourceRecordConflict("immutable representation layout already registered")
            self._manifests[key] = manifest

    def resolve(self, tenant_scope: str, anchor: EvidenceAnchor) -> ResolvedAnchor:
        source = self.sources.get_source(tenant_scope, anchor.document_id, anchor.version_id)
        representation = self.sources.get_representation_for_source(
            tenant_scope, anchor.document_id, anchor.version_id, anchor.representation_id
        )
        if (source.sha256_hex != anchor.source_sha256_hex
                or representation.sha256_hex != anchor.representation_sha256_hex
                or representation.source_sha256_hex != anchor.source_sha256_hex):
            raise AnchorResolutionError("source/representation fingerprint mismatch")

        locator = anchor.locator
        if isinstance(locator, TextSpan):
            if representation.coordinate_convention != TEXT_BASIS:
                raise AnchorResolutionError("text offset coordinate convention mismatch")
            try:
                text = representation.content.decode(locator.encoding, errors="strict")
            except UnicodeDecodeError as exc:
                raise AnchorResolutionError("representation is not valid UTF-8") from exc
            if locator.normalization != "none" and not unicodedata.is_normalized(
                locator.normalization, text
            ):
                raise AnchorResolutionError("text normalization differs from anchor basis")
            if locator.end > len(text):
                raise AnchorResolutionError("text span exceeds code-point bounds")
            return ResolvedAnchor(anchor, text[locator.start:locator.end])

        expected_basis = (
            PDF_BASIS if isinstance(locator, PdfRegion)
            else SHEET_BASIS if isinstance(locator, SheetRange)
            else JSON_BASIS
        )
        if representation.coordinate_convention != expected_basis:
            raise AnchorResolutionError("locator coordinate convention mismatch")
        with self._lock:
            manifest = self._manifests.get((tenant_scope, anchor.representation_id))
        if (manifest is None or manifest.document_id != anchor.document_id
                or manifest.version_id != anchor.version_id
                or manifest.representation_sha256_hex != anchor.representation_sha256_hex):
            raise AnchorResolutionError("exact trusted representation layout unavailable")
        layout = manifest.layout
        if isinstance(locator, PdfRegion):
            if not isinstance(layout, PdfLayout) or locator.page_index >= len(layout.pages):
                raise AnchorResolutionError("physical PDF page missing")
            page = layout.pages[locator.page_index]
            if (locator.page_width != page.width or locator.page_height != page.height
                    or locator.rotation != page.rotation):
                raise AnchorResolutionError("PDF page geometry/rotation mismatch")
            return ResolvedAnchor(anchor)

        if isinstance(locator, SheetRange):
            if not isinstance(layout, WorkbookLayout):
                raise AnchorResolutionError("workbook layout type mismatch")
            sheet = next((s for s in layout.sheets if s.sheet_id == locator.sheet_id), None)
            if sheet is None:
                raise AnchorResolutionError("stable sheet ID missing")
            _, _, end_row, end_col = _a1_bounds(locator.a1_range)
            if end_row > sheet.max_row or end_col > sheet.max_column:
                raise AnchorResolutionError("spreadsheet range outside known sheet bounds")
            if locator.table_id is not None and locator.table_id not in sheet.table_ids:
                raise AnchorResolutionError("table identifier missing")
            return ResolvedAnchor(anchor)

        if not isinstance(locator, StructuredField) or not isinstance(layout, StructuredLayout):
            raise AnchorResolutionError("structured path type mismatch")
        if layout.schema_id != locator.schema_id:
            raise AnchorResolutionError("structured schema mismatch")
        try:
            document: Any = json.loads(
                representation.content.decode("utf-8"),
                object_pairs_hook=_json_unique_pairs,
                parse_constant=_invalid_json_constant,
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AnchorResolutionError("representation is not valid JSON UTF-8") from exc
        node = document
        for segment in locator.path:
            if type(segment) is int:
                if not isinstance(node, list) or segment >= len(node):
                    raise AnchorResolutionError("JSON array index unavailable")
                node = node[segment]
            elif not isinstance(node, dict) or segment not in node:
                raise AnchorResolutionError("JSON object field unavailable")
            else:
                node = node[segment]
        return ResolvedAnchor(anchor, node)
