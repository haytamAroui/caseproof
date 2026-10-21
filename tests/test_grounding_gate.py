"""KRN-105: deterministic evidence-grounding gate and adversarial snapshots."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from hashlib import sha256

import pytest

from packages.evidence_kernel.domain.anchors import AnchorResolver, EvidenceAnchor, TextSpan
from packages.evidence_kernel.domain.fidelity import ExactQuote, FidelityEvaluator
from packages.evidence_kernel.domain.finding_links import (
    AssessorKind,
    FindingLinkError,
    FindingLinkNotFound,
    FindingStatement,
    InMemoryFindingEvidenceLedger,
    LinkSufficiency,
    SemanticAssessmentProposal,
    SemanticRelation,
)
from packages.evidence_kernel.domain.grounding import (
    GroundingEvaluation,
    GroundingGate,
    GroundingPolicy,
    GroundingReason,
    GroundingSnapshot,
)
from packages.evidence_kernel.domain.source_versions import (
    DerivedRepresentation,
    InMemorySourceRegistry,
    SourceVersion,
)

NOW = datetime(2026, 10, 21, 18, tzinfo=UTC)
ORIGINAL = b"private original document bytes"
TEXT = "Approved by Alice. Payment NOT received."


def sha(value: bytes) -> str:
    return sha256(value).hexdigest()


def setup() -> tuple[
    GroundingGate, InMemoryFindingEvidenceLedger, FindingStatement, EvidenceAnchor
]:
    sources = InMemorySourceRegistry()
    source = SourceVersion(
        "doc", "v1", sha(ORIGINAL), ORIGINAL, NOW, "application/pdf",
    )
    raw = TEXT.encode("utf-8")
    representation = DerivedRepresentation(
        "rep", "doc", "v1", source.sha256_hex, sha(raw), raw,
        "text/plain", "parser", "1", sha(b"config"),
        "unicode_codepoint_zero_based_half_open", NOW,
    )
    sources.register_source("tenant", source)
    sources.register_representation("tenant", representation)
    ledger = InMemoryFindingEvidenceLedger(FidelityEvaluator(AnchorResolver(sources)))
    finding = FindingStatement("f1", 1, "Payment was received.")
    ledger.register_statement("tenant", finding)
    anchor = EvidenceAnchor(
        "a1", "doc", "v1", source.sha256_hex,
        "rep", representation.sha256_hex, TextSpan(0, 8),
    )
    return GroundingGate(ledger), ledger, finding, anchor


def assessment(
    *,
    relation: SemanticRelation = SemanticRelation.CONTRADICTS,
    actor: AssessorKind = AssessorKind.DETERMINISTIC,
    sufficiency: LinkSufficiency = LinkSufficiency.NOT_ASSESSED,
) -> SemanticAssessmentProposal:
    return SemanticAssessmentProposal(
        relation, sufficiency, actor, "assessment-1", "method-1",
        "Recorded without claiming factual truth.", NOW,
    )


def link(
    ledger: InMemoryFindingEvidenceLedger,
    statement: FindingStatement,
    anchor: EvidenceAnchor,
    *,
    link_id: str = "l1",
    revision: int = 1,
    quote: str = "Approved",
    relation: SemanticRelation = SemanticRelation.CONTRADICTS,
    actor: AssessorKind = AssessorKind.DETERMINISTIC,
) -> None:
    ledger.append_assessment(
        "tenant", link_id, revision, statement, anchor, ExactQuote(quote),
        assessment(relation=relation, actor=actor),
    )


def evaluate(gate: GroundingGate, policy: GroundingPolicy | None = None) -> GroundingEvaluation:
    return gate.evaluate("tenant", gate.snapshot("tenant", "f1"), policy or GroundingPolicy("p1"))


def test_candidate_unanchored_is_ineligible_without_mutation() -> None:
    gate, _, finding, _ = setup()
    result = evaluate(gate)
    assert not result.eligible
    assert result.reason_codes == (GroundingReason.NO_LINKS,)
    assert result.snapshot.statement_sha256_hex == finding.statement_sha256_hex
    assert not hasattr(gate, "promote")
    assert not hasattr(gate, "approve")


def test_matching_quote_which_contradicts_false_finding_can_be_grounded_not_approved() -> None:
    gate, ledger, finding, anchor = setup()
    link(ledger, finding, anchor)
    result = evaluate(gate)
    assert result.eligible
    assert result.reason_codes == (GroundingReason.ELIGIBLE,)
    assert result.assessed_link_ids == ("l1",)
    assert result.current_contradiction_ids == ("l1",)
    assert result.historical_contradiction_ids == ("l1",)
    assert result.policy_version == "p1"
    assert not hasattr(result, "approved")
    assert ledger.latest_statement("tenant", "f1").revision == 1


def test_model_only_proposal_cannot_satisfy_default_policy_even_if_fidelity_matches() -> None:
    gate, ledger, finding, anchor = setup()
    link(ledger, finding, anchor, actor=AssessorKind.MODEL, relation=SemanticRelation.SUPPORTS)
    result = evaluate(gate)
    assert not result.eligible
    assert GroundingReason.UNTRUSTED_ASSESSOR in result.reason_codes
    assert result.assessed_link_ids == ()


def test_inconclusive_or_qualified_is_assessed_but_never_approved() -> None:
    for relation in (SemanticRelation.INCONCLUSIVE, SemanticRelation.QUALIFIES):
        gate, ledger, finding, anchor = setup()
        link(ledger, finding, anchor, relation=relation)
        result = evaluate(gate)
        assert result.eligible
        assert result.current_contradiction_ids == ()
        assert not hasattr(result, "promoted_state")


def test_not_assessed_semantic_is_not_a_grounding_assessment() -> None:
    gate, ledger, finding, anchor = setup()
    link(ledger, finding, anchor, relation=SemanticRelation.NOT_ASSESSED)
    result = evaluate(gate)
    assert not result.eligible
    assert GroundingReason.SEMANTIC_NOT_ASSESSED in result.reason_codes
    assert GroundingReason.INSUFFICIENT_LINKS in result.reason_codes


def test_missing_quote_or_out_of_bounds_locator_blocks_even_supporting_label() -> None:
    for a, expected in ((None, "Rejected"), (TextSpan(0, 500), "Approved")):
        gate, ledger, finding, anchor = setup()
        if a is not None:
            anchor = replace(anchor, locator=a)
        link(ledger, finding, anchor, quote=expected, relation=SemanticRelation.SUPPORTS)
        result = evaluate(gate)
        assert not result.eligible
        assert GroundingReason.FIDELITY_NOT_MATCHED in result.reason_codes


def test_known_wrong_source_hash_remains_ineligible() -> None:
    gate, ledger, finding, anchor = setup()
    anchor = replace(anchor, source_sha256_hex="f" * 64)
    link(ledger, finding, anchor, relation=SemanticRelation.SUPPORTS)
    result = evaluate(gate)
    assert not result.eligible
    assert GroundingReason.CITATION_UNAVAILABLE in result.reason_codes
    assert GroundingReason.FIDELITY_NOT_MATCHED in result.reason_codes


def test_source_removed_after_assessment_fails_current_resolution() -> None:
    gate, ledger, finding, anchor = setup()
    link(ledger, finding, anchor, relation=SemanticRelation.SUPPORTS)
    assert evaluate(gate).eligible
    # Simulate data loss / access revocation in the in-memory reference only.
    ledger.evaluator.resolver.sources._representations.pop(("tenant", "rep"))
    result = evaluate(gate)
    assert not result.eligible
    assert GroundingReason.CITATION_UNAVAILABLE in result.reason_codes


def test_all_current_links_in_snapshot_are_checked_no_cherry_picking() -> None:
    gate, ledger, finding, anchor = setup()
    link(ledger, finding, anchor, link_id="l1", relation=SemanticRelation.SUPPORTS)
    link(ledger, finding, replace(anchor, anchor_id="a2", locator=TextSpan(0, 800)),
         link_id="l2", relation=SemanticRelation.SUPPORTS)
    result = evaluate(gate)
    assert not result.eligible
    assert result.snapshot.link_revisions == (("l1", 1), ("l2", 1))
    assert result.assessed_link_ids == ("l1",)
    assert GroundingReason.FIDELITY_NOT_MATCHED in result.reason_codes


def test_scope_snapshot_missing_a_link_cannot_hide_contradiction() -> None:
    gate, ledger, finding, anchor = setup()
    link(ledger, finding, anchor, link_id="l1", relation=SemanticRelation.SUPPORTS)
    original = gate.snapshot("tenant", "f1")
    link(ledger, finding, replace(anchor, anchor_id="a2"),
         link_id="l2", relation=SemanticRelation.CONTRADICTS)
    result = gate.evaluate("tenant", original, GroundingPolicy("p1"))
    assert not result.eligible
    assert result.reason_codes == (GroundingReason.STALE_LINKS,)


def test_reassessment_invalidates_old_optimistic_snapshot() -> None:
    gate, ledger, finding, anchor = setup()
    link(ledger, finding, anchor)
    first = gate.snapshot("tenant", "f1")
    link(ledger, finding, anchor, revision=2, relation=SemanticRelation.SUPPORTS)
    result = gate.evaluate("tenant", first, GroundingPolicy("p1"))
    assert result.reason_codes == (GroundingReason.STALE_LINKS,)
    current = evaluate(gate)
    assert current.eligible
    assert current.current_contradiction_ids == ()
    assert current.historical_contradiction_ids == ("l1",)


def test_new_statement_revision_invalidates_old_snapshot_even_with_same_quote() -> None:
    gate, ledger, finding, anchor = setup()
    link(ledger, finding, anchor)
    previous = gate.snapshot("tenant", "f1")
    ledger.register_statement("tenant", FindingStatement("f1", 2, "Revised statement."))
    result = gate.evaluate("tenant", previous, GroundingPolicy("p1"))
    assert result.reason_codes == (GroundingReason.STALE_STATEMENT,)
    assert evaluate(gate).reason_codes == (GroundingReason.NO_LINKS,)


def test_multi_link_policy_requires_explicit_minimum_qualifying_count() -> None:
    gate, ledger, finding, anchor = setup()
    link(ledger, finding, anchor, relation=SemanticRelation.SUPPORTS)
    policy = GroundingPolicy("p2", min_assessed_links=2)
    assert GroundingReason.INSUFFICIENT_LINKS in evaluate(gate, policy).reason_codes
    link(ledger, finding, replace(anchor, anchor_id="a2", locator=TextSpan(0, 8)),
         link_id="l2", relation=SemanticRelation.QUALIFIES)
    result = evaluate(gate, policy)
    assert result.eligible
    assert result.assessed_link_ids == ("l1", "l2")
    assert result.policy_version == "p2"


def test_policy_can_restrict_to_human_claimed_assessments_but_not_verify_human() -> None:
    gate, ledger, finding, anchor = setup()
    link(ledger, finding, anchor, actor=AssessorKind.DETERMINISTIC)
    restricted = GroundingPolicy("human-only", allowed_assessors=(AssessorKind.HUMAN,))
    assert GroundingReason.UNTRUSTED_ASSESSOR in evaluate(gate, restricted).reason_codes
    # A HUMAN label is a *claim*: this reference cannot establish real auth.
    next_finding = FindingStatement("f1", 2, "Human claimed.")
    ledger.register_statement("tenant", next_finding)
    link(ledger, next_finding, anchor, link_id="new", actor=AssessorKind.HUMAN)
    assert evaluate(gate, restricted).eligible


def test_model_cannot_be_made_authoritative_by_editing_the_policy() -> None:
    for kinds in ((AssessorKind.MODEL,), (AssessorKind.HUMAN, AssessorKind.MODEL)):
        with pytest.raises(FindingLinkError, match="model"):
            GroundingPolicy("p", allowed_assessors=kinds)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"version": ""},
        {"min_assessed_links": 0},
        {"min_assessed_links": -1},
        {"min_assessed_links": True},
        {"allowed_assessors": ()},
        {"allowed_assessors": ("human",)},
        {"allowed_assessors": (AssessorKind.HUMAN, AssessorKind.HUMAN)},
    ],
)
def test_bad_grounding_policy_is_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(FindingLinkError):
        GroundingPolicy(**{"version": "p1", **kwargs})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"finding_id": ""},
        {"statement_revision": 0},
        {"statement_revision": False},
        {"statement_sha256_hex": "xyz"},
        {"link_revisions": (("z", 1), ("a", 1))},
        {"link_revisions": (("a", 1), ("a", 2))},
        {"link_revisions": (("a", 0),)},
        {"link_revisions": (("a", True),)},
        {"link_revisions": (("", 1),)},
        {"link_revisions": [("a", 1)]},
    ],
)
def test_malformed_frozen_snapshot_is_rejected(kwargs: dict[str, object]) -> None:
    defaults: dict[str, object] = {
        "finding_id": "f", "statement_revision": 1,
        "statement_sha256_hex": "a" * 64, "link_revisions": (),
    }
    with pytest.raises(FindingLinkError):
        GroundingSnapshot(**{**defaults, **kwargs})  # type: ignore[arg-type]


def test_direct_forged_mismatched_eligibility_result_is_rejected() -> None:
    gate, _, _, _ = setup()
    snapshot = gate.snapshot("tenant", "f1")
    with pytest.raises(FindingLinkError):
        GroundingEvaluation(snapshot, "p", True, (GroundingReason.NO_LINKS,), (), (), ())
    with pytest.raises(FindingLinkError):
        GroundingEvaluation(snapshot, "p", False, (GroundingReason.ELIGIBLE,), (), (), ())


def test_evaluation_does_not_mutate_state_or_authorize_external_actions() -> None:
    gate, ledger, finding, anchor = setup()
    link(ledger, finding, anchor, relation=SemanticRelation.SUPPORTS)
    before = ledger.link_history("tenant", "l1")
    first, second = evaluate(gate), evaluate(gate)
    assert first == second
    assert first.eligible
    assert ledger.link_history("tenant", "l1") == before
    assert not hasattr(gate, "commit")
    assert not hasattr(gate, "notify")
    assert not hasattr(gate, "approve")
    with pytest.raises(FrozenInstanceError):
        first.eligible = False  # type: ignore[misc]


def test_tenant_scope_cannot_read_another_tenants_finding() -> None:
    gate, ledger, finding, anchor = setup()
    link(ledger, finding, anchor)
    with pytest.raises(FindingLinkNotFound):
        gate.snapshot("other", "f1")
    with pytest.raises(FindingLinkNotFound):
        gate.evaluate("other", gate.snapshot("tenant", "f1"), GroundingPolicy("p1"))
    with pytest.raises(FindingLinkError, match="scope"):
        gate.snapshot("", "f1")


def test_unknown_actors_and_stale_policy_are_not_authorization_claims() -> None:
    gate, ledger, finding, anchor = setup()
    link(ledger, finding, anchor, actor=AssessorKind.HUMAN)
    d = evaluate(gate, GroundingPolicy("unapproved-policy-v1"))
    assert d.eligible
    assert d.policy_version == "unapproved-policy-v1"
    assert not hasattr(d, "actor_authorized")
    assert not hasattr(d, "policy_effective")
    assert not hasattr(d, "committed")


def test_v1_workflow_contract_untouched() -> None:
    from packages.evidence_kernel.domain.evidence import SourceReference
    from packages.evidence_kernel.domain.workflow import DocumentVersion

    gate, _, _, _ = setup()
    assert gate.snapshot("tenant", "f1").link_revisions == ()
    assert SourceReference("doc", sha(ORIGINAL), "quote").document_id == "doc"
    assert DocumentVersion("doc", "v1", sha(b"legacy"), "legacy").version_id == "v1"
