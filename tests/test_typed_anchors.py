"""KRN-102: deterministic positive, negative, and adversarial citation tests."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256

import pytest

from packages.evidence_kernel.domain.anchors import (
    AnchorError,
    AnchorResolutionError,
    AnchorResolver,
    EvidenceAnchor,
    LayoutManifest,
    PdfLayout,
    PdfPage,
    PdfRegion,
    ResolvedAnchor,
    SheetRange,
    StructuredField,
    StructuredLayout,
    TextSpan,
    WorkbookLayout,
    WorkbookSheet,
)
from packages.evidence_kernel.domain.source_versions import (
    DerivedRepresentation,
    InMemorySourceRegistry,
    SourceRecordConflict,
    SourceRecordNotFound,
    SourceVersion,
)

STAMP = datetime(2026, 10, 21, 12, tzinfo=UTC)
D = Decimal
SOURCE = b"captured external document bytes"
TEXT = "A😀e\u0301 café"


def hashed(data: bytes) -> str:
    return sha256(data).hexdigest()


def setup(
    basis: str = "unicode_codepoint_zero_based_half_open",
    *,
    text: bytes | None = None,
    tenant: str = "a",
    source_data: bytes = SOURCE,
    document_id: str = "doc",
    version_id: str = "v1",
    representation_id: str = "rep-1",
) -> tuple[AnchorResolver, SourceVersion, DerivedRepresentation]:
    raw = TEXT.encode("utf-8") if text is None else text
    source = SourceVersion(document_id, version_id, hashed(source_data), source_data, STAMP, "application/pdf")
    representation = DerivedRepresentation(
        representation_id=representation_id,
        document_id=document_id,
        version_id=version_id,
        source_sha256_hex=source.sha256_hex,
        sha256_hex=hashed(raw),
        content=raw,
        media_type="text/plain",
        transform_name="trusted-parser",
        transform_version="1.0",
        transform_config_sha256=hashed(b"configuration"),
        coordinate_convention=basis,
        created_at=STAMP,
    )
    registry = InMemorySourceRegistry()
    registry.register_source(tenant, source)
    registry.register_representation(tenant, representation)
    return AnchorResolver(registry), source, representation


def anchor(source: SourceVersion, rep: DerivedRepresentation, locator: object) -> EvidenceAnchor:
    return EvidenceAnchor(
        anchor_id="anchor-1",
        document_id=source.document_id,
        version_id=source.version_id,
        source_sha256_hex=source.sha256_hex,
        representation_id=rep.representation_id,
        representation_sha256_hex=rep.sha256_hex,
        locator=locator,  # type: ignore[arg-type]
    )


def page() -> PdfPage:
    return PdfPage(0, D("595.5"), D("842"), 90)


def pdf_region() -> PdfRegion:
    return PdfRegion(
        page_index=0, x0=D("1"), y0=D("2"), x1=D("100.25"), y1=D("200"),
        page_width=D("595.5"), page_height=D("842"), rotation=90,
    )


def layout(source: SourceVersion, rep: DerivedRepresentation, geometry: object) -> LayoutManifest:
    return LayoutManifest(
        source.document_id, source.version_id, rep.representation_id, rep.sha256_hex,
        geometry,  # type: ignore[arg-type]
    )


def test_unicode_offsets_are_codepoints_not_bytes_or_utf16_units() -> None:
    resolver, src, rep = setup()
    assert resolver.resolve("a", anchor(src, rep, TextSpan(1, 2))).value == "😀"
    assert resolver.resolve("a", anchor(src, rep, TextSpan(2, 4))).value == "e\u0301"
    assert resolver.resolve("a", anchor(src, rep, TextSpan(5, 9))).value == "café"
    assert len(TEXT.encode("utf-8")) > len(TEXT)


def test_text_out_of_bounds_wrong_offsets_and_empty_spans_fail_closed() -> None:
    resolver, src, rep = setup()
    for start, end in ((0, 0), (-1, 1), (2, 1)):
        with pytest.raises(AnchorError):
            TextSpan(start, end)
    with pytest.raises(AnchorResolutionError, match="bounds"):
        resolver.resolve("a", anchor(src, rep, TextSpan(2, 500)))


def test_unicode_normalization_is_not_silently_rewritten() -> None:
    resolver, src, rep = setup()
    assert resolver.resolve("a", anchor(src, rep, TextSpan(2, 4, normalization="none"))).value == "e\u0301"
    with pytest.raises(AnchorResolutionError, match="normalization"):
        resolver.resolve("a", anchor(src, rep, TextSpan(2, 4, normalization="NFC")))


def test_invalid_utf8_and_coordinate_basis_are_unresolvable() -> None:
    resolver, src, rep = setup(text=b"\xffnot UTF8")
    with pytest.raises(AnchorResolutionError, match="UTF-8"):
        resolver.resolve("a", anchor(src, rep, TextSpan(0, 1)))
    resolver, src, rep = setup(basis="different")
    with pytest.raises(AnchorResolutionError, match="coordinate"):
        resolver.resolve("a", anchor(src, rep, TextSpan(0, 1)))


def test_exact_digest_version_and_identity_are_mandatory() -> None:
    resolver, src, rep = setup()
    original = anchor(src, rep, TextSpan(0, 1))
    for field_name, new_value in (
        ("source_sha256_hex", "a" * 64),
        ("representation_sha256_hex", "a" * 64),
    ):
        with pytest.raises(AnchorResolutionError, match="fingerprint"):
            resolver.resolve("a", replace(original, **{field_name: new_value}))
    for field_name, new_value in (
        ("document_id", "other"),
        ("version_id", "other"),
        ("representation_id", "other"),
    ):
        with pytest.raises(SourceRecordNotFound):
            resolver.resolve("a", replace(original, **{field_name: new_value}))


def test_cross_tenant_resolution_does_not_fallback_to_other_scope() -> None:
    resolver, src, rep = setup()
    with pytest.raises(SourceRecordNotFound):
        resolver.resolve("tenant-b", anchor(src, rep, TextSpan(0, 1)))
    with pytest.raises(ValueError, match="tenant"):
        resolver.resolve("", anchor(src, rep, TextSpan(0, 1)))


def test_reocr_never_remaps_an_old_citation() -> None:
    resolver, src, rep = setup()
    original_anchor = anchor(src, rep, TextSpan(1, 2))
    rep2 = replace(rep, representation_id="rep-2", content=b"new OCR text",
                   sha256_hex=hashed(b"new OCR text"))
    resolver.sources.register_representation("a", rep2)
    assert resolver.resolve("a", original_anchor).value == "😀"
    with pytest.raises(AnchorResolutionError, match="fingerprint"):
        resolver.resolve("a", replace(original_anchor, representation_id="rep-2"))


def test_pdf_requires_trusted_page_manifest_and_checks_physical_page_and_rotation() -> None:
    resolver, src, rep = setup(basis="pdf_points_unrotated_bottom_left", text=b"pdf layout bytes")
    pdf = anchor(src, rep, pdf_region())
    with pytest.raises(AnchorResolutionError, match="layout"):
        resolver.resolve("a", pdf)
    resolver.register_layout("a", layout(src, rep, PdfLayout((page(),))))
    resolved = resolver.resolve("a", pdf)
    assert isinstance(resolved, ResolvedAnchor)
    assert resolved.value is None  # KRN-102 does not claim to extract a quote from PDF pixels.
    for locator in (
        replace(pdf_region(), page_index=1),
        replace(pdf_region(), rotation=0),
        replace(pdf_region(), page_width=D("595")),
        replace(pdf_region(), page_height=D("800")),
    ):
        with pytest.raises(AnchorResolutionError):
            resolver.resolve("a", anchor(src, rep, locator))


@pytest.mark.parametrize(
    "change",
    [
        {"x0": D("-1")},
        {"x1": D("600")},
        {"x0": D("40"), "x1": D("40")},
        {"y1": D("843")},
        {"rotation": 45},
        {"page_index": -1},
        {"page_width": D("Infinity")},
        {"page_height": D("NaN")},
        {"x0": D("NaN")},
    ],
)
def test_pdf_invalid_geometry_is_rejected_at_construction(change: dict[str, object]) -> None:
    with pytest.raises(AnchorError):
        replace(pdf_region(), **change)


def test_pdf_page_manifest_must_be_physical_contiguous_and_immutable() -> None:
    with pytest.raises(AnchorError, match="contiguous"):
        PdfLayout((PdfPage(1, D("595"), D("842"), 0),))
    with pytest.raises(AnchorError, match="contiguous"):
        PdfLayout((page(), page()))
    with pytest.raises(FrozenInstanceError):
        page().rotation = 0  # type: ignore[misc]


def test_workbook_valid_range_requires_known_sheet_and_table() -> None:
    resolver, src, rep = setup(basis="spreadsheet_a1_sheet_id", text=b"sheet-layout-bytes")
    a = anchor(src, rep, SheetRange("sheet-uid-1", "AA2:AB5", "table-1"))
    with pytest.raises(AnchorResolutionError, match="layout"):
        resolver.resolve("a", a)
    resolver.register_layout(
        "a", layout(src, rep, WorkbookLayout((WorkbookSheet("sheet-uid-1", 20, 28, ("table-1",)),)))
    )
    assert resolver.resolve("a", a).value is None
    for bad in (
        SheetRange("sheet-name-not-id", "AA2"),
        SheetRange("sheet-uid-1", "AC1"),
        SheetRange("sheet-uid-1", "A21"),
        SheetRange("sheet-uid-1", "AA2", "missing-table"),
    ):
        with pytest.raises(AnchorResolutionError):
            resolver.resolve("a", anchor(src, rep, bad))


@pytest.mark.parametrize(
    "a1",
    ["a1", "A0", "A", "A1:", "A1:B0", "B2:A2", "A2:A1", "A-1", "$A$1", "A1:B2:C3", "1A"],
)
def test_unsupported_or_ambiguous_a1_ranges_fail_closed(a1: str) -> None:
    with pytest.raises(AnchorError):
        SheetRange("sheet", a1)


def test_worksheet_manifest_ambiguity_and_duplicate_table_ids_fail() -> None:
    with pytest.raises(AnchorError, match="ambiguous"):
        WorkbookLayout((WorkbookSheet("s", 4, 4), WorkbookSheet("s", 5, 5)))
    with pytest.raises(AnchorError, match="duplicate"):
        WorkbookSheet("s", 4, 4, ("t", "t"))


def test_structured_json_schema_and_typed_path_resolve_exact_value() -> None:
    data = b'{"line_items":[{"sku":"X","qty":2}],"active":true}'
    resolver, src, rep = setup(basis="json_path_v1", text=data)
    resolver.register_layout("a", layout(src, rep, StructuredLayout("schema-v1")))
    assert resolver.resolve(
        "a", anchor(src, rep, StructuredField("schema-v1", ("line_items", 0, "sku")))
    ).value == "X"
    assert resolver.resolve(
        "a", anchor(src, rep, StructuredField("schema-v1", ("line_items", 0, "qty")))
    ).value == 2
    assert resolver.resolve(
        "a", anchor(src, rep, StructuredField("schema-v1", ("active",)))
    ).value is True
    for path in (("missing",), ("line_items", 2), ("line_items", "0")):
        with pytest.raises(AnchorResolutionError):
            resolver.resolve("a", anchor(src, rep, StructuredField("schema-v1", path)))
    with pytest.raises(AnchorResolutionError, match="schema"):
        resolver.resolve("a", anchor(src, rep, StructuredField("schema-v2", ("active",))))


def test_duplicate_json_keys_invalid_constants_and_invalid_utf8_fail_closed() -> None:
    for payload in (
        b'{"value":1,"value":2}',
        b'{"value":NaN}',
        b"\xff",
        b'{"value":',
    ):
        resolver, src, rep = setup(basis="json_path_v1", text=payload)
        resolver.register_layout("a", layout(src, rep, StructuredLayout("schema-v1")))
        with pytest.raises(AnchorResolutionError):
            resolver.resolve("a", anchor(src, rep, StructuredField("schema-v1", ("value",))))


@pytest.mark.parametrize("bad_path", [(), ("",), (-1,), (True,), (1.2,), ("arr", -1)])
def test_structured_path_disallows_empty_invalid_and_ambiguous_indices(
    bad_path: tuple[object, ...],
) -> None:
    with pytest.raises(AnchorError):
        StructuredField("schema", bad_path)  # type: ignore[arg-type]


def test_wrong_layout_basis_and_digest_do_not_register() -> None:
    resolver, src, rep = setup()
    with pytest.raises(AnchorResolutionError, match="coordinate"):
        resolver.register_layout("a", layout(src, rep, PdfLayout((page(),))))
    with pytest.raises(AnchorResolutionError, match="digest"):
        resolver.register_layout(
            "a", replace(layout(src, rep, StructuredLayout("schema")), representation_sha256_hex="a" * 64)
        )


def test_layout_cannot_be_replaced_or_registered_cross_tenant() -> None:
    resolver, src, rep = setup(basis="pdf_points_unrotated_bottom_left")
    metadata = layout(src, rep, PdfLayout((page(),)))
    with pytest.raises(SourceRecordNotFound):
        resolver.register_layout("other", metadata)
    resolver.register_layout("a", metadata)
    with pytest.raises(SourceRecordConflict):
        resolver.register_layout("a", metadata)


def test_repr_and_input_validation_do_not_accidentally_claim_support_or_leak_values() -> None:
    resolver, src, rep = setup()
    resolved = resolver.resolve("a", anchor(src, rep, TextSpan(0, len(TEXT))))
    assert resolved.value == TEXT
    assert TEXT not in repr(resolved)
    with pytest.raises(AnchorError, match="locator"):
        replace(resolved.anchor, locator=object())  # type: ignore[arg-type]
    with pytest.raises(AnchorError, match="SHA"):
        replace(resolved.anchor, source_sha256_hex="bad")
    with pytest.raises(FrozenInstanceError):
        resolved.anchor.version_id = "new"  # type: ignore[misc]


def test_existing_v1_contracts_remain_independent() -> None:
    from packages.evidence_kernel.domain.evidence import SourceReference
    from packages.evidence_kernel.domain.workflow import DocumentVersion

    assert SourceReference("doc", hashed(SOURCE), "quote").document_id == "doc"
    assert DocumentVersion("doc", "v1", hashed(b"version"), "version").version_id == "v1"
