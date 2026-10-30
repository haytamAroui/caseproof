"""Bounded dual-representation review gate; no legal or approval authority.

Inputs must be loaded by a matter-authorized adapter, never accepted as browser
assertions. Equal text does not prove that formatting survived extraction.
"""
from dataclasses import dataclass
from enum import StrEnum

from application.litigation.representation_normalization import NORMALIZATION, normalize_region


class RepresentationState(StrEnum):
    NOT_ASSESSED = "not_assessed"
    REPRESENTATION_CONFLICT = "representation_conflict"
    OCR_UNRELIABLE = "ocr_unreliable"


@dataclass(frozen=True, slots=True)
class RepresentationComparison:
    original_sha256: str
    representation_id: str
    pdf_page: int
    crop_sha256: str
    extracted_text: str
    visual_text: str
    visual_reliable: bool
    meaning_bearing_edit: bool
    text_start: int | None = None
    text_end: int | None = None
    bbox: tuple[int, int, int, int] | None = None
    coordinate_basis: str = "raster_pixels_top_left_150dpi"
    detector_version: str = "unrecorded"
    # Adapter observations only: strikethrough/insertion is a review trigger,
    # never an automatic instruction to delete or accept contractual language.

    def __post_init__(self) -> None:
        for digest in (self.original_sha256, self.crop_sha256):
            if (type(digest) is not str or len(digest) != 64
                    or any(c not in "0123456789abcdef" for c in digest)):
                raise ValueError("immutable source and crop hashes required")
        if (type(self.pdf_page) is not int or not 1 <= self.pdf_page <= 100_000
                or not self.representation_id or len(self.representation_id) > 256
                or type(self.visual_reliable) is not bool
                or type(self.meaning_bearing_edit) is not bool):
            raise ValueError("bounded page and typed adapter observations required")
        if (self.text_start is None) != (self.text_end is None):
            raise ValueError("paired regional text bounds required")
        if self.text_start is not None and (type(self.text_start) is not int
                or type(self.text_end) is not int or not 0 <= self.text_start < self.text_end):
            raise ValueError("invalid regional text bounds")
        if self.bbox is not None and (len(self.bbox) != 4
                or any(type(x) is not int for x in self.bbox)
                or not 0 <= self.bbox[0] < self.bbox[2] <= 5000
                or not 0 <= self.bbox[1] < self.bbox[3] <= 6500):
            raise ValueError("invalid raster region")
        for text in (self.extracted_text, self.visual_text):
            if type(text) is not str or len(text) > 4000:
                raise ValueError("bounded regional text required")

    @property
    def state(self) -> RepresentationState:
        if not self.visual_reliable or not self.visual_text.strip():
            return RepresentationState.OCR_UNRELIABLE
        if self.meaning_bearing_edit or normalize_region(self.extracted_text).text != normalize_region(self.visual_text).text:
            return RepresentationState.REPRESENTATION_CONFLICT
        return RepresentationState.NOT_ASSESSED

    def review_contract(self) -> dict[str, object]:
        """No URL or embedded bytes; crop retrieval must reauthorize the matter."""
        return {
            "schema": "caseproof.representation-review.v1",
            "state": self.state.value,
            "human_confirmation_required": self.state != RepresentationState.NOT_ASSESSED,
            "original_sha256": self.original_sha256,
            "representation_id": self.representation_id,
            "pdf_page": self.pdf_page,
            "crop_sha256": self.crop_sha256,
            "extracted_text": self.extracted_text,
            "visual_text": self.visual_text,
            "semantic_support": "not_assessed",
            "normalization_version": NORMALIZATION,
            "text_start": self.text_start, "text_end": self.text_end,
            "bbox": self.bbox, "coordinate_basis": self.coordinate_basis,
            "detector_version": self.detector_version,
        }
