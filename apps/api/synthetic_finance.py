"""MVP-01A: deterministic SYNTHETIC UBL invoice/order candidate intake.

Not a customer upload service, verified evidence resolver, PDF parser or review API.
Only a constrained UBL subset is supported; full XSD/business validation is pending.
All source references are UNVERIFIED draft locators in a parser-derived representation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Literal
from xml.etree import ElementTree as ET

from domains.finance.candidate_policy import assess_invoice_order_net
from domains.finance.reconciliation import DocumentAmount, Money
from packages.evidence_kernel.domain.anchors import StructuredField

CBC = "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}"
CAC = "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}"
INVOICE_ROOT = "{urn:oasis:names:specification:ubl:schema:xsd:Invoice-2}Invoice"
ORDER_ROOT = "{urn:oasis:names:specification:ubl:schema:xsd:Order-2}Order"
PARSER_VERSION = "exceptiondesk-ubl-net-subset-v1"
REP_SCHEMA = "exceptiondesk.finance.net-subset.v1"
MAX_SYNTHETIC_BYTES = 64 * 1024
MAX_NODES = 250
_DECIMAL_TEXT = re.compile(r"(?:0|[1-9][0-9]{0,17})(?:\.[0-9]{1,6})?\Z")
_CURRENCY = re.compile(r"[A-Z]{3}\Z")


class SyntheticParseError(ValueError):
    """Unsupported or ambiguous synthetic input must fail closed."""


@dataclass(frozen=True, slots=True)
class DraftSourceReference:
    """Unverified source/representation identity; NOT a resolved EvidenceAnchor."""

    document_id: str
    version_id: str
    source_sha256_hex: str
    representation_id: str
    representation_sha256_hex: str
    locator: StructuredField
    verification_status: Literal["unverified_demo"] = "unverified_demo"


@dataclass(frozen=True, slots=True)
class ParsedNetAmount:
    kind: Literal["invoice", "purchase_order"]
    ubl_id: str
    currency: str
    amount: Decimal
    order_reference: str | None
    evidence: DraftSourceReference


def _single_text(root: ET.Element, path: str, label: str, *, required: bool = True) -> str | None:
    found = root.findall(path)
    if not found and not required:
        return None
    if (
        len(found) != 1 or len(found[0]) != 0
        or found[0].text is None or not found[0].text.strip()
    ):
        raise SyntheticParseError(f"{label} missing, nested or ambiguous")
    result = found[0].text.strip()
    if len(result) > 128:
        raise SyntheticParseError(f"{label} too long")
    return result


def parse_synthetic_ubl(
    raw: bytes, kind: Literal["invoice", "purchase_order"]
) -> ParsedNetAmount:
    """Parse only a bounded, well-formed UBL net-amount subset, never external XML."""
    if kind not in ("invoice", "purchase_order"):
        raise SyntheticParseError("unsupported UBL kind")
    if type(raw) is not bytes or not raw or len(raw) > MAX_SYNTHETIC_BYTES:
        raise SyntheticParseError("synthetic UBL byte limit or type invalid")
    # Constrain encoding before scanning so UTF-16/32 cannot hide DTD tokens
    # in interleaved NUL bytes. Do not trust a conflicting XML declaration.
    try:
        xml_text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise SyntheticParseError("only UTF-8 synthetic XML supported") from exc
    if "\x00" in xml_text or xml_text.startswith("\ufeff"):
        raise SyntheticParseError("BOM/NUL or non-UTF8 XML unsupported")
    declaration = re.match(r"\s*<\?xml\b[^>]*\?>", xml_text, re.IGNORECASE)
    if declaration is not None:
        declared = re.search(
            r"""\bencoding\s*=\s*(['"])([^'"]+)\1""",
            declaration.group(0),
            re.IGNORECASE,
        )
        if declared is not None and declared.group(2).lower() != "utf-8":
            raise SyntheticParseError("declared XML encoding must be UTF-8")
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise SyntheticParseError("DTD and entities forbidden")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise SyntheticParseError("malformed UBL XML") from exc
    expected_root = INVOICE_ROOT if kind == "invoice" else ORDER_ROOT
    if root.tag != expected_root or sum(1 for _ in root.iter()) > MAX_NODES:
        raise SyntheticParseError("unsupported root or synthetic XML complexity")
    ubl_id = _single_text(root, f"{CBC}ID", "document ID")
    currency = _single_text(root, f"{CBC}DocumentCurrencyCode", "currency")
    if ubl_id is None or currency is None or not _CURRENCY.fullmatch(currency):
        raise SyntheticParseError("invalid document identity or currency")

    total_parent = (
        f"{CAC}LegalMonetaryTotal"
        if kind == "invoice" else f"{CAC}AnticipatedMonetaryTotal"
    )
    totals = root.findall(f"{total_parent}/{CBC}LineExtensionAmount")
    if len(totals) != 1:
        raise SyntheticParseError("exactly one net line-extension total required")
    total = totals[0]
    if len(total) != 0:
        raise SyntheticParseError("nested net amount content forbidden")
    amount_text = total.text.strip() if total.text else ""
    if total.attrib.get("currencyID") != currency or not _DECIMAL_TEXT.fullmatch(amount_text):
        raise SyntheticParseError("currency mismatch or invalid net amount")
    try:
        amount = Decimal(amount_text)
    except InvalidOperation as exc:
        raise SyntheticParseError("invalid amount") from exc
    if not amount.is_finite():
        raise SyntheticParseError("nonfinite net amount")
    order_ref = (
        _single_text(root, f"{CAC}OrderReference/{CBC}ID", "PO reference", required=False)
        if kind == "invoice" else None
    )
    source_sha = sha256(raw).hexdigest()
    representation = json.dumps(
        {
            "parser_version": PARSER_VERSION,
            "kind": kind,
            "document_id": ubl_id,
            "currency": currency,
            "net_excluding_tax": amount_text,
            "order_reference": order_ref,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    representation_sha = sha256(representation).hexdigest()
    evidence = DraftSourceReference(
        document_id=f"{kind}:{ubl_id}",
        version_id=f"synthetic-sha256:{source_sha}",
        source_sha256_hex=source_sha,
        representation_id=f"{PARSER_VERSION}:{representation_sha}",
        representation_sha256_hex=representation_sha,
        locator=StructuredField(REP_SCHEMA, ("net_excluding_tax",)),
    )
    return ParsedNetAmount(kind, ubl_id, currency, amount, order_ref, evidence)


def synthetic_review_packet(invoice_bytes: bytes, po_bytes: bytes | None) -> dict[str, object]:
    """An UNREVIEWED deterministic candidate packet. No privileged state change."""
    invoice = parse_synthetic_ubl(invoice_bytes, "invoice")
    order = parse_synthetic_ubl(po_bytes, "purchase_order") if po_bytes is not None else None
    candidate = assess_invoice_order_net(
        DocumentAmount(
            invoice.evidence.document_id,
            Money(invoice.amount, invoice.currency),
            invoice.evidence.representation_id,
        ),
        invoice.order_reference,
        (
            DocumentAmount(
                order.evidence.document_id,
                Money(order.amount, order.currency),
                order.evidence.representation_id,
            )
            if order is not None else None
        ),
        order.ubl_id if order is not None else None,
    )

    def serialize(item: ParsedNetAmount) -> dict[str, object]:
        ref = item.evidence
        return {
            "kind": item.kind,
            "ubl_id": item.ubl_id,
            "currency": item.currency,
            "net_excluding_tax": str(item.amount),
            "order_reference": item.order_reference,
            "source": {
                "document_id": ref.document_id,
                "version_id": ref.version_id,
                "source_sha256_hex": ref.source_sha256_hex,
                "representation_id": ref.representation_id,
                "representation_sha256_hex": ref.representation_sha256_hex,
                "locator": {
                    "kind": "structured_field",
                    "schema_id": ref.locator.schema_id,
                    "path": list(ref.locator.path),
                },
                "verification_status": ref.verification_status,
            },
        }

    return {
        "schema_version": "exceptiondesk.synthetic-finance-review.v1",
        "mode": "synthetic_only_no_customer_data",
        "parser_version": PARSER_VERSION,
        "status": candidate.status,
        "difference": candidate.delta,
        "currency": candidate.currency,
        "invoice": serialize(invoice),
        "purchase_order": serialize(order) if order is not None else None,
        "unresolved": list(candidate.unresolved),
        "review": {"state": "not_requested", "authenticated": False, "authorized": False},
        "audit": {"persisted": False, "receipt": None},
        "export": {"status": "draft_only_not_an_approved_report"},
    }
