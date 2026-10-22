"""Golden and adversarial controls for synthetic-only finance intake."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from apps.api.synthetic_finance import (
    SyntheticParseError,
    parse_synthetic_ubl,
    synthetic_review_packet,
)

FIX = Path(__file__).parent / "fixtures" / "finance"
INVOICE = (FIX / "synthetic_invoice_mismatch_ubl21.xml").read_bytes()
ORDER = (FIX / "synthetic_purchase_order_ubl21.xml").read_bytes()
MATCH = (FIX / "synthetic_invoice_match_ubl21.xml").read_bytes()


def test_mismatch_is_unreviewed_and_has_two_versioned_parser_draft_sources() -> None:
    packet = synthetic_review_packet(INVOICE, ORDER)
    assert packet["status"] == "candidate_requires_review"
    assert packet["difference"] == "100.00"
    assert packet["currency"] == "EUR"
    assert packet["review"] == {
        "state": "not_requested", "authenticated": False, "authorized": False
    }
    assert packet["audit"] == {"persisted": False, "receipt": None}
    assert packet["mode"] == "synthetic_only_no_customer_data"
    assert len(packet["unresolved"]) >= 2
    for item in (packet["invoice"], packet["purchase_order"]):
        source = item["source"]
        assert source["verification_status"] == "unverified_demo"
        assert len(source["source_sha256_hex"]) == 64
        assert len(source["representation_sha256_hex"]) == 64
        assert source["version_id"].startswith("synthetic-sha256:")
        assert source["locator"] == {
            "kind": "structured_field",
            "schema_id": "exceptiondesk.finance.net-subset.v1",
            "path": ["net_excluding_tax"],
        }
    assert json.loads(json.dumps(packet)) == packet


def test_match_does_not_become_approved_or_audited() -> None:
    packet = synthetic_review_packet(MATCH, ORDER)
    assert packet["status"] == "match_unreviewed"
    assert packet["difference"] == "0"
    assert packet["review"]["authorized"] is False
    assert packet["export"]["status"] == "draft_only_not_an_approved_report"


def test_missing_order_never_yields_fake_comparison() -> None:
    packet = synthetic_review_packet(INVOICE, None)
    assert packet["status"] == "unresolved"
    assert packet["difference"] is None
    assert packet["purchase_order"] is None
    assert "Purchase order missing." in packet["unresolved"]


def test_mismatched_order_reference_blocks_deterministic_total_comparison() -> None:
    changed = INVOICE.replace(b"PO-2026-001", b"PO-OTHER-001")
    packet = synthetic_review_packet(changed, ORDER)
    assert packet["status"] == "unresolved"
    assert packet["difference"] is None
    assert "Invoice references a different purchase order." in packet["unresolved"]


def test_missing_order_reference_blocks_comparison() -> None:
    changed = INVOICE.replace(
        b"<cac:OrderReference><cbc:ID>PO-2026-001</cbc:ID></cac:OrderReference>", b""
    )
    packet = synthetic_review_packet(changed, ORDER)
    assert packet["status"] == "unresolved"
    assert "Invoice purchase-order reference missing." in packet["unresolved"]


def test_currency_mismatch_never_auto_converts() -> None:
    changed = ORDER.replace(b">EUR<", b">USD<").replace(b'currencyID="EUR"', b'currencyID="USD"')
    packet = synthetic_review_packet(INVOICE, changed)
    assert packet["difference"] is None
    assert packet["status"] == "unresolved"
    assert "Currencies differ; no conversion rule is authorized." in packet["unresolved"]


def test_parsed_decimal_is_exact_and_raw_byte_versions_change() -> None:
    parsed = parse_synthetic_ubl(INVOICE, "invoice")
    assert parsed.amount == Decimal("1250.00")
    assert str(parsed.amount) == "1250.00"
    updated = parse_synthetic_ubl(INVOICE.replace(b"1250.00", b"1250.01"), "invoice")
    assert updated.evidence.version_id != parsed.evidence.version_id
    assert updated.evidence.representation_sha256_hex != parsed.evidence.representation_sha256_hex


@pytest.mark.parametrize("bad", [
    b"",
    b"<Invoice>",
    b'<!DOCTYPE x [<!ENTITY boom "bad">]><Invoice>&boom;</Invoice>',
    b"x" * (64 * 1024 + 1),
    b"<?xml version='1.0'?><Invoice/>",
])
def test_untrusted_or_unbounded_xml_rejected(bad: bytes) -> None:
    with pytest.raises(SyntheticParseError):
        parse_synthetic_ubl(bad, "invoice")


def test_missing_total_or_duplicate_total_rejected_not_defaulted_zero() -> None:
    original = b'<cbc:LineExtensionAmount currencyID="EUR">1250.00</cbc:LineExtensionAmount>'
    missing = INVOICE.replace(original, b"")
    double = INVOICE.replace(original, original + original)
    for raw in (missing, double):
        with pytest.raises(SyntheticParseError):
            parse_synthetic_ubl(raw, "invoice")


def test_monetary_basis_and_currency_are_not_guessed() -> None:
    old = b'<cbc:LineExtensionAmount currencyID="EUR">1250.00</cbc:LineExtensionAmount>'
    for value in (b"1e2", b"NaN", b"-1.00", b"100.1234567", b"0,99"):
        with pytest.raises(SyntheticParseError):
            parse_synthetic_ubl(
                INVOICE.replace(old, b'<cbc:LineExtensionAmount currencyID="EUR">' + value
                                + b"</cbc:LineExtensionAmount>"),
                "invoice",
            )
    with pytest.raises(SyntheticParseError):
        parse_synthetic_ubl(INVOICE.replace(b'currencyID="EUR"', b'currencyID="USD"'), "invoice")


def test_duplicate_document_id_is_ambiguous_and_not_silently_overwritten() -> None:
    original = b"<cbc:ID>INV-2026-001</cbc:ID>"
    duplicate = INVOICE.replace(original, original + original)
    with pytest.raises(SyntheticParseError):
        parse_synthetic_ubl(duplicate, "invoice")


def test_kind_confusion_rejected() -> None:
    with pytest.raises(SyntheticParseError):
        parse_synthetic_ubl(ORDER, "invoice")
    with pytest.raises(SyntheticParseError):
        parse_synthetic_ubl(INVOICE, "purchase_order")


def test_utf16_and_false_utf8_declarations_cannot_bypass_dtd_rejection() -> None:
    entity_invoice = INVOICE.replace(
        b"1250.00",
        b"&probe;",
    ).replace(
        b"<Invoice ",
        b'<!DOCTYPE Invoice [<!ENTITY probe "1250.00">]><Invoice ',
    )
    for raw in (
        entity_invoice,
        entity_invoice.decode("utf-8").encode("utf-16"),
        entity_invoice.decode("utf-8").encode("utf-16-le"),
        INVOICE.replace(b'encoding="UTF-8"', b'encoding="UTF-16"'),
    ):
        with pytest.raises(SyntheticParseError):
            parse_synthetic_ubl(raw, "invoice")


def test_oversized_decimal_digits_rejected_before_default_context_rounding() -> None:
    over_precision = INVOICE.replace(b"1250.00", b"9" * 28)
    with pytest.raises(SyntheticParseError):
        parse_synthetic_ubl(over_precision, "invoice")


def test_child_bearing_amount_is_not_accepted_as_scalar() -> None:
    nested = INVOICE.replace(
        b"1250.00</cbc:LineExtensionAmount>",
        b"1250.00<cbc:Note>amended</cbc:Note></cbc:LineExtensionAmount>",
    )
    with pytest.raises(SyntheticParseError):
        parse_synthetic_ubl(nested, "invoice")


def test_child_bearing_document_id_is_not_accepted_as_scalar() -> None:
    nested = INVOICE.replace(
        b"INV-2026-001</cbc:ID>",
        b"INV-2026-001<cbc:Note>extra</cbc:Note></cbc:ID>",
    )
    with pytest.raises(SyntheticParseError):
        parse_synthetic_ubl(nested, "invoice")
