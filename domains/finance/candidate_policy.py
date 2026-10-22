"""Domain-owned eligibility policy for an unreviewed invoice/PO net candidate.

No parsing, storage, transport, AI approval or human authorization belongs here.
This function never infers VAT compatibility, deliveries, credits or contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import localcontext
from typing import Literal

from domains.finance.reconciliation import DocumentAmount, compare_invoice_to_po


@dataclass(frozen=True, slots=True)
class NetCandidate:
    status: Literal["unresolved", "match_unreviewed", "candidate_requires_review"]
    delta: str | None
    currency: str | None
    unresolved: tuple[str, ...]


# Explicit pilot net-amount bounds: max 18 integral + 6 fractional digits.
# Bounded operands and fixed precision ensure subtraction never rounds a delta.
MAX_NET_INTEGRAL_DIGITS = 18
MAX_NET_FRACTIONAL_DIGITS = 6


def _supported_net(amount: object) -> bool:
    from decimal import Decimal

    if not isinstance(amount, Decimal) or not amount.is_finite() or amount < 0:
        return False
    integral_digits = max(1, amount.adjusted() + 1) if amount != 0 else 1
    fractional_digits = max(0, -amount.as_tuple().exponent)
    return (
        integral_digits <= MAX_NET_INTEGRAL_DIGITS
        and fractional_digits <= MAX_NET_FRACTIONAL_DIGITS
    )


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
        not _supported_net(invoice.amount.amount)
        or (order is not None and not _supported_net(order.amount.amount))
    ):
        unresolved.append("Net amount is outside supported precision or is a credit/negative amount.")

    if (
        order is None or not order_number or invoice_order_reference != order_number
        or invoice.amount.currency != order.amount.currency
        or not _supported_net(invoice.amount.amount)
        or not _supported_net(order.amount.amount)
    ):
        return NetCandidate("unresolved", None, None, tuple(unresolved))

    # Do not inherit a caller's narrow Decimal context; 28 digits exceeds the
    # maximum 18+6 operand precision with a possible subtraction carry.
    with localcontext() as decimal_context:
        decimal_context.prec = 28
        finding = compare_invoice_to_po(invoice, order)
    if finding is None:
        return NetCandidate("match_unreviewed", "0", invoice.amount.currency, tuple(unresolved))
    return NetCandidate(
        "candidate_requires_review",
        str(finding.difference.amount),
        invoice.amount.currency,
        tuple(unresolved),
    )
