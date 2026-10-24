"""Regression tests for scout-guided targeting, explicit review and typed reconciliation."""

from dataclasses import replace
import pytest

from application.extraction.analysis import (
    BoundaryReview,
    confirm_reviewed_boundaries,
    evidence_matrix,
    reconcile_facts,
)
from application.extraction.contracts import EntityScope, ExtractionConfig, ExtractionError, ProviderReply, decode, digest
from application.extraction.journal import MemoryJournal
from application.extraction.pipeline import EvidenceIntelligence, check_atom
from domains.finance.extraction_rules import FinanceEvidencePolicy
from scripts.extraction_fixtures import NOW, SCOPE, ScriptedProvider, atom, envelope, request, source


def test_scout_guidance_affects_targeting_without_granting_boundary_authority():
    req = request()
    req = replace(req, entities=(replace(req.entities[0], confirmed=False),))
    discovery = {
        "entity_id": "E1", "kind": "invoice", "source_id": "synthetic",
        "quote": req.sources[0].content,
    }

    class Scout(ScriptedProvider):
        def __init__(self):
            super().__init__()
            self.payloads = []

        def complete(self, system, payload, *, request_id, max_tokens):
            data = decode(payload)
            self.payloads.append(data)
            body = envelope([atom(req)], entities=[discovery] if data["purpose"].startswith("case-wide") else [])
            return ProviderReply(body, self.identity, self.model)

    provider = Scout()
    report = EvidenceIntelligence(provider, MemoryJournal(), FinanceEvidencePolicy()).run(req)
    assert len(provider.payloads) == 2
    guidance = provider.payloads[1]["scout_guidance"]
    assert len(guidance) == 1 and guidance[0]["authority"] == "unconfirmed_discovery_only"
    assert guidance[0]["start"] == 0
    assert report.atoms[0].reason == "unconfirmed_entity_boundary"
    assert report.discoveries[0]["state"] == "proposed"
    assert not report.approved


def test_boundary_confirmation_requires_authorized_review_and_exact_frozen_bytes():
    req = request()
    req = replace(req, entities=(replace(req.entities[0], confirmed=False),))
    discovered = {
        "category": "entities", "id": digest({"entity_id": "E1", "kind": "invoice", "source_id": "synthetic", "quote": req.sources[0].content}), "state": "proposed", "start": 0,
        "proposal": {
            "entity_id": "E1", "kind": "invoice", "source_id": "synthetic",
            "quote": req.sources[0].content,
        },
    }
    decision = BoundaryReview(
        discovered["id"], "application-review-001", "confirm",
        req.sources[0].source.sha256_hex, req.sources[0].representation.sha256_hex,
    )
    with pytest.raises(ExtractionError, match="authorized"):
        confirm_reviewed_boundaries(req, (discovered,), (decision,), authorize=lambda s, r: False)
    approved = confirm_reviewed_boundaries(
        req, (discovered,), (decision,), authorize=lambda s, r: s == SCOPE and r == "application-review-001"
    )
    assert approved.entities[0].confirmed
    assert not req.entities[0].confirmed
    assert check_atom(atom(approved), approved, FinanceEvidencePolicy(), "test", NOW.isoformat()).state == "validated"
    with pytest.raises(ExtractionError, match="stale"):
        confirm_reviewed_boundaries(
            req, (discovered,), (replace(decision, source_sha256="0" * 64),),
            authorize=lambda s, r: True,
        )


def test_review_can_only_narrow_existing_entity_span():
    req = request(content="Introduction. Invoice I1: net EUR 1150.00.")
    req = replace(req, entities=(replace(req.entities[0], confirmed=False),))
    quote = "Invoice I1: net EUR 1150.00."
    offset = req.sources[0].content.index(quote)
    discovered = {
        "category": "entities", "id": digest({"entity_id": "E1", "kind": "invoice", "source_id": "synthetic", "quote": quote}), "state": "proposed", "start": offset,
        "proposal": {"entity_id": "E1", "kind": "invoice", "source_id": "synthetic", "quote": quote},
    }
    dec = BoundaryReview(
        discovered["id"], "authorized", "confirm",
        req.sources[0].source.sha256_hex, req.sources[0].representation.sha256_hex,
    )
    revised = confirm_reviewed_boundaries(req, (discovered,), (dec,), authorize=lambda s, r: True)
    assert (revised.entities[0].start, revised.entities[0].end) == (offset, offset + len(quote))
    assert check_atom(atom(revised, quote=req.sources[0].content), revised, FinanceEvidencePolicy(), "t", NOW.isoformat()).reason == "entity_or_claim_attribution_failed"


def test_amount_and_amendment_reconciliation_never_auto_supersedes():
    req = request()
    second = source("revision", "Invoice I1: revised net EUR 1050.00.")
    req = replace(
        req,
        sources=(*req.sources, second),
        entities=(*req.entities, EntityScope("E1", "invoice", "revision", 0, len(second.content), True)),
        slots=(replace(req.slots[0], source_ids=("synthetic", "revision")),),
        config=ExtractionConfig(repair_passes=0),
    )
    x = atom(req)
    y = atom(req, source_id="revision", quote=second.content, value="1050.00")
    report = EvidenceIntelligence(
        ScriptedProvider(envelope([x, y])), MemoryJournal(), FinanceEvidencePolicy()
    ).run(req)
    assert report.reconciliation[0]["kind"] == "amendment_requires_review"
    assert report.reconciliation[0]["auto_supersede"] is False
    assert report.slots[0]["state"] == "conflicting"
    assert len([row for row in report.signal_decisions if row["disposition"] == "validated"]) == 2
    assert all(row["level"] == "candidate_validation_not_semantic_support" for row in report.signal_decisions)
    assert report.evidence_matrix[0]["state"] == "conflicting"


def test_money_difference_and_noncomparable_currencies():
    req = request()
    second = source("second", "Invoice I1: net EUR 1050.00.")
    req = replace(
        req,
        sources=(*req.sources, second),
        entities=(*req.entities, EntityScope("E1", "invoice", "second", 0, len(second.content), True)),
        slots=(replace(req.slots[0], source_ids=("synthetic", "second")),),
    )
    first = check_atom(atom(req), req, FinanceEvidencePolicy(), "t", NOW.isoformat())
    latter = check_atom(
        atom(req, source_id="second", quote=second.content, value="1050.00"),
        req, FinanceEvidencePolicy(), "t", NOW.isoformat(),
    )
    classification = reconcile_facts((first, latter), ((first.candidate_id, latter.candidate_id),))
    assert classification[0]["kind"] == "monetary_difference"
    assert classification[0]["details"]["difference"] == "100.00"
    matrix = evidence_matrix(req, (first, latter), ((first.candidate_id, latter.candidate_id),))
    assert matrix[0]["repair_eligible"] is True


def test_repair_matrix_blocks_unconfirmed_boundaries():
    req = request()
    req = replace(req, entities=(replace(req.entities[0], confirmed=False),))
    item = check_atom(atom(req), req, FinanceEvidencePolicy(), "t", NOW.isoformat())
    row = evidence_matrix(req, (item,), ())
    assert row[0]["repair_eligible"] is False
    assert row[0]["human_review_required"] is True
