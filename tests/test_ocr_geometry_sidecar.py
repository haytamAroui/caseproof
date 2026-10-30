"""Phase 3 OCR geometry sidecar contract tests."""
from dataclasses import replace

import pytest

from infrastructure.parsers.ocr_geometry_sidecar import (
    GeometryRejected,
    encode_page_geometry,
    verify_page_geometry,
)
from infrastructure.parsers.pdf_ocr import OCRPage, OCRWord


def _page() -> OCRPage:
    return OCRPage(
        source_document_id="doc",
        source_version_id="version",
        original_sha256="a" * 64,
        page_number=1,
        image_sha256="b" * 64,
        image_width_px=1200,
        image_height_px=1800,
        image_dpi=150,
        content="test",
        words=(OCRWord("Pièce", 20, 40, 90, 22, "71"),),
    )


def test_sidecar_is_content_addressed_and_roundtrips():
    reference, encoded = encode_page_geometry(_page())
    assert reference.word_count == 1
    assert verify_page_geometry(reference, encoded)["words"][0]["text"] == "Pièce"


def test_geometry_reference_refuses_tampered_bytes():
    reference, encoded = encode_page_geometry(_page())
    with pytest.raises(GeometryRejected, match="geometry_integrity_failed"):
        verify_page_geometry(reference, encoded + b" ")


def test_geometry_rejects_out_of_image_word():
    page = _page()
    bad = replace(page, words=(OCRWord("bad", 1190, 40, 90, 22, "71"),))
    with pytest.raises(GeometryRejected, match="invalid_word_bounds"):
        encode_page_geometry(bad)


def test_geometry_rejects_wrong_original_hash():
    with pytest.raises(GeometryRejected, match="invalid_original_hash"):
        encode_page_geometry(replace(_page(), original_sha256="wrong"))
