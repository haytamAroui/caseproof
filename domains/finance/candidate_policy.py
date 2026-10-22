"""Domain-owned eligibility policy for an unreviewed invoice/PO net candidate.

No parsing, storage, transport, AI approval or human authorization belongs here.
This function never infers VAT compatibility, deliveries, credits or contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from domains.finance.reconciliation import DocumentAmount, compare_invoice_to_po


@dataclass(frozen=True, slots=True)
class NetCandidate:
    status: Literal["unresolved", "match_unreviewed", "candidate_requires_review"]
    delta: str | None
    currency: str | None
    unresolved: tuple[str, ...]


_CONTEXT_GAPS = (
    "No evidence byte-store verification, real coverage or authenticated human review.",
    "Delivery, amendments, credit notes, freight and applicable VAT/tolerance policy not assessed.",
)


def assess_invoice_order_net(
    invoice: DocumentAmount,
    invoice_order_reference: str | None,
    order: DocumentAmount | None,
    order_number: str | None,
) -> NetCandidate:
    """Only a same-reference, same-currency net comparison can create a candidate.

    Evidence claim IDs are required by DocumentAmount but are still unverified
    until the application's independent evidence and review gates are satisfied.
    """
    unresolved = list(_CONTEXT_GAPS)
    if order is None:
        unresolved.append("Purchase order missing.")
    elif not order_number:
        unresolved.append("Purchase order identity missing.")
    if invoice_order_reference is None:
        unresolved.append("Invoice purchase-order reference missing.")
    elif order is not None and order_number is not None and invoice_order_reference != order_number:
        unresolved.append("Invoice references a different purchase order.")
    if order is not None and invoice.amount.currency != order.amount.currency:
        unresolved.append("Currencies differ; no conversion rule is authorized.")

    if (
        order is None or not order_number or invoice_order_reference != order_number
        or invoice.amount.currency != order.amount.currency
    ):
        return NetCandidate("unresolved", None, None, tuple(unresolved))

    finding = compare_invoice_to_po(invoice, order)
    if finding is None:
        return NetCandidate("match_unreviewed", "0", invoice.amount.currency, tuple(unresolved))
    return NetCandidate(
        "candidate_requires_review",
        str(finding.difference.amount),
        invoice.amount.currency,
        tuple(unresolved),
    )
