"""Bounded dual-representation review gate; no legal or approval authority.

Inputs must be loaded by a matter-authorized adapter, never accepted as browser
assertions. Equal text does not prove that formatting survived extraction.
"""
from dataclasses import dataclass
from enum import StrEnum


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
        for text in (self.extracted_text, self.visual_text):
            if type(text) is not str or len(text) > 4000:
                raise ValueError("bounded regional text required")

    @property
    def state(self) -> RepresentationState:
        if not self.visual_reliable or not self.visual_text.strip():
            return RepresentationState.OCR_UNRELIABLE
        if self.meaning_bearing_edit or self.extracted_text != self.visual_text:
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
        }
