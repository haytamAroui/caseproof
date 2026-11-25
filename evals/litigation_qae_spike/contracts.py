"""Versioned contracts for the isolated Tier-2 QAE adversarial evaluation spike.

Every contract enforces strict separation between:
- Tier-1 deterministic verification vs. optional Tier-2 semantic reader
- Level 1 raw model proposal vs. Level 2 mechanically grounded lead vs. Level 3 lawyer decision
- Visual pixel anchors, cross-document entity link proofs, review budgets, and data minimization.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Literal


def canonical_digest(value: Any) -> str:
    """Deterministic SHA-256 hex digest over canonical JSON."""
    serialized = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class VisualBox:
    """Normalized visual bounding box on a specific PDF page."""

    page: int
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True, slots=True)
class PageTextBlock:
    """Page-indexed derived text block retaining version, offset, and visual-box lineage."""

    block_id: str
    exhibit_id: str
    document_id: str
    version_id: str
    representation_id: str
    representation_sha256: str
    pdf_page: int
    char_start: int
    char_end: int
    text: str
    visual_bboxes: tuple[VisualBox, ...]
    ocr_uncertain: bool = False


@dataclass(frozen=True, slots=True)
class IndexedDocument:
    """Immutable indexed document representation spanning blocks and PDF pages."""

    exhibit_id: str
    document_id: str
    version_id: str
    version_sha256: str
    representation_id: str
    representation_sha256: str
    full_text: str
    blocks: tuple[PageTextBlock, ...]
    ocr_uncertain_pages: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class EntityLinkProof:
    """Explicit entity link evidence across exhibits (Bordereau confirmation alone is insufficient)."""

    entity_id: str
    source_exhibit_ids: tuple[str, ...]
    link_basis: Literal["human_confirmed", "explicit_reference_id", "unconfirmed_model_proposal"]
    confirmed_by: str | None = None
    reference_token: str | None = None


@dataclass(frozen=True, slots=True)
class ContentReleaseGrant:
    """Explicit per-matter authorization bounding what may be sent to a model provider."""

    release_id: str
    matter_id: str
    destination: str
    retention_policy: str
    max_total_chars: int
    authorized: bool


@dataclass(frozen=True, slots=True)
class TransmittedExcerpt:
    """Zero-raw-text audit entry for one minimally transmitted block."""

    exhibit_id: str
    pdf_page: int
    block_id: str
    char_start: int
    char_end: int
    excerpt_sha256: str
    char_count: int


@dataclass(frozen=True, slots=True)
class TransmissionManifest:
    """Audit manifest proving data minimization and zero raw client text logging."""

    release_id: str
    destination: str
    retention_policy: str
    total_chars_sent: int
    full_bundle_chars: int
    excerpts: tuple[TransmittedExcerpt, ...]
    raw_text_logged: bool = False


Polarity = Literal["affirmative", "negative", "conditional", "alleged", "unknown"]
ActionKind = Literal["confirm_discrepancy", "qualify", "reject_lead", "waive"]
SupportState = Literal[
    "NOT_ASSESSED",
    "CONFIRMED_SUPPORTED",
    "CONFIRMED_QUALIFIED",
    "CONFIRMED_CONTRADICTED",
]
VisualAnchorStatus = Literal["visual_boxes_attached", "visual_anchor_unavailable"]
EntityLinkStatus = Literal[
    "human_confirmed",
    "explicit_reference_id",
    "unconfirmed_bordereau_insufficient",
]


@dataclass(frozen=True, slots=True)
class ModelCandidate:
    """Level 1 — Unverified model proposal (untrusted hypothesis)."""

    candidate_id: str
    exhibit_id: str
    entity_id: str
    slot: str
    signal: str
    raw_value: str
    quote: str
    polarity: Polarity
    provider: str
    model: str
    prompt_version: str


@dataclass(frozen=True, slots=True)
class MechanicallyGroundedLead:
    """Level 2 atom — Exact quote located across blocks/pages with safety warnings attached."""

    lead_id: str
    epistemic_level: Literal["mechanically_grounded_lead"]
    source_exhibit_id: str
    document_id: str
    version_id: str
    version_sha256: str
    representation_id: str
    representation_sha256: str
    char_start: int
    char_end: int
    spanned_pages: tuple[int, ...]
    spanned_block_ids: tuple[str, ...]
    visual_anchor_status: VisualAnchorStatus
    visual_bboxes: tuple[VisualBox, ...]
    quote: str
    surrounding_context: str
    entity_id: str
    slot: str
    signal: str
    raw_value: str
    polarity: Polarity
    warnings: tuple[str, ...]
    candidate_provenance: dict[str, str]


@dataclass(frozen=True, slots=True)
class ReconciledReviewLead:
    """Level 2 reconciliation output — Review lead only, never established truth."""

    lead_id: str
    rule_code: str
    priority: Literal["P0", "deferred"]
    epistemic_level: Literal["mechanically_grounded_lead"]
    brief_lead_id: str
    exhibit_lead_id: str
    summary: str
    warnings: tuple[str, ...]
    entity_link_status: EntityLinkStatus
    visual_anchor_status: VisualAnchorStatus
    human_semantic_support: Literal["NOT_ASSESSED"] = "NOT_ASSESSED"
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LawyerActionState:
    """Level 3 — Separates access trace (opening PDF) from explicit human decision."""

    lead_id: str
    bound_source_sha256: str
    source_opened_at: str | None = None
    explicit_action: ActionKind | None = None
    human_semantic_support: SupportState = "NOT_ASSESSED"
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class QaeCoverageManifest:
    """Mandatory denominator disclosure — deferred or unread items are never masked."""

    exhibits_in_bundle: tuple[str, ...]
    exhibits_read_by_qae: tuple[str, ...]
    unread_exhibits: tuple[str, ...]
    unreadable_ocr_pages: tuple[str, ...]
    excluded_by_preselection: tuple[str, ...]
    p0_leads_count: int
    deferred_leads_count: int
    rejected_candidates_count: int
    model_status: Literal["completed", "partial_failure", "failed_or_unavailable"]
    zero_p0_means_clean: Literal[False] = False
