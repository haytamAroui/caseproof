"""Minimal dependency-inverted contracts for a future durable decision transaction.

No approval is implemented here. A concrete adapter must enforce current identity,
action grants, optimistic concurrency, atomic audit, and idempotent receipts.
"""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TrustedActor:
    """Identity resolved by a verified server-side authentication boundary."""
    subject_id: str
    organization_id: str


@dataclass(frozen=True)
class DecisionRequest:
    case_id: str
    expected_snapshot_digest: str
    expected_revision: int
    idempotency_key: str


@dataclass(frozen=True)
class DecisionReceipt:
    case_id: str
    committed_revision: int
    snapshot_digest: str
    audit_event_id: str
    receipt_id: str


class AuthorizedDecisionPort(Protocol):
    """Single authoritative commit boundary; never implemented by an in-memory preflight."""

    def commit_approved_decision(
        self, *, actor: TrustedActor, request: DecisionRequest
    ) -> DecisionReceipt:
        """Atomically revalidate authority/snapshot and commit state+audit+receipt.

        Must fail closed on revoked authority, stale snapshot, conflicting
        idempotency key, missing evidence, or any failed audit write.
        """
        ...
