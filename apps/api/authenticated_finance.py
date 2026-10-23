"""Authenticated finance read boundary; never a review or approval endpoint.

This composition connects existing signed-identity and joined PostgreSQL
membership checks to the finance candidate use case. It performs no writes,
vault reads, evidence verification, or decision authorization.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.api.access_control import CaseAccessService, CaseAction, AuthorizedCase
from domains.finance.candidate_policy import NetCandidate, assess_invoice_order_net
from domains.finance.reconciliation import DocumentAmount


@dataclass(frozen=True, slots=True)
class ScopedFinanceCandidate:
    case_id: str
    organization_id: str
    status: str
    delta: str | None
    currency: str | None
    unresolved: tuple[str, ...]
    evidence_verified: bool = False
    approved: bool = False


@dataclass(frozen=True, slots=True)
class AuthenticatedFinanceComparison:
    access: CaseAccessService

    def compare(
        self, *, bearer: str, case_id: str, invoice: DocumentAmount,
        invoice_order_reference: str | None, purchase_order: DocumentAmount | None,
        purchase_order_number: str | None,
    ) -> ScopedFinanceCandidate:
        """Read permission only; authenticated case ownership is authoritative.

        The input amounts and document IDs are unverified caller candidates.
        No evidence link or source bytes have been validated by this operation.
        """
        # Existing access service verifies signed bearer, current membership,
        # action grant and case ownership through the configured DB adapter.
        authorized: AuthorizedCase = self.access.authorize(
            bearer, case_id, CaseAction.READ_CASE
        )
        candidate: NetCandidate = assess_invoice_order_net(
            invoice, invoice_order_reference, purchase_order, purchase_order_number,
        )
        return ScopedFinanceCandidate(
            case_id=authorized.case_id,
            organization_id=authorized.org_id,
            status=candidate.status,
            delta=candidate.delta,
            currency=candidate.currency,
            unresolved=candidate.unresolved,
        )
