"""Fail-closed raster crop of an original scanned PDF.

Coordinates are pixels in the 150-DPI OCR raster, not PDF points or bundle pages.
The caller must authorize and SHA-256 verify the original before invoking this.
"""
from __future__ import annotations

import io
import shutil
import struct
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image

from pypdf import PdfReader

from infrastructure.parsers.pdf_ocr import RASTER_DPI, OCRUnavailable, _run

MAX_CROP_PIXELS = 4_000_000
MAX_SOURCE_BYTES = 3 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class CropBox:
    left: int
    top: int
    width: int
    height: int

    def validate(self, image_width: int, image_height: int) -> None:
        if any(type(v) is not int for v in (self.left, self.top, self.width, self.height)):
            raise OCRUnavailable("crop_integer_coordinates_required")
        if not (0 <= self.left < image_width and 0 <= self.top < image_height):
            raise OCRUnavailable("crop_origin_out_of_bounds")
        if not (0 < self.width <= image_width - self.left and 0 < self.height <= image_height - self.top):
            raise OCRUnavailable("crop_out_of_bounds")
        if self.width * self.height > MAX_CROP_PIXELS:
            raise OCRUnavailable("crop_pixel_budget")


def _rasterize_page(original: bytes, *, page_number: int) -> tuple[bytes, int, int]:
    """Bounded 150-DPI PNG raster of one physical page of a verified original."""
    if not original.startswith(b"%PDF-") or not 0 < len(original) <= MAX_SOURCE_BYTES:
        raise OCRUnavailable("crop_pdf_input_budget")
    if type(page_number) is not int or not 1 <= page_number <= 64:
        raise OCRUnavailable("crop_page_range")
    try:
        pdf = PdfReader(io.BytesIO(original), strict=True)
        if pdf.is_encrypted or not 1 <= len(pdf.pages) <= 64 or page_number > len(pdf.pages):
            raise OCRUnavailable("crop_pdf_unsupported")
    except (OSError, ValueError) as exc:
        raise OCRUnavailable("crop_pdf_unreadable") from exc
    rasterizer = shutil.which("pdftoppm")
    if rasterizer is None:
        raise OCRUnavailable("crop_rasterizer_unavailable")
    with tempfile.TemporaryDirectory(prefix="caseproof-crop-") as directory:
        root = Path(directory)
        (root / "original.pdf").write_bytes(original)
        prefix = root / "page"
        _run([
            rasterizer, "-f", str(page_number), "-l", str(page_number),
            "-singlefile", "-r", str(RASTER_DPI), "-png",
            str(root / "original.pdf"), str(prefix),
        ], timeout=12)
        png = (root / "page.png").read_bytes()
    if not 24 <= len(png) <= 12 * 1024 * 1024 or png[:8] != bytes((137, 80, 78, 71, 13, 10, 26, 10)):
        raise OCRUnavailable("crop_invalid_raster")
    width, height = struct.unpack(">II", png[16:24])
    if not (0 < width <= 5000 and 0 < height <= 6500):
        raise OCRUnavailable("crop_raster_dimensions")
    return png, width, height


def _decode(png: bytes, width: int, height: int) -> tuple[Image.Image, int, int]:
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:
        raise OCRUnavailable("crop_pillow_unavailable") from exc
    try:
        return Image.open(io.BytesIO(png)), width, height
    except (OSError, UnidentifiedImageError) as exc:
        raise OCRUnavailable("crop_decode_failed") from exc


def crop_scanned_pdf(original: bytes, *, page_number: int, box: CropBox) -> bytes:
    """Return bounded PNG crop; no network, shell, OCR inference or guessed page mapping."""
    png, width, height = _rasterize_page(original, page_number=page_number)
    box.validate(width, height)
    image, _, _ = _decode(png, width, height)
    with image:
        if image.format != "PNG" or image.size != (width, height):
            raise OCRUnavailable("crop_image_mismatch")
        region = image.crop((
            box.left, box.top, box.left + box.width, box.top + box.height,
        ))
        out = io.BytesIO()
        region.save(out, format="PNG")
    result = out.getvalue()
    if len(result) > 8 * 1024 * 1024:
        raise OCRUnavailable("crop_output_budget")
    return result


def render_pdf_page(original: bytes, *, page_number: int) -> bytes:
    """Bounded full-page PNG rendering of a verified original.

    A display rendering only: it is never a visual-verification verdict and
    carries no page mapping beyond the caller's verified physical page.
    """
    png, width, height = _rasterize_page(original, page_number=page_number)
    if width * height > MAX_CROP_PIXELS:
        raise OCRUnavailable("crop_pixel_budget")
    image, _, _ = _decode(png, width, height)
    with image:
        if image.format != "PNG" or image.size != (width, height):
            raise OCRUnavailable("crop_image_mismatch")
        out = io.BytesIO()
        image.save(out, format="PNG")
    result = out.getvalue()
    if len(result) > 8 * 1024 * 1024:
        raise OCRUnavailable("crop_output_budget")
    return result
