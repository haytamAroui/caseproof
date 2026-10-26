"""Evaluator scoring controls; scripted replies never establish live model accuracy."""
import json
from dataclasses import replace

from application.extraction.contracts import ProviderReply
from scripts.verify_live_extraction_quality import CASES, evaluate_case, run_quality


class Scripted:
    identity = "synthetic"
    model = "synthetic/quality-control"

    def __init__(self, mode="gold", cost="0.0001"):
        self.mode = mode
        self.cost = cost

    def complete(self, system, payload, *, request_id, max_tokens):
        data = json.loads(payload)
        src = data["sources"][0]
        case = next(c for c in CASES if c.content == src["text"])
        atoms = []
        if self.mode != "empty":
            for value in case.expected:
                quote = next(line for line in case.content.split(". ") if value in line)
                atoms.append({
                    "entity_id": "E1", "source_id": src["id"], "quote": quote,
                    "statement": "Synthetic literal", "signal": "amount_mentioned",
                    "slot": "amount_mentioned", "value": value,
                    "polarity": "affirmative", "relation": "supports",
                })
        return ProviderReply(
            json.dumps({"entities": [], "relationships": [], "atoms": atoms}),
            self.identity, self.model, 10, 10, self.cost,
        )


def test_complete_quality_corpus_and_scoring_controls():
    assert len(CASES) == 18
    assert len({c.case_id for c in CASES}) == 18
    result = run_quality(Scripted())
    assert result["quality_gate"] == "pass"
    assert result["model_calls_reserved"] == 18
    assert result["literal_recall"] == result["literal_precision"] == 1
    assert result["customer_ready"] is False
    assert result["expected_count_evaluated"] == 15


def test_empty_output_fails_positive_but_passes_completed_negative_control():
    positive = evaluate_case(CASES[0], Scripted("empty"))
    assert positive["status"] == "fail" and positive["missed_count"] == 2
    negative = evaluate_case(CASES[3], Scripted("empty"))
    assert negative["status"] == "pass" and negative["successful_response"]


def test_unexpected_grounded_amount_counts_as_false_positive():
    case = replace(CASES[0], expected=("125,00",))
    row = evaluate_case(case, Scripted())
    assert row["status"] == "fail"
    assert row["unexpected_validated_count"] == 1


def test_unknown_cost_stops_and_never_claims_complete_or_free():
    result = run_quality(Scripted(cost=None))
    assert result["model_calls_reserved"] == 1
    assert result["coverage_complete"] is False
    assert result["reported_total_usd"] is None
    assert result["quality_gate"] == "not_passed"


def test_report_excludes_sources_and_model_outputs():
    encoded = json.dumps(run_quality(Scripted()))
    assert all(c.content not in encoded for c in CASES)
    assert "response_text" not in encoded
