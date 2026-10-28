"""ClearBrief development reviewer composition, using the existing signed M2 ledger.

This is NOT a new persistence layer. The caller must inject a checker that
publishes a trusted immutable VerificationRun into a ledger backed by the
reviewed PostgreSQL schema. No approval, publication, filing or source editing.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol
from uuid import UUID

from application.litigation.review_cycle import ReviewPacket
from application.litigation.unified_review import (
    ObservationReview,
    ReviewDisposition,
    VerificationRun,
)
from apps.api.access_control import AccessFailure, AccessRejected, VerifiedSubject
from apps.api.litigation_check_service import (
    AuthorizedLitigationChecker,
    CheckedRunPublisher,
    PrivateMatterAccess,
)


class ReviewState(Protocol):
    revision: int
    packet: ReviewPacket


class ReviewLedger(CheckedRunPublisher, Protocol):
    def state(
        self, *, org_id: UUID, actor_id: UUID, run: VerificationRun,
    ) -> ReviewState: ...

    def record(
        self, *, org_id: UUID, actor_id: UUID, run: VerificationRun,
        request_id: UUID, expected_revision: int, decision: ObservationReview,
    ) -> tuple[ReviewState, bool]: ...

@dataclass(frozen=True, slots=True)
class ReviewCommand:
    snapshot_hash: str
    observation_id: str
    request_id: UUID
    expected_revision: int
    disposition: ReviewDisposition
    rationale: str


class SignedReviewWorkspace:
    """Bind real signed identity to checked version, then to persistent review."""

    def __init__(self, checker: AuthorizedLitigationChecker, ledger: ReviewLedger) -> None:
        if checker.publisher is not ledger:
            raise ValueError("The checker must publish to the same exact review ledger")
        self.checker = checker
        self.ledger = ledger

    def _context(
        self, bearer: str, case_id: str, brief_version_id: str,
    ) -> tuple[VerifiedSubject, PrivateMatterAccess, VerificationRun]:
        subject = self.checker._verified(bearer)
        scope = self.checker._scope(subject, case_id)
        run = self.checker.check(
            bearer=bearer, case_id=case_id, brief_version_id=brief_version_id,
        )
        if run.case_id != case_id or run.brief_version_id != brief_version_id:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        return subject, scope, run

    def state(self, *, bearer: str, case_id: str, brief_version_id: str) -> dict[str, Any]:
        subject, scope, run = self._context(bearer, case_id, brief_version_id)
        try:
            state = self.ledger.state(
                org_id=UUID(scope.org_id), actor_id=UUID(subject.subject_id), run=run,
            )
            return {
                "schema": "caseproof-clearbrief-review-v1",
                "case_id": case_id,
                "brief_version_id": brief_version_id,
                "snapshot_hash": run.snapshot_hash,
                "revision": state.revision,
                "decisions": [asdict(x) for x in state.packet.decisions],
                "release_authorized": False,
            }
        except Exception:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None

    def record(
        self, *, bearer: str, case_id: str, brief_version_id: str, command: ReviewCommand,
    ) -> dict[str, Any]:
        subject, scope, run = self._context(bearer, case_id, brief_version_id)
        if command.snapshot_hash != run.snapshot_hash:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        decision = ObservationReview(
            command.observation_id, subject.subject_id,
            command.disposition, command.rationale,
        )
        try:
            state, replayed = self.ledger.record(
                org_id=UUID(scope.org_id), actor_id=UUID(subject.subject_id),
                run=run, request_id=command.request_id,
                expected_revision=command.expected_revision, decision=decision,
            )
            return {
                "schema": "caseproof-clearbrief-review-receipt-v1",
                "snapshot_hash": run.snapshot_hash,
                "revision": state.revision,
                "replayed": replayed,
                "release_authorized": False,
            }
        except Exception:
            # Never turn a lost acknowledgement into an unverified success.
            # Client retries the identical request_id and body.
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
