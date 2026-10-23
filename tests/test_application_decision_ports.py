"""Application boundary is a contract, not a mock approval implementation."""
import dataclasses
from dataclasses import FrozenInstanceError

import pytest

from application.decision_ports import (
    AuthorizedDecisionPort,
    DecisionReceipt,
    DecisionRequest,
    TrustedActor,
)


def test_identity_and_request_are_immutable() -> None:
    actor = TrustedActor(subject_id="verified-subject", organization_id="org-1")
    request = DecisionRequest(
        case_id="case-1",
        expected_snapshot_digest="digest",
        expected_revision=2,
        idempotency_key="key-1",
    )
    with pytest.raises(FrozenInstanceError):
        actor.organization_id = "org-2"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        request.expected_revision = 3  # type: ignore[misc]


def test_commit_contract_requires_authoritative_inputs() -> None:
    fields = {field.name for field in dataclasses.fields(DecisionRequest)}
    assert fields == {
        "case_id", "expected_snapshot_digest", "expected_revision", "idempotency_key"
    }
    assert "actor" in AuthorizedDecisionPort.commit_approved_decision.__annotations__
    assert {field.name for field in dataclasses.fields(DecisionReceipt)} == {
        "case_id", "committed_revision", "snapshot_digest", "audit_event_id", "receipt_id"
    }
