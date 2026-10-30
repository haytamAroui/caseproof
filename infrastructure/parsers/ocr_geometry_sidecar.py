"""Bounded OCR geometry sidecar contract; never embed words in a parse manifest.

The sidecar must be stored in private, matter-authorized persistence before its
reference can be exposed. This module intentionally does not grant access.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from infrastructure.parsers.pdf_ocr import OCRPage

MAX_GEOMETRY_BYTES = 8 * 1024 * 1024
MAX_PAGES = 256


class GeometryRejected(ValueError):
    """Malformed or oversized geometry; fail closed."""


@dataclass(frozen=True, slots=True)
class GeometryReference:
    original_sha256: str
    geometry_sha256: str
    page_number: int
    word_count: int
    coordinate_basis: str


def encode_page_geometry(page: OCRPage) -> tuple[GeometryReference, bytes]:
    """Canonical sidecar and content-addressed reference, without OCR text in manifest."""
    if page.page_number < 1 or page.page_number > MAX_PAGES:
        raise GeometryRejected("page_out_of_range")
    if len(page.original_sha256) != 64 or any(c not in "0123456789abcdef" for c in page.original_sha256):
        raise GeometryRejected("invalid_original_hash")
    words = []
    for word in page.words:
        if not (0 <= word.left < page.image_width_px and 0 <= word.top < page.image_height_px):
            raise GeometryRejected("invalid_word_origin")
        if not (0 < word.width <= page.image_width_px - word.left and 0 < word.height <= page.image_height_px - word.top):
            raise GeometryRejected("invalid_word_bounds")
        words.append(asdict(word))
    payload = {
        "schema": "caseproof.ocr.geometry.v1",
        "original_sha256": page.original_sha256,
        "page_number": page.page_number,
        "image_sha256": page.image_sha256,
        "image_width_px": page.image_width_px,
        "image_height_px": page.image_height_px,
        "coordinate_basis": page.coordinate_basis,
        "words": words,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_GEOMETRY_BYTES:
        raise GeometryRejected("geometry_budget_exceeded")
    reference = GeometryReference(
        original_sha256=page.original_sha256,
        geometry_sha256=hashlib.sha256(encoded).hexdigest(),
        page_number=page.page_number,
        word_count=len(words),
        coordinate_basis=page.coordinate_basis,
    )
    return reference, encoded


def verify_page_geometry(reference: GeometryReference, encoded: bytes) -> dict:
    if len(encoded) > MAX_GEOMETRY_BYTES or hashlib.sha256(encoded).hexdigest() != reference.geometry_sha256:
        raise GeometryRejected("geometry_integrity_failed")
    try:
        data = json.loads(encoded)
    except (ValueError, UnicodeDecodeError) as exc:
        raise GeometryRejected("invalid_geometry_json") from exc
    if (
        not isinstance(data, dict)
        or data.get("schema") != "caseproof.ocr.geometry.v1"
        or data.get("original_sha256") != reference.original_sha256
        or data.get("page_number") != reference.page_number
        or not isinstance(data.get("words"), list)
        or len(data["words"]) != reference.word_count
        or data.get("coordinate_basis") != reference.coordinate_basis
    ):
        raise GeometryRejected("geometry_reference_mismatch")
    return data
