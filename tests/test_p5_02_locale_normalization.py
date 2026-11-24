"""BE-08 (P5-02): Belgian FR/NL Decimal currency & DD/MM/YYYY date normalization."""

from __future__ import annotations

from application.litigation.factual_values import (
    FactAssertion,
    FactKind,
    FactRole,
    FactState,
    compare_fact,
)
from application.litigation.library import EvidencePreview, EvidenceRow


def _preview(text: str) -> EvidencePreview:
    row = EvidenceRow(
        source_id="src-1",
        document_id="doc-1",
        version_id="ver-1",
        original_sha256="a" * 64,
        media_type="text/plain",
        status="ready",
        parser_id="synthetic-v1",
        representation_id="repr-1",
        pages=(),
        warnings=(),
    )
    return EvidencePreview(row, text, ((0, len(text), "unpaginated", None),))


def test_belgian_nbsp_currency_and_decimal_normalization_matches() -> None:
    brief = "Le paiement de 1\u00a0250,00 EUR a été versé."
    source = "Betaling ontvangen: 1.250,00 €"
    assertion = FactAssertion(
        "c-money-1", "ref-1", brief, 0, len(brief), FactKind.MONEY, FactRole.PAYMENT, "fr", "nl"
    )
    obs = compare_fact(assertion, verified_brief_text=brief, preview=_preview(source), pdf_page=None)
    assert obs.state is FactState.MATCH
    assert obs.explanation == "same_role_typed_tokens_equal"


def test_ambiguous_number_format_abstains_with_typed_reason() -> None:
    brief = "Le paiement de 14,500 EUR a été versé."
    source = "Le paiement de 14.500 EUR a été reçu."
    assertion = FactAssertion(
        "c-money-amb", "ref-1", brief, 0, len(brief), FactKind.MONEY, FactRole.PAYMENT, "fr", "fr"
    )
    obs = compare_fact(assertion, verified_brief_text=brief, preview=_preview(source), pdf_page=None)
    assert obs.state is FactState.NEEDS_CONTEXT
    assert obs.explanation == "AMBIGUOUS_NUMBER_FORMAT"


def test_ambiguous_date_format_abstains_with_typed_reason() -> None:
    brief = "Le paiement a eu lieu le 04/05/2026."
    source = "Le paiement a été reçu le 22 mai 2026."
    assertion = FactAssertion(
        "c-date-amb", "ref-1", brief, 0, len(brief), FactKind.DATE, FactRole.PAYMENT, "fr", "fr"
    )
    obs = compare_fact(assertion, verified_brief_text=brief, preview=_preview(source), pdf_page=None)
    assert obs.state is FactState.NEEDS_CONTEXT
    assert obs.explanation == "AMBIGUOUS_DATE_FORMAT"


def test_unambiguous_dd_mm_yyyy_matches_named_french_date() -> None:
    brief = "Le paiement a eu lieu le 22/05/2026."
    source = "Betaling ontvangen op 22 mei 2026."
    assertion = FactAssertion(
        "c-date-ok", "ref-1", brief, 0, len(brief), FactKind.DATE, FactRole.PAYMENT, "fr", "nl"
    )
    obs = compare_fact(assertion, verified_brief_text=brief, preview=_preview(source), pdf_page=None)
    assert obs.state is FactState.MATCH
