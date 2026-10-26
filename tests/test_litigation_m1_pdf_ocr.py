"""M1 OCR geometry and explicit failures. These are not live scan-quality evidence."""
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO

import pytest
from pypdf import PdfWriter

from infrastructure.parsers.pdf_ocr import (
    LocalPDFOCR,
    OCRUnavailable,
    parse_tsv,
)
from packages.evidence_kernel.domain.source_versions import SourceVersion

HEADER = b"level\tleft\ttop\twidth\theight\tconf\ttext\n"


def source() -> SourceVersion:
    pdf = PdfWriter()
    pdf.add_blank_page(width=200, height=200)
    b = BytesIO()
    pdf.write(b)
    content = b.getvalue()
    return SourceVersion("scan-1", "v1", sha256(content).hexdigest(), content,
                         datetime(2026, 10, 26, tzinfo=UTC), "application/pdf")


def test_ocr_word_geometry_and_lineage_is_explicit():
    data = HEADER + b"5\t12\t20\t100\t12\t76.5\tWelkom\n"
    result = parse_tsv(data, width=400, height=500)
    assert result[0].text == "Welkom"
    assert result[0].confidence == "76.5"
    assert (result[0].left, result[0].top) == (12, 20)


@pytest.mark.parametrize("bad", [
    HEADER + b"5\t390\t20\t40\t12\t76.5\tText\n",
    HEADER + b"5\t12\t20\t40\t12\tNaN\tText\n",
    HEADER + b"5\t12\t20\t40\t12\t101\tText\n",
    b"arbitrary output with no TSV header",
])
def test_ocr_malformed_and_outside_image_fails_closed(bad):
    with pytest.raises(OCRUnavailable):
        parse_tsv(bad, width=400, height=500)


def test_ocr_unsupported_languages_and_pages_are_denied_without_processing():
    adapter = LocalPDFOCR()
    for langs, page in [(("es",), 1), (("en",), 0), (("nl", "nl"), 1), ((), 1), (("en",), 65)]:
        with pytest.raises(OCRUnavailable):
            adapter.recognize(source(), page_number=page, languages=langs)


def test_ocr_binaries_absent_does_not_fabricate_text():
    adapter = LocalPDFOCR()
    adapter.rasterizer = None
    adapter.recognizer = None
    with pytest.raises(OCRUnavailable, match="not_installed"):
        adapter.recognize(source(), page_number=1, languages=("nl", "fr", "en"))
