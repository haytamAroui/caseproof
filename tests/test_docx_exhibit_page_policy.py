"""DOCX page policy: identity allowed, mutable page coordinates never certified."""

from domains.disputes.docx_exhibit_page_policy import (
    PinpointState,
    docx_exhibit_page_policy,
)


def test_docx_without_pdf_is_identity_only() -> None:
    result = docx_exhibit_page_policy(has_verified_pdf_rendition=False)
    assert result.identity_check_allowed
    assert result.pinpoint_state is PinpointState.PAGE_UNMAPPED
    assert "identity only" in result.lawyer_message.lower()


def test_pdf_rendition_does_not_automatically_verify_page() -> None:
    result = docx_exhibit_page_policy(has_verified_pdf_rendition=True)
    assert result.pinpoint_state is PinpointState.NOT_ASSESSED
    assert "Verify" in result.lawyer_message
