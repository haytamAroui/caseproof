"""Phase 3 crop bounds and denial tests (no external raster tools needed)."""
import pytest

from infrastructure.parsers.pdf_ocr import OCRUnavailable
from infrastructure.parsers.pdf_source_crop import CropBox, crop_scanned_pdf


@pytest.mark.parametrize("box", [
    CropBox(-1, 0, 10, 10),
    CropBox(0, -1, 10, 10),
    CropBox(100, 0, 1, 10),
    CropBox(0, 100, 10, 1),
    CropBox(90, 0, 11, 10),
    CropBox(0, 90, 10, 11),
    CropBox(0, 0, 0, 10),
    CropBox(0, 0, 5000, 5000),
])
def test_crop_rejects_invalid_geometry(box):
    with pytest.raises(OCRUnavailable):
        box.validate(100, 100)


def test_crop_valid_pixel_bounds():
    CropBox(10, 20, 40, 50).validate(100, 100)


def test_crop_rejects_non_pdf_original():
    with pytest.raises(OCRUnavailable, match="crop_pdf_input_budget"):
        crop_scanned_pdf(b"not-a-pdf", page_number=1, box=CropBox(0, 0, 10, 10))


def test_crop_rejects_noninteger_page():
    with pytest.raises(OCRUnavailable, match="crop_page_range"):
        crop_scanned_pdf(b"%PDF-test", page_number=True, box=CropBox(0, 0, 10, 10))
