"""Typed, conservative signal registry and nonbillable topology measurement."""

import pytest

from application.extraction.contracts import ExtractionError
from domains.construction.extraction_rules import ConstructionEvidencePolicy
from domains.finance.extraction_rules import FinanceEvidencePolicy
from evals.topology_comparison import BILLABLE_CALL_CAP, compare_topologies


def test_registry_versions_and_money_semantics_require_explicit_units():
    finance = FinanceEvidencePolicy()
    assert finance.definitions["amount_disputed"].value_type == "money"
    assert finance.validate(
        "amount_disputed", "amount_disputed", "Invoice discrepancy: 1150.00", "1150.00", "invoice"
    ) == ("needs_review", "typed_currency_ambiguous")
    assert finance.validate(
        "amount_disputed", "amount_disputed", "Invoice discrepancy EUR 1150.00", "1150.00", "invoice"
    ) == ("validated", "proposal_lexically_consistent")
    assert finance.validate(
        "amount_disputed", "amount_disputed", "Discrepancy EUR 1150.00 USD", "1150.00", "invoice"
    )[0] == "needs_review"
    assert finance.validate(
        "amount_disputed", "amount_disputed", "Discrepancy EUR 1150.00", "1150.00", "variation"
    )[0] == "rejected"
    construction = ConstructionEvidencePolicy()
    assert construction.definitions["price_agreed"].value_type == "money"
    assert construction.validate("price_agreed", "price_agreed", "Price agreed EUR 150.00", "150.00", "variation")[0] == "validated"


def test_topology_comparison_default_is_safe_scripted_not_quality_claim():
    report = compare_topologies()
    assert report["mode"] == "scripted_safety_only"
    assert report["provider_boundary"] == "scripted_no_inference"
    assert report["billable_call_cap"] == 0
    assert report["strategies"]["global_first"]["configured_call_ceiling"] == 8
    assert report["strategies"]["segmented"]["configured_call_ceiling"] == 4
    assert report["strategies"]["four_pass"]["configured_call_ceiling"] == 16


def test_live_comparison_requires_explicit_billable_budget_without_calling_provider():
    with pytest.raises(ExtractionError, match="acknowledgement"):
        compare_topologies(live=True)
    assert BILLABLE_CALL_CAP == 28
