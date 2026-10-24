"""Synthetic behavior/authority tests. Scripted responses are not extraction accuracy evidence."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier
from uuid import UUID

import pytest

from application.extraction.contracts import (
    ClaimSlot,
    EntityScope,
    ExtractionConfig,
    ExtractionError,
    Scope,
    StepState,
    decode,
    digest,
)
from application.extraction.journal import MemoryJournal
from application.extraction.pipeline import EvidenceIntelligence, check_atom, project_to_kernel
from domains.construction.extraction_rules import ConstructionEvidencePolicy
from domains.finance.extraction_rules import FinanceEvidencePolicy
from scripts.extraction_fixtures import NOW, ScriptedProvider, atom, envelope, request, source

AT = NOW.isoformat()


@pytest.mark.parametrize("construction", [False, True])
@pytest.mark.parametrize("topology,calls", [("global_first", 2), ("segmented", 1), ("four_pass", 4)])
def test_shared_runtime_exact_kernel_projection_and_replay(construction, topology, calls):
    req = request(construction=construction, topology=topology)
    provider, journal = ScriptedProvider(), MemoryJournal()
    policy = ConstructionEvidencePolicy() if construction else FinanceEvidencePolicy()
    service = EvidenceIntelligence(provider, journal, policy)
    report = service.run(req)
    assert len(provider.calls) == calls
    assert len(report.atoms) == 1  # Four passes do not create four votes.
    assert report.atoms[0].state == "validated"
    assert report.extraction_complete and not report.coverage_complete and not report.approved
    assert report.slots[0]["state"] == "unverified"
    projection = project_to_kernel(req, report)
    assert not projection.ordinary_complete
    assert "link_sufficiency_unassessed" in projection.blockers
    assert service.run(req).to_json() == report.to_json()
    assert len(provider.calls) == calls


@pytest.mark.parametrize(
    "override,reason",
    [
        ({"source_id": "other"}, "source_not_in_manifest"),
        ({"entity_id": "other"}, "entity_or_claim_attribution_failed"),
        ({"slot": "other"}, "entity_or_claim_attribution_failed"),
        ({"quote": "Invoice I1: net EUR 1151.00."}, "quote_not_found"),
        ({"start": 1}, "invalid_exact_offset"),
        ({"start": True}, "invalid_exact_offset"),
        ({"start": -1}, "invalid_exact_offset"),
        ({"value": "115"}, "value_not_in_quote"),
        ({"signal": "conclusion_approved"}, "unregistered_signal"),
        ({"polarity": "negative"}, "qualified_or_untrusted_assertion"),
        ({"polarity": "conditional"}, "qualified_or_untrusted_assertion"),
        ({"polarity": "alleged"}, "qualified_or_untrusted_assertion"),
        ({"confidence": 1.0}, "invalid_atom_schema"),
        ({"approved": True}, "invalid_atom_schema"),
        ({"polarity": "approved"}, "invalid_atom_schema"),
        ({"relation": "sufficient"}, "invalid_atom_schema"),
    ],
)
def test_per_item_guards(override, reason):
    req = request()
    item = check_atom(atom(req, **override), req, FinanceEvidencePolicy(), "test", AT)
    assert item.state != "validated"
    assert item.reason == reason


@pytest.mark.parametrize(
    "word", ["No", "Not", "Never", "If", "Unless", "Alleged", "Legal", "Article", "Ignore", "Approve"]
)
def test_lexical_qualification_cannot_be_overridden_by_affirmative_label(word):
    req = request(content=f"{word} invoice issued for 1150.00.")
    item = check_atom(atom(req), req, FinanceEvidencePolicy(), "test", AT)
    assert item.state == "needs_review"


def test_one_valid_and_four_invalid_never_approve_material_claim():
    req = request()
    bad = [atom(req, source_id=f"bad{i}") for i in range(4)]
    result = EvidenceIntelligence(
        ScriptedProvider(envelope([atom(req), *bad])), MemoryJournal(), FinanceEvidencePolicy()
    ).run(req)
    assert len([a for a in result.atoms if a.state == "validated"]) == 1
    assert len([a for a in result.atoms if a.state == "rejected"]) == 4
    assert not result.coverage_complete and not result.approved


def test_repeated_quote_requires_exact_disambiguation():
    quote = "Invoice 1150.00."
    req = request(content=quote + " " + quote)
    item = check_atom(atom(req, quote=quote), req, FinanceEvidencePolicy(), "test", AT)
    assert item.reason == "ambiguous_quote"
    located = check_atom(
        atom(req, quote=quote, start=len(quote) + 1), req, FinanceEvidencePolicy(), "test", AT
    )
    assert located.start == len(quote) + 1 and located.state == "validated"


def test_entity_scope_blocks_wrong_variation_even_with_exact_quote():
    req = request(construction=True)
    boundary = replace(req.entities[0], end=9)
    req = replace(req, entities=(boundary,))
    item = check_atom(atom(req), req, ConstructionEvidencePolicy(), "test", AT)
    assert item.reason == "entity_or_claim_attribution_failed"


@pytest.mark.parametrize(
    "confirmed,complete,reason",
    [(False, True, "unconfirmed_entity_boundary"), (True, False, "incomplete_representation")],
)
def test_boundary_or_representation_review(confirmed, complete, reason):
    req = request()
    req = replace(
        req,
        sources=(replace(req.sources[0], complete=complete),),
        entities=(replace(req.entities[0], confirmed=confirmed),),
    )
    result = EvidenceIntelligence(ScriptedProvider(), MemoryJournal(), FinanceEvidencePolicy()).run(req)
    assert result.atoms[0].reason == reason and not result.coverage_complete
    assert result.extraction_complete == complete


def test_zero_atoms_is_not_ordinary_complete():
    result = EvidenceIntelligence(
        ScriptedProvider(envelope([])), MemoryJournal(), FinanceEvidencePolicy()
    ).run(request())
    assert not result.extraction_complete
    assert result.slots[0]["state"] == "missing"
    assert result.failures[0]["reason"] == "zero_atoms_unresolved"


def test_conflicting_amounts_preserve_both_sources():
    req = request()
    second = source("revision", "Invoice I1: net EUR 1050.00.")
    req = replace(
        req,
        sources=(*req.sources, second),
        entities=(*req.entities, EntityScope("E1", "invoice", "revision", 0, len(second.content), True)),
        slots=(ClaimSlot("E1", "invoice_issued", ("synthetic", "revision")),),
    )
    values = [atom(req), atom(req, source_id="revision", quote=second.content, value="1050.00")]
    result = EvidenceIntelligence(
        ScriptedProvider(envelope(values)), MemoryJournal(), FinanceEvidencePolicy()
    ).run(req)
    assert result.conflicts
    assert result.slots[0]["state"] == "conflicting"
    assert {a.source_id for a in result.atoms if a.state == "validated"} == {"synthetic", "revision"}
    assert not result.approved


def test_discovery_proposals_cannot_confirm_entity_boundaries():
    req = request()
    req = replace(req, entities=(replace(req.entities[0], confirmed=False),))
    discoveries = [
        {"entity_id": "E1", "kind": "invoice", "source_id": "synthetic", "quote": req.sources[0].content}
    ]
    report = EvidenceIntelligence(
        ScriptedProvider(envelope([atom(req)], entities=discoveries)),
        MemoryJournal(),
        FinanceEvidencePolicy(),
    ).run(req)
    assert report.discoveries[0]["state"] == "proposed"
    assert report.atoms[0].reason == "unconfirmed_entity_boundary"


@pytest.mark.parametrize(
    "raw",
    [
        '{"entities":[],"entities":[],"relationships":[],"atoms":[]}',
        '{"atoms":[],"entities":[],"relationships":[],"approved":true}',
        '{"entities":[],"relationships":[],"atoms":NaN}',
        '{"entities":[],"relationships":[],"atoms":{}}',
    ],
)
def test_invalid_envelope_has_visible_failure(raw):
    provider = ScriptedProvider(raw)
    report = EvidenceIntelligence(provider, MemoryJournal(), FinanceEvidencePolicy()).run(request())
    assert not report.extraction_complete and len(provider.calls) == 1
    assert report.failures == ({"step": "scout", "reason": "extraction_failed"},)


def test_unknown_dispatch_never_retried_and_replay_stable():
    class Timeout(ScriptedProvider):
        def complete(self, *args, **kwargs):
            self.calls.append("timeout")
            raise TimeoutError("synthetic")

    provider = Timeout()
    service = EvidenceIntelligence(provider, MemoryJournal(), FinanceEvidencePolicy())
    report = service.run(request())
    assert report.failures[0]["reason"] == "outcome_unknown"
    assert service.run(request()).to_json() == report.to_json()
    assert len(provider.calls) == 1


def test_received_response_replays_after_crash_without_provider_call():
    class CrashAfterSave(MemoryJournal):
        crashed = False

        def transition(self, *args, **kwargs):
            result = super().transition(*args, **kwargs)
            if result.state is StepState.RECEIVED and not self.crashed:
                self.crashed = True
                raise RuntimeError("simulated process crash after committed receive")
            return result

    provider, journal = ScriptedProvider(), CrashAfterSave()
    service = EvidenceIntelligence(provider, journal, FinanceEvidencePolicy())
    with pytest.raises(RuntimeError):
        service.run(request())
    report = service.run(request())
    assert report.extraction_complete and len(provider.calls) == 2


def test_concurrent_dispatch_only_one_cas_winner():
    journal = MemoryJournal()
    req = request()
    row = journal.reserve(req.scope, "r", "s", digest({}))
    barrier = Barrier(2)

    def advance():
        barrier.wait()
        try:
            journal.transition(req.scope, "r", "s", row.state, StepState.DISPATCHED)
            return "dispatch"
        except ExtractionError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: advance(), range(2)))
    assert sorted(results) == ["conflict", "dispatch"]


def test_changed_input_and_cross_scope_projection_fail():
    req = request()
    journal = MemoryJournal()
    service = EvidenceIntelligence(ScriptedProvider(), journal, FinanceEvidencePolicy())
    report = service.run(req)
    changed = replace(req, sources=(replace(req.sources[0], complete=False),))
    with pytest.raises(ExtractionError, match="input changed"):
        service.run(changed)
    with pytest.raises(ExtractionError):
        project_to_kernel(changed, report)
    with pytest.raises(ExtractionError, match="scope"):
        project_to_kernel(replace(req, scope=Scope(UUID(int=102), UUID(int=202))), report)


def test_call_budget_preflight_and_repair_bound():
    req = request()
    provider = ScriptedProvider()
    service = EvidenceIntelligence(provider, MemoryJournal(), FinanceEvidencePolicy())
    with pytest.raises(ExtractionError, match="budget"):
        service.run(replace(req, config=ExtractionConfig(max_calls=1)))
    assert not provider.calls
    unknown = ScriptedProvider(envelope([atom(req, signal="unknown")]))
    report = EvidenceIntelligence(unknown, MemoryJournal(), FinanceEvidencePolicy()).run(
        replace(req, config=ExtractionConfig(max_calls=3, repair_passes=2))
    )
    assert len(unknown.calls) == 3 and len(report.atoms) == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_calls": True},
        {"max_concurrency": 5},
        {"max_calls": 65},
        {"repair_passes": 3},
        {"topology": "fallback"},
    ],
)
def test_invalid_execution_configuration(kwargs):
    with pytest.raises(ExtractionError):
        ExtractionConfig(**kwargs)


def test_inventory_rejects_unassigned_source_and_duplicate_alias():
    req = request()
    with pytest.raises(ExtractionError, match="assigned"):
        replace(req, sources=(*req.sources, source("extra", "Unused")))
    with pytest.raises(ExtractionError, match="aliases"):
        replace(req, sources=(*req.sources, replace(req.sources[0], source_id="alias")))


def test_candidate_telemetry_never_invents_usage_or_cost():
    result = EvidenceIntelligence(ScriptedProvider(), MemoryJournal(), FinanceEvidencePolicy()).run(request())
    assert all(t["cost"] is None and t["input_tokens"] is None for t in result.telemetry)


def test_duplicate_json_and_nonfinite_disallowed():
    for raw in ('{"x":1,"x":2}', '{"x":NaN}', "[]"):
        with pytest.raises(ExtractionError):
            decode(raw)


def test_concurrent_observer_cannot_freeze_winning_report():
    from threading import Event

    entered, release = Event(), Event()

    class Slow(ScriptedProvider):
        def complete(self, *args, **kwargs):
            if not self.calls:
                entered.set()
                assert release.wait(timeout=5)
            return super().complete(*args, **kwargs)

    provider, journal = Slow(), MemoryJournal()
    service = EvidenceIntelligence(provider, journal, FinanceEvidencePolicy())
    with ThreadPoolExecutor(max_workers=1) as pool:
        winner = pool.submit(service.run, request())
        assert entered.wait(timeout=5)
        provisional = service.run(request())
        assert not provisional.extraction_complete
        release.set()
        completed = winner.result(timeout=5)
    assert completed.extraction_complete and len(provider.calls) == 2
    assert service.run(request()).to_json() == completed.to_json()


def test_partial_entity_failure_is_visible_and_blocks_inventory():
    req = request(topology="segmented")
    req = replace(
        req,
        entities=(
            *req.entities,
            EntityScope("E2", "invoice", "synthetic", 0, len(req.sources[0].content), True),
        ),
        slots=(*req.slots, ClaimSlot("E2", "invoice_issued", ("synthetic",))),
    )

    class Partial(ScriptedProvider):
        def complete(self, system, payload, **kwargs):
            if decode(payload)["focus_entity"] == "E2":
                raise TimeoutError("synthetic second entity failure")
            return super().complete(system, payload, **kwargs)

    report = EvidenceIntelligence(Partial(), MemoryJournal(), FinanceEvidencePolicy()).run(req)
    assert not report.extraction_complete
    assert report.failures == ({"step": "entity:1", "reason": "outcome_unknown"},)
    assert "source_unaccounted" in project_to_kernel(req, report).blockers
    assert any(s["entity_id"] == "E2" and s["state"] == "missing" for s in report.slots)


@pytest.mark.parametrize(
    "value,quote",
    [
        ("1150", "Invoice 1150.00"),
        ("150.00", "Invoice 1150.00"),
        ("1150.00", "Invoice -1150.00"),
        ("1150.00", "Invoice 0.1150.00"),
    ],
)
def test_scalar_substrings_or_sign_loss_cannot_validate(value, quote):
    req = request(content=quote)
    item = check_atom(atom(req, value=value), req, FinanceEvidencePolicy(), "test", AT)
    assert item.state == "rejected" and item.reason == "value_not_in_quote"


@pytest.mark.parametrize("word", ["pas", "aucun", "jamais", "geen", "niet", "nooit", "tenzij"])
def test_french_dutch_qualification_stays_review_only(word):
    req = request(content=f"{word} invoice 1150.00")
    assert check_atom(atom(req), req, FinanceEvidencePolicy(), "test", AT).state == "needs_review"


def test_revision_bound_candidate_identity_changes_with_representation():
    req = request()
    item = check_atom(atom(req), req, FinanceEvidencePolicy(), "test", AT)
    changed_rep = replace(
        req.sources[0].representation,
        representation_id="new-parser-representation",
        content=req.sources[0].representation.content,
        transform_version="v2",
    )
    changed = replace(req, sources=(replace(req.sources[0], representation=changed_rep),))
    revised = check_atom(atom(changed), changed, FinanceEvidencePolicy(), "test", AT)
    # Same bytes but a new parser representation is a distinct evidence identity.
    assert item.candidate_id != revised.candidate_id


@pytest.mark.parametrize(
    "folder,module",
    [
        ("domains/finance", "domains.construction.extraction_rules"),
        ("domains/construction", "domains.finance.extraction_rules"),
        ("domains/construction", "application.extraction.pipeline"),
        ("application", "apps.api.requesty_extraction"),
    ],
)
def test_new_runtime_and_second_vocabulary_import_boundaries(folder, module):
    from scripts.check_architecture import RULES, scan_source

    assert scan_source(f"import {module}", filename=f"{folder}/bad.py", banned=RULES[folder])
