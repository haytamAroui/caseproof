"""Finance application boundary: candidate production cannot authorize decisions."""

from decimal import Decimal

import pytest

from application.finance_comparison import (
    FinanceComparisonInput,
    compare_finance_candidate,
)
from domains.finance.reconciliation import DocumentAmount, Money


def document(identifier: str, amount: str, currency: str = "EUR") -> DocumentAmount:
    return DocumentAmount(identifier, Money(Decimal(amount), currency), identifier + "-draft")


def test_discrepancy_is_unverified_review_candidate() -> None:
    result = compare_finance_candidate(FinanceComparisonInput(
        document("invoice", "1250.00"), "PO-1",
        document("po", "1150.00"), "PO-1",
    ))
    assert result.status == "candidate_requires_review"
    assert result.delta == "100.00"
    assert result.currency == "EUR"
    assert result.requires_evidence_verification
    assert result.requires_authorized_human_review
    assert result.unresolved
    assert not hasattr(result, "approved")


def test_equal_amounts_never_imply_approval() -> None:
    result = compare_finance_candidate(FinanceComparisonInput(
        document("invoice", "10.00"), "PO-1",
        document("po", "10.00"), "PO-1",
    ))
    assert result.status == "match_unreviewed"
    assert result.requires_authorized_human_review


@pytest.mark.parametrize("reference, currency", [
    ("WRONG-PO", "EUR"),
    ("PO-1", "USD"),
])
def test_noncomparable_inputs_fail_closed(reference: str, currency: str) -> None:
    result = compare_finance_candidate(FinanceComparisonInput(
        document("invoice", "20.00"), reference,
        document("po", "10.00", currency), "PO-1",
    ))
    assert result.status == "unresolved"
    assert result.delta is None
    assert result.currency is None


def test_typed_input_required() -> None:
    with pytest.raises(TypeError):
        compare_finance_candidate(None)  # type: ignore[arg-type]
