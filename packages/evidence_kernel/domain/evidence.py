"""Immutable source-backed claims. Source verification is not factual truth."""
from dataclasses import dataclass
from enum import Enum


class SourceStatus(str, Enum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    INVALID = "invalid"


class CorroborationStatus(str, Enum):
    NOT_ASSESSED = "not_assessed"
    CORROBORATED = "corroborated"
    CONTRADICTED = "contradicted"
    INSUFFICIENT = "insufficient"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class SourceReference:
    document_id: str
    document_sha256: str
    quote: str
    page: int | None = None

    def __post_init__(self) -> None:
        if not self.document_id.strip() or not self.quote.strip():
            raise ValueError("document ID and source quote are required")
        if len(self.document_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.document_sha256):
            raise ValueError("document_sha256 must be a lowercase SHA-256 hex digest")
        if self.page is not None and self.page < 1:
            raise ValueError("page must be >= 1")


@dataclass(frozen=True, slots=True)
class ExtractedClaim:
    claim_id: str
    statement: str
    source: SourceReference
    source_status: SourceStatus = SourceStatus.UNVERIFIED
    corroboration: CorroborationStatus = CorroborationStatus.NOT_ASSESSED

    def __post_init__(self) -> None:
        if not self.claim_id.strip() or not self.statement.strip():
            raise ValueError("claim ID and statement are required")


@dataclass(frozen=True, slots=True)
class ReviewDecision:
    claim_id: str
    reviewer_id: str
    disposition: ReviewStatus
    rationale: str

    def __post_init__(self) -> None:
        if self.disposition is ReviewStatus.PENDING:
            raise ValueError("persisted decisions cannot be pending")
        if not all(v.strip() for v in (self.claim_id, self.reviewer_id, self.rationale)):
            raise ValueError("claim, reviewer and rationale are required")
