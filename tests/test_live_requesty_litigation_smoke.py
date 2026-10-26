"""No-network regressions for the optional Requesty synthetic live-model smoke."""
import json
from pathlib import Path

import pytest

from application.extraction.contracts import ExtractionError, OutcomeUnknown, ProviderReply
from scripts.verify_live_requesty_litigation import (
    FIXTURES,
    MAX_OUTPUT_TOKENS,
    MAX_REPORTED_USD,
    BudgetedProvider,
    Fixture,
    LiveProbeError,
    SmokeLiteralPolicy,
    request_for,
    run_probe,
)


class Scripted:
    identity = "requesty-eu-http-v1"
    model = "synthetic/test-model"

    def __init__(self, mode="good", cost="0.0005"):
        self.mode, self.cost, self.calls = mode, cost, []

    def complete(self, system, payload, *, request_id, max_tokens):
        self.calls.append(request_id)
        assert "never approve" in system and len(request_id) == 64
        assert max_tokens == MAX_OUTPUT_TOKENS
        body = json.loads(payload)
        assert body["purpose"] == "entity-scoped observations"
        src = body["sources"][0]
        assert src["text"] in [x.text for x in FIXTURES]
        if self.mode == "unknown":
            raise OutcomeUnknown("no response known")
        if self.mode == "http503":
            raise OutcomeUnknown("requesty_http_503")
        if self.mode == "dns":
            raise OutcomeUnknown("requesty_transport_dns")
        if self.mode == "badmodel":
            raise ExtractionError("unexpected Requesty model identity")
        if self.mode == "rejected":
            raise ExtractionError("provider rejected")
        value = "125.00" if "125.00" in src["text"] else "125,00"
        if self.mode == "full_sentence":
            value = src["text"]
        atom = {
            "entity_id": "E1", "source_id": src["id"],
            "quote": "fabricated" if self.mode == "fabricated" else src["text"],
            "statement": "Synthetic payment candidate",
            "signal": "amount_mentioned", "slot": "amount_mentioned",
            "value": value,
            "polarity": "conditional" if self.mode == "conditional" else "affirmative",
            "relation": "supports",
        }
        reply = json.dumps({"entities": [], "relationships": [], "atoms": [atom]})
        return ProviderReply(reply, self.identity, self.model, 100, 65, self.cost)


def test_fixture_integrity_and_one_call_contract():
    assert [f.lang for f in FIXTURES] == ["nl", "fr", "en"]
    for f in FIXTURES:
        r = request_for(f)
        assert r.sources[0].source.sha256_hex == r.sources[0].representation.sha256_hex
        assert r.config.max_calls == 1 and r.config.repair_passes == 0
        assert r.config.max_output_tokens == MAX_OUTPUT_TOKENS
        assert r.entities[0].confirmed


def test_three_language_model_answers_really_pass_through_evidence_pipeline():
    model = Scripted()
    receipt = run_probe(model)
    assert receipt["quality_gate"] == "pass"
    assert receipt["model_calls_reserved"] == len(model.calls) == 3
    assert receipt["reported_total_usd"] == "0.0015"
    assert receipt["legal_decision"] == "not_assessed"
    assert receipt["customer_ready"] is False
    assert all(c["status"] == "pass" and c["source_verified"]
               and c["validated_grounded_gold_candidates"] >= 1
               and c["human_review_required"] for c in receipt["cases"])


@pytest.mark.parametrize("mode", ["fabricated", "conditional", "full_sentence"])
def test_hallucinated_quote_or_conditional_assertion_does_not_pass(mode):
    model = Scripted(mode)
    receipt = run_probe(model)
    assert receipt["quality_gate"] == "not_passed"
    assert receipt["model_calls_reserved"] == len(model.calls) == 1
    assert receipt["cases"][0]["status"] == "candidate_quality_gap"


@pytest.mark.parametrize("mode", ["unknown", "rejected"])
def test_provider_failure_does_not_trigger_retries_or_further_calls(mode):
    model = Scripted(mode)
    receipt = run_probe(model)
    assert receipt["quality_gate"] == "not_passed"
    assert receipt["model_calls_reserved"] == len(model.calls) == 1


def test_missing_or_excessive_reported_cost_stops_probe():
    missing = run_probe(Scripted(cost=None))
    assert missing["quality_gate"] == "not_passed"
    assert missing["cost_gate"] == "cost_telemetry_unavailable"
    assert missing["model_calls_reserved"] == 1
    assert missing["reported_total_usd"] is None
    expensive = run_probe(Scripted(cost=str(MAX_REPORTED_USD + 1)))
    assert expensive["cost_gate"] == "reported_cost_cap_exceeded"
    assert expensive["model_calls_reserved"] == 1
    assert expensive["reported_total_usd"] == str(MAX_REPORTED_USD + 1)


def test_fourth_call_blocked_before_network():
    model = Scripted()
    p = BudgetedProvider(model)
    p.calls = 3
    with pytest.raises(LiveProbeError, match="call_budget_exceeded"):
        p.complete("system", "payload", request_id="a" * 64, max_tokens=100)
    assert not model.calls


def test_synthetic_policy_cannot_promote_unquoted_or_wrong_kind():
    p = SmokeLiteralPolicy()
    assert p.validate("amount_mentioned", "amount_mentioned",
                      "Payment EUR 125.00", "125.00", "synthetic_legal_note")[0] == "validated"
    assert p.validate("amount_mentioned", "amount_mentioned",
                      "Payment EUR 125.00", "999", "synthetic_legal_note")[0] == "rejected"
    assert p.validate("amount_mentioned", "amount_mentioned",
                      "Payment EUR 125.00", "125.00", "legal_verdict")[0] == "rejected"


def test_invalid_fixtures_fail_before_network():
    with pytest.raises(LiveProbeError):
        request_for(Fixture("xx", "EUR 125.00", "125.00"))
    with pytest.raises(LiveProbeError):
        request_for(Fixture("en", "EUR 2.00", "125.00"))


def test_manual_workflow_never_leaks_requesty_key_or_auth_admin_to_pr():
    path = Path(__file__).resolve().parents[1] / ".github/workflows/caseproof-dev-requesty-smoke.yml"
    workflow = json.loads(path.read_text(encoding="utf-8"))
    assert list(workflow["on"]) == ["workflow_dispatch"]
    assert workflow["permissions"] == {"contents": "read"}
    j = workflow["jobs"]["live-requesty"]
    assert j["environment"] == "caseproof-dev-model"
    assert "github.event_name == 'workflow_dispatch'" in j["if"]
    assert "github.repository == 'haytamAroui/caseproof'" in j["if"]
    assert "github.ref == 'refs/heads/main'" in j["if"]
    assert j["timeout-minutes"] <= 5
    assert j["steps"][0]["with"] == {"ref": "main", "persist-credentials": False}
    env = next(s["env"] for s in j["steps"] if "env" in s)
    assert env["CASEPROOF_REQUESTY_API_KEY"] == "$" + "{{ secrets.CASEPROOF_REQUESTY_API_KEY }}"
    # Only the configured shorthand is qualified; other explicit routes pass through.
    assert env["CASEPROOF_EXTRACTION_MODEL"] == (
        "$" + "{{ vars.CASEPROOF_EXTRACTION_MODEL == 'mistral-small-2603' "
        "&& 'mistral/mistral-small-2603' || vars.CASEPROOF_EXTRACTION_MODEL }}"
    )
    assert "AUTH_ADMIN" not in str(workflow)
    assert j["steps"][-1]["with"]["retention-days"] <= 7


def test_receipt_never_contains_raw_source_quote_or_credentials():
    raw = json.dumps(run_probe(Scripted()))
    assert all(f.text not in raw for f in FIXTURES)
    assert "api_key" not in raw and "response_text" not in raw


def test_cost_of_failed_quality_is_still_reported_and_never_marked_under_cap():
    r = run_probe(Scripted("fabricated", "1.00"))
    assert r["quality_gate"] == "not_passed"
    assert r["cost_gate"] == "reported_cost_cap_exceeded"
    assert r["reported_total_usd"] == "1.00"
    assert r["model_calls_reserved"] == 1


def test_failed_quality_with_missing_cost_does_not_pretend_zero():
    r = run_probe(Scripted("full_sentence", None))
    assert r["quality_gate"] == "not_passed"
    assert r["cost_gate"] == "cost_telemetry_unavailable"
    assert r["reported_total_usd"] is None
    assert r["model_calls_reserved"] == 1


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("http503", "requesty_http_503"),
        ("dns", "requesty_transport_dns"),
        ("badmodel", "requesty_model_identity_mismatch"),
        ("unknown", "requesty_outcome_unknown_unclassified"),
        ("rejected", "requesty_response_validation_failed"),
    ],
)
def test_safe_provider_diagnostic_in_receipt(mode, expected):
    receipt = run_probe(Scripted(mode))
    assert receipt["model_calls_reserved"] == 1
    assert receipt["cases"][0]["provider_diagnostic"] == expected
    assert receipt["cost_gate"] == "cost_telemetry_unavailable"
    assert receipt["reported_total_usd"] is None


def test_protected_receipt_never_copies_raw_provider_exception_text():
    from scripts.verify_live_requesty_litigation import safe_provider_diagnostic

    value = "PRIVATE-RAW-BEARER-API-KEY-DO-NOT-LOG"
    assert safe_provider_diagnostic(OutcomeUnknown(value)) == "requesty_outcome_unknown_unclassified"
    assert safe_provider_diagnostic(ExtractionError(value)) == "requesty_response_validation_failed"
