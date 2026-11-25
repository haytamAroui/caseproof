"""Isolated Tier-2 QAE adversarial evaluation spike (not Pilot Core)."""
from __future__ import annotations

from evals.litigation_qae_spike.contracts import (
    ContentReleaseGrant,
    EntityLinkProof,
    IndexedDocument,
    LawyerActionState,
    MechanicallyGroundedLead,
    ModelCandidate,
    PageTextBlock,
    QaeCoverageManifest,
    ReconciledReviewLead,
    TransmissionManifest,
    TransmittedExcerpt,
    VisualBox,
    canonical_digest,
)
from evals.litigation_qae_spike.engine import (
    apply_lawyer_action,
    build_minimized_transmission,
    index_document_blocks,
    normalize_belgian_date,
    normalize_belgian_money,
    reconcile_litigation_leads,
    record_source_open,
    run_two_tier_evaluation,
    shortlist_uncited_exhibits,
    verify_and_harden_candidate,
)
from evals.litigation_qae_spike.metrics import run_scripted_adversarial_benchmark

__all__ = [
    "ContentReleaseGrant",
    "EntityLinkProof",
    "IndexedDocument",
    "LawyerActionState",
    "MechanicallyGroundedLead",
    "ModelCandidate",
    "PageTextBlock",
    "QaeCoverageManifest",
    "ReconciledReviewLead",
    "TransmissionManifest",
    "TransmittedExcerpt",
    "VisualBox",
    "apply_lawyer_action",
    "build_minimized_transmission",
    "canonical_digest",
    "index_document_blocks",
    "normalize_belgian_date",
    "normalize_belgian_money",
    "reconcile_litigation_leads",
    "record_source_open",
    "run_scripted_adversarial_benchmark",
    "run_two_tier_evaluation",
    "shortlist_uncited_exhibits",
    "verify_and_harden_candidate",
]
