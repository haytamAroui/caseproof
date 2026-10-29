"""Synthetic DOCX package fixtures; no customer data."""
from io import BytesIO
from zipfile import ZipFile

from infrastructure.parsers.docx_region_inventory import (
    RegionStatus,
    inventory_docx_regions,
)


def package(parts: dict[str, str]) -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        for name, content in parts.items():
            archive.writestr(name, content)
    return stream.getvalue()


NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def test_discovers_body_header_footnote_and_textbox_without_claiming_scan() -> None:
    payload = package({
        "word/document.xml": f'<w:document {NS}><w:body><w:txbxContent/></w:body></w:document>',
        "word/header1.xml": f'<w:hdr {NS}/>',
        "word/footnotes.xml": f'<w:footnotes {NS}/>',
    })
    result = inventory_docx_regions(payload)
    assert result.coverage_unknown is False
    assert result.regions_discovered == 4
    assert result.regions_scanned == 0
    assert result.full_coverage is False
    assert any(r.kind == "STRUCTURED_CONTENT" and r.status is RegionStatus.UNSUPPORTED for r in result.regions)


def test_tracked_changes_block_frozen_view() -> None:
    payload = package({"word/document.xml": f'<w:document {NS}><w:body><w:del/></w:body></w:document>'})
    result = inventory_docx_regions(payload)
    assert any(r.status is RegionStatus.REVISION_UNRESOLVED for r in result.regions)


def test_malformed_docx_abstains() -> None:
    assert inventory_docx_regions(b"bad").coverage_unknown
    assert inventory_docx_regions(package({"word/header1.xml": "<x/>"})).reason == "NOT_DOCX"


def test_unrecognized_word_part_is_reported() -> None:
    payload = package({
        "word/document.xml": f'<w:document {NS}/>',
        "word/otherStory.xml": "<x/>",
    })
    result = inventory_docx_regions(payload)
    assert any(r.kind == "UNKNOWN_WORD_PART" for r in result.regions)


def test_doctype_is_rejected() -> None:
    payload = package({"word/document.xml": '<!DOCTYPE x [<!ENTITY x "a">]><x/>'})
    assert inventory_docx_regions(payload).reason == "DTD_FORBIDDEN"
