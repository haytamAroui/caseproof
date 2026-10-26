"""Server exact matching resolves Unicode quotes without trusting model arithmetic."""
from application.extraction.pipeline import SYSTEM, _locate


def test_accented_french_quote_resolves_to_exact_codepoint_slice():
    content = "Préface : paiement de EUR 125,00 confirmé le 12 mai 2026."
    quote = "paiement de EUR 125,00 confirmé"
    start, reason = _locate(content, quote, None)
    assert reason == "exact" and start is not None
    assert content[start:start + len(quote)] == quote
    assert start == len("Préface : ")


def test_explicit_wrong_offset_is_still_rejected():
    assert _locate("Préface : paiement confirmé", "paiement confirmé", 1) == (
        None, "invalid_exact_offset"
    )


def test_repeated_quote_without_context_remains_unresolved():
    assert _locate("EUR 125,00 puis EUR 125,00", "EUR 125,00", None) == (
        None, "ambiguous_quote"
    )
    assert _locate("EUR 125,00 puis EUR 125,00", "puis EUR 125,00", None) == (11, "exact")


def test_prompt_requests_server_resolution_with_bounded_size():
    assert "Omit start" in SYSTEM
    assert len(SYSTEM) <= 3000
