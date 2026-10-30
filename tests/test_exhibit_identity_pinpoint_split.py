"""Regression fixtures for independent exhibit identity and pinpoint state."""

from domains.disputes.exhibits import (
    ExhibitEntry,
    ExhibitPage,
    ExhibitRegister,
    MappingState,
)


def _register() -> ExhibitRegister:
    return ExhibitRegister(1, (
        ExhibitEntry("ex-4", "Stuk 4", (
            ExhibitPage("src-4", "v1", pdf_page=1),
            ExhibitPage("src-4", "v1", pdf_page=2),
        ), confirmed=True),
    ))


def test_confirmed_identity_does_not_depend_on_unique_page() -> None:
    result = _register().resolve("Stuk 4")
    assert result.exhibit_id == "ex-4"
    assert result.identity_confirmed
    assert result.state is MappingState.AMBIGUOUS
    assert result.page is None


def test_unknown_pinpoint_does_not_invalidate_identity() -> None:
    result = _register().resolve("Stuk 4", pdf_page=8)
    assert result.exhibit_id == "ex-4"
    assert result.identity_confirmed
    assert result.state is MappingState.PAGE_UNMAPPED
    assert result.page is None


def test_confirmed_page_and_identity() -> None:
    result = _register().resolve("Stuk 4", pdf_page=2)
    assert result.state is MappingState.CONFIRMED
    assert result.identity_confirmed
    assert result.page is not None and result.page.pdf_page == 2
