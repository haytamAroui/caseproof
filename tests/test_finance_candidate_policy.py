"""Finance-domain candidate eligibility tests; API serialization is not policy authority."""

from decimal import Decimal

from domains.finance.candidate_policy import assess_invoice_order_net
from domains.finance.reconciliation import DocumentAmount, Money


def _doc(name: str, amount: str, currency: str = "EUR") -> DocumentAmount:
    return DocumentAmount(name, Money(Decimal(amount), currency), name + "-draft")


def test_domain_net_discrepancy_is_review_candidate_not_decision() -> None:
    result = assess_invoice_order_net(
        _doc("invoice", "1250.00"), "PO-1", _doc("po", "1150.00"), "PO-1"
    )
    assert result.status == "candidate_requires_review"
    assert result.delta == "100.00"
    assert result.currency == "EUR"
    assert result.unresolved


def test_domain_missing_or_wrong_order_cannot_create_amount_finding() -> None:
    invoice = _doc("invoice", "1250.00")
    for ref, po, order_number in (
        ("PO-1", None, None),
        (None, _doc("po", "1150.00"), "PO-1"),
        ("PO-2", _doc("po", "1150.00"), "PO-1"),
        ("PO-1", _doc("po", "1150.00"), None),
    ):
        result = assess_invoice_order_net(invoice, ref, po, order_number)
        assert result.status == "unresolved"
        assert result.delta is None
        assert result.currency is None


def test_domain_mismatched_currencies_not_implicitly_converted() -> None:
    result = assess_invoice_order_net(
        _doc("invoice", "1250.00"), "PO-1",
        _doc("po", "1150.00", "USD"), "PO-1",
    )
    assert result.status == "unresolved"
    assert result.delta is None
    assert any("Currencies differ" in x for x in result.unresolved)


def test_domain_matching_totals_are_unreviewed_not_approved() -> None:
    result = assess_invoice_order_net(
        _doc("invoice", "1150.00"), "PO-1", _doc("po", "1150.00"), "PO-1"
    )
    assert result.status == "match_unreviewed"
    assert result.delta == "0"
    assert result.unresolved
