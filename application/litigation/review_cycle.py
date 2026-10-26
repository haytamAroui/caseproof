"""M2 pure human review and reversible correction proposals.

No authorizes, DB commit, real Word write, legal approval or filing. Signed
actor authorization and atomic persistent review events are M1-B/M2 integration
gates. These values are immutable transaction proposals for trusted callers.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from application.litigation.unified_review import (
    ObservationReview,
    ReviewDisposition,
    VerificationError,
    VerificationRun,
)


@dataclass(frozen=True, slots=True)
class ReviewPacket:
    run_snapshot_hash: str
    revision: int
    decisions: tuple[ObservationReview, ...] = ()

    def __post_init__(self) -> None:
        if (len(self.run_snapshot_hash) != 64 or type(self.revision) is not int
                or self.revision < 0 or len(self.decisions) > 256):
            raise VerificationError("invalid versioned review packet")
        if len({d.observation_id for d in self.decisions}) != len(self.decisions):
            raise VerificationError("multiple dispositions for one observation")


def revise_review(
    *, run: VerificationRun, packet: ReviewPacket,
    expected_revision: int, decision: ObservationReview,
) -> ReviewPacket:
    """Pure compare-and-swap proposal. Persist with current permission + audit in one transaction."""
    if (not isinstance(run, VerificationRun) or packet.run_snapshot_hash != run.snapshot_hash
            or type(expected_revision) is not int or packet.revision != expected_revision
            or not isinstance(decision, ObservationReview)):
        raise VerificationError("stale review, untrusted decision or source revision")
    valid = {f"citation:{x.reference_id}" for x in run.citation_observations}
    valid |= {f"fact:{x.claim_id}" for x in run.factual_observations}
    if decision.observation_id not in valid:
        raise VerificationError("decision refers to an unknown observation")
    updated = tuple(d for d in packet.decisions if d.observation_id != decision.observation_id)
    return ReviewPacket(run.snapshot_hash, packet.revision + 1, updated + (decision,))


@dataclass(frozen=True, slots=True)
class CorrectionProposal:
    observation_id: str
    actor_id: str
    expected_run_hash: str
    expected_brief_version: str
    expected_text_sha256: str
    start: int
    end: int
    before: str
    after: str
    rationale: str

    def __post_init__(self) -> None:
        if (not self.observation_id or not self.actor_id or not self.expected_brief_version
                or len(self.expected_run_hash) != 64 or len(self.expected_text_sha256) != 64
                or type(self.start) is not int or type(self.end) is not int
                or not 0 <= self.start < self.end or not self.before or not self.after
                or len(self.after) > 4000 or self.before == self.after
                or not 0 < len(self.rationale.strip()) <= 2000):
            raise VerificationError("invalid bounded correction proposal")


@dataclass(frozen=True, slots=True)
class CorrectionPreview:
    old_text_sha256: str
    proposed_text_sha256: str
    proposed_text: str
    invalidates_check_hash: str
    changed_observation_id: str
    requires_new_brief_version: bool = True
    # Persisting document, checked range, undo journal and new version is an
    # application transaction; these pure results are not acknowledgements.


def preview_correction(
    *, run: VerificationRun, text: str, proposal: CorrectionProposal,
) -> CorrectionPreview:
    if (not isinstance(run, VerificationRun) or not isinstance(proposal, CorrectionProposal)
            or proposal.expected_run_hash != run.snapshot_hash
            or proposal.expected_brief_version != run.brief_version_id
            or proposal.expected_text_sha256 != run.representation_sha256
            or type(text) is not str or sha256(text.encode()).hexdigest() != run.representation_sha256):
        raise VerificationError("stale correction or unverified current document")
    valid = {f"citation:{x.reference_id}" for x in run.citation_observations}
    valid |= {f"fact:{x.claim_id}" for x in run.factual_observations}
    if (proposal.observation_id not in valid or proposal.end > len(text)
            or text[proposal.start:proposal.end] != proposal.before):
        raise VerificationError("changed range or unknown observation")
    proposed = text[:proposal.start] + proposal.after + text[proposal.end:]
    if len(proposed) > 120_000:
        raise VerificationError("corrected representation exceeds budget")
    return CorrectionPreview(
        run.representation_sha256, sha256(proposed.encode()).hexdigest(), proposed,
        run.snapshot_hash, proposal.observation_id,
    )


def revert_correction(
    *, preview: CorrectionPreview, current_text: str,
    proposal: CorrectionProposal,
) -> str:
    """Undo a still-current exact proposed representation, never a mutable Word range."""
    if (not isinstance(preview, CorrectionPreview) or not isinstance(proposal, CorrectionProposal)
            or not isinstance(current_text, str)
            or sha256(current_text.encode()).hexdigest() != preview.proposed_text_sha256
            or current_text[proposal.start:proposal.start + len(proposal.after)] != proposal.after):
        raise VerificationError("stale undo requires refreshed review")
    old = (
        current_text[:proposal.start] + proposal.before
        + current_text[proposal.start + len(proposal.after):]
    )
    if sha256(old.encode()).hexdigest() != preview.old_text_sha256:
        raise VerificationError("undo would not restore exact source")
    return old


def ready_for_release(run: VerificationRun, packet: ReviewPacket) -> bool:
    """Always false: release authority is M4, NOT authenticated M2 review."""
    if run.snapshot_hash != packet.run_snapshot_hash:
        raise VerificationError("stale review")
    return False


def decision_summary(packet: ReviewPacket) -> dict[str, int]:
    return {
        status.value: sum(d.disposition is status for d in packet.decisions)
        for status in ReviewDisposition
    }
