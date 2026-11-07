"""Adversarial NL/FR P0 seed cases. Synthetic labels, NOT independent human ratings."""

from __future__ import annotations

import pytest

from application.litigation.paraphrase_guard import GUARD_VERSION, guard_paraphrase


def check(
    draft: str,
    source: str | None,
    *,
    quote: str | None = "Le paiement est enregistré.",
    lang: str = "fr",
    source_lang: str = "fr",
    version: str | None = "source-v1",
    ocr: bool = False,
    partial: bool = False,
) -> dict[str, object]:
    marker = "Pièce 7" if lang == "fr" else "Stuk 4"
    start = draft.index(marker)
    return guard_paraphrase(
        draft_region=draft,
        reference_start=start,
        reference_end=start + len(marker),
        quoted_text=quote,
        source_text_context=source,
        source_version_id=version,
        source_sha256="a" * 64 if version else None,
        pdf_page=1 if version else None,
        ocr_uncertain=ocr,
        source_text_partial=partial,
        draft_language=lang,
        source_language=source_lang,
    )


@pytest.mark.parametrize(
    ("draft", "source", "quote", "kind"),
    [
        (
            "Pièce 7, PDF p. 1, «Le paiement est enregistré.» Le montant est EUR 900,00.",
            "Le paiement est enregistré. Le montant est EUR 500,00.",
            "Le paiement est enregistré.",
            "amount",
        ),
        (
            "Pièce 7, PDF p. 1, «Le paiement est enregistré.» Le paiement date du 14/09/2026.",
            "Le paiement est enregistré. Il date du 13/09/2026.",
            "Le paiement est enregistré.",
            "date",
        ),
        (
            "Pièce 7, PDF p. 1, «Le paiement est enregistré.» L'article 12 s'applique.",
            "Le paiement est enregistré. Selon l'article 13, le délai est expiré.",
            "Le paiement est enregistré.",
            "article",
        ),
        (
            "Pièce 7, PDF p. 1, «Le paiement est enregistré.» Madame Dupont était présente.",
            "Le paiement est enregistré. Madame Martin était présente.",
            "Le paiement est enregistré.",
            "party_name",
        ),
        (
            "Pièce 7, PDF p. 1, «Le paiement est enregistré.» Le versement n'est pas dû.",
            "Le paiement est enregistré. Le versement est dû.",
            "Le paiement est enregistré.",
            "negation",
        ),
        (
            "Pièce 7, PDF p. 1, «Le paiement est enregistré.» Le règlement est uniquement provisoire.",
            "Le paiement est enregistré. Le règlement est définitif.",
            "Le paiement est enregistré.",
            "qualifier",
        ),
        (
            "Stuk 4, PDF p. 1, «De betaling is geboekt.» De factuur is niet betaald.",
            "De betaling is geboekt. De factuur is betaald.",
            "De betaling is geboekt.",
            "negation",
        ),
        (
            "Stuk 4, PDF p. 1, «De betaling is geboekt.» Slechts EUR 450,00 is verschuldigd.",
            "De betaling is geboekt. EUR 400,00 is verschuldigd.",
            "De betaling is geboekt.",
            "qualifier",
        ),
    ],
)
def test_seeded_unsupported_term_creates_warning_never_contradiction(
    draft: str,
    source: str,
    quote: str,
    kind: str,
) -> None:
    lang = "nl" if "Stuk 4" in draft else "fr"
    result = check(draft, source, quote=quote, lang=lang, source_lang=lang)
    assert result["schema"] == GUARD_VERSION
    assert result["semantic_support"] == "not_assessed"
    assert result["state"] == "needs_manual_review"
    assert result["anchor_basis"] == "unique_exact_quote_in_derived_page_text"
    assert any(item["kind"] == kind for item in result["warnings"])
    assert all(item["reason_code"] == "TERM_NOT_SEEN_IN_NEARBY_DERIVED_TEXT" for item in result["warnings"])
    assert "contradicted" not in str(result)


def test_same_number_and_quotation_does_not_invent_semantic_support() -> None:
    text = "Pièce 7, PDF p. 1, «Le paiement est enregistré.» Somme EUR 250,00."
    result = check(text, "Le paiement est enregistré. Somme EUR 250,00.")
    assert result["warnings"] == []
    assert result["state"] == "not_assessed"
    assert result["semantic_support"] == "not_assessed"


def test_adjacent_paragraph_prevents_false_absence_warning() -> None:
    draft = "Pièce 7, PDF p. 1, «Le paiement est enregistré.» Madame Dupont était présente."
    result = check(draft, "Madame Dupont était présente.\nLe paiement est enregistré.")
    assert not any(w["kind"] == "party_name" for w in result["warnings"])


@pytest.mark.parametrize(
    ("source", "quote", "version", "ocr", "partial", "reason"),
    [
        (
            "Le paiement est enregistré. Le paiement est enregistré.",
            "Le paiement est enregistré.",
            "source-v1",
            False,
            False,
            "DUPLICATE_QUOTE_AMBIGUOUS",
        ),
        (
            "Le paiement est constaté.",
            "Le paiement est enregistré.",
            "source-v1",
            False,
            False,
            "QUOTE_NOT_FOUND_IN_DERIVED_PAGE_TEXT",
        ),
        (None, "Le paiement est enregistré.", "source-v1", False, False, "SOURCE_TEXT_UNAVAILABLE"),
        ("Le paiement est enregistré.", None, "source-v1", False, False, "NO_UNIQUE_VERBATIM_ANCHOR"),
        (
            "Le paiement est enregistré.",
            "Le paiement est enregistré.",
            None,
            False,
            False,
            "SOURCE_PINPOINT_UNRESOLVED",
        ),
        (
            "Le paiement est enregistré.",
            "Le paiement est enregistré.",
            "source-v1",
            True,
            False,
            "OCR_OR_VISUAL_FIDELITY_UNCERTAIN",
        ),
        (
            "Le paiement est enregistré.",
            "Le paiement est enregistré.",
            "source-v1",
            False,
            True,
            "SOURCE_TEXT_PARTIAL",
        ),
    ],
)
def test_uncertain_or_wrong_version_evidence_abstains(
    source: str | None,
    quote: str | None,
    version: str | None,
    ocr: bool,
    partial: bool,
    reason: str,
) -> None:
    draft = "Pièce 7, PDF p. 1, «Le paiement est enregistré.» La somme est EUR 300,00."
    result = check(draft, source, quote=quote, version=version, ocr=ocr, partial=partial)
    assert reason in result["reason_codes"]
    assert result["warnings"] == []
    assert result["source_excerpt"] == ""
    assert result["anchor_basis"] == "unavailable"
    assert result["semantic_support"] == "not_assessed"


def test_cross_language_never_reports_absence_as_contradiction() -> None:
    draft = "Stuk 4, PDF p. 1, «Le paiement est enregistré.» EUR 300,00."
    result = check(draft, "Le paiement est enregistré.", lang="nl", source_lang="fr")
    assert "CROSS_LANGUAGE_LEXICAL_COMPARISON_UNSUPPORTED" in result["reason_codes"]
    assert result["warnings"] == []
    assert result["semantic_support"] == "not_assessed"


def test_unsupported_offsets_fail_closed_without_guessing() -> None:
    with pytest.raises(ValueError, match="offsets"):
        guard_paraphrase(
            draft_region="Pièce 7",
            reference_start=99,
            reference_end=100,
            quoted_text=None,
            source_text_context=None,
            source_version_id=None,
            source_sha256=None,
            pdf_page=None,
            ocr_uncertain=True,
            source_text_partial=True,
        )


def test_long_paragraph_and_large_page_never_generate_false_absence() -> None:
    draft = "Pièce 7 " + "A" * 1300
    result = check(draft, "Le paiement est enregistré.", quote="Le paiement est enregistré.")
    assert "DRAFT_PARAGRAPH_MISSING_OR_UNBOUNDED" in result["reason_codes"]
    assert result["warnings"] == []
    assert result["semantic_support"] == "not_assessed"


@pytest.mark.parametrize(
    ("claim", "source", "kind"),
    [
        (
            "Pièce 7, PDF p. 1, «Le paiement est enregistré.» Le montant est accepté.",
            "Le paiement est enregistré. Le montant est accepté sous réserve.",
            "qualifier",
        ),
        (
            "Stuk 4, PDF p. 1, «De betaling is geboekt.» De factuur is betaald.",
            "De betaling is geboekt. De factuur is niet betaald.",
            "negation",
        ),
    ],
)
def test_source_modifier_omitted_from_claim_is_warning_only(
    claim: str,
    source: str,
    kind: str,
) -> None:
    nl = "Stuk 4" in claim
    result = check(
        claim,
        source,
        quote="De betaling is geboekt." if nl else "Le paiement est enregistré.",
        lang="nl" if nl else "fr",
        source_lang="nl" if nl else "fr",
    )
    assert any(
        w["kind"] == kind and w["reason_code"] == "SOURCE_MODIFIER_NOT_SEEN_IN_DRAFT"
        for w in result["warnings"]
    )
    assert result["semantic_support"] == "not_assessed"
    assert result["state"] == "needs_manual_review"
