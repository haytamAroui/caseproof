"""Evidence-linked finance reconciliation without inferring missing accounting components.

All inputs are immutable, already-normalized, source-cited claims. This module
is NOT an ERP ledger, payment instruction, or financial approval. Differences,
missing VAT/basis and amendments always demand human review.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal, cast

from domains.finance.reconciliation import DocumentAmount, Money

COMPONENTS = ("vat", "freight", "discount", "credit")
RULE_VERSION = "finance-factual-comparison-v1"


@dataclass(frozen=True)
class DeliveryEvidence:
    ordered: Decimal
    received: Decimal
    citation_id: str

    def __post_init__(self) -> None:
        for value in (self.ordered, self.received):
            if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
                raise ValueError("nonnegative, finite Decimal quantities required")
        if self.ordered <= 0 or not self.citation_id.strip():
            raise ValueError("positive ordered units and citation required")


@dataclass(frozen=True)
class AmendmentEvidence:
    document_id: str
    supersedes_document_id: str
    effective_date: date | None
    citation_id: str

    def __post_init__(self) -> None:
        if (
            not self.document_id.strip()
            or not self.supersedes_document_id.strip()
            or self.document_id == self.supersedes_document_id
            or not self.citation_id.strip()
        ):
            raise ValueError("source-linked, non-self-referencing amendment required")
        if self.effective_date is not None and not isinstance(self.effective_date, date):
            raise ValueError("date must be an explicit ISO date")


@dataclass(frozen=True)
class AccountingEvidence:
    """Known numbers only. None means unassessed, never zero."""

    net: DocumentAmount
    vat: DocumentAmount | None = None
    freight: DocumentAmount | None = None
    discount: DocumentAmount | None = None
    credit: DocumentAmount | None = None
    gross: DocumentAmount | None = None
    amount_basis: Literal["line_net", "tax_exclusive_net"] = "line_net"
    amendment: AmendmentEvidence | None = None

    def __post_init__(self) -> None:
        if self.amount_basis not in {"line_net", "tax_exclusive_net"}:
            raise ValueError("unsupported comparison basis")
        for name in (*COMPONENTS, "gross"):
            value = getattr(self, name)
            if value is not None and value.amount.currency != self.net.amount.currency:
                raise ValueError("cross-currency components must be explicit separate claims")
        if self.amendment is not None and self.amendment.document_id != self.net.document_id:
            raise ValueError("amendment must belong to this source document")


@dataclass(frozen=True)
class AccountingDifference:
    code: str
    claim_ids: tuple[str, ...]
    delta: Money | None
    detail: str


@dataclass(frozen=True)
class AccountingAssessment:
    """match_unreviewed still means every consequential conclusion needs a human."""

    status: Literal["unresolved", "match_unreviewed", "candidate_requires_review"]
    rule_version: str
    differences: tuple[AccountingDifference, ...]
    unresolved: tuple[str, ...]
    evidence_claim_ids: tuple[str, ...]
    requires_authorized_human_review: bool = True
    approved: bool = False


def assess_accounting_evidence(
    invoice: AccountingEvidence,
    order: AccountingEvidence,
    *,
    delivery: DeliveryEvidence | None = None,
) -> AccountingAssessment:
    if not isinstance(invoice, AccountingEvidence) or not isinstance(order, AccountingEvidence):
        raise TypeError("typed accounting evidence required")
    sources = {invoice.net.evidence_claim_id, order.net.evidence_claim_id}
    differences: list[AccountingDifference] = []
    gaps: list[str] = []

    def note(code: str, ids: tuple[str, ...], delta: Money | None, detail: str) -> None:
        differences.append(AccountingDifference(code, ids, delta, detail))
        sources.update(ids)

    if invoice.net.amount.currency != order.net.amount.currency:
        gaps.append("currency_conversion_not_established")
    if invoice.amount_basis != order.amount_basis:
        gaps.append("invoice_order_amount_basis_incomparable")
    if invoice.amendment is not None or order.amendment is not None:
        gaps.append("amendment_validity_and_precedence_unverified")
        for doc in (invoice, order):
            if doc.amendment is not None:
                sources.add(doc.amendment.citation_id)
    if delivery is not None:
        sources.add(delivery.citation_id)
        if delivery.received > delivery.ordered:
            gaps.append("overdelivery_requires_verification")
        if invoice.amendment is not None or order.amendment is not None:
            gaps.append("partial_delivery_amendment_interaction_unresolved")
    else:
        gaps.append("delivery_and_quantity_basis_unassessed")

    comparable = (
        invoice.net.amount.currency == order.net.amount.currency
        and invoice.amount_basis == order.amount_basis
        and not any(s.startswith("amendment_") for s in gaps)
    )
    if comparable:
        reference = order.net.amount.amount
        if delivery is not None and delivery.received <= delivery.ordered:
            reference = reference * delivery.received / delivery.ordered
            if delivery.received < delivery.ordered:
                gaps.append("partial_delivery_billing_terms_unverified")
        net_delta = invoice.net.amount.amount - reference
        if net_delta:
            note(
                "NET_INVOICE_ORDER_DIFFERENCE",
                (invoice.net.evidence_claim_id, order.net.evidence_claim_id),
                Money(net_delta, invoice.net.amount.currency),
                "Compared only like-for-like declared net line amounts; rights/basis unassessed",
            )
    for component in COMPONENTS:
        a, b = getattr(invoice, component), getattr(order, component)
        if a is None or b is None:
            gaps.append(f"{component}_component_incomplete")
            continue
        sources.update((a.evidence_claim_id, b.evidence_claim_id))
        if a.amount.currency != b.amount.currency:
            gaps.append(f"{component}_currency_incomparable")
        elif a.amount.amount != b.amount.amount:
            note(
                f"{component.upper()}_DIFFERENCE",
                (a.evidence_claim_id, b.evidence_claim_id),
                Money(a.amount.amount - b.amount.amount, a.amount.currency),
                "Component difference; tax/commercial applicability not assumed",
            )
    for label, doc in (("invoice", invoice), ("order", order)):
        if doc.gross is None:
            gaps.append(f"{label}_gross_unassessed")
            continue
        sources.add(doc.gross.evidence_claim_id)
        if any(getattr(doc, component) is None for component in COMPONENTS):
            gaps.append(f"{label}_gross_components_incomplete")
            continue
        assert all(getattr(doc, component) is not None for component in COMPONENTS)
        components = {
            part: cast(DocumentAmount, getattr(doc, part))
            for part in COMPONENTS
        }
        expected = (
            doc.net.amount.amount
            + components["vat"].amount.amount
            + components["freight"].amount.amount
            - components["discount"].amount.amount
            - components["credit"].amount.amount
        )
        delta = doc.gross.amount.amount - expected
        if delta:
            note(
                f"{label.upper()}_GROSS_COMPONENT_MISMATCH",
                (doc.net.evidence_claim_id, *(components[part].evidence_claim_id for part in COMPONENTS), doc.gross.evidence_claim_id),
                Money(delta, doc.net.amount.currency),
                "Original gross does not reconcile to explicitly evidenced components",
            )
    status: Literal["unresolved", "match_unreviewed", "candidate_requires_review"] = (
        "candidate_requires_review" if differences
        else "unresolved" if gaps
        else "match_unreviewed"
    )
    return AccountingAssessment(
        status, RULE_VERSION, tuple(differences), tuple(sorted(set(gaps))),
        tuple(sorted(sources)),
    )
