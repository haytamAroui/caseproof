"""KRN-104: immutable, revision-bound finding-to-evidence assessment links.

A semantic relation is an assessor's recorded *proposal*, not verified truth,
legal authority, approval, or policy-level sufficiency. This reference ledger
is in-memory only; trusted tenant/actor authorization and durable audit are
application/infrastructure responsibilities. Nothing here promotes a finding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from threading import RLock

from packages.evidence_kernel.domain.anchors import EvidenceAnchor
from packages.evidence_kernel.domain.fidelity import (
    CitationResolution,
    ContentFidelity,
    ExactJsonScalar,
    ExactQuote,
    Expectation,
    FidelityAssessment,
    FidelityEvaluator,
    FindingRevision,
)

LINK_METHOD_VERSION = "krn104-link-v1"


class FindingLinkError(ValueError):
    """Malformed finding/link revision or violated link invariant."""


class FindingLinkConflict(FindingLinkError):
    """Immutable finding/link identity cannot be rewritten or moved."""


class FindingLinkNotFound(KeyError):
    """No accessible finding/link in the trusted tenant namespace."""


class SemanticRelation(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    QUALIFIES = "qualifies"
    INCONCLUSIVE = "inconclusive"
    NOT_ASSESSED = "not_assessed"


class LinkSufficiency(StrEnum):
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"
    NOT_ASSESSED = "not_assessed"


class AssessorKind(StrEnum):
    HUMAN = "human"
    MODEL = "model"
    DETERMINISTIC = "deterministic"


def _required(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise FindingLinkError(f"{label} required")


def _revision(value: object, label: str) -> None:
    if type(value) is not int or value < 1:
        raise FindingLinkError(f"{label} must be a positive integer")


@dataclass(frozen=True, slots=True)
class FindingStatement:
    """Exact immutable statement version, allowing unanchored candidates."""

    finding_id: str
    revision: int
    text: str = field(repr=False)
    statement_sha256_hex: str = field(init=False)

    def __post_init__(self) -> None:
        _required(self.finding_id, "finding_id")
        _revision(self.revision, "statement revision")
        _required(self.text, "finding statement")
        object.__setattr__(self, "statement_sha256_hex", sha256(self.text.encode("utf-8")).hexdigest())

    @property
    def reference(self) -> FindingRevision:
        return FindingRevision(self.finding_id, str(self.revision))


@dataclass(frozen=True, slots=True)
class SemanticAssessmentProposal:
    """Untrusted semantic/sufficiency proposal with attributable provenance.

    The assessor_reference is informational. A caller saying 'human' is NOT
    proof of authentication, reviewer permissions, or actual human approval.
    """

    relation: SemanticRelation
    sufficiency: LinkSufficiency
    assessor_kind: AssessorKind
    assessor_reference: str
    assessment_method_version: str
    rationale: str = field(repr=False)
    assessed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.relation, SemanticRelation):
            raise FindingLinkError("typed semantic relation required")
        if not isinstance(self.sufficiency, LinkSufficiency):
            raise FindingLinkError("typed link sufficiency required")
        if not isinstance(self.assessor_kind, AssessorKind):
            raise FindingLinkError("typed assessor kind required")
        _required(self.assessor_reference, "assessor_reference")
        _required(self.assessment_method_version, "assessment_method_version")
        _required(self.rationale, "assessment rationale")
        if (
            not isinstance(self.assessed_at, datetime)
            or self.assessed_at.tzinfo is None
            or self.assessed_at.utcoffset() != timedelta(0)
        ):
            raise FindingLinkError("assessed_at must be timezone-aware UTC")


@dataclass(frozen=True, slots=True)
class FindingEvidenceLinkRevision:
    """Append-only assessment. A revision never changes its statement/anchor."""

    link_id: str
    assessment_revision: int
    statement: FindingStatement
    fidelity: FidelityAssessment
    semantic: SemanticAssessmentProposal
    expected_content_sha256_hex: str
    link_method_version: str = LINK_METHOD_VERSION

    def __post_init__(self) -> None:
        _required(self.link_id, "link_id")
        _revision(self.assessment_revision, "assessment revision")
        if not isinstance(self.statement, FindingStatement):
            raise FindingLinkError("registered finding statement required")
        if not isinstance(self.fidelity, FidelityAssessment):
            raise FindingLinkError("fidelity assessment required")
        if not isinstance(self.semantic, SemanticAssessmentProposal):
            raise FindingLinkError("semantic assessment proposal required")
        if self.fidelity.finding != self.statement.reference:
            raise FindingLinkError("fidelity references a different finding revision")
        if (
            not isinstance(self.expected_content_sha256_hex, str)
            or len(self.expected_content_sha256_hex) != 64
            or any(c not in "0123456789abcdef" for c in self.expected_content_sha256_hex)
        ):
            raise FindingLinkError("expected content fingerprint must be SHA-256")
        if self.link_method_version != LINK_METHOD_VERSION:
            raise FindingLinkError("unsupported link method version")

    @property
    def anchor(self) -> EvidenceAnchor:
        return self.fidelity.anchor

    @property
    def location_and_fidelity_eligible(self) -> bool:
        """Only prerequisite checks, NEVER permission to promote/approve."""
        return (
            self.fidelity.citation_resolution is CitationResolution.RESOLVED
            and self.fidelity.content_fidelity is ContentFidelity.MATCHED
        )


def _expected_digest(expected: Expectation) -> str:
    """Hash exact typed expectation; don't expose the quote in link history."""
    if isinstance(expected, ExactQuote):
        raw = b"quote-v1\x00" + expected.text.encode("utf-8")
    elif isinstance(expected, ExactJsonScalar):
        scalar = expected.value
        if scalar is None:
            raw = b"json-null-v1\x00"
        elif type(scalar) is bool:
            raw = b"json-bool-v1\x00" + (b"true" if scalar else b"false")
        elif type(scalar) is int:
            raw = b"json-int-v1\x00" + str(scalar).encode("ascii")
        elif isinstance(scalar, str):
            raw = b"json-string-v1\x00" + scalar.encode("utf-8")
        else:
            raise FindingLinkError("unsupported JSON scalar type")
    else:
        raise FindingLinkError("expected exact quote or typed JSON scalar required")
    return sha256(raw).hexdigest()


@dataclass
class InMemoryFindingEvidenceLedger:
    """Scoped reference store, not tenant authentication or a durable audit.

    All writes recompute fidelity through the supplied deterministic evaluator,
    rather than trusting caller-authored fidelity statuses. Stored semantic
    assessments remain proposals until later independent review/policy gates.
    """

    evaluator: FidelityEvaluator
    _statements: dict[tuple[str, str, int], FindingStatement] = field(default_factory=dict)
    _latest: dict[tuple[str, str], int] = field(default_factory=dict)
    _links: dict[tuple[str, str], tuple[FindingEvidenceLinkRevision, ...]] = field(
        default_factory=dict
    )
    _lock: RLock = field(default_factory=RLock)

    @staticmethod
    def _scope(tenant_scope: str) -> str:
        _required(tenant_scope, "trusted tenant scope")
        return tenant_scope

    def register_statement(
        self, tenant_scope: str, statement: FindingStatement
    ) -> FindingStatement:
        tenant = self._scope(tenant_scope)
        with self._lock:
            key = (tenant, statement.finding_id)
            if statement.revision != self._latest.get(key, 0) + 1:
                raise FindingLinkConflict("finding revision must advance exactly once")
            self._statements[(tenant, statement.finding_id, statement.revision)] = statement
            self._latest[key] = statement.revision
        return statement

    def get_statement(
        self, tenant_scope: str, finding_id: str, revision: int
    ) -> FindingStatement:
        tenant = self._scope(tenant_scope)
        with self._lock:
            result = self._statements.get((tenant, finding_id, revision))
            if result is None:
                raise FindingLinkNotFound("finding version unavailable")
            return result

    def latest_statement(self, tenant_scope: str, finding_id: str) -> FindingStatement:
        """Return registered current revision without trusting a caller's selector."""
        tenant = self._scope(tenant_scope)
        with self._lock:
            revision = self._latest.get((tenant, finding_id))
            if revision is None:
                raise FindingLinkNotFound("finding unavailable")
            return self._statements[(tenant, finding_id, revision)]

    def append_assessment(
        self,
        tenant_scope: str,
        link_id: str,
        assessment_revision: int,
        statement: FindingStatement,
        anchor: EvidenceAnchor,
        expected: Expectation,
        proposed_semantic: SemanticAssessmentProposal,
    ) -> FindingEvidenceLinkRevision:
        tenant = self._scope(tenant_scope)
        _required(link_id, "link_id")
        _revision(assessment_revision, "assessment revision")
        if not isinstance(statement, FindingStatement):
            raise FindingLinkError("finding statement required")
        if not isinstance(anchor, EvidenceAnchor):
            raise FindingLinkError("typed evidence anchor required")
        if not isinstance(proposed_semantic, SemanticAssessmentProposal):
            raise FindingLinkError("semantic assessment proposal required")
        expected_digest = _expected_digest(expected)
        with self._lock:
            current = self._statements.get(
                (tenant, statement.finding_id, statement.revision)
            )
            if current is None:
                raise FindingLinkNotFound("finding version unavailable")
            if current != statement:
                raise FindingLinkConflict("finding statement hash/revision mismatch")
            if self._latest[(tenant, statement.finding_id)] != statement.revision:
                raise FindingLinkConflict("cannot attach new assessment to superseded statement")
            history = self._links.get((tenant, link_id), ())
            if assessment_revision != len(history) + 1:
                raise FindingLinkConflict("link assessment revisions must be consecutive")
            if history:
                first = history[0]
                if first.statement != statement or first.anchor != anchor:
                    raise FindingLinkConflict(
                        "cannot move a link to another statement or source anchor"
                    )
            computed = self.evaluator.evaluate(tenant, statement.reference, anchor, expected)
            result = FindingEvidenceLinkRevision(
                link_id=link_id,
                assessment_revision=assessment_revision,
                statement=current,
                fidelity=computed,
                semantic=proposed_semantic,
                expected_content_sha256_hex=expected_digest,
            )
            self._links[(tenant, link_id)] = (*history, result)
            return result

    def link_history(
        self, tenant_scope: str, link_id: str
    ) -> tuple[FindingEvidenceLinkRevision, ...]:
        tenant = self._scope(tenant_scope)
        with self._lock:
            history = self._links.get((tenant, link_id))
            if history is None:
                raise FindingLinkNotFound("link unavailable")
            return history

    def links_for_statement(
        self, tenant_scope: str, finding_id: str, revision: int
    ) -> tuple[FindingEvidenceLinkRevision, ...]:
        """Return latest assessment per link, preserving each link's full history."""
        tenant = self._scope(tenant_scope)
        with self._lock:
            if (tenant, finding_id, revision) not in self._statements:
                raise FindingLinkNotFound("finding version unavailable")
            latest = [
                history[-1]
                for (key_tenant, _), history in self._links.items()
                if key_tenant == tenant
                and history[-1].statement.finding_id == finding_id
                and history[-1].statement.revision == revision
            ]
            return tuple(sorted(latest, key=lambda record: record.link_id))
