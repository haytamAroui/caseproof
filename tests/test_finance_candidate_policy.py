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


def test_domain_oversized_net_amount_fails_closed_without_rounding() -> None:
    from decimal import localcontext

    with localcontext() as ctx:
        ctx.prec = 3
        too_long = assess_invoice_order_net(
            _doc("inv", "9" * 40), "PO-1", _doc("po", "1"), "PO-1"
        )
        assert too_long.status == "unresolved"
        assert too_long.delta is None
        precise = assess_invoice_order_net(
            _doc("inv", "1250.01"), "PO-1", _doc("po", "1150.00"), "PO-1"
        )
        assert precise.status == "candidate_requires_review"
        assert precise.delta == "100.01"


def test_domain_unsupported_fractional_precision_or_credit_is_unresolved() -> None:
    for amount in ("1.1234567", "-2.00", "1E+40"):
        result = assess_invoice_order_net(
            _doc("inv", amount), "PO-1", _doc("po", "1.00"), "PO-1"
        )
        assert result.status == "unresolved"
        assert result.delta is None
        assert any("precision" in message for message in result.unresolved)
