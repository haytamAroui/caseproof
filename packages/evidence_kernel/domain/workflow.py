"""Pure Python evidence workflow. Source checks never establish factual truth."""
from dataclasses import dataclass, field
from hashlib import sha256
from threading import RLock

from packages.evidence_kernel.domain.evidence import (
    CorroborationStatus,
    ExtractedClaim,
    ReviewDecision,
    SourceStatus,
)


class EvidenceWorkflowError(ValueError):
    pass


class SourceNotFound(EvidenceWorkflowError):
    pass


class ClaimNotFound(EvidenceWorkflowError):
    pass


class EvidenceConflict(EvidenceWorkflowError):
    pass


@dataclass(frozen=True, slots=True)
class DocumentVersion:
    document_id: str
    version_id: str
    sha256_hex: str
    text: str

    def __post_init__(self) -> None:
        if not self.document_id.strip() or not self.version_id.strip():
            raise EvidenceWorkflowError("document and version IDs required")
        if sha256(self.text.encode("utf-8")).hexdigest() != self.sha256_hex:
            raise EvidenceWorkflowError("source digest mismatch")


@dataclass(frozen=True, slots=True)
class SourceCheck:
    claim_id: str
    version_id: str
    status: SourceStatus
    explanation: str


@dataclass(frozen=True, slots=True)
class CorroborationAssessment:
    claim_id: str
    status: CorroborationStatus
    rationale: str


@dataclass
class EvidenceWorkflow:
    """In-memory, tenant-scoped reference implementation; not durable or authenticated."""

    _documents: dict[tuple[str, str, str], DocumentVersion] = field(default_factory=dict)
    _claims: dict[tuple[str, str], tuple[ExtractedClaim, str]] = field(default_factory=dict)
    _checks: dict[tuple[str, str], tuple[SourceCheck, ...]] = field(default_factory=dict)
    _assessments: dict[tuple[str, str], tuple[CorroborationAssessment, ...]] = field(default_factory=dict)
    _reviews: dict[tuple[str, str], tuple[ReviewDecision, ...]] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    @staticmethod
    def _scope(scope: str) -> str:
        if not scope.strip():
            raise EvidenceWorkflowError("trusted scope required")
        return scope

    def register_source(self, scope: str, source: DocumentVersion) -> DocumentVersion:
        key = (self._scope(scope), source.document_id, source.version_id)
        with self._lock:
            if key in self._documents:
                raise EvidenceConflict("source version exists")
            self._documents[key] = source
        return source

    def add_claim(self, scope: str, claim: ExtractedClaim, version_id: str) -> ExtractedClaim:
        scope = self._scope(scope)
        if not version_id.strip():
            raise EvidenceWorkflowError("version required")
        with self._lock:
            source = self._documents.get((scope, claim.source.document_id, version_id))
            if source is None:
                raise SourceNotFound("source version missing")
            if source.sha256_hex != claim.source.document_sha256:
                raise EvidenceWorkflowError("claim source hash mismatch")
            key = (scope, claim.claim_id)
            if key in self._claims:
                raise EvidenceConflict("claim exists")
            self._claims[key] = (claim, version_id)
        return claim

    def get_claim(self, scope: str, claim_id: str) -> ExtractedClaim:
        with self._lock:
            try:
                return self._claims[(self._scope(scope), claim_id)][0]
            except KeyError as exc:
                raise ClaimNotFound("claim missing") from exc

    def verify_quote(self, scope: str, claim_id: str) -> SourceCheck:
        scope = self._scope(scope)
        with self._lock:
            claim, version_id = self._claims.get((scope, claim_id), (None, None))
            if claim is None:
                raise ClaimNotFound("claim missing")
            source = self._documents[(scope, claim.source.document_id, version_id)]
            present = claim.source.quote in source.text
            result = SourceCheck(
                claim_id, version_id,
                SourceStatus.VERIFIED if present else SourceStatus.INVALID,
                "exact quotation present" if present else "exact quotation absent",
            )
            key = (scope, claim_id)
            self._checks[key] = (*self._checks.get(key, ()), result)
            return result

    def assess(self, scope: str, assessment: CorroborationAssessment) -> CorroborationAssessment:
        if assessment.status is CorroborationStatus.NOT_ASSESSED or not assessment.rationale.strip():
            raise EvidenceWorkflowError("substantive assessment required")
        with self._lock:
            self.get_claim(scope, assessment.claim_id)
            key = (scope, assessment.claim_id)
            self._assessments[key] = (*self._assessments.get(key, ()), assessment)
        return assessment

    def review(self, scope: str, decision: ReviewDecision) -> ReviewDecision:
        with self._lock:
            self.get_claim(scope, decision.claim_id)
            key = (scope, decision.claim_id)
            self._reviews[key] = (*self._reviews.get(key, ()), decision)
        return decision

    def history(self, scope: str, claim_id: str) -> dict[str, object]:
        scope = self._scope(scope)
        with self._lock:
            claim = self.get_claim(scope, claim_id)
            key = (scope, claim_id)
            return {
                "claim": claim,
                "checks": self._checks.get(key, ()),
                "assessments": self._assessments.get(key, ()),
                "reviews": self._reviews.get(key, ()),
            }
