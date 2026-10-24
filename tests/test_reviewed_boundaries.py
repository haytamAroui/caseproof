"""Governed discovery approval: persisted review event -> future scoped extraction.

Only independently authorized reviewer events can narrow existing unconfirmed
boundaries. A boundary confirmation never promotes semantic/financial authority.
"""

from dataclasses import replace
from uuid import UUID

import pytest

from application.documents.intake import CapturedDocument, DocumentIntelligence, EntityAssignment
from application.extraction.analysis import confirmed_boundaries_from_audit
from application.extraction.contracts import ExtractionError, Scope
from application.extraction.journal import MemoryJournal
from application.review.contracts import ReviewCommand, ReviewKind, freeze_review
from application.review.memory import MemoryReviewRepository
from domains.finance.extraction_rules import FinanceEvidencePolicy
from infrastructure.parsers.limited import LimitedDocumentParser
from scripts.extraction_fixtures import SCOPE, ScriptedProvider, atom, envelope, request


ACTOR = UUID(int=301)


def discovery_material():
    req = request()
    req = replace(req, entities=(replace(req.entities[0], confirmed=False),))
    proposal = {
        "entity_id": "E1", "kind": "invoice", "source_id": "synthetic",
        "quote": req.sources[0].content,
    }
    provider = ScriptedProvider(envelope([atom(req)], entities=[proposal]))
    result = DocumentIntelligence(
        LimitedDocumentParser(), provider, MemoryJournal(), FinanceEvidencePolicy()
    ).run(
        scope=req.scope,
        run_id="boundary-proposals",
        documents=(CapturedDocument("synthetic", req.sources[0].source),),
        assignments=(EntityAssignment("E1", "invoice", "synthetic", confirmed=False),),
        slots=req.slots,
    )
    assert result.extraction is not None
    snap = freeze_review(
        result, scope=req.scope, title="Synthetic boundary review",
        case_revision=1, policy_version="boundary-test-v1",
    )
    return req, result, snap


def test_persisted_confirmation_controls_future_run_not_existing_review():
    req, result, snap = discovery_material()
    discovery = next(d for d in result.extraction.discoveries if d["category"] == "entities")
    repo = MemoryReviewRepository()
    repo.publish(snap, ACTOR)
    command = ReviewCommand(
        UUID(int=124), snap.snapshot_hash, 0, discovery["id"],
        ReviewKind.CONFIRM_BOUNDARY, "I reviewed the preserved evidence span",
    )
    receipt = repo.record(req.scope, ACTOR, command)
    state = repo.state(req.scope, ACTOR)
    assert state["approved"] is False
    assert repo.record(req.scope, ACTOR, command)["replayed"] is True
    assert receipt["revision"] == 1
    revised = confirmed_boundaries_from_audit(
        req, result.extraction.discoveries, state,
        authorize=lambda scope, review_hash: scope == SCOPE and review_hash == receipt["audit_hash"],
    )
    assert revised.entities[0].confirmed
    assert req.entities[0].confirmed is False
    assert snap.data["extraction"]["atoms"][0]["reason"] == "unconfirmed_entity_boundary"


def test_boundary_rejection_does_not_narrow_and_invalid_item_denied():
    req, result, snap = discovery_material()
    repo = MemoryReviewRepository()
    repo.publish(snap, ACTOR)
    proposal = result.extraction.discoveries[0]["id"]
    invalid = ReviewCommand(
        UUID(int=127), snap.snapshot_hash, 0, "not-an-entity",
        ReviewKind.CONFIRM_BOUNDARY, "Fake evidence",
    )
    with pytest.raises(ExtractionError, match="proposal"):
        repo.record(req.scope, ACTOR, invalid)
    valid = replace(invalid, request_id=UUID(int=128), item_id=proposal, kind=ReviewKind.REJECT_BOUNDARY)
    repo.record(req.scope, ACTOR, valid)
    after = confirmed_boundaries_from_audit(
        req, result.extraction.discoveries, repo.state(req.scope, ACTOR),
        authorize=lambda s, h: s == req.scope,
    )
    assert after == req


def test_replay_rejects_unauthorized_actor_and_tampered_audit_chain():
    req, result, snap = discovery_material()
    repo = MemoryReviewRepository()
    repo.publish(snap, ACTOR)
    pid = result.extraction.discoveries[0]["id"]
    repo.record(
        req.scope, ACTOR,
        ReviewCommand(UUID(int=223), snap.snapshot_hash, 0, pid, ReviewKind.CONFIRM_BOUNDARY, "Verified"),
    )
    state = repo.state(req.scope, ACTOR)
    with pytest.raises(ExtractionError, match="authorized"):
        confirmed_boundaries_from_audit(
            req, result.extraction.discoveries, state, authorize=lambda s, h: False
        )
    changed = {**state, "audit_head": "f" * 64}
    with pytest.raises(ExtractionError, match="audit"):
        confirmed_boundaries_from_audit(
            req, result.extraction.discoveries, changed, authorize=lambda s, h: True
        )
    other = replace(req, scope=Scope(UUID(int=101), UUID(int=999)))
    with pytest.raises(ExtractionError):
        confirmed_boundaries_from_audit(
            other, result.extraction.discoveries, state, authorize=lambda s, h: True
        )


def test_boundary_snapshot_fail_closed_on_unconfirmed_original():
    req, result, snap = discovery_material()
    proposal = result.extraction.discoveries[0]["id"]
    # An existing confirmed boundary cannot be superseded by a model suggestion.
    altered = replace(req, entities=(replace(req.entities[0], confirmed=True),))
    repo = MemoryReviewRepository()
    repo.publish(snap, ACTOR)
    repo.record(
        req.scope, ACTOR,
        ReviewCommand(UUID(int=300), snap.snapshot_hash, 0, proposal, ReviewKind.CONFIRM_BOUNDARY, "Review"),
    )
    with pytest.raises(ExtractionError):
        confirmed_boundaries_from_audit(
            altered, result.extraction.discoveries, repo.state(req.scope, ACTOR),
            authorize=lambda s, h: True,
        )
