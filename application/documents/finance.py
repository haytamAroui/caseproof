"""Connect normalized UBL scalar evidence to existing deterministic finance comparison."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from application.documents.contracts import ParsedDocument
from application.documents.structured import StructuredCitation, resolve_xml_citation, xml_citation
from application.extraction.contracts import ExtractionError
from application.finance_comparison import (
    FinanceComparisonInput,
    FinanceComparisonResult,
    compare_finance_candidate,
)
from domains.finance.reconciliation import DocumentAmount, Money

CBC = "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}"
CAC = "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}"


@dataclass(frozen=True)
class UBLObservation:
    identifier: str
    order_reference: str | None
    amount: DocumentAmount
    citation: StructuredCitation


def observe_ubl(parsed: ParsedDocument, *, kind: str, scope: str) -> UBLObservation:
    if not parsed.evidence.complete or kind not in {"invoice", "purchase_order"}:
        raise ExtractionError("complete supported UBL source required")
    name = "Invoice" if kind == "invoice" else "Order"
    root = f"/{{urn:oasis:names:specification:ubl:schema:xsd:{name}-2}}{name}[1]"
    fields = dict(parsed.fields)

    def single(path: str) -> str:
        # Sibling [2] is a real ambiguity, never silently first-wins.
        if path not in fields or path.replace("[1]", "[2]", 1) in fields:
            raise ExtractionError("required UBL scalar missing or ambiguous")
        for key in fields:
            if re.sub(r"\[[0-9]+\]", "[]", key) == re.sub(r"\[[0-9]+\]", "[]", path) and key != path:
                raise ExtractionError("duplicate UBL scalar")
        value = fields[path].strip()
        if not value:
            raise ExtractionError("nonempty UBL scalar required")
        return value

    identifier = single(root + "/" + CBC + "ID[1]")
    currency = single(root + "/" + CBC + "DocumentCurrencyCode[1]")
    total = "LegalMonetaryTotal" if kind == "invoice" else "AnticipatedMonetaryTotal"
    amount_path = root + "/" + CAC + total + "[1]/" + CBC + "LineExtensionAmount[1]"
    amount = single(amount_path)
    if not re.fullmatch(r"[0-9]{1,18}(?:\.[0-9]{1,6})?", amount) or not re.fullmatch(r"[A-Z]{3}", currency):
        raise ExtractionError("explicit finite decimal/currency required")
    if single(amount_path + "/@currencyID") != currency:
        raise ExtractionError("UBL currency contradiction")
    order_path = root + "/" + CAC + "OrderReference[1]/" + CBC + "ID[1]"
    reference = single(order_path) if order_path in fields else None
    citation = xml_citation(parsed, amount_path)
    resolve_xml_citation(scope, parsed, citation)
    value = DocumentAmount(
        parsed.evidence.source.document_id, Money(Decimal(amount), currency), citation.anchor.anchor_id
    )
    return UBLObservation(identifier, reference, value, citation)


def compare_ubl_evidence(
    invoice: ParsedDocument, order: ParsedDocument, *, scope: str
) -> FinanceComparisonResult:
    # A deterministic discrepancy candidate, never a balance, payment authorization or approval.
    inv = observe_ubl(invoice, kind="invoice", scope=scope)
    po = observe_ubl(order, kind="purchase_order", scope=scope)
    return compare_finance_candidate(
        FinanceComparisonInput(inv.amount, inv.order_reference, po.amount, po.identifier)
    )
