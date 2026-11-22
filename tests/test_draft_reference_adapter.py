"""Adapter: exhibit markers -> DraftReference with abstain-first page grounding."""
from apps.api.draft_reference_adapter import adapt_text
from domains.disputes.exhibits import ExhibitEntry, ExhibitPage, ExhibitRegister


def _register() -> ExhibitRegister:
    entry = ExhibitEntry(
        "ex-12",
        "Pièce 12 — décompte",
        (
            ExhibitPage("src-1", "v1", pdf_page=7, printed_page=3, bundle_page=41),
            ExhibitPage("src-1", "v1", pdf_page=8, printed_page=4, bundle_page=42),
        ),
        ("pièce 12",),
        True,
    )
    ambiguous = ExhibitEntry(
        "ex-13",
        "Pièce 13 — ambiguë",
        (
            ExhibitPage("src-1", "v1", pdf_page=3, printed_page=10, bundle_page=50),
            ExhibitPage("src-1", "v1", pdf_page=9, printed_page=3, bundle_page=51),
        ),
        ("pièce 13",),
        True,
    )
    unconfirmed = ExhibitEntry(
        "ex-14",
        "Pièce 14 — non confirmée",
        (ExhibitPage("src-1", "v1", pdf_page=20, printed_page=1, bundle_page=60),),
        ("pièce 14",),
        False,
    )
    return ExhibitRegister(1, (entry, ambiguous, unconfirmed))


def test_reference_without_page_stays_pageless() -> None:
    adapted = adapt_text("Comme il ressort de la pièce 12, le bail est signé.", _register())
    assert len(adapted.references) == 1
    ref = adapted.references[0]
    assert ref.exhibit_label == "pièce 12"
    assert ref.pdf_page is None
    assert adapted.page_abstentions == ()


def test_unique_confirmed_mapping_grounds_hint_to_physical_page() -> None:
    adapted = adapt_text("Le décompte figure en pièce 12, p. 3.", _register())
    ref = adapted.references[0]
    # printed_page 3 maps uniquely to physical PDF page 7.
    assert ref.pdf_page == 7
    assert adapted.page_abstentions == ()


def test_ambiguous_page_space_abstains() -> None:
    adapted = adapt_text("Voir pièce 13, p. 3.", _register())
    ref = adapted.references[0]
    assert ref.pdf_page is None
    assert [a.reason for a in adapted.page_abstentions] == ["page_space_ambiguous"]


def test_unmapped_page_abstains() -> None:
    adapted = adapt_text("Voir pièce 12, p. 99.", _register())
    assert adapted.references[0].pdf_page is None
    assert [a.reason for a in adapted.page_abstentions] == ["page_unmapped"]


def test_unconfirmed_exhibit_abstains() -> None:
    adapted = adapt_text("Voir pièce 14, p. 1.", _register())
    assert adapted.references[0].pdf_page is None
    assert [a.reason for a in adapted.page_abstentions] == ["exhibit_unconfirmed"]


def test_article_markers_reported_out_of_scope() -> None:
    text = "Selon l'article 15 de la loi du 20 février 1991, voir pièce 12."
    adapted = adapt_text(text, _register())
    assert len(adapted.references) == 1
    assert len(adapted.out_of_scope_markers) == 1
