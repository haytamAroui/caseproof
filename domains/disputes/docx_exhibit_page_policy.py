"""Conservative page policy for DOCX exhibits without a stable PDF rendering."""

from dataclasses import dataclass
from enum import StrEnum


class PinpointState(StrEnum):
    VERIFIED = "verified"
    PAGE_UNMAPPED = "page_unmapped"
    NOT_ASSESSED = "not_assessed"


@dataclass(frozen=True)
class DocxExhibitPagePolicy:
    identity_check_allowed: bool
    pinpoint_state: PinpointState
    reason: str
    lawyer_message: str


def docx_exhibit_page_policy(*, has_verified_pdf_rendition: bool) -> DocxExhibitPagePolicy:
    """No page certification from mutable Word layout without a verified PDF."""
    if has_verified_pdf_rendition:
        return DocxExhibitPagePolicy(
            True,
            PinpointState.NOT_ASSESSED,
            "PDF_RENDITION_REQUIRES_PAGE_VERIFICATION",
            "Exhibit identity can be checked. Verify the cited page against the preserved PDF rendition.",
        )
    return DocxExhibitPagePolicy(
        True,
        PinpointState.PAGE_UNMAPPED,
        "DOCX_HAS_NO_STABLE_PDF_PAGE_SPACE",
        "Exhibit identity only: page references cannot be verified until a preserved PDF rendition is supplied.",
    )
