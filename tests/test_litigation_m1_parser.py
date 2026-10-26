"""M1 bounded parsers, DOCX attack surfaces and per-page completeness."""

from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from zipfile import ZIP_STORED, ZipFile

import pytest
from pypdf import PdfWriter

from application.documents.contracts import restore
from application.extraction.contracts import ExtractionError
from application.litigation.library import page_inventory
from infrastructure.parsers.engines import DOCX_MIME, parse_bytes
from infrastructure.parsers.limited import LimitedDocumentParser
from packages.evidence_kernel.domain.source_versions import SourceVersion


def make_docx(*, main="Bienvenue — Welkom", extras=None):
    body = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body><w:p><w:r><w:t>' + main + "</w:t></w:r></w:p></w:body></w:document>"
    ).encode()
    buf = BytesIO()
    with ZipFile(buf, "w", compression=ZIP_STORED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", body)
        for name, content in extras or []:
            archive.writestr(name, content)
    return buf.getvalue()


def make_source(content, media=DOCX_MIME):
    return SourceVersion(
        "document-test", "v1", sha256(content).hexdigest(), content,
        datetime(2026, 10, 26, tzinfo=UTC), media,
    )


def test_real_bounded_docx_worker_preserves_text_and_declares_unmapped_pages():
    raw = make_docx()
    source = make_source(raw)
    artifact = LimitedDocumentParser().parse(source)
    parsed = restore("synthetic-docx", source, artifact, source.ingested_at)
    assert "Bienvenue — Welkom" in parsed.evidence.content
    assert parsed.evidence.complete is False
    assert "docx_layout_page_numbers_unverified" in parsed.warnings
    assert page_inventory(parsed)[0].state == "page_unmapped"
    assert parsed.blocks[0].locator == "docx:body:paragraph:0"


def test_docx_notes_are_preserved_separately():
    footnote = (
        b'<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        b'<w:footnote><w:p><w:r><w:t>Note fictive</w:t></w:r></w:p></w:footnote>'
        b'</w:footnotes>'
    )
    raw = make_docx(extras=[("word/footnotes.xml", footnote)])
    source = make_source(raw)
    parsed = restore("note", source, LimitedDocumentParser().parse(source), source.ingested_at)
    assert "Note fictive" in parsed.evidence.content
    assert any(b.kind == "docx_note" for b in parsed.blocks)


@pytest.mark.parametrize(
    "file_name,extra",
    [
        ("../escape", b"some data"),
        ("word/vbaProject.bin", b"macro"),
        ("word/embeddings/ole1", b"object"),
        (
            "word/_rels/document.xml.rels",
            b'<Relationships><Relationship TargetMode="External" Target="https://bad.example"/></Relationships>',
        ),
    ],
)
def test_docx_rejects_unsafe_archive_members(file_name, extra):
    with pytest.raises(ExtractionError):
        parse_bytes(make_docx(extras=[(file_name, extra)]), DOCX_MIME)


def test_pdf_each_empty_page_gets_explicit_ocr_unavailable_status():
    pdf = PdfWriter()
    pdf.add_blank_page(width=400, height=500)
    pdf.add_blank_page(width=400, height=500)
    buffer = BytesIO()
    pdf.write(buffer)
    source = make_source(buffer.getvalue(), "application/pdf")
    parsed = restore("blank", source, LimitedDocumentParser().parse(source), source.ingested_at)
    pages = page_inventory(parsed)
    assert [page.pdf_page for page in pages] == [1, 2]
    assert [page.state for page in pages] == ["needs_ocr_or_review", "needs_ocr_or_review"]
    assert not parsed.evidence.complete


def test_docx_tracked_changes_never_claim_complete_or_legal_truth():
    raw = make_docx(main="Texte initial")
    # Replace a text-run node with a tracked insertion in the tiny synthetic XML.
    with ZipFile(BytesIO(raw)) as archive:
        main = archive.read("word/document.xml")
    modified = main.replace(b"<w:r><w:t>", b"<w:ins><w:r><w:t>").replace(
        b"</w:t></w:r>", b"</w:t></w:r></w:ins>"
    )
    buf = BytesIO()
    with ZipFile(buf, "w", compression=ZIP_STORED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", modified)
    source = make_source(buf.getvalue())
    parsed = restore("edited", source, LimitedDocumentParser().parse(source), source.ingested_at)
    assert "docx_tracked_changes_require_review" in parsed.warnings


def test_docx_unprocessed_header_has_explicit_completeness_warning():
    raw = make_docx(extras=[("word/header1.xml", b"synthetic header placeholder")])
    source = make_source(raw)
    parsed = restore("header", source, LimitedDocumentParser().parse(source), source.ingested_at)
    assert "docx_headers_footers_comments_unprocessed" in parsed.warnings
    assert parsed.evidence.complete is False


def test_docx_nested_textbox_is_rejected_before_creating_fabricated_passages():
    """A nested text box must not yield 'Outer beforeSeparate boxOuter after'."""
    raw = make_docx(main="Outer before")
    with ZipFile(BytesIO(raw)) as archive:
        document = archive.read("word/document.xml")
    modified = document.replace(
        b"</w:t></w:r></w:p>",
        (
            b"</w:t></w:r>"
            b"<w:r><w:txbxContent><w:p><w:r><w:t>Separate box</w:t>"
            b"</w:r></w:p></w:txbxContent></w:r>"
            b"<w:r><w:t>Outer after</w:t></w:r></w:p>"
        ),
    )
    assert modified != document
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_STORED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", modified)
    with pytest.raises(ExtractionError, match="docx_textboxes_unsupported"):
        parse_bytes(buffer.getvalue(), DOCX_MIME)
    # Existing isolated boundary refuses unrepresentable input; no preview.
    with pytest.raises(ExtractionError):
        LimitedDocumentParser().parse(make_source(buffer.getvalue()))


def test_docx_footnotes_and_endnotes_keep_tabs_and_breaks_verbatim():
    for kind in ("footnotes", "endnotes"):
        xml = (
            '<w:root xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:p><w:r><w:t>Alpha</w:t><w:tab/><w:t>Beta</w:t>'
            '<w:br/><w:t>Gamma</w:t><w:cr/><w:t>Delta</w:t></w:r></w:p></w:root>'
        ).encode()
        raw = make_docx(extras=[(f"word/{kind}.xml", xml)])
        source = make_source(raw)
        parsed = restore(
            "notes", source, LimitedDocumentParser().parse(source), source.ingested_at
        )
        note = next(block for block in parsed.blocks if block.kind == "docx_note")
        assert parsed.evidence.content[note.start:note.end] == "Alpha\tBeta\nGamma\nDelta"


def test_docx_textbox_inside_note_is_also_rejected():
    note = (
        '<w:root xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:p><w:txbxContent><w:p><w:r><w:t>Separate</w:t></w:r></w:p>'
        '</w:txbxContent></w:p></w:root>'
    ).encode()
    with pytest.raises(ExtractionError, match="docx_textboxes_unsupported"):
        parse_bytes(make_docx(extras=[("word/footnotes.xml", note)]), DOCX_MIME)
