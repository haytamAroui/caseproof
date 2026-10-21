"""KRN-105: policy-versioned eligibility gate for evidence-grounded candidates.

A positive decision is only a prospective, immutable evaluation of one frozen
finding/link snapshot. It does not change lifecycle state, verify real-world
truth, authorize a person, resolve contradictions, or commit an audit event.

Stage 2 must provide the authenticated scope, trusted actor authorization,
atomic promotion+audit, and concurrency/idempotency protections.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from packages.evidence_kernel.domain.anchors import AnchorResolutionError
from packages.evidence_kernel.domain.fidelity import CitationResolution, ContentFidelity
from packages.evidence_kernel.domain.finding_links import (
    AssessorKind,
    FindingEvidenceLinkRevision,
    FindingLinkError,
    InMemoryFindingEvidenceLedger,
    SemanticRelation,
)
from packages.evidence_kernel.domain.source_versions import SourceRecordNotFound


class GroundingReason(StrEnum):
    ELIGIBLE = "eligible"
    STALE_STATEMENT = "stale_statement_snapshot"
    STALE_LINKS = "stale_link_snapshot"
    NO_LINKS = "no_assessed_links"
    INSUFFICIENT_LINKS = "insufficient_assessed_links"
    CITATION_UNAVAILABLE = "citation_unavailable"
    FIDELITY_NOT_MATCHED = "fidelity_not_matched"
    SEMANTIC_NOT_ASSESSED = "semantic_not_assessed"
    UNTRUSTED_ASSESSOR = "untrusted_assessor_kind"


def _required(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise FindingLinkError(f"{name} required")


def _positive(value: object, name: str) -> None:
    if type(value) is not int or value < 1:
        raise FindingLinkError(f"{name} must be positive integer")


@dataclass(frozen=True, slots=True)
class GroundingPolicy:
    """A stable versioned policy; does NOT confer actor permission or approval.

    A claimed HUMAN assessor kind is *not* proof of human identity. The
    trusted application boundary must verify it before using this decision.
    MODEL-only proposals never satisfy this reference gate.
    """

    version: str
    min_assessed_links: int = 1
    allowed_assessors: tuple[AssessorKind, ...] = (
        AssessorKind.HUMAN,
        AssessorKind.DETERMINISTIC,
    )

    def __post_init__(self) -> None:
        _required(self.version, "policy version")
        _positive(self.min_assessed_links, "min_assessed_links")
        if (
            not isinstance(self.allowed_assessors, tuple)
            or not self.allowed_assessors
            or len(set(self.allowed_assessors)) != len(self.allowed_assessors)
            or any(not isinstance(x, AssessorKind) for x in self.allowed_assessors)
            or AssessorKind.MODEL in self.allowed_assessors
        ):
            raise FindingLinkError("model or invalid assessor kind cannot authorize grounding")


@dataclass(frozen=True, slots=True)
class GroundingSnapshot:
    """Optimistic preconditions against the COMPLETE current finding/link set."""

    finding_id: str
    statement_revision: int
    statement_sha256_hex: str
    # Sorted by link ID; exactly one current assessment revision for every link.
    link_revisions: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        _required(self.finding_id, "finding_id")
        _positive(self.statement_revision, "statement_revision")
        if (
            not isinstance(self.statement_sha256_hex, str)
            or len(self.statement_sha256_hex) != 64
            or any(c not in "0123456789abcdef" for c in self.statement_sha256_hex)
        ):
            raise FindingLinkError("statement fingerprint must be lowercase SHA-256")
        if not isinstance(self.link_revisions, tuple):
            raise FindingLinkError("link revisions must be immutable tuple")
        previous = ""
        for pair in self.link_revisions:
            if not isinstance(pair, tuple) or len(pair) != 2:
                raise FindingLinkError("each link revision must be an ID/revision pair")
            link_id, revision = pair
            _required(link_id, "link_id")
            _positive(revision, "link revision")
            if link_id <= previous:
                raise FindingLinkError("link IDs must be sorted and unique")
            previous = link_id


@dataclass(frozen=True, slots=True)
class GroundingEvaluation:
    """Reviewable result, never a persisted lifecycle transition or approval."""

    snapshot: GroundingSnapshot
    policy_version: str
    eligible: bool
    reason_codes: tuple[GroundingReason, ...]
    assessed_link_ids: tuple[str, ...]
    historical_contradiction_ids: tuple[str, ...]
    current_contradiction_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.snapshot, GroundingSnapshot)
            or not isinstance(self.eligible, bool)
            or not isinstance(self.reason_codes, tuple)
            or not self.reason_codes
            or any(not isinstance(x, GroundingReason) for x in self.reason_codes)
        ):
            raise FindingLinkError("typed immutable grounding evaluation required")
        _required(self.policy_version, "policy_version")
        if self.eligible != (self.reason_codes == (GroundingReason.ELIGIBLE,)):
            raise FindingLinkError("grounding eligibility must agree with reason codes")


@dataclass(frozen=True, slots=True)
class GroundingGate:
    """Fail-closed, read-only Stage 1 snapshot gate.

    No user can obtain an authorized state change from this object. Inputs
    from an agent/client are not trustworthy authorization credentials.
    """

    ledger: InMemoryFindingEvidenceLedger

    def snapshot(self, tenant_scope: str, finding_id: str) -> GroundingSnapshot:
        statement = self.ledger.latest_statement(tenant_scope, finding_id)
        links = self.ledger.links_for_statement(
            tenant_scope, finding_id, statement.revision
        )
        return GroundingSnapshot(
            statement.finding_id, statement.revision,
            statement.statement_sha256_hex,
            tuple((x.link_id, x.assessment_revision) for x in links),
        )

    def evaluate(
        self, tenant_scope: str, expected: GroundingSnapshot, policy: GroundingPolicy
    ) -> GroundingEvaluation:
        if not isinstance(expected, GroundingSnapshot):
            raise FindingLinkError("typed grounding snapshot required")
        if not isinstance(policy, GroundingPolicy):
            raise FindingLinkError("versioned grounding policy required")
        current = self.snapshot(tenant_scope, expected.finding_id)
        if (
            current.statement_revision != expected.statement_revision
            or current.statement_sha256_hex != expected.statement_sha256_hex
        ):
            return self._decision(expected, policy, [GroundingReason.STALE_STATEMENT], ())
        if current.link_revisions != expected.link_revisions:
            return self._decision(expected, policy, [GroundingReason.STALE_LINKS], ())

        records = self.ledger.links_for_statement(
            tenant_scope, current.finding_id, current.statement_revision
        )
        if not records:
            return self._decision(expected, policy, [GroundingReason.NO_LINKS], ())

        problems: set[GroundingReason] = set()
        assessed_ids: list[str] = []
        history_conflicts: list[str] = []
        current_conflicts: list[str] = []

        for record in records:
            if any(
                rev.semantic.relation is SemanticRelation.CONTRADICTS
                for rev in self.ledger.link_history(tenant_scope, record.link_id)
            ):
                history_conflicts.append(record.link_id)
            if record.semantic.relation is SemanticRelation.CONTRADICTS:
                current_conflicts.append(record.link_id)

            if not self._still_resolves(tenant_scope, record):
                problems.add(GroundingReason.CITATION_UNAVAILABLE)
            if (
                record.fidelity.citation_resolution is not CitationResolution.RESOLVED
                or record.fidelity.content_fidelity is not ContentFidelity.MATCHED
            ):
                problems.add(GroundingReason.FIDELITY_NOT_MATCHED)
            if record.semantic.relation is SemanticRelation.NOT_ASSESSED:
                problems.add(GroundingReason.SEMANTIC_NOT_ASSESSED)
            if record.semantic.assessor_kind not in policy.allowed_assessors:
                problems.add(GroundingReason.UNTRUSTED_ASSESSOR)

            if (
                self._still_resolves(tenant_scope, record)
                and record.location_and_fidelity_eligible
                and record.semantic.relation is not SemanticRelation.NOT_ASSESSED
                and record.semantic.assessor_kind in policy.allowed_assessors
            ):
                assessed_ids.append(record.link_id)

        if len(assessed_ids) < policy.min_assessed_links:
            problems.add(GroundingReason.INSUFFICIENT_LINKS)
        return GroundingEvaluation(
            snapshot=expected,
            policy_version=policy.version,
            eligible=not problems,
            reason_codes=tuple(sorted(problems, key=str)) if problems else (GroundingReason.ELIGIBLE,),
            assessed_link_ids=tuple(assessed_ids),
            historical_contradiction_ids=tuple(history_conflicts),
            current_contradiction_ids=tuple(current_conflicts),
        )

    def _still_resolves(self, tenant_scope: str, record: FindingEvidenceLinkRevision) -> bool:
        """Recheck immutable locator against current tenant-visible source.

        This deliberately does NOT recompute quote fidelity because KRN-104
        preserves only the typed expected-content digest, not the raw quote.
        The earlier KRN-103 fidelity is anchored to immutable representation
        bytes and may only be used if that exact source remains resolvable.
        """
        try:
            source = self.ledger.evaluator.resolver.sources.get_source(
                tenant_scope, record.anchor.document_id, record.anchor.version_id
            )
            representation = self.ledger.evaluator.resolver.sources.get_representation_for_source(
                tenant_scope, record.anchor.document_id,
                record.anchor.version_id, record.anchor.representation_id,
            )
            if (
                source.sha256_hex != record.anchor.source_sha256_hex
                or representation.sha256_hex != record.anchor.representation_sha256_hex
                or representation.source_sha256_hex != record.anchor.source_sha256_hex
            ):
                return False
            self.ledger.evaluator.resolver.resolve(tenant_scope, record.anchor)
        except (SourceRecordNotFound, AnchorResolutionError):
            return False
        return True

    @staticmethod
    def _decision(
        snapshot: GroundingSnapshot,
        policy: GroundingPolicy,
        reasons: list[GroundingReason],
        assessed: tuple[str, ...],
    ) -> GroundingEvaluation:
        return GroundingEvaluation(
            snapshot, policy.version, False, tuple(reasons),
            assessed, (), (),
        )
