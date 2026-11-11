"""Unit tests for deterministic Level-1 Belgian NL/FR statutory citation parser."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from domains.disputes.statute_parser import (
    CitationParseError,
    StatuteCitation,
    extract_anchored_statute_citations,
    extract_statute_citations,
    parse_statute_citation,
)
from packages.evidence_kernel.domain.anchors import TextSpan


def test_parse_nl_judicial_code_with_bis_suffix() -> None:
    result = parse_statute_citation("Art. 737bis Ger.W.")
    assert result == StatuteCitation(
        code="Ger.W.",
        article="737bis",
        paragraph=None,
        language="nl",
        raw_text="Art. 737bis Ger.W.",
    )
    assert isinstance(result.article, str)


def test_parse_fr_judicial_code_with_bis_suffix() -> None:
    result = parse_statute_citation("Article 737bis du Code judiciaire")
    assert result == StatuteCitation(
        code="Ger.W.",
        article="737bis",
        paragraph=None,
        language="fr",
        raw_text="Article 737bis du Code judiciaire",
    )


def test_parse_fr_civil_code_dotted_article_8_4_short() -> None:
    result = parse_statute_citation("Art. 8.4 C.civ.")
    assert result == StatuteCitation(
        code="C.civ.",
        article="8.4",
        paragraph=None,
        language="fr",
        raw_text="Art. 8.4 C.civ.",
    )


def test_parse_fr_civil_code_dotted_article_8_4_full() -> None:
    result = parse_statute_citation("Article 8.4 du Code civil")
    assert result == StatuteCitation(
        code="C.civ.",
        article="8.4",
        paragraph=None,
        language="fr",
        raw_text="Article 8.4 du Code civil",
    )


def test_parse_nl_economic_code_roman_book_iv_1() -> None:
    result = parse_statute_citation("Art. IV.1 WER")
    assert result == StatuteCitation(
        code="WER",
        article="IV.1",
        paragraph=None,
        language="nl",
        raw_text="Art. IV.1 WER",
    )


def test_parse_fr_economic_code_roman_book_iv_1() -> None:
    result = parse_statute_citation("Article IV.1 du Code de droit économique")
    assert result == StatuteCitation(
        code="WER",
        article="IV.1",
        paragraph=None,
        language="fr",
        raw_text="Article IV.1 du Code de droit économique",
    )


def test_parse_nl_slash_subarticle_744_1() -> None:
    result = parse_statute_citation("Art. 744/1 Ger.W.")
    assert result == StatuteCitation(
        code="Ger.W.",
        article="744/1",
        paragraph=None,
        language="nl",
        raw_text="Art. 744/1 Ger.W.",
    )


def test_parse_roman_numeral_xii_edge_case() -> None:
    result = parse_statute_citation("Art. XII WER")
    assert result == StatuteCitation(
        code="WER",
        article="XII",
        paragraph=None,
        language="nl",
        raw_text="Art. XII WER",
    )


def test_parse_nl_judicial_code_with_paragraph_symbol() -> None:
    result = parse_statute_citation("Art. 737, § 2 Ger.W.")
    assert result == StatuteCitation(
        code="Ger.W.",
        article="737",
        paragraph="§ 2",
        language="nl",
        raw_text="Art. 737, § 2 Ger.W.",
    )


def test_parse_nl_dated_statute_wet_van_13_april_2019() -> None:
    result = parse_statute_citation("Wet van 13 april 2019")
    assert result == StatuteCitation(
        code="Wet van 13 april 2019",
        article="13 april 2019",
        paragraph=None,
        language="nl",
        raw_text="Wet van 13 april 2019",
    )


def test_parse_fr_dated_statute_loi_du_13_avril_2019() -> None:
    result = parse_statute_citation("Loi du 13 avril 2019")
    assert result == StatuteCitation(
        code="Loi du 13 avril 2019",
        article="13 avril 2019",
        paragraph=None,
        language="fr",
        raw_text="Loi du 13 avril 2019",
    )


def test_parse_nl_civil_code_bw_with_paragraph() -> None:
    result = parse_statute_citation("Artikel 5.142, § 1 BW")
    assert result == StatuteCitation(
        code="C.civ.",
        article="5.142",
        paragraph="§ 1",
        language="nl",
        raw_text="Artikel 5.142, § 1 BW",
    )


def test_reject_malformed_five_digit_article_99999() -> None:
    with pytest.raises(CitationParseError):
        parse_statute_citation("Art. 99999")


def test_reject_malformed_five_digit_article_with_code() -> None:
    with pytest.raises(CitationParseError):
        parse_statute_citation("Art. 99999 Ger.W.")


def test_reject_malformed_lowercase_code_without_article() -> None:
    with pytest.raises(CitationParseError):
        parse_statute_citation("Art. ger.w.")


def test_reject_malformed_lowercase_code_with_article() -> None:
    with pytest.raises(CitationParseError):
        parse_statute_citation("Art. 737 ger.w.")


def test_reject_malformed_inverted_code_and_article() -> None:
    with pytest.raises(CitationParseError):
        parse_statute_citation("Art. Ger.W. 737")


def test_reject_inconsistent_nl_prefix_with_fr_code() -> None:
    with pytest.raises(CitationParseError):
        parse_statute_citation("Artikel 8.4 du Code civil")


def test_reject_inconsistent_fr_prefix_with_nl_code() -> None:
    with pytest.raises(CitationParseError):
        parse_statute_citation("Article 737 Ger.W.")


def test_reject_invalid_calendar_day_in_statute_date() -> None:
    with pytest.raises(CitationParseError):
        parse_statute_citation("Wet van 31 april 2019")


def test_reject_invalid_roman_numeral_iiii() -> None:
    with pytest.raises(CitationParseError):
        parse_statute_citation("Art. IIII.1 WER")


def test_reject_empty_and_strict_non_string_article_type() -> None:
    with pytest.raises(CitationParseError):
        parse_statute_citation("   ")
    with pytest.raises(ValidationError):
        StatuteCitation(
            code="Ger.W.",
            article=737,  # type: ignore[arg-type]
            paragraph=None,
            language="nl",
            raw_text="Art. 737 Ger.W.",
        )


def test_extract_anchored_citations_binds_to_evidence_kernel_text_span() -> None:
    passage = (
        "Conform Art. 737bis Ger.W. en Art. IV.1 WER, alsmede "
        "Article 8.4 du Code civil en de Wet van 13 april 2019."
    )
    anchored = extract_anchored_statute_citations(passage)
    assert len(anchored) == 4
    assert [item.citation.article for item in anchored] == [
        "737bis",
        "IV.1",
        "8.4",
        "13 april 2019",
    ]
    for item in anchored:
        assert isinstance(item.span, TextSpan)
        assert passage[item.span.start : item.span.end] == item.citation.raw_text
    assert extract_statute_citations(passage) == [item.citation for item in anchored]



def test_reject_oversized_citation_with_domain_error() -> None:
    oversized = "Art. 737" + " " * 600 + "Ger.W."
    with pytest.raises(CitationParseError, match="maximum supported length"):
        parse_statute_citation(oversized)


def test_extraction_skips_oversized_candidate_but_keeps_following() -> None:
    oversized = "Art. 737" + " " * 600 + "Ger.W."
    passage = oversized + "; Article 8.4 du Code civil"
    anchored = extract_anchored_statute_citations(passage)
    assert len(anchored) == 1
    assert anchored[0].citation.article == "8.4"
    assert passage[anchored[0].span.start:anchored[0].span.end] == (
        "Article 8.4 du Code civil"
    )


@pytest.mark.parametrize(
    ("token", "expected_article"),
    [
        ("Art. 737 Ger.W.\n", "737"),
        ("Wet van 13 april 2019\n", "13 april 2019"),
    ],
)
def test_dense_citation_passage_extracts_each_once(
    token: str, expected_article: str,
) -> None:
    # Both single-family cases previously repeatedly searched the entire suffix.
    passage = token * 2000
    anchored = extract_anchored_statute_citations(passage)
    assert len(anchored) == 2000
    assert all(item.citation.article == expected_article for item in anchored)
    assert anchored[0].span.start == 0
    assert anchored[-1].span.end == len(passage.rstrip())


def test_nested_act_in_article_is_not_emitted_twice() -> None:
    passage = "Article 737 de la Loi du 13 avril 2019; Loi du 14 avril 2019"
    citations = extract_statute_citations(passage)
    assert len(citations) == 2
    assert [citation.article for citation in citations] == [
        "737", "14 avril 2019",
    ]
