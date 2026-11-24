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


class SuitabilityRowView(BaseModel):
    """A lawyer-defined rule on declared facts. Never a machine legal conclusion."""
    model_config = ConfigDict(extra="forbid", strict=True)
    observation_id: str = Field(min_length=1, max_length=220)
    rule_id: str = Field(min_length=1, max_length=200)
    rule_version: str = Field(min_length=1, max_length=100)
    reference: str = Field(max_length=400)
    scope: str = Field(max_length=400)
    status: LegalStatus
    reason: str = Field(min_length=1, max_length=400)
    article_key: str = Field(max_length=400)
    cited_by: list[str] = Field(max_length=1000)
    missing: list[str] = Field(max_length=200)
    facts: list[list[str | bool]] = Field(max_length=200)
    input_hashes: list[list[str]] = Field(max_length=200)
    subresults: list[list[str]] = Field(max_length=200)


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
    suitability: list[SuitabilityRowView] = Field(max_length=10000)

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
        if any(row.status == "PASS" and row.missing for row in self.suitability):
            raise ValueError("a rule with missing inputs cannot pass")
        return self


class OtherFindingView(BaseModel):
    """Another finding inside the same excerpt, separately checked."""
    model_config = ConfigDict(extra="forbid", strict=True)
    reference_id: str = Field(min_length=1, max_length=200)
    status: LegalStatus
    span: list[int] = Field(min_length=2, max_length=2)
    quote_span: list[int] | None = Field(default=None, min_length=2, max_length=2)


class LegalPassageView(BaseModel):
    """The lawyer's sentence beside the exact stored article text."""
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)
    schema_version: Literal["caseproof-legal-passage-v1"] = Field(alias="schema")
    observation_id: str = Field(min_length=1, max_length=220)
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    brief_excerpt: str = Field(max_length=2000)
    citation_span: list[int] = Field(min_length=2, max_length=2)
    quote: str | None = Field(max_length=4000)
    quote_span: list[int] | None = Field(min_length=2, max_length=2)
    other_findings: list[OtherFindingView] = Field(max_length=200)
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
        n = len(self.brief_excerpt)
        if not 0 <= a <= b <= n:
            raise ValueError("citation span outside excerpt")
        spans = [self.quote_span] if self.quote_span else []
        for o in self.other_findings:
            spans += [o.span] + ([o.quote_span] if o.quote_span else [])
        if any(not 0 <= x <= y <= n for x, y in spans):
            raise ValueError("span outside excerpt")
        if self.quote_span and self.brief_excerpt[self.quote_span[0]:self.quote_span[1]] != self.quote:
            raise ValueError("quote span does not match the checked quotation")
        return self


class ClearbriefDecisionView(BaseModel):
    """A signed reviewer statement about one observation. Never semantic truth."""
    model_config = ConfigDict(extra="forbid", strict=True)
    observation_id: str = Field(min_length=1, max_length=220)
    actor_id: str = Field(min_length=1, max_length=200)
    disposition: Literal["confirmed_candidate", "dismissed", "needs_information"]
    rationale: str = Field(min_length=1, max_length=2000)


class BlockerItemView(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    observation_id: str = Field(min_length=1, max_length=400)
    reason: str = Field(max_length=800)
    review_disposition: str = Field(max_length=100)


class BlockerInventoryView(BaseModel):
    """Open items only. Not readiness and not permission to file."""
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)
    schema_version: Literal["caseproof-blocker-inventory-v1"] = Field(alias="schema")
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    items: list[BlockerItemView] = Field(max_length=20000)
    verdict: Literal["not_computed"]
    release_authorized: Literal[False]
    waiver_policy: Literal["not_decided"]
    note: str = Field(max_length=1000)


class ClearbriefReviewState(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)
    schema_version: Literal["caseproof-clearbrief-review-v1"] = Field(alias="schema")
    case_id: str = Field(min_length=1, max_length=200)
    brief_version_id: str = Field(min_length=1, max_length=200)
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    revision: int = Field(ge=0, le=100000)
    decisions: list[ClearbriefDecisionView] = Field(max_length=10000)
    blocker_inventory: BlockerInventoryView
    release_authorized: Literal[False]


class ClearbriefReviewReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)
    schema_version: Literal["caseproof-clearbrief-review-receipt-v1"] = Field(alias="schema")
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    revision: int = Field(ge=0, le=100000)
    replayed: bool
    release_authorized: Literal[False]


class OfflinePackManifest(BaseModel):
    """Exact digest and size of the offline review pack for one frozen check."""
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)
    schema_version: Literal["caseproof-offline-pack-manifest-v1"] = Field(alias="schema")
    brief_version_id: str = Field(min_length=1, max_length=200)
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_length: int = Field(ge=1, le=20_000_000)
    checkpoint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    media: Literal["application/zip"]
    note: str = Field(max_length=1000)


class ExhibitPageView(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    space: Literal["printed", "bundle"]
    label: str = Field(min_length=1, max_length=12)
    pdf_page: int = Field(ge=1, le=100000)


class ExhibitEntryView(BaseModel):
    """The confirmed inventory identity, passed through as recorded."""
    model_config = ConfigDict(extra="forbid", strict=True)
    label: Literal["stuk", "piece"]
    number: str = Field(max_length=12)
    source_version_id: str | None = Field(default=None, max_length=64)
    filename: str | None = Field(default=None, max_length=128)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    readback: Literal["verified", "unknown", "integrity_mismatch"] | None = None
    page_count: int | None = Field(default=None, ge=0, le=100000)
    pages: list[ExhibitPageView] = Field(max_length=128)


class ExhibitReferenceView(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    reference_id: str = Field(pattern=r"^exhibit-ref-\d{2,5}$")
    raw_text: str = Field(max_length=64)
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    status: Literal["UNVERIFIED", "UNDETERMINED"]
    reason: str = Field(max_length=120)
    page_cited: bool
    entry: ExhibitEntryView | None = None


class ExhibitCoverageView(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    detected: int = Field(ge=0)
    by_status: dict[str, int]
    located: int = Field(ge=0)
    inventory_entries: int = Field(ge=0)
    entries_not_detected_in_brief: list[str] = Field(max_length=600)


class ExhibitReferencesView(BaseModel):
    """Exhibit mentions mapped to the confirmed inventory. Located never means content verified."""
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)
    schema_version: Literal["caseproof-exhibit-references-v1"] = Field(alias="schema")
    brief_version_id: str = Field(min_length=1, max_length=200)
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    note: str = Field(max_length=1000)
    inventory_confirmed: bool
    inventory_complete: bool
    confirmation_id: str | None = Field(default=None, max_length=128)
    references: list[ExhibitReferenceView] = Field(max_length=10000)
    coverage: ExhibitCoverageView

    @model_validator(mode="after")
    def coherent(self) -> "ExhibitReferencesView":
        ids = [r.reference_id for r in self.references]
        if len(ids) != len(set(ids)) or self.coverage.detected != len(ids):
            raise ValueError("references and coverage disagree")
        if self.inventory_complete and not self.inventory_confirmed:
            raise ValueError("complete without confirmation")
        if not self.inventory_confirmed and any(r.entry for r in self.references):
            raise ValueError("mapping without confirmed inventory")
        for status, n in self.coverage.by_status.items():
            if n != sum(1 for r in self.references if r.status == status):
                raise ValueError("status counts disagree")
        if self.coverage.located != sum(1 for r in self.references if r.reason.startswith("piece_located")):
            raise ValueError("located count disagrees")
        return self
