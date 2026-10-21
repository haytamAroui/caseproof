"""Deterministic tests for the source-backed evidence workflow."""
from hashlib import sha256

import pytest

from packages.evidence_kernel.domain.evidence import (
    CorroborationStatus,
    ExtractedClaim,
    ReviewDecision,
    ReviewStatus,
    SourceReference,
    SourceStatus,
)
from packages.evidence_kernel.domain.workflow import (
    ClaimNotFound,
    CorroborationAssessment,
    DocumentVersion,
    EvidenceConflict,
    EvidenceWorkflow,
    EvidenceWorkflowError,
    SourceNotFound,
)


def setup_workflow():
    workflow = EvidenceWorkflow()
    text = "100 units delivered on Tuesday"
    digest = sha256(text.encode()).hexdigest()
    workflow.register_source("tenant-a", DocumentVersion("doc1", "v1", digest, text))
    claim = ExtractedClaim("c1", "100 units delivered", SourceReference("doc1", digest, "100 units delivered"))
    workflow.add_claim("tenant-a", claim, "v1")
    return workflow


def test_exact_quote_verification_does_not_change_claim():
    workflow = setup_workflow()
    assert workflow.verify_quote("tenant-a", "c1").status is SourceStatus.VERIFIED
    assert workflow.get_claim("tenant-a", "c1").source_status is SourceStatus.UNVERIFIED


def test_tenant_isolation():
    workflow = setup_workflow()
    with pytest.raises(ClaimNotFound):
        workflow.get_claim("tenant-b", "c1")
    with pytest.raises(ClaimNotFound):
        workflow.verify_quote("tenant-b", "c1")


def test_duplicate_source_rejected():
    workflow = setup_workflow()
    text = "100 units delivered on Tuesday"
    with pytest.raises(EvidenceConflict):
        workflow.register_source("tenant-a", DocumentVersion("doc1", "v1", sha256(text.encode()).hexdigest(), text))


def test_mismatched_source_digest_rejected():
    with pytest.raises(EvidenceWorkflowError):
        DocumentVersion("doc1", "v1", "a" * 64, "different bytes")


def test_source_version_required():
    workflow = EvidenceWorkflow()
    claim = ExtractedClaim("c1", "statement", SourceReference("doc1", "a" * 64, "quote"))
    with pytest.raises(SourceNotFound):
        workflow.add_claim("tenant-a", claim, "v1")


def test_assessment_and_review_are_separate():
    workflow = setup_workflow()
    workflow.assess("tenant-a", CorroborationAssessment("c1", CorroborationStatus.CONTRADICTED, "other source disagrees"))
    workflow.review("tenant-a", ReviewDecision("c1", "reviewer1", ReviewStatus.REJECTED, "unsupported"))
    history = workflow.history("tenant-a", "c1")
    assert len(history["assessments"]) == 1
    assert len(history["reviews"]) == 1
    assert history["checks"] == ()
    assert workflow.get_claim("tenant-a", "c1").corroboration is CorroborationStatus.NOT_ASSESSED


def test_missing_scope_rejected():
    with pytest.raises(EvidenceWorkflowError):
        EvidenceWorkflow().register_source("", DocumentVersion("doc1", "v1", sha256(b"x").hexdigest(), "x"))
