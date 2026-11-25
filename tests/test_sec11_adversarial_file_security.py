"""SEC-11 automated adversarial file-bomb, XML/XXE, and active-PDF rejection matrix.

Exercises genuine hostile DOCX/ZIP archives and hostile PDF payloads directly against:
- application.documents.file_boundary.validate_original_container
- infrastructure.parsers.docx_text_regions.extract_docx_text_regions
- infrastructure.parsers.engines.parse_pdf
- infrastructure.parsers.filing_pdf_parity_adapter.check_filing_pdf_parity
"""

from __future__ import annotations

import io
import stat
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest
from docx import Document
from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, TextStringObject

from application.documents.file_boundary import DOCX, validate_original_container
from application.extraction.contracts import ExtractionError
from infrastructure.parsers.docx_text_regions import extract_docx_text_regions
from infrastructure.parsers.engines import parse_pdf
from infrastructure.parsers.filing_pdf_parity_adapter import (
    MAX_FILING_PDF_BYTES,
    check_filing_pdf_parity,
)


def _docx_archive(entries: list[tuple[str, bytes]], *, compression: int = ZIP_DEFLATED) -> bytes:
    buf = io.BytesIO()
    with ZipFile(buf, "w", compression=compression) as zf:
        for name, content in entries:
            zf.writestr(name, content)
    return buf.getvalue()


def _minimal_docx() -> bytes:
    doc = Document()
    doc.add_paragraph("Pièce 1 — Texte synthétique.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _minimal_pdf(*, pages: int = 1, encrypt: bool = False, root_extra: dict | None = None) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    if root_extra:
        root = writer._root_object
        for k, v in root_extra.items():
            root[NameObject(k)] = v
    if encrypt:
        writer.encrypt("secret")
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# --- DOCX / ZIP attack vectors ---


def test_sec11_rejects_high_ratio_zip_bomb() -> None:
    payload = _docx_archive([
        ("[Content_Types].xml", b"<Types/>"),
        ("word/document.xml", b"A" * (1_500_000)),
    ])
    assert len(payload) < 15_000  # >100x compression ratio triggers >80x limit
    with pytest.raises(ExtractionError, match="unsafe_original_archive"):
        validate_original_container(payload, DOCX)


def test_sec11_rejects_excessive_zip_entries_and_oversized_uncompressed_total() -> None:
    too_many = _docx_archive([("[Content_Types].xml", b"<Types/>")] + [(f"word/p{i}.xml", b"<x/>") for i in range(130)])
    with pytest.raises(ExtractionError, match="unsafe_original_archive"):
        validate_original_container(too_many, DOCX)

    too_big = _docx_archive([("[Content_Types].xml", b"<Types/>")] + [(f"word/b{i}.xml", b"x" * 1_900_000) for i in range(5)])
    with pytest.raises(ExtractionError, match="unsafe_original_archive"):
        validate_original_container(too_big, DOCX)


def test_sec11_rejects_symlink_encrypted_duplicate_and_prefixed_zip_entries() -> None:
    # Symlink entry inside ZIP
    sym_buf = io.BytesIO()
    with ZipFile(sym_buf, "w") as zf:
        zf.writestr("[Content_Types].xml", b"<Types/>")
        info = ZipInfo("word/document.xml")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        zf.writestr(info, b"/etc/passwd")
    with pytest.raises(ExtractionError, match="unsafe_original_archive"):
        validate_original_container(sym_buf.getvalue(), DOCX)

    # Encrypted flag bit set in central directory header (ZipFile.writestr clears flag_bits on write).
    enc_buf = io.BytesIO()
    with ZipFile(enc_buf, "w") as zf:
        zf.writestr("[Content_Types].xml", b"<Types/>")
        zf.writestr("word/document.xml", b"<doc/>")
    raw_enc = bytearray(enc_buf.getvalue())
    cd_pos = raw_enc.index(b"PK\x01\x02")
    raw_enc[cd_pos + 8] |= 1
    with pytest.raises(ExtractionError, match="unsafe_original_archive"):
        validate_original_container(bytes(raw_enc), DOCX)

    # Duplicate ZIP member names
    with pytest.warns(UserWarning, match="Duplicate name"):
        dup_payload = _docx_archive([
            ("[Content_Types].xml", b"<Types/>"),
            ("word/document.xml", b"<a/>"),
            ("word/document.xml", b"<b/>"),
        ])
    with pytest.raises(ExtractionError, match="unsafe_original_archive"):
        validate_original_container(dup_payload, DOCX)

    # Non-PK prefix polyglot ZIP
    prefixed = b"PNG\x89garbage" + _minimal_docx()
    with pytest.raises(ExtractionError, match="unsafe_original_archive"):
        validate_original_container(prefixed, DOCX)


def test_sec11_xml_entity_expansion_or_doctype_never_succeeds_silently() -> None:
    xxe_doc = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<!DOCTYPE foo [<!ENTITY xxe "EXPANDED_SECRET">]>'
        b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        b'<w:body><w:p><w:r><w:t>&xxe;</w:t></w:r></w:p></w:body></w:document>'
    )
    payload = _docx_archive([("[Content_Types].xml", b"<Types/>"), ("word/document.xml", xxe_doc)])
    extraction = extract_docx_text_regions(payload)
    assert extraction.coverage_complete is False
    assert extraction.regions == ()
    assert "COVERAGE_UNKNOWN" in extraction.unscanned_parts
    assert extraction.manifest.get("reason") == "DTD_FORBIDDEN"
    assert "EXPANDED_SECRET" not in "".join(r.text for r in extraction.regions)


# --- PDF active content, corruption & budget attack vectors ---


def test_sec11_rejects_encrypted_truncated_and_overpage_pdfs() -> None:
    with pytest.raises(ExtractionError, match="pdf_signature_or_truncation"):
        parse_pdf(b"not-a-pdf")
    with pytest.raises(ExtractionError, match="pdf_signature_or_truncation"):
        parse_pdf(b"%PDF-1.4\n1 0 obj<<>>endobj\n")
    with pytest.raises(ExtractionError, match="encrypted_pdf_unsupported"):
        parse_pdf(_minimal_pdf(encrypt=True))
    with pytest.raises(ExtractionError, match="pdf_page_limit"):
        parse_pdf(_minimal_pdf(pages=65))


@pytest.mark.parametrize(
    ("root_key", "expected_error"),
    [
        ("/OpenAction", "active_or_form_pdf_unsupported"),
        ("/AA", "active_or_form_pdf_unsupported"),
        ("/AcroForm", "active_or_form_pdf_unsupported"),
    ],
)
def test_sec11_rejects_active_or_form_pdf_actions(root_key: str, expected_error: str) -> None:
    hostile = _minimal_pdf(root_extra={root_key: DictionaryObject()})
    with pytest.raises(ExtractionError, match=expected_error):
        parse_pdf(hostile)


@pytest.mark.parametrize("names_key", ["/JavaScript", "/EmbeddedFiles"])
def test_sec11_rejects_embedded_js_and_files_in_pdf_names(names_key: str) -> None:
    names_dict = DictionaryObject({
        NameObject(names_key): DictionaryObject({
            NameObject("/Names"): ArrayObject([TextStringObject("x"), DictionaryObject()]),
        })
    })
    hostile = _minimal_pdf(root_extra={"/Names": names_dict})
    with pytest.raises(ExtractionError, match="active_or_embedded_pdf_unsupported"):
        parse_pdf(hostile)


def test_sec11_filing_pdf_parity_enforces_size_limit_and_ocr_abstention() -> None:
    docx_raw = _minimal_docx()
    oversized = b"%PDF-1.4\n" + (b"x" * MAX_FILING_PDF_BYTES) + b"\n%%EOF"
    with pytest.raises(ExtractionError, match="pdf_size_limit"):
        check_filing_pdf_parity(
            original_docx=docx_raw,
            filing_pdf=oversized,
            case_id="c1",
            brief_id="b1",
            snapshot_hash="a" * 64,
        )

    blank_pdf = _minimal_pdf(pages=1)
    res = check_filing_pdf_parity(
        original_docx=docx_raw,
        filing_pdf=blank_pdf,
        case_id="c1",
        brief_id="b1",
        snapshot_hash="a" * 64,
    )
    assert res["status"] == "CANNOT_VERIFY"
    assert "OCR_UNRELIABLE" in res["reason_codes"]
