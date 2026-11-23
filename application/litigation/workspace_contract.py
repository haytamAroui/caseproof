"""Bounded read-only workspace projection; no capabilities inferred from membership."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MatterView(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    case_id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    case_revision: int = Field(ge=1)
    # Descriptive database state, never interpreted as an action permission.
    state: str = Field(min_length=1, max_length=64)


class MatterCatalogView(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)
    schema_version: Literal["caseproof-workspace-matters-v1"] = Field(alias="schema")
    matters: list[MatterView] = Field(max_length=100)

    @model_validator(mode="after")
    def unique_matters(self) -> "MatterCatalogView":
        if any(matter.case_id == "00000000-0000-0000-0000-000000000000" for matter in self.matters):
            raise ValueError("Nil matter identity")
        if len({matter.case_id for matter in self.matters}) != len(self.matters):
            raise ValueError("Duplicate matter identity")
        return self


class ReportLinkView(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    brief_id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    snapshot_hash: str = Field(pattern="^[0-9a-f]{64}$")
    created_at: str = Field(min_length=1, max_length=64)

    @field_validator('created_at')
    @classmethod
    def aware_creation_time(cls, value: str) -> str:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError('Timezone required')
        return value



class ReportCatalogView(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)
    schema_version: Literal["caseproof-workspace-reports-v1"] = Field(alias="schema")
    case_id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    reports: list[ReportLinkView] = Field(max_length=20)
    next_cursor: str | None = Field(pattern="^[0-9a-f]{64}$")

class ReviewDecisionView(BaseModel):
    """A persisted signed human disposition, never a machine finding."""
    model_config = ConfigDict(extra="forbid", strict=True)
    reference_id: str = Field(min_length=1, max_length=200)
    decision: Literal["CONFIRMED_SUPPORTED", "CONFIRMED_QUALIFIED", "CONFIRMED_CONTRADICTED"]
    rationale: str = Field(min_length=1, max_length=2000)
    reviewer_id: str = Field(min_length=1, max_length=200)
    request_id: str = Field(min_length=1, max_length=100)
    timestamp: str = Field(min_length=1, max_length=64)
    reviewed_region_ids: list[str] = Field(max_length=96)

    @field_validator("timestamp")
    @classmethod
    def aware_review_time(cls, value: str) -> str:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("Review timestamp needs timezone")
        return value


class ReviewLedgerView(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)
    schema_version: Literal["caseproof-review-ledger-v1"] = Field(alias="schema")
    case_id: str = Field(min_length=1, max_length=200)
    brief_id: str = Field(min_length=1, max_length=200)
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    decisions: list[ReviewDecisionView] = Field(max_length=10000)

    @model_validator(mode="after")
    def unique_decisions(self) -> "ReviewLedgerView":
        keys = [decision.request_id for decision in self.decisions]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate review request identity")
        return self


class DraftExcerptView(BaseModel):
    """Bounded plain-text excerpt from the exact signed preserved DOCX."""
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)
    schema_version: Literal["caseproof-draft-excerpt-v1"] = Field(alias="schema")
    case_id: str = Field(min_length=1, max_length=200)
    brief_id: str = Field(min_length=1, max_length=200)
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    reference_id: str = Field(min_length=1, max_length=200)
    original_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    available: bool
    region: str | None = None
    excerpt: str = Field(max_length=2400)
    selection_start: int = Field(ge=0, le=2400)
    selection_end: int = Field(ge=0, le=2400)
    reason: Literal["unsupported_or_ambiguous_anchor"] | None = None

    @model_validator(mode="after")
    def validate_excerpt(self) -> "DraftExcerptView":
        if self.available:
            if self.region is None or self.reason is not None or not (
                self.selection_start < self.selection_end <= len(self.excerpt)
            ):
                raise ValueError("Invalid supported excerpt")
        elif self.excerpt or self.selection_start or self.selection_end or self.reason is None:
            raise ValueError("Unsupported excerpt cannot claim an anchor")
        return self



LegalStatus = Literal["PASS", "FAIL", "UNVERIFIED", "UNDETERMINED"]


class LegalReferenceView(BaseModel):
    """One cited article checked against the matter's chosen corpus.

    status says corpus presence and quotation integrity only. It is never
    applicability, correct reading or support for the claim.
    """
    model_config = ConfigDict(extra="forbid", strict=True)
    reference_id: str = Field(min_length=1, max_length=200)
    observation_id: str = Field(min_length=1, max_length=220)
    raw_text: str = Field(max_length=4000)
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    act_code: str | None = Field(default=None, max_length=200)
    article: str | None = Field(default=None, max_length=200)
    language: str | None = Field(default=None, max_length=20)
    status: LegalStatus
    reason: str = Field(min_length=1, max_length=400)
    corpus_key: str | None = Field(default=None, max_length=400)
    corpus_version: str | None = Field(default=None, max_length=400)
    corpus_text_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    corpus_source_uri: str | None = Field(default=None, max_length=1000)
    quote: str | None = Field(default=None, max_length=4000)
    claim_support: Literal["not_assessed"]

    @model_validator(mode="after")
    def ordered_span(self) -> "LegalReferenceView":
        if self.end < self.start:
            raise ValueError("citation span reversed")
        return self


class LegalCoverageView(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    detected: int = Field(ge=0, le=100000)
    by_status: dict[LegalStatus, int]
    analysed: str = Field(max_length=400)
    not_analysed: list[str] = Field(max_length=20)

    @model_validator(mode="after")
    def totals(self) -> "LegalCoverageView":
        if set(self.by_status) != {"PASS", "FAIL", "UNVERIFIED", "UNDETERMINED"} or sum(
            self.by_status.values()
        ) != self.detected:
            raise ValueError("coverage does not add up")
        return self


class LegalReferencesView(BaseModel):
    """Cited-article results of ONE frozen run. Observations, not verdicts."""
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)
    schema_version: Literal["caseproof-legal-references-v1"] = Field(alias="schema")
    brief_version_id: str = Field(min_length=1, max_length=200)
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    note: str = Field(max_length=1000)
    corpus: Literal["configured", "not_configured"]
    corpus_pack_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    corpus_articles: int = Field(ge=0, le=100000)
    corpus_failures: list[str] = Field(max_length=500)
    references: list[LegalReferenceView] = Field(max_length=10000)
    coverage: LegalCoverageView

    @model_validator(mode="after")
    def coverage_matches(self) -> "LegalReferencesView":
        ids = [r.reference_id for r in self.references]
        if len(ids) != len(set(ids)) or self.coverage.detected != len(ids):
            raise ValueError("references and coverage disagree")
        for status, n in self.coverage.by_status.items():
            if n != sum(1 for r in self.references if r.status == status):
                raise ValueError("status counts disagree")
        if self.corpus == "not_configured" and any(r.status == "PASS" for r in self.references):
            raise ValueError("PASS without a chosen corpus")
        return self


class LegalPassageView(BaseModel):
    """The lawyer's sentence beside the exact stored article text."""
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)
    schema_version: Literal["caseproof-legal-passage-v1"] = Field(alias="schema")
    observation_id: str = Field(min_length=1, max_length=220)
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    brief_excerpt: str = Field(max_length=2000)
    citation_span: list[int] = Field(min_length=2, max_length=2)
    article_text: str | None = Field(default=None, max_length=200000)
    corpus_key: str | None = Field(default=None, max_length=400)
    corpus_version: str | None = Field(default=None, max_length=400)
    corpus_text_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    corpus_source_uri: str | None = Field(default=None, max_length=1000)
    status: LegalStatus
    reason: str = Field(min_length=1, max_length=400)
    note: str = Field(max_length=1000)

    @model_validator(mode="after")
    def span_inside_excerpt(self) -> "LegalPassageView":
        a, b = self.citation_span
        if not 0 <= a <= b <= len(self.brief_excerpt):
            raise ValueError("citation span outside excerpt")
        return self
