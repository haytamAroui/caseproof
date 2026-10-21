"""KRN-106: negative coverage, omissions, exclusion claims and anchored issue links."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from hashlib import sha256

import pytest

from packages.evidence_kernel.domain.anchors import AnchorResolver, EvidenceAnchor, TextSpan
from packages.evidence_kernel.domain.coverage import (
    AttemptState,
    CoverageConflict,
    CoverageError,
    CoverageEvaluator,
    CoverageManifest,
    CoverageNotFound,
    CoveragePolicy,
    CoverageReason,
    ExclusionProposal,
    ExpectedSource,
    InMemoryCoverageLedger,
    IssueStatus,
    LinkUse,
    ProcessingAttempt,
    RequiredIssue,
    SourceState,
)
from packages.evidence_kernel.domain.fidelity import ExactQuote, FidelityEvaluator
from packages.evidence_kernel.domain.finding_links import (
    AssessorKind,
    FindingStatement,
    InMemoryFindingEvidenceLedger,
    LinkSufficiency,
    SemanticAssessmentProposal,
    SemanticRelation,
)
from packages.evidence_kernel.domain.source_versions import (
    DerivedRepresentation,
    InMemorySourceRegistry,
    SourceVersion,
)

NOW = datetime(2026, 10, 21, 19, tzinfo=UTC)
ORIGINAL = b"captured source version"
TEXT = b"Approved by Alice. Payment was NOT received."


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def good_attempt() -> ProcessingAttempt:
    return ProcessingAttempt("run-1", AttemptState.SUCCEEDED, ("rep",))


def processed_source() -> ExpectedSource:
    return ExpectedSource("src", "doc", "v1", SourceState.PROCESSED, (good_attempt(),))


def issue(*, links: tuple[LinkUse, ...] | None = None) -> RequiredIssue:
    return RequiredIssue(
        "question", "issue-rule-v1", ("src",),
        (LinkUse("link", 1, "finding", 1),) if links is None else links,
        finding_ids=("finding",),
    )


def manifest(
    *,
    issues: tuple[RequiredIssue, ...] | None = None,
    sources: tuple[ExpectedSource, ...] | None = None,
    exclusions: tuple[ExclusionProposal, ...] = (),
    revision: int = 1,
    scope: int = 1,
    policy: str = "coverage-v1",
    reason: str = "",
) -> CoverageManifest:
    return CoverageManifest(
        case_id="case-1",
        scope_version=scope,
        manifest_revision=revision,
        policy_version=policy,
        issues=(issue(),) if issues is None else issues,
        sources=(processed_source(),) if sources is None else sources,
        exclusions=exclusions,
        scope_change_reason=reason,
    )


def exclude() -> ExclusionProposal:
    return ExclusionProposal(
        "src", "claimed confidential source", "reviewer-claimed",
        "permission-claimed", "audit-event-claimed",
    )


def fixture(
    *,
    semantic: SemanticRelation = SemanticRelation.SUPPORTS,
    sufficiency: LinkSufficiency = LinkSufficiency.SUFFICIENT,
    quote: str = "Approved",
) -> tuple[
    InMemoryCoverageLedger, InMemoryFindingEvidenceLedger,
    CoverageEvaluator, CoverageManifest, EvidenceAnchor,
]:
    sources = InMemorySourceRegistry()
    src = SourceVersion("doc", "v1", digest(ORIGINAL), ORIGINAL, NOW, "application/pdf")
    rep = DerivedRepresentation(
        "rep", "doc", "v1", src.sha256_hex, digest(TEXT), TEXT, "text/plain",
        "parser", "v1", digest(b"cfg"), "unicode_codepoint_zero_based_half_open", NOW,
    )
    sources.register_source("tenant", src)
    sources.register_representation("tenant", rep)
    links = InMemoryFindingEvidenceLedger(FidelityEvaluator(AnchorResolver(sources)))
    finding = FindingStatement("finding", 1, "Document approval was recorded.")
    links.register_statement("tenant", finding)
    anchor = EvidenceAnchor(
        "a1", "doc", "v1", src.sha256_hex, "rep", rep.sha256_hex, TextSpan(0, 8)
    )
    links.append_assessment(
        "tenant", "link", 1, finding, anchor, ExactQuote(quote),
        SemanticAssessmentProposal(
            semantic, sufficiency, AssessorKind.DETERMINISTIC,
            "deterministic-v1", "method-v1", "Assessment proposal, not approval.", NOW,
        ),
    )
    records = InMemoryCoverageLedger()
    m = manifest()
    records.register("tenant", m)
    return records, links, CoverageEvaluator(records, links), m, anchor


def errors(result: object) -> set[CoverageReason]:
    return {item.reason for item in result.blockers}  # type: ignore[attr-defined]


def test_complete_declared_scope_requires_all_issues_and_registered_processed_sources() -> None:
    ledger, links, evaluator, m, _ = fixture()
    result = evaluator.evaluate("tenant", m, CoveragePolicy("coverage-v1"))
    assert result.ordinary_complete
    assert result.blockers == ()
    assert result.issues[0].status is IssueStatus.SUPPORTED
    assert result.policy_version == "coverage-v1"
    assert result.scope_version == 1
    assert result.excluded_source_ids == ()
    assert not hasattr(evaluator, "approve")
    assert not hasattr(result, "approved_conclusion")
    assert len(ledger.history("tenant", "case-1")) == 1
    assert len(links.link_history("tenant", "link")) == 1


@pytest.mark.parametrize(
    ("state", "reason"),
    [
        (SourceState.MISSING, CoverageReason.SOURCE_UNACCOUNTED),
        (SourceState.PENDING, CoverageReason.SOURCE_UNACCOUNTED),
        (SourceState.EXPECTED_UNKNOWN, CoverageReason.SOURCE_UNACCOUNTED),
        (SourceState.FAILED, CoverageReason.SOURCE_UNACCOUNTED),
    ],
)
def test_missing_pending_unknown_and_failed_sources_never_mean_complete(
    state: SourceState, reason: CoverageReason
) -> None:
    ledger, _, evaluator, old, _ = fixture()
    attempt = (ProcessingAttempt("failed-1", AttemptState.FAILED, reason_code="parse_error"),)
    source = (
        ExpectedSource("src", None, None, state)
        if state is SourceState.EXPECTED_UNKNOWN
        else ExpectedSource(
            "src", "doc", "v1", state,
            attempt if state is SourceState.FAILED else (),
        )
    )
    changed_scope = state is SourceState.EXPECTED_UNKNOWN
    replacement = manifest(
        sources=(source,), revision=2, scope=2 if changed_scope else 1,
        reason="source identity remains unresolved" if changed_scope else "",
    )
    ledger.register("tenant", replacement)
    result = evaluator.evaluate("tenant", replacement, CoveragePolicy("coverage-v1"))
    assert not result.ordinary_complete
    assert reason in errors(result)
    assert evaluator.evaluate("tenant", old, CoveragePolicy("coverage-v1")).ordinary_complete is False


def test_mismatched_claimed_processed_source_without_registered_bytes_fails() -> None:
    _, _, evaluator, original, _ = fixture()
    # A separate tenant may claim processed with no authorized source bytes.
    other = InMemoryCoverageLedger()
    other.register("other", original)
    evaluator = CoverageEvaluator(other, evaluator.findings)
    result = evaluator.evaluate("other", original, CoveragePolicy("coverage-v1"))
    assert CoverageReason.SOURCE_NOT_REGISTERED in errors(result)
    assert not result.ordinary_complete


def test_processed_claim_with_missing_derived_representation_fails() -> None:
    ledger, _, evaluator, _, _ = fixture()
    source = replace(
        processed_source(), attempts=(ProcessingAttempt(
            "run-2", AttemptState.SUCCEEDED, ("absent-rep",)
        ),)
    )
    changed = manifest(sources=(source,), revision=2)
    ledger.register("tenant", changed)
    result = evaluator.evaluate("tenant", changed, CoveragePolicy("coverage-v1"))
    assert CoverageReason.REPRESENTATION_NOT_REGISTERED in errors(result)


def test_only_a_real_registered_current_link_satisfies_an_issue() -> None:
    ledger, _, evaluator, _, _ = fixture()
    changed = manifest(
        issues=(issue(links=(LinkUse("nonexistent", 1, "finding", 1),)),),
        revision=2,
    )
    ledger.register("tenant", changed)
    result = evaluator.evaluate("tenant", changed, CoveragePolicy("coverage-v1"))
    assert not result.ordinary_complete
    assert result.issues[0].status is IssueStatus.OPEN
    assert CoverageReason.LINK_UNAVAILABLE_OR_STALE in errors(result)


def test_no_evidence_link_never_converts_processed_to_supported() -> None:
    ledger, _, evaluator, _, _ = fixture()
    empty = manifest(issues=(issue(links=()),), revision=2)
    ledger.register("tenant", empty)
    result = evaluator.evaluate("tenant", empty, CoveragePolicy("coverage-v1"))
    assert not result.ordinary_complete
    assert result.issues[0].status is IssueStatus.OPEN
    assert CoverageReason.ISSUE_UNSUPPORTED in errors(result)


@pytest.mark.parametrize(
    ("semantic", "expected_status", "reason"),
    [
        (SemanticRelation.CONTRADICTS, IssueStatus.CONTRADICTED,
         CoverageReason.CONTRADICTION_PRESENT),
        (SemanticRelation.QUALIFIES, IssueStatus.QUALIFIED,
         CoverageReason.ISSUE_UNSUPPORTED),
        (SemanticRelation.INCONCLUSIVE, IssueStatus.UNRESOLVED,
         CoverageReason.SEMANTIC_UNRESOLVED),
        (SemanticRelation.NOT_ASSESSED, IssueStatus.UNRESOLVED,
         CoverageReason.SEMANTIC_UNRESOLVED),
    ],
)
def test_semantic_contradiction_qualification_and_unknown_never_silently_complete(
    semantic: SemanticRelation, expected_status: IssueStatus, reason: CoverageReason,
) -> None:
    _, _, evaluator, m, _ = fixture(semantic=semantic)
    result = evaluator.evaluate("tenant", m, CoveragePolicy("coverage-v1"))
    assert not result.ordinary_complete
    assert result.issues[0].status is expected_status
    assert reason in errors(result)


@pytest.mark.parametrize("suff", [
    LinkSufficiency.NOT_ASSESSED, LinkSufficiency.INSUFFICIENT,
])
def test_insufficient_or_unassessed_link_sufficiency_is_not_complete(
    suff: LinkSufficiency,
) -> None:
    _, _, evaluator, m, _ = fixture(sufficiency=suff)
    result = evaluator.evaluate("tenant", m, CoveragePolicy("coverage-v1"))
    assert not result.ordinary_complete
    assert CoverageReason.LINK_SUFFICIENCY_UNASSESSED in errors(result)


def test_wrong_quotation_does_not_count_as_supported() -> None:
    _, _, evaluator, m, _ = fixture(quote="Rejected")
    result = evaluator.evaluate("tenant", m, CoveragePolicy("coverage-v1"))
    assert not result.ordinary_complete
    assert CoverageReason.LINK_FIDELITY_NOT_MATCHED in errors(result)


def test_declared_source_outside_actual_anchor_prevents_completion() -> None:
    ledger, _, evaluator, _, _ = fixture()
    src = replace(
        processed_source(), document_id="another-document"
    )
    replacement = manifest(sources=(src,), revision=2, scope=2, reason="source replaced")
    ledger.register("tenant", replacement)
    result = evaluator.evaluate("tenant", replacement, CoveragePolicy("coverage-v1"))
    assert not result.ordinary_complete
    assert CoverageReason.SOURCE_NOT_REGISTERED in errors(result)


def test_exclusion_claim_is_visible_but_does_not_authorize_ordinary_completion() -> None:
    ledger, _, evaluator, _, _ = fixture()
    excluded = ExpectedSource("src", "doc", "v1", SourceState.EXCLUDED)
    m = manifest(sources=(excluded,), exclusions=(exclude(),), revision=2)
    ledger.register("tenant", m)
    result = evaluator.evaluate("tenant", m, CoveragePolicy("coverage-v1"))
    assert not result.ordinary_complete
    assert CoverageReason.EXCLUSION_NOT_AUTHORIZED in errors(result)
    assert result.excluded_source_ids == ("src",)
    assert "claimed confidential source" not in repr(exclude())
    assert not hasattr(result, "business_exception_accepted")


def test_stale_manifest_revision_and_policy_change_fail_closed() -> None:
    ledger, _, evaluator, old, _ = fixture()
    fresh = manifest(revision=2)
    ledger.register("tenant", fresh)
    assert errors(evaluator.evaluate("tenant", old, CoveragePolicy("coverage-v1"))) == {
        CoverageReason.STALE_MANIFEST
    }
    assert errors(evaluator.evaluate("tenant", fresh, CoveragePolicy("wrong-policy"))) == {
        CoverageReason.POLICY_MISMATCH
    }


def test_revisions_are_append_only_and_cannot_omit_issue_or_source_in_same_scope() -> None:
    ledger, _, _, _, _ = fixture()
    with pytest.raises(CoverageConflict):
        ledger.register("tenant", manifest(revision=1))
    with pytest.raises(CoverageConflict):
        ledger.register("tenant", manifest(revision=3))
    with pytest.raises(CoverageConflict, match="scope"):
        ledger.register("tenant", manifest(
            revision=2,
            issues=(RequiredIssue("new-issue", "rule", ("src",), finding_ids=("finding",)),),
        ))
    assert len(ledger.history("tenant", "case-1")) == 1


def test_explicit_new_scope_revision_preserves_old_history_without_authorizing_omission() -> None:
    ledger, _, evaluator, previous, _ = fixture()
    next_scope = manifest(
        revision=2, scope=2, reason="review-required scope amendment",
        issues=(RequiredIssue("different-issue", "new-rule", ("src",), finding_ids=("finding",)),),
    )
    ledger.register("tenant", next_scope)
    assert ledger.history("tenant", "case-1") == (previous, next_scope)
    assert evaluator.evaluate("tenant", next_scope, CoveragePolicy("coverage-v1")).ordinary_complete is False
    assert CoverageReason.ISSUE_UNSUPPORTED in errors(
        evaluator.evaluate("tenant", next_scope, CoveragePolicy("coverage-v1"))
    )


def test_cross_tenant_read_write_does_not_reuse_other_tenant_coverage() -> None:
    ledger, _, evaluator, m, _ = fixture()
    with pytest.raises(CoverageNotFound):
        ledger.current("another", "case-1")
    with pytest.raises(CoverageNotFound):
        evaluator.evaluate("another", m, CoveragePolicy("coverage-v1"))
    ledger.register("another", m)
    assert ledger.current("another", "case-1") is m
    other = evaluator.evaluate("another", m, CoveragePolicy("coverage-v1"))
    assert not other.ordinary_complete


def test_wrong_link_revision_and_new_finding_statement_require_reassessment() -> None:
    ledger, links, evaluator, _, _ = fixture()
    wrong = manifest(
        revision=2,
        issues=(issue(links=(LinkUse("link", 2, "finding", 1),)),),
    )
    ledger.register("tenant", wrong)
    assert CoverageReason.LINK_UNAVAILABLE_OR_STALE in errors(
        evaluator.evaluate("tenant", wrong, CoveragePolicy("coverage-v1"))
    )
    updated = FindingStatement("finding", 2, "The approved scope was amended.")
    links.register_statement("tenant", updated)
    next_m = manifest(revision=3)
    ledger.register("tenant", next_m)
    assert CoverageReason.LINK_UNAVAILABLE_OR_STALE in errors(
        evaluator.evaluate("tenant", next_m, CoveragePolicy("coverage-v1"))
    )


def test_historical_contradiction_is_not_erased_by_a_new_supporting_revision() -> None:
    ledger, links, evaluator, _, anchor = fixture(semantic=SemanticRelation.CONTRADICTS)
    stmt = links.get_statement("tenant", "finding", 1)
    links.append_assessment(
        "tenant", "link", 2, stmt, anchor, ExactQuote("Approved"),
        SemanticAssessmentProposal(
            SemanticRelation.SUPPORTS, LinkSufficiency.SUFFICIENT,
            AssessorKind.DETERMINISTIC, "deterministic-v2", "method-v2",
            "Second proposal does not erase earlier contradiction.", NOW,
        ),
    )
    m = manifest(
        revision=2, issues=(issue(links=(LinkUse("link", 2, "finding", 1),)),),
    )
    ledger.register("tenant", m)
    result = evaluator.evaluate("tenant", m, CoveragePolicy("coverage-v1"))
    assert CoverageReason.HISTORICAL_CONTRADICTION in errors(result)
    assert not result.ordinary_complete


def test_omitted_source_or_missing_issue_rejected_before_ledger_registration() -> None:
    with pytest.raises(CoverageError):
        manifest(issues=())
    with pytest.raises(CoverageError):
        manifest(sources=())
    with pytest.raises(CoverageError, match="unknown"):
        manifest(issues=(RequiredIssue("question", "policy", ("missing-src",), finding_ids=("finding",)),))
    with pytest.raises(CoverageError, match="associated"):
        manifest(
            sources=(processed_source(), ExpectedSource("src2", "d2", "v1", SourceState.MISSING))
        )


def test_manifest_requires_explicit_exclusion_records_and_no_forged_approval() -> None:
    excluded = ExpectedSource("src", "doc", "v1", SourceState.EXCLUDED)
    with pytest.raises(CoverageError, match="excluded"):
        manifest(sources=(excluded,))
    with pytest.raises(CoverageError, match="excluded"):
        manifest(exclusions=(exclude(),))


def test_invalid_attempt_state_transitions_rejected_by_schema() -> None:
    with pytest.raises(CoverageError):
        ExpectedSource("src", "doc", "v1", SourceState.PROCESSED)
    with pytest.raises(CoverageError):
        ExpectedSource("src", "doc", "v1", SourceState.PROCESSED, (
            ProcessingAttempt("pending", AttemptState.PENDING),
        ))
    with pytest.raises(CoverageError):
        ProcessingAttempt("failed", AttemptState.FAILED, ("rep",), "oops")
    with pytest.raises(CoverageError):
        ProcessingAttempt("success", AttemptState.SUCCEEDED)
    with pytest.raises(CoverageError):
        ExpectedSource("src", None, "v1", SourceState.EXPECTED_UNKNOWN)


@pytest.mark.parametrize("bad", ["", " ", None])
def test_coverage_identity_and_policy_are_mandatory(bad: object) -> None:
    with pytest.raises(CoverageError):
        CoveragePolicy(bad)  # type: ignore[arg-type]
    with pytest.raises(CoverageError):
        replace(manifest(), policy_version=bad)  # type: ignore[arg-type]


def test_immutable_frozen_manifest_and_failure_result() -> None:
    m = manifest()
    with pytest.raises(FrozenInstanceError):
        m.scope_version = 99  # type: ignore[misc]
    _, _, evaluator, registered, _ = fixture()
    result = evaluator.evaluate("tenant", registered, CoveragePolicy("coverage-v1"))
    with pytest.raises(FrozenInstanceError):
        result.ordinary_complete = False  # type: ignore[misc]


def test_existing_v1_and_krn105_interfaces_remain_unchanged() -> None:
    from packages.evidence_kernel.domain.evidence import SourceReference
    from packages.evidence_kernel.domain.grounding import GroundingPolicy
    from packages.evidence_kernel.domain.workflow import DocumentVersion

    assert SourceReference("doc", digest(ORIGINAL), "quote").document_id == "doc"
    assert DocumentVersion("doc", "v1", digest(b"old"), "old").version_id == "v1"
    assert GroundingPolicy("grounding-v1").version == "grounding-v1"


def test_unrelated_finding_link_cannot_be_used_to_close_an_issue() -> None:
    with pytest.raises(CoverageError, match="required finding"):
        RequiredIssue(
            "question", "policy", ("src",),
            (LinkUse("link", 1, "finding", 1),), finding_ids=("other-finding",),
        )


def test_required_finding_without_its_own_link_blocks_completion() -> None:
    ledger, _, evaluator, _, _ = fixture()
    required = RequiredIssue(
        "question", "policy", ("src",),
        (LinkUse("link", 1, "finding", 1),), finding_ids=("another-finding", "finding"),
    )
    changed = manifest(issues=(required,), revision=2, scope=2,
                       reason="New material finding added to scope")
    ledger.register("tenant", changed)
    result = evaluator.evaluate("tenant", changed, CoveragePolicy("coverage-v1"))
    assert not result.ordinary_complete
    assert CoverageReason.ISSUE_UNSUPPORTED in errors(result)


def test_mapping_to_different_required_finding_requires_scope_revision() -> None:
    ledger, _, _, _, _ = fixture()
    changed = manifest(
        revision=2,
        issues=(RequiredIssue(
            "question", "issue-rule-v1", ("src",),
            (LinkUse("another-link", 1, "alternative", 1),),
            finding_ids=("alternative",),
        ),),
    )
    with pytest.raises(CoverageConflict, match="scope"):
        ledger.register("tenant", changed)
