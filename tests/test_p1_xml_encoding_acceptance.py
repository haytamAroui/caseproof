"""Synthetic, deterministic XML boundary cases for both DOCX discovery paths."""
from io import BytesIO
from zipfile import ZipFile

import pytest

from infrastructure.parsers.docx_region_inventory import inventory_docx_regions
from infrastructure.parsers.docx_text_regions import extract_docx_text_regions
from infrastructure.parsers.safe_docx_xml import parse_docx_xml

NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
ENCODINGS = [
    ("utf-8", b""), ("utf-8", b"\xef\xbb\xbf"),
    ("utf-16-le", b""), ("utf-16-le", b"\xff\xfe"),
    ("utf-16-be", b""), ("utf-16-be", b"\xfe\xff"),
]


def package(document: bytes) -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", document)
    return stream.getvalue()


@pytest.mark.parametrize(("encoding", "bom"), ENCODINGS)
@pytest.mark.parametrize("declaration", [
    '<!DOCTYPE w:document>',
    '<!DOCTYPE w:document [<!ENTITY x "Stuk 99">]>',
    '<!DOCTYPE w:document SYSTEM "file:///not-accessible">',
])
def test_hostile_declarations_fail_closed(encoding: str, bom: bytes, declaration: str) -> None:
    xml = f'{declaration}<w:document {NS}><w:body/></w:document>'
    payload = package(bom + xml.encode(encoding))
    inventory = inventory_docx_regions(payload)
    extracted = extract_docx_text_regions(payload)
    assert inventory.coverage_unknown
    assert extracted.regions == ()
    assert not extracted.coverage_complete
    assert extracted.manifest["coverage_unknown"] is True


@pytest.mark.parametrize(("encoding", "bom"), ENCODINGS)
def test_supported_encodings_preserve_text(encoding: str, bom: bytes) -> None:
    xml = (f'<w:document {NS}><w:body><w:p><w:r><w:t>Pièce 12</w:t>'
           '</w:r></w:p></w:body></w:document>')
    result = extract_docx_text_regions(package(bom + xml.encode(encoding)))
    assert result.coverage_complete
    assert result.regions[0].text == "Pièce 12"


@pytest.mark.parametrize("encoding,bom", [
    ("utf-32-le", b""), ("utf-32-le", b"\xff\xfe\x00\x00"),
    ("utf-32-be", b""), ("utf-32-be", b"\x00\x00\xfe\xff"),
])
def test_utf32_is_explicitly_rejected(encoding: str, bom: bytes) -> None:
    data = bom + '<x/>'.encode(encoding)
    with pytest.raises(ValueError, match="unsupported XML encoding"):
        parse_docx_xml(data)
    assert inventory_docx_regions(package(data)).coverage_unknown
    assert not extract_docx_text_regions(package(data)).coverage_complete
