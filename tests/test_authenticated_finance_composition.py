"""Authentication and current case membership precede finance candidate computation."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from apps.api.access_control import (
    AccessFailure, AccessRejected, CaseAccessService, CaseAction,
    StoredCase, StoredMembership, VerifiedSubject,
)
from apps.api.authenticated_finance import AuthenticatedFinanceComparison
from domains.finance.reconciliation import DocumentAmount, Money

NOW = datetime(2026, 10, 23, 9, tzinfo=UTC)


class Verifier:
    def verify_bearer(self, token: str) -> VerifiedSubject:
        if token != "valid":
            from apps.api.access_control import InvalidBearer
            raise InvalidBearer("invalid")
        return VerifiedSubject(
            "subject", "issuer", "authenticated", NOW,
            NOW + timedelta(hours=1), False,
        )


class Repository:
    def __init__(self, actions: frozenset[CaseAction]) -> None:
        self.actions = actions
        self.calls = 0

    def lookup_case_membership(self, subject_id: str, case_id: str):
        self.calls += 1
        if case_id != "case-1":
            return None
        return (
            StoredCase("case-1", "org-1", 1, "creator"),
            StoredMembership("subject", "org-1", True, self.actions),
        )


def service(actions: frozenset[CaseAction]):
    repository = Repository(actions)
    access = CaseAccessService(Verifier(), repository, "issuer", "authenticated", lambda: NOW)
    return AuthenticatedFinanceComparison(access), repository


def document(name: str, value: str) -> DocumentAmount:
    return DocumentAmount(name, Money(Decimal(value), "EUR"), name + "-draft")


def run(comparison: AuthenticatedFinanceComparison, *, bearer: str = "valid", case_id: str = "case-1"):
    return comparison.compare(
        bearer=bearer, case_id=case_id, invoice=document("invoice", "120.00"),
        invoice_order_reference="PO-1", purchase_order=document("po", "100.00"),
        purchase_order_number="PO-1",
    )


def test_authenticated_case_reader_returns_unverified_candidate() -> None:
    comparison, repository = service(frozenset({CaseAction.READ_CASE}))
    result = run(comparison)
    assert result.case_id == "case-1" and result.organization_id == "org-1"
    assert result.status == "candidate_requires_review" and result.delta == "20.00"
    assert result.evidence_verified is False and result.approved is False
    assert repository.calls == 1


def test_missing_or_invalid_bearer_does_not_read_case() -> None:
    comparison, repository = service(frozenset({CaseAction.READ_CASE}))
    for token in ("", "invalid"):
        with pytest.raises(AccessRejected) as exc:
            run(comparison, bearer=token)
        assert exc.value.code is AccessFailure.AUTHENTICATION_REQUIRED
    assert repository.calls == 0


def test_missing_permission_and_foreign_case_fail_closed() -> None:
    comparison, _ = service(frozenset())
    with pytest.raises(AccessRejected) as denied:
        run(comparison)
    assert denied.value.code is AccessFailure.PERMISSION_DENIED
    comparison, _ = service(frozenset({CaseAction.READ_CASE}))
    with pytest.raises(AccessRejected) as missing:
        run(comparison, case_id="foreign")
    assert missing.value.code is AccessFailure.RESOURCE_MASKED
