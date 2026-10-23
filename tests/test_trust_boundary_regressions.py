"""Cross-boundary regressions: evidence eligibility is never business approval.

These tests intentionally use the reference ledgers only. They do not simulate
production authentication, persistent transactions or real-world completeness.
"""

from dataclasses import fields, is_dataclass, replace

from application.decision_ports import DecisionRequest, TrustedActor
from packages.evidence_kernel.domain.finding_links import SemanticRelation
from packages.evidence_kernel.domain.grounding import GroundingPolicy, GroundingReason
from test_coverage_ledger import fixture as coverage_fixture
from tests.test_coverage_ledger import errors as coverage_errors
from test_grounding_gate import link, setup


def test_support_and_contradiction_are_distinct_from_grounding_eligibility() -> None:
    for relation in (SemanticRelation.SUPPORTS, SemanticRelation.CONTRADICTS):
        gate, ledger, statement, anchor = setup()
        link(ledger, statement, anchor, relation=relation)
        result = gate.evaluate("tenant", gate.snapshot("tenant", "f1"), GroundingPolicy("p1"))
        assert result.eligible
        assert result.reason_codes == (GroundingReason.ELIGIBLE,)
        assert result.current_contradiction_ids == (
            ("l1",) if relation is SemanticRelation.CONTRADICTS else ()
        )
        assert not hasattr(result, "approved")


def test_old_snapshot_cannot_hide_a_new_contradictory_link() -> None:
    gate, ledger, statement, anchor = setup()
    link(ledger, statement, anchor, relation=SemanticRelation.SUPPORTS)
    previous = gate.snapshot("tenant", "f1")
    link(
        ledger, statement, replace(anchor, anchor_id="second-anchor"),
        link_id="second-link", relation=SemanticRelation.CONTRADICTS,
    )
    result = gate.evaluate("tenant", previous, GroundingPolicy("p1"))
    assert not result.eligible
    assert result.reason_codes == (GroundingReason.STALE_LINKS,)


def test_declared_coverage_is_not_a_world_completeness_or_approval_certificate() -> None:
    _, _, evaluator, manifest, _ = coverage_fixture()
    from packages.evidence_kernel.domain.coverage import CoveragePolicy

    evaluation = evaluator.evaluate("tenant", manifest, CoveragePolicy("coverage-v1"))
    assert evaluation.ordinary_complete
    assert not coverage_errors(evaluation)
    assert not hasattr(evaluation, "real_world_complete")
    assert not hasattr(evaluation, "approved")
    assert not hasattr(evaluation, "authorization")


def test_request_and_trusted_actor_are_data_not_self_authorizing_approval() -> None:
    actor = TrustedActor("untrusted-if-client-supplied", "org-1")
    request = DecisionRequest("case-1", "snapshot-digest", 1, "request-1")
    assert is_dataclass(actor) and is_dataclass(request)
    assert "verified" not in {field.name for field in fields(actor)}
    assert "approved" not in {field.name for field in fields(request)}
    assert not hasattr(request, "commit")
    assert not hasattr(actor, "approve")
