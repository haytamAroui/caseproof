"""Citation marker extraction: deterministic, lexical, from the read text."""

from __future__ import annotations

import pytest

from infrastructure.parsers.citation_markers import (
    MAX_MARKERS,
    CitationExtractionError,
    extract_citations,
)

BELGIAN_BRIEF = (
    "1. Le bail est réputé conclu pour neuf ans : « Tout bail visé à l'article premier "
    "est réputé conclu pour une durée de neuf années. » (Code civil, Livre III, Titre VIII, "
    "Ch. II, Section 2, art. 3, §1er).\n"
    "2. La garantie est plafonnée : « Lorsque le preneur opte pour un compte individualisé, "
    "la garantie locative ne peut excéder un montant équivalent à 2 mois de loyer. » "
    "(Section 2, art. 10, §1er).\n"
    "3. Sur les dégradations : « Il répond des dégradations ou des pertes qui arrivent "
    "pendant sa jouissance. » (Code civil, art. 1732).\n"
    "5. Conformément à l'article 15 de la loi du 20 février 1991, le preneur conserve ses droits.\n"
    "6. Le bail ayant été enregistré, le congé suit le régime ordinaire (Section 2, art. 3, §5).\n"
    "Montant : 1 700 EUR (2 × 850 EUR)."
)


def test_parenthesized_markers_with_adjacent_quotes() -> None:
    extraction = extract_citations(BELGIAN_BRIEF)
    by_id = {m.marker_id: m for m in extraction.markers}
    assert [m.marker_id for m in extraction.markers] == [
        "cit-01",
        "cit-02",
        "cit-03",
        "cit-04",
        "cit-05",
    ]
    assert by_id["cit-01"].target == "Code civil, Livre III, Titre VIII, Ch. II, Section 2, art. 3, §1er"
    assert by_id["cit-01"].quote == (
        "Tout bail visé à l'article premier est réputé conclu pour une durée de neuf années."
    )
    assert by_id["cit-02"].target == "Section 2, art. 10, §1er"
    assert by_id["cit-03"].target == "Code civil, art. 1732"
    assert by_id["cit-03"].quote == "Il répond des dégradations ou des pertes qui arrivent pendant sa jouissance."


def test_marker_without_quote_and_non_article_parentheses() -> None:
    extraction = extract_citations(BELGIAN_BRIEF)
    by_id = {m.marker_id: m for m in extraction.markers}
    # (Section 2, art. 3, §5) has no quotation; (2 × 850 EUR) is not a citation.
    assert by_id["cit-05"].target == "Section 2, art. 3, §5"
    assert by_id["cit-05"].quote is None
    assert all("850 EUR" not in m.target for m in extraction.markers)


def test_autonomous_act_mention_without_quote() -> None:
    extraction = extract_citations(BELGIAN_BRIEF)
    auto = [m for m in extraction.markers if m.form == "autonomous_act"]
    assert len(auto) == 1
    assert auto[0].target == "article 15 de la loi du 20 février 1991"
    assert auto[0].quote is None


def test_quote_never_attached_across_a_sentence() -> None:
    text = "« Une citation isolée. » Plus loin, une autre phrase. (Code civil, art. 1732)."
    extraction = extract_citations(text)
    assert len(extraction.markers) == 1
    assert extraction.markers[0].quote is None
    assert len(extraction.orphan_quotes) == 1


def test_orphan_quote_without_marker_is_reported() -> None:
    text = "Le brief affirme « trois mois » sans citer de source."
    extraction = extract_citations(text)
    assert extraction.markers == ()
    assert len(extraction.orphan_quotes) == 1


def test_deterministic_same_text_same_markers() -> None:
    first = extract_citations(BELGIAN_BRIEF)
    second = extract_citations(BELGIAN_BRIEF)
    assert first == second


def test_marker_positions_locate_the_target() -> None:
    extraction = extract_citations(BELGIAN_BRIEF)
    for marker in extraction.markers:
        assert marker.target in BELGIAN_BRIEF[marker.start : marker.end] or marker.form == "autonomous_act"
        if marker.quote is not None:
            assert marker.quote_start is not None and marker.quote_end is not None
            assert marker.quote in BELGIAN_BRIEF[marker.quote_start : marker.quote_end]


def test_bounds_enforced() -> None:
    with pytest.raises(CitationExtractionError):
        extract_citations("")
    with pytest.raises(CitationExtractionError):
        extract_citations("(Code civil, art. 1). " * (MAX_MARKERS + 1))
