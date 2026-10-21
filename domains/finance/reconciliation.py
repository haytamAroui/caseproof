"""Deterministic, review-first invoice/PO comparison."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal) or not self.amount.is_finite():
            raise ValueError("amount must be a finite Decimal")
        if len(self.currency) != 3 or not self.currency.isalpha() or self.currency != self.currency.upper():
            raise ValueError("currency must be a 3-letter uppercase code")


@dataclass(frozen=True, slots=True)
class DocumentAmount:
    document_id: str
    amount: Money
    evidence_claim_id: str

    def __post_init__(self) -> None:
        if not self.document_id.strip() or not self.evidence_claim_id.strip():
            raise ValueError("document ID and evidence claim ID are required")


@dataclass(frozen=True, slots=True)
class FinancialFinding:
    code: str
    status: str
    expected: Money
    actual: Money
    difference: Money
    evidence_claim_ids: tuple[str, str]
    explanation: str


def compare_invoice_to_po(invoice: DocumentAmount, po: DocumentAmount) -> FinancialFinding | None:
    """Compare like-for-like totals only; caller must establish VAT/fees/basis first."""
    if invoice.amount.currency != po.amount.currency:
        raise ValueError("cannot compare amounts in different currencies")
    delta = invoice.amount.amount - po.amount.amount
    if delta == 0:
        return None
    return FinancialFinding(
        code="AMOUNT_MISMATCH",
        status="requires_review",
        expected=po.amount,
        actual=invoice.amount,
        difference=Money(delta, invoice.amount.currency),
        evidence_claim_ids=(invoice.evidence_claim_id, po.evidence_claim_id),
        explanation="Unexplained amount difference; check VAT basis, delivery, fees, credits and amendments.",
    )
