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


def test_external_dtd_is_rejected_without_network_or_file_access() -> None:
    payload = package({"word/document.xml": '<!DOCTYPE x SYSTEM "file:///etc/passwd"><x/>'})
    result = inventory_docx_regions(payload)
    assert result.coverage_unknown is True
    assert result.reason == "DTD_FORBIDDEN"


def test_internal_entity_is_rejected_without_expansion() -> None:
    payload = package({"word/document.xml": '<!DOCTYPE x [<!ENTITY secret "value">]><x>&secret;</x>'})
    result = inventory_docx_regions(payload)
    assert result.coverage_unknown is True
    assert result.reason == "DTD_FORBIDDEN"


def test_mixed_case_doctype_is_rejected() -> None:
    payload = package({"word/document.xml": '<!DoCtYpE x><x/>'})
    result = inventory_docx_regions(payload)
    assert result.coverage_unknown is True
    assert result.reason == "DTD_FORBIDDEN"


def test_utf16_entity_payloads_abstain_in_inventory_and_extraction() -> None:
    from infrastructure.parsers.docx_text_regions import extract_docx_text_regions

    xml = '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE x [<!ENTITY secret "Stuk 99">]><x>&secret;</x>'
    for encoding in ("utf-16", "utf-16-le", "utf-16-be"):
        for bom in (b"", b"\xff\xfe" if encoding.endswith("le") else b"\xfe\xff" if encoding.endswith("be") else b""):
            stream = BytesIO()
            with ZipFile(stream, "w") as archive:
                archive.writestr("[Content_Types].xml", "<Types/>")
                archive.writestr("word/document.xml", bom + xml.encode(encoding))
            payload = stream.getvalue()
            assert inventory_docx_regions(payload).coverage_unknown
            extraction = extract_docx_text_regions(payload)
            assert extraction.regions == ()
            assert not extraction.coverage_complete


def test_xml_complexity_limits_fail_closed(monkeypatch) -> None:
    from infrastructure.parsers import safe_docx_xml
    from infrastructure.parsers.docx_text_regions import extract_docx_text_regions

    monkeypatch.setattr(safe_docx_xml, "MAX_XML_DEPTH", 4)
    monkeypatch.setattr(safe_docx_xml, "MAX_XML_NODES", 6)
    for document in ("<x><x><x><x><x/></x></x></x></x>", "<x><x/><x/><x/><x/><x/><x/></x>"):
        payload = package({"word/document.xml": document})
        assert inventory_docx_regions(payload).coverage_unknown
        assert not extract_docx_text_regions(payload).coverage_complete
    assert not inventory_docx_regions(package({"word/document.xml": "<x><x/><x/></x>"})).coverage_unknown


def test_utf32_fails_closed() -> None:
    from infrastructure.parsers.docx_text_regions import extract_docx_text_regions

    for encoding in ("utf-32", "utf-32-le", "utf-32-be"):
        stream = BytesIO()
        with ZipFile(stream, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types/>")
            archive.writestr("word/document.xml", "<x/>".encode(encoding))
        payload = stream.getvalue()
        assert inventory_docx_regions(payload).coverage_unknown
        assert extract_docx_text_regions(payload).regions == ()


def test_safe_utf16_text_still_extracts() -> None:
    from infrastructure.parsers.docx_text_regions import extract_docx_text_regions

    xml = (f'<?xml version="1.0" encoding="UTF-16"?><w:document {NS}>'
           '<w:body><w:p><w:r><w:t>Pièce 12</w:t></w:r></w:p></w:body></w:document>')
    for encoding in ("utf-16", "utf-16-le", "utf-16-be"):
        stream = BytesIO()
        with ZipFile(stream, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types/>")
            archive.writestr("word/document.xml", xml.encode(encoding))
        result = extract_docx_text_regions(stream.getvalue())
        assert result.coverage_complete
        assert result.regions[0].text == "Pièce 12"
