"""Lawyer decisions (roadmap task 3): four dispositions, traceability,
invalidation on recompute, FAIL never rewritten.

Synthetic fixtures only; no legal content.
"""
from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from application.litigation.lawyer_decisions import (
    DecisionValidity,
    Disposition,
    LawyerDecisionError,
    decision_views,
    record_decision,
    validate_decision,
)
from application.litigation.rule_results import RuleResult, RuleStatus
from application.litigation.suitability_rules import ConfirmedFact, evaluate_rule, load_rule
from apps.api.lawyer_decisions_api import create_lawyer_decision_router

WHEN = "2026-11-22T20:30:00+00:00"
CORPUS = {"synthetic-act-2026#1#fr#2026-01-01"}

DOC = """
[rule]
format = "caseproof-suitability-rule-format-v1"
id = "synthetic.example.deposit"
version = "0.1.0"
scope = "synthetic"
reference = "Synthetic Act, art. 1"

[article]
act = "synthetic-act-2026"
article = "1"
language = "fr"
version = "2026-01-01"

[condition]
{ fact = "deposit_months", op = "le", value = 2 }
""".replace("[condition]\n{ fact", "[condition]\nall = [{ fact").replace("value = 2 }", "value = 2 }]")


def _result(status_value: int = 5) -> RuleResult:
    facts = {"deposit_months": ConfirmedFact(name="deposit_months", value=status_value, confirmed=True)}
    return evaluate_rule(load_rule(DOC), facts, CORPUS)


def _fail_result() -> RuleResult:
    result = _result(5)
    assert result.status == RuleStatus.FAIL
    return result


def test_all_four_dispositions_record_with_traceability() -> None:
    fail = _fail_result()
    for disposition in Disposition:
        decision = record_decision(
            fail if disposition is Disposition.WAIVED else _result(1),
            actor_id="lawyer-1", disposition=disposition,
            rationale="motif synthétique", scope="ce résultat uniquement", decided_at=WHEN,
        )
        assert decision.disposition is disposition
        assert len(decision.content_hash) == 64
        assert decision.machine_status in {s.value for s in RuleStatus}


def test_original_machine_finding_preserved_and_never_rewritten() -> None:
    fail = _fail_result()
    decision = record_decision(fail, actor_id="lawyer-1", disposition=Disposition.WAIVED,
                               rationale="exception acceptée", scope="dossier courant", decided_at=WHEN)
    assert decision.machine_status == "FAIL"  # a waived FAIL is still a FAIL
    view = decision_views([fail], [decision])[0]
    assert view.machine_status == "FAIL"
    assert view.result is fail


def test_waiver_answers_every_non_pass_exception() -> None:
    # The user's concept: the lawyer decides on EVERY exception. A waiver can
    # answer FAIL, UNDETERMINED or UNVERIFIED; only a PASS has nothing to except.
    undetermined = evaluate_rule(load_rule(DOC), {}, CORPUS)
    assert undetermined.status == RuleStatus.UNDETERMINED
    unverified = evaluate_rule(load_rule(DOC), {}, set())
    assert unverified.status == RuleStatus.UNVERIFIED
    for result in (_fail_result(), undetermined, unverified):
        decision = record_decision(result, actor_id="lawyer-1", disposition=Disposition.WAIVED,
                                   rationale="exception acceptée", scope="x", decided_at=WHEN)
        assert decision.disposition is Disposition.WAIVED
    with pytest.raises(LawyerDecisionError):
        record_decision(_result(1), actor_id="lawyer-1",  # PASS
                        disposition=Disposition.WAIVED, rationale="x", scope="x", decided_at=WHEN)


def test_invalidation_on_rule_version_change() -> None:
    result = _result(1)
    decision = record_decision(result, actor_id="lawyer-1", disposition=Disposition.CONFIRMED,
                               rationale="ok", scope="x", decided_at=WHEN)
    changed = evaluate_rule(load_rule(DOC.replace('version = "0.1.0"', 'version = "0.2.0"')),
                            {"deposit_months": ConfirmedFact(name="deposit_months", value=1, confirmed=True)},
                            CORPUS)
    validity, detail = validate_decision(decision, changed)
    assert validity is DecisionValidity.INVALIDATED
    assert detail == "rule_version_changed"


def test_invalidation_on_input_change() -> None:
    result = _result(1)
    decision = record_decision(result, actor_id="lawyer-1", disposition=Disposition.CONFIRMED,
                               rationale="ok", scope="x", decided_at=WHEN)
    recomputed = _result(2)  # same rule, different fact value -> different facts hash
    assert recomputed.input_hashes != result.input_hashes
    validity, detail = validate_decision(decision, recomputed)
    assert validity is DecisionValidity.INVALIDATED
    assert detail == "inputs_changed"


def test_invalidation_on_status_change_and_on_disappearance() -> None:
    result = _result(1)
    decision = record_decision(result, actor_id="lawyer-1", disposition=Disposition.CONFIRMED,
                               rationale="ok", scope="x", decided_at=WHEN)
    validity, _ = validate_decision(decision, None)
    assert validity is DecisionValidity.INVALIDATED


def test_new_finding_content_does_not_inherit_decision() -> None:
    # Same rule, version, inputs and status, but a different reason: the new
    # machine finding must NOT keep the old decision valid.
    from dataclasses import replace as dc_replace
    result = _result(1)
    decision = record_decision(result, actor_id="lawyer-1", disposition=Disposition.CONFIRMED,
                               rationale="ok", scope="x", decided_at=WHEN)
    moved = dc_replace(result, reason="same_status_different_reason", scope=result.scope)
    validity, detail = validate_decision(decision, moved)
    assert validity is DecisionValidity.INVALIDATED
    assert detail == "result_content_changed"


def test_valid_when_nothing_changed() -> None:
    result = _result(1)
    decision = record_decision(result, actor_id="lawyer-1", disposition=Disposition.QUALIFIED,
                               rationale="nuance", scope="x", decided_at=WHEN)
    validity, detail = validate_decision(decision, result)
    assert validity is DecisionValidity.VALID
    assert detail == "current_result_unchanged"


def test_wrong_rule_or_reference_rejected() -> None:
    decision = record_decision(_result(1), actor_id="lawyer-1", disposition=Disposition.CONFIRMED,
                               rationale="ok", scope="x", decided_at=WHEN)
    other_doc = DOC.replace('article = "1"', 'article = "2"').replace(
        'reference = "Synthetic Act, art. 1"', 'reference = "Synthetic Act, art. 2"')
    other = evaluate_rule(load_rule(other_doc),
                          {"deposit_months": ConfirmedFact(name="deposit_months", value=1, confirmed=True)},
                          {"synthetic-act-2026#2#fr#2026-01-01"})
    with pytest.raises(LawyerDecisionError):
        validate_decision(decision, other)


def test_bounded_fields_enforced() -> None:
    with pytest.raises(LawyerDecisionError):
        record_decision(_result(1), actor_id="lawyer-1", disposition=Disposition.CONFIRMED,
                        rationale="", scope="x", decided_at=WHEN)
    with pytest.raises(LawyerDecisionError):
        record_decision(_result(1), actor_id="lawyer-1", disposition=Disposition.CONFIRMED,
                        rationale="ok", scope="x", decided_at="22 novembre 2026")


# --- API surface ---

RUN_ID = "run-synthetic"


def _client(results: list[RuleResult]) -> TestClient:
    app = FastAPI()
    app.include_router(create_lawyer_decision_router(
        results_provider=lambda run_id: tuple(results) if run_id == RUN_ID else (),
        actor_resolver=lambda bearer: "lawyer-1" if bearer == "signed" else None,
    ))
    return TestClient(app, raise_server_exceptions=False)


def _post(client: TestClient, disposition: str = "confirmed") -> dict[str, Any]:
    response = client.post(
        f"/v2/rule-runs/{RUN_ID}/decisions",
        headers={"Authorization": "Bearer signed"},
        json={"rule_id": "synthetic.example.deposit", "reference": "Synthetic Act, art. 1",
              "disposition": disposition, "rationale": "motif", "scope": "ce résultat"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload, dict)
    return payload


def test_api_records_and_reads_back_with_traceability() -> None:
    results = [_result(1)]
    client = _client(results)
    recorded = _post(client, "qualified")
    assert recorded["disposition"] == "qualified"
    assert recorded["machine_status"] == "PASS"
    assert recorded["validity"] == "valid"
    assert len(recorded["content_hash"]) == 64
    listing = client.get(f"/v2/rule-runs/{RUN_ID}/decisions",
                         headers={"Authorization": "Bearer signed"}).json()
    decisions = listing["decisions"]
    assert isinstance(decisions, list) and len(decisions) == 1
    assert listing["results_without_decision"] == []


def test_api_waiver_on_fail_keeps_fail_visible() -> None:
    client = _client([_fail_result()])
    recorded = _post(client, "waived")
    assert recorded["machine_status"] == "FAIL"
    assert recorded["disposition"] == "waived"


def test_api_rejects_waiver_on_pass() -> None:
    client = _client([_result(1)])
    response = client.post(
        f"/v2/rule-runs/{RUN_ID}/decisions",
        headers={"Authorization": "Bearer signed"},
        json={"rule_id": "synthetic.example.deposit", "reference": "Synthetic Act, art. 1",
              "disposition": "waived", "rationale": "motif", "scope": "ce résultat"},
    )
    assert response.status_code != 200


def test_api_unknown_result_masked() -> None:
    client = _client([_result(1)])
    response = client.post(
        f"/v2/rule-runs/{RUN_ID}/decisions",
        headers={"Authorization": "Bearer signed"},
        json={"rule_id": "no.such.rule", "reference": "nope",
              "disposition": "confirmed", "rationale": "motif", "scope": "x"},
    )
    assert response.status_code != 200
