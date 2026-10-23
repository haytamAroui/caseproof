"""Finance-first application use case: deterministic candidates, never approvals.

The application coordinates trusted, already-parsed inputs with the finance
domain. Parsing, HTTP, database transactions and evidence verification remain
outside this pure use case. Callers must not treat a candidate as a finding
promotion, an approved conclusion, or a verified source.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from domains.finance.candidate_policy import NetCandidate, assess_invoice_order_net
from domains.finance.reconciliation import DocumentAmount


@dataclass(frozen=True, slots=True)
class FinanceComparisonInput:
    invoice: DocumentAmount
    invoice_order_reference: str | None
    purchase_order: DocumentAmount | None
    purchase_order_number: str | None


@dataclass(frozen=True, slots=True)
class FinanceComparisonResult:
    status: Literal["unresolved", "match_unreviewed", "candidate_requires_review"]
    delta: str | None
    currency: str | None
    unresolved: tuple[str, ...]
    requires_evidence_verification: bool = True
    requires_authorized_human_review: bool = True


def compare_finance_candidate(request: FinanceComparisonInput) -> FinanceComparisonResult:
    """Produce an unverified candidate without state changes or approvals."""
    if not isinstance(request, FinanceComparisonInput):
        raise TypeError("typed finance comparison input required")
    outcome: NetCandidate = assess_invoice_order_net(
        request.invoice,
        request.invoice_order_reference,
        request.purchase_order,
        request.purchase_order_number,
    )
    return FinanceComparisonResult(
        status=outcome.status,
        delta=outcome.delta,
        currency=outcome.currency,
        unresolved=outcome.unresolved,
    )
