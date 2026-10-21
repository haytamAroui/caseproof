"""KRN-104: append-only evidence edges, semantic proposals, and adversarial revisions."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from hashlib import sha256

import pytest

from packages.evidence_kernel.domain.anchors import AnchorResolver, EvidenceAnchor, TextSpan
from packages.evidence_kernel.domain.fidelity import (
    CitationResolution,
    ContentFidelity,
    ExactJsonScalar,
    ExactQuote,
    FidelityEvaluator,
    FindingRevision,
)
from packages.evidence_kernel.domain.finding_links import (
    AssessorKind,
    FindingEvidenceLinkRevision,
    FindingLinkConflict,
    FindingLinkError,
    FindingLinkNotFound,
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

STAMP = datetime(2026, 10, 21, 15, tzinfo=UTC)
RAW = b"document captured bytes"
TEXT = "Payment NOT received. The contract was signed."


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def rig(
    *,
    tenant: str = "tenant-a",
    text: str = TEXT,
) -> tuple[InMemoryFindingEvidenceLedger, FindingStatement, EvidenceAnchor]:
    registry = InMemorySourceRegistry()
    source = SourceVersion(
        "document-1", "source-v1", digest(RAW), RAW, STAMP, "application/pdf"
    )
    raw = text.encode("utf-8")
    representation = DerivedRepresentation(
        representation_id="ocr-1",
        document_id="document-1",
        version_id="source-v1",
        source_sha256_hex=source.sha256_hex,
        sha256_hex=digest(raw),
        content=raw,
        media_type="text/plain",
        transform_name="ocr",
        transform_version="1",
        transform_config_sha256=digest(b"config"),
        coordinate_convention="unicode_codepoint_zero_based_half_open",
        created_at=STAMP,
    )
    registry.register_source(tenant, source)
    registry.register_representation(tenant, representation)
    evaluator = FidelityEvaluator(AnchorResolver(registry))
    ledger = InMemoryFindingEvidenceLedger(evaluator)
    finding = FindingStatement("claim-1", 1, "The customer already paid.")
    ledger.register_statement(tenant, finding)
    anchor = EvidenceAnchor(
        "anchor-1", "document-1", "source-v1", source.sha256_hex, "ocr-1",
        representation.sha256_hex, TextSpan(0, 20),
    )
    assert text[:20] == "Payment NOT received"
    return ledger, finding, anchor


def proposal(
    *,
    relation: SemanticRelation = SemanticRelation.CONTRADICTS,
    sufficiency: LinkSufficiency = LinkSufficiency.INSUFFICIENT,
    kind: AssessorKind = AssessorKind.MODEL,
    assessor_ref: str = "model-output-1",
    rationale: str = "The quote challenges the stated finding.",
) -> SemanticAssessmentProposal:
    return SemanticAssessmentProposal(
        relation, sufficiency, kind, assessor_ref, "semantic-proposal-v1", rationale, STAMP
    )


def add(
    ledger: InMemoryFindingEvidenceLedger,
    finding: FindingStatement,
    anchor: EvidenceAnchor,
    *,
    tenant: str = "tenant-a",
    link: str = "link-a",
    revision: int = 1,
    quote: str = "Payment NOT received",
    semantic: SemanticAssessmentProposal | None = None,
) -> FindingEvidenceLinkRevision:
    return ledger.append_assessment(
        tenant, link, revision, finding, anchor, ExactQuote(quote),
        semantic if semantic is not None else proposal(),
    )


def test_candidate_can_be_unanchored_without_approval_or_evidence() -> None:
    ledger, finding, _ = rig()
    assert ledger.get_statement("tenant-a", "claim-1", 1) is finding
    assert ledger.links_for_statement("tenant-a", "claim-1", 1) == ()
    assert not hasattr(ledger, "approve")
    assert not hasattr(ledger, "promote")


def test_exact_quote_can_contradict_finding_and_does_not_approve_it() -> None:
    ledger, finding, anchor = rig()
    link = add(ledger, finding, anchor)
    assert link.fidelity.citation_resolution is CitationResolution.RESOLVED
    assert link.fidelity.content_fidelity is ContentFidelity.MATCHED
    assert link.semantic.relation is SemanticRelation.CONTRADICTS
    assert link.semantic.sufficiency is LinkSufficiency.INSUFFICIENT
    assert link.location_and_fidelity_eligible
    assert not hasattr(link, "approved")
    assert not hasattr(link, "verified")
    assert link.statement.text == "The customer already paid."


def test_semantic_support_is_recorded_as_proposal_not_as_truth() -> None:
    ledger, finding, anchor = rig()
    link = add(ledger, finding, anchor, semantic=proposal(
        relation=SemanticRelation.SUPPORTS,
        sufficiency=LinkSufficiency.SUFFICIENT,
        kind=AssessorKind.HUMAN,
        assessor_ref="user-supplied-human-claim",
    ))
    assert link.semantic.relation is SemanticRelation.SUPPORTS
    assert link.semantic.assessor_kind is AssessorKind.HUMAN
    assert link.fidelity.semantic_relation == "not_assessed"
    assert link.fidelity.sufficiency == "not_assessed"
    assert link.location_and_fidelity_eligible
    assert not hasattr(link, "approval_authority")


def test_invalid_and_mismatched_quotes_are_never_location_fidelity_eligible() -> None:
    ledger, finding, anchor = rig()
    result = add(
        ledger, finding, anchor, quote="Payment WAS received",
        semantic=proposal(relation=SemanticRelation.SUPPORTS),
    )
    assert result.semantic.relation is SemanticRelation.SUPPORTS
    assert result.fidelity.content_fidelity is ContentFidelity.MISMATCHED
    assert not result.location_and_fidelity_eligible
    missing = add(
        ledger, finding, replace(anchor, locator=TextSpan(0, 5000)),
        link="link-invalid",
        semantic=proposal(relation=SemanticRelation.SUPPORTS),
    )
    assert missing.fidelity.citation_resolution is CitationResolution.INVALID
    assert missing.fidelity.content_fidelity is ContentFidelity.INDETERMINATE
    assert not missing.location_and_fidelity_eligible


def test_semantic_link_revisions_are_append_only_and_preserve_contradictions() -> None:
    ledger, finding, anchor = rig()
    first = add(ledger, finding, anchor)
    second = add(
        ledger, finding, anchor, revision=2,
        semantic=proposal(relation=SemanticRelation.QUALIFIES,
                          rationale="New proposed interpretation; earlier conflict remains."),
    )
    assert ledger.link_history("tenant-a", "link-a") == (first, second)
    assert ledger.links_for_statement("tenant-a", "claim-1", 1) == (second,)
    assert first.semantic.relation is SemanticRelation.CONTRADICTS
    assert second.semantic.relation is SemanticRelation.QUALIFIES
    assert first.fidelity == second.fidelity


def test_reassessment_against_different_quote_recomputes_fidelity() -> None:
    ledger, finding, anchor = rig()
    first = add(ledger, finding, anchor)
    second = add(ledger, finding, anchor, revision=2, quote="Payment was received")
    assert first.expected_content_sha256_hex != second.expected_content_sha256_hex
    assert first.fidelity.content_fidelity is ContentFidelity.MATCHED
    assert second.fidelity.content_fidelity is ContentFidelity.MISMATCHED


@pytest.mark.parametrize("bad", [0, -1, True, 1.0])
def test_bad_assessment_revision_fails(bad: object) -> None:
    ledger, finding, anchor = rig()
    with pytest.raises(FindingLinkError):
        ledger.append_assessment(
            "tenant-a", "link-a", bad, finding, anchor, ExactQuote("Payment NOT received"),
            proposal(),
        )  # type: ignore[arg-type]


def test_duplicate_or_skipped_link_revisions_cannot_replace_history() -> None:
    ledger, finding, anchor = rig()
    first = add(ledger, finding, anchor)
    for rev in (1, 3):
        with pytest.raises(FindingLinkConflict):
            add(ledger, finding, anchor, revision=rev)
    assert ledger.link_history("tenant-a", "link-a") == (first,)


def test_link_id_cannot_be_moved_to_another_anchor_or_finding() -> None:
    ledger, finding, anchor = rig()
    add(ledger, finding, anchor)
    with pytest.raises(FindingLinkConflict, match="move"):
        add(ledger, finding, replace(anchor, locator=TextSpan(1, 4)), revision=2)
    other = FindingStatement("claim-other", 1, "Different finding.")
    ledger.register_statement("tenant-a", other)
    with pytest.raises(FindingLinkConflict, match="move"):
        add(ledger, other, anchor, revision=2)


def test_statement_revision_changes_require_new_link_and_reassessment() -> None:
    ledger, finding, anchor = rig()
    first = add(ledger, finding, anchor)
    updated = FindingStatement("claim-1", 2, "Payment was NOT received.")
    ledger.register_statement("tenant-a", updated)
    assert ledger.links_for_statement("tenant-a", "claim-1", 2) == ()
    with pytest.raises(FindingLinkConflict, match="superseded"):
        add(ledger, finding, anchor, revision=2)
    with pytest.raises(FindingLinkConflict, match="move"):
        add(ledger, updated, anchor, revision=2)
    fresh = add(ledger, updated, anchor, link="link-updated")
    assert fresh.statement == updated
    assert fresh.fidelity.finding == FindingRevision("claim-1", "2")
    assert ledger.link_history("tenant-a", "link-a") == (first,)


def test_finding_version_cannot_be_overwritten_or_skipped() -> None:
    ledger, first, _ = rig()
    with pytest.raises(FindingLinkConflict):
        ledger.register_statement("tenant-a", first)
    with pytest.raises(FindingLinkConflict):
        ledger.register_statement("tenant-a", FindingStatement("claim-1", 3, "Skipped"))
    with pytest.raises(FindingLinkConflict):
        ledger.register_statement("tenant-a", FindingStatement("claim-1", 1, "Forgery"))
    ledger.register_statement("tenant-a", FindingStatement("claim-1", 2, "Changed"))


def test_matching_quote_against_unregistered_finding_is_rejected() -> None:
    ledger, _, anchor = rig()
    with pytest.raises(FindingLinkNotFound):
        add(ledger, FindingStatement("unknown", 1, "Unknown."), anchor)


def test_same_version_but_changed_statement_is_rejected() -> None:
    ledger, _, anchor = rig()
    tampered = FindingStatement("claim-1", 1, "Altered while reusing revision.")
    with pytest.raises(FindingLinkConflict):
        add(ledger, tampered, anchor)


def test_forged_fidelity_is_not_accepted_as_write_input() -> None:
    ledger, finding, anchor = rig()
    result = add(ledger, finding, anchor)
    # No method takes a caller-supplied FidelityAssessment: re-evaluated against bytes.
    assert "fidelity" not in ledger.append_assessment.__code__.co_varnames[
        :ledger.append_assessment.__code__.co_argcount
    ]
    with pytest.raises(FindingLinkError):
        ledger.append_assessment(
            "tenant-a", "link-b", 1, finding, anchor, result.fidelity, proposal()
        )  # type: ignore[arg-type]


def test_cross_tenant_scope_hides_statements_and_links() -> None:
    ledger, finding, anchor = rig()
    add(ledger, finding, anchor)
    with pytest.raises(FindingLinkNotFound):
        ledger.get_statement("tenant-b", "claim-1", 1)
    with pytest.raises(FindingLinkNotFound):
        ledger.link_history("tenant-b", "link-a")
    with pytest.raises(FindingLinkNotFound):
        ledger.links_for_statement("tenant-b", "claim-1", 1)
    with pytest.raises(FindingLinkNotFound):
        add(ledger, finding, anchor, tenant="tenant-b")


def test_tenant_specific_same_keys_do_not_cross_pollinate() -> None:
    ledger, finding, anchor = rig()
    first = add(ledger, finding, anchor)
    ledger.register_statement("tenant-b", FindingStatement("claim-1", 1, "B's finding"))
    # Tenant B has no source representation. It receives no leak from tenant A.
    assert ledger.links_for_statement("tenant-b", "claim-1", 1) == ()
    assert ledger.link_history("tenant-a", "link-a") == (first,)


def test_conflicting_source_does_not_disappear_due_to_supporting_source() -> None:
    ledger, finding, anchor = rig()
    conflict = add(ledger, finding, anchor, link="conflict")
    support = add(
        ledger, finding, anchor, link="support",
        semantic=proposal(relation=SemanticRelation.SUPPORTS,
                          sufficiency=LinkSufficiency.SUFFICIENT),
    )
    collected = ledger.links_for_statement("tenant-a", "claim-1", 1)
    assert collected == (conflict, support)
    assert {item.semantic.relation for item in collected} == {
        SemanticRelation.CONTRADICTS, SemanticRelation.SUPPORTS
    }
    assert not hasattr(ledger, "promote")


def test_semantic_proposal_cannot_mutate_and_keeps_rationale_out_of_repr() -> None:
    assessment = proposal(rationale="private underlying reasoning")
    assert "private underlying reasoning" not in repr(assessment)
    with pytest.raises(FrozenInstanceError):
        assessment.relation = SemanticRelation.SUPPORTS  # type: ignore[misc]


@pytest.mark.parametrize(
    "changes",
    [
        {"relation": "supports"},
        {"sufficiency": "sufficient"},
        {"assessor_kind": "human"},
        {"assessor_reference": ""},
        {"assessment_method_version": " "},
        {"rationale": ""},
        {"assessed_at": datetime(2026, 10, 21)},
        {"assessed_at": STAMP.astimezone(timezone(timedelta(hours=2)))},
    ],
)
def test_invalid_proposal_provenance_or_untyped_states_fail_closed(
    changes: dict[str, object],
) -> None:
    with pytest.raises(FindingLinkError):
        replace(proposal(), **changes)


def test_statement_is_immutable_and_not_exposed_in_repr() -> None:
    f = FindingStatement("claim", 1, "highly private customer statement")
    assert "highly private customer statement" not in repr(f)
    assert f.statement_sha256_hex == digest(f.text.encode("utf-8"))
    with pytest.raises(FrozenInstanceError):
        f.revision = 2  # type: ignore[misc]


def test_link_revision_rejects_finding_fidelity_mismatch_and_bad_hash() -> None:
    ledger, finding, anchor = rig()
    valid = add(ledger, finding, anchor)
    with pytest.raises(FindingLinkError):
        replace(valid, statement=FindingStatement("another-claim", 1, "Different"))
    with pytest.raises(FindingLinkError):
        replace(valid, expected_content_sha256_hex="not-a-hash")
    with pytest.raises(FindingLinkError):
        replace(valid, assessment_revision=0)


def test_typed_expectation_fingerprint_distinguishes_boolean_number_and_string() -> None:
    from packages.evidence_kernel.domain.finding_links import _expected_digest

    assert _expected_digest(ExactJsonScalar(True)) != _expected_digest(ExactJsonScalar(1))
    assert _expected_digest(ExactJsonScalar(1)) != _expected_digest(ExactJsonScalar("1"))
    assert _expected_digest(ExactJsonScalar(None)) != _expected_digest(ExactJsonScalar("null"))
    assert _expected_digest(ExactQuote("abc")) != _expected_digest(ExactJsonScalar("abc"))


def test_missing_scope_and_unavailable_link_fail_closed() -> None:
    ledger, finding, anchor = rig()
    for tenant in ("", " "):
        with pytest.raises(FindingLinkError, match="scope"):
            ledger.register_statement(tenant, FindingStatement("another", 1, "X"))
        with pytest.raises(FindingLinkError, match="scope"):
            add(ledger, finding, anchor, tenant=tenant)
        with pytest.raises(FindingLinkError, match="scope"):
            ledger.link_history(tenant, "missing")
    with pytest.raises(FindingLinkNotFound):
        ledger.link_history("tenant-a", "missing")


def test_legacy_v1_and_fidelity_v1_remain_independent() -> None:
    from packages.evidence_kernel.domain.evidence import SourceReference
    from packages.evidence_kernel.domain.workflow import DocumentVersion

    ledger, finding, anchor = rig()
    link = add(ledger, finding, anchor)
    assert SourceReference("doc", digest(RAW), "quote").document_id == "doc"
    assert DocumentVersion("doc", "v1", digest(b"old"), "old").version_id == "v1"
    assert link.fidelity.semantic_relation == "not_assessed"
    assert link.fidelity.sufficiency == "not_assessed"
