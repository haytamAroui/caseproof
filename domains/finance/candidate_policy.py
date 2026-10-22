"""Domain-owned eligibility policy for an unreviewed invoice/PO net candidate.

No parsing, storage, transport, AI approval or human authorization belongs here.
This function never infers VAT compatibility, deliveries, credits or contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Context, localcontext
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
    exponent = amount.as_tuple().exponent
    if not isinstance(exponent, int):
        return False
    fractional_digits = max(0, -exponent)
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
    # A domain caller may bypass XML parsing: trim edge whitespace and fail
    # closed on missing/blank identities, rather than matching two blanks.
    order_ref = invoice_order_reference.strip() if isinstance(invoice_order_reference, str) else ""
    po_number = order_number.strip() if isinstance(order_number, str) else ""
    if order is None:
        unresolved.append("Purchase order missing.")
    elif not po_number:
        unresolved.append("Purchase order identity missing.")
    if not order_ref:
        unresolved.append("Invoice purchase-order reference missing.")
    elif order is not None and po_number and order_ref != po_number:
        unresolved.append("Invoice references a different purchase order.")
    if order is not None and invoice.amount.currency != order.amount.currency:
        unresolved.append("Currencies differ; no conversion rule is authorized.")

    if (
        not _supported_net(invoice.amount.amount)
        or (order is not None and not _supported_net(order.amount.amount))
    ):
        unresolved.append("Net amount is outside supported precision or is a credit/negative amount.")

    if (
        order is None or not po_number or not order_ref or order_ref != po_number
        or invoice.amount.currency != order.amount.currency
        or not _supported_net(invoice.amount.amount)
        or not _supported_net(order.amount.amount)
    ):
        return NetCandidate("unresolved", None, None, tuple(unresolved))

    # Do not inherit a caller's narrow Decimal context; 28 digits exceeds the
    # maximum 18+6 operand precision with a possible subtraction carry.
    # Use a complete, fixed Decimal context. Cloning the caller context can
    # inherit exponent traps or limits even when precision is overwritten.
    with localcontext(Context(
        prec=28, rounding=ROUND_HALF_EVEN, Emin=-999999, Emax=999999,
    )):
        finding = compare_invoice_to_po(invoice, order)
    if finding is None:
        return NetCandidate("match_unreviewed", "0", invoice.amount.currency, tuple(unresolved))
    return NetCandidate(
        "candidate_requires_review",
        str(finding.difference.amount),
        invoice.amount.currency,
        tuple(unresolved),
    )
