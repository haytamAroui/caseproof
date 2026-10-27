"""Immutable factual accounting proposals with fail-closed missing basis and source IDs."""

from datetime import date
from decimal import Decimal

import pytest

from domains.finance.factual_reconciliation import (
    AccountingEvidence,
    AmendmentEvidence,
    DeliveryEvidence,
    assess_accounting_evidence,
)
from domains.finance.reconciliation import DocumentAmount, Money


def amount(value, *, doc="invoice", claim="net", currency="EUR"):
    return DocumentAmount(doc, Money(Decimal(value), currency), f"{doc}:{claim}")


def test_comparable_net_difference_and_explicit_partial_delivery():
    inv = AccountingEvidence(amount("600"))
    po = AccountingEvidence(amount("1000", doc="order"))
    full = assess_accounting_evidence(inv, po)
    assert full.differences[0].delta.amount == Decimal("-400")
    assert "delivery_and_quantity_basis_unassessed" in full.unresolved
    partial = assess_accounting_evidence(
        inv, po, delivery=DeliveryEvidence(Decimal("10"), Decimal("6"), "delivery:receipt"),
    )
    assert partial.status == "unresolved"
    assert not partial.differences
    assert "partial_delivery_billing_terms_unverified" in partial.unresolved
    assert "delivery:receipt" in partial.evidence_claim_ids
    assert partial.approved is False


def test_missing_tax_freight_discounts_and_credit_never_mean_zero():
    inv = AccountingEvidence(amount("100"), gross=amount("121", claim="gross"))
    po = AccountingEvidence(amount("100", doc="order"))
    outcome = assess_accounting_evidence(inv, po)
    assert "vat_component_incomplete" in outcome.unresolved
    assert "invoice_gross_components_incomplete" in outcome.unresolved
    assert outcome.status == "unresolved"
    assert outcome.requires_authorized_human_review


def test_complete_gross_mismatch_uses_decimal_only_and_precise_citations():
    inv = AccountingEvidence(
        amount("100"), vat=amount("21", claim="vat"), freight=amount("5", claim="freight"),
        discount=amount("2", claim="discount"), credit=amount("3", claim="credit"),
        gross=amount("122", claim="gross"),
    )
    po = AccountingEvidence(amount("100", doc="order"))
    out = assess_accounting_evidence(inv, po)
    diff = next(d for d in out.differences if d.code == "INVOICE_GROSS_COMPONENT_MISMATCH")
    assert diff.delta.amount == Decimal("1")
    assert "invoice:credit" in diff.claim_ids


def test_currency_basis_amendment_and_overdelivery_are_unresolved_not_approved():
    inv = AccountingEvidence(
        amount("100", currency="USD"), amendment=AmendmentEvidence(
            "invoice", "original", date(2026, 10, 1), "amendment:citation"
        ),
    )
    po = AccountingEvidence(amount("100", doc="order"))
    out = assess_accounting_evidence(
        inv, po, delivery=DeliveryEvidence(Decimal("10"), Decimal("11"), "delivery:citation")
    )
    assert not out.differences
    assert "currency_conversion_not_established" in out.unresolved
    assert "amendment_validity_and_precedence_unverified" in out.unresolved
    assert "overdelivery_requires_verification" in out.unresolved
    assert out.status == "unresolved"


@pytest.mark.parametrize("bad", [float("nan"), 10.1, Decimal("NaN")])
def test_invalid_quantity_rejected(bad):
    with pytest.raises(ValueError):
        DeliveryEvidence(Decimal("10"), bad, "source:1")


def test_cross_currency_component_and_uncited_amendment_fail():
    with pytest.raises(ValueError):
        AccountingEvidence(amount("100"), vat=amount("20", claim="vat", currency="USD"))
    with pytest.raises(ValueError):
        AmendmentEvidence("invoice", "invoice", None, "citation")
