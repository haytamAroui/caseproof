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
        values = [] if self.mode == "empty" else list(case.expected)
        if self.mode in {"inject", "selective"} and case.category == "source_injection":
            values.append("999,00" if "," in case.expected[0] else "999.00")
        if self.mode == "review" and not case.expected:
            values = ["125,00"]
        for value in values:
            quote = next(
                part for line in case.content.splitlines()
                for part in line.split(". ") if value in part
            )
            if self.mode == "selective" and value.startswith("999"):
                quote = quote[quote.index("payment of EUR"):]
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
    assert positive["negative_control"] is False and positive["abstained"] is False
    negative = evaluate_case(CASES[3], Scripted("empty"))
    assert negative["status"] == "pass" and negative["successful_response"]
    assert negative["negative_control"] is True and negative["abstained"] is True


def test_unexpected_grounded_amount_counts_as_false_positive():
    case = replace(CASES[0], expected=("125,00",))
    row = evaluate_case(case, Scripted())
    assert row["status"] == "fail"
    assert row["unexpected_validated_count"] == 1


def test_injected_amount_is_flagged_as_unexpected():
    case = next(c for c in CASES if c.case_id == "en-injection")
    row = evaluate_case(case, Scripted("selective"))
    assert row["status"] == "fail"
    assert row["missed_count"] == 0
    assert row["unexpected_validated_count"] == 1
    assert row["unexpected_grounded_count"] == 1
    assert row["ungrounded_validated_count"] == 0


def test_instruction_bearing_quote_is_withheld_not_a_validated_false_positive():
    case = next(c for c in CASES if c.case_id == "en-injection")
    row = evaluate_case(case, Scripted("inject"))
    assert row["status"] == "pass"
    assert row["unexpected_validated_count"] == 0
    assert row["candidate_reason_counts"]["qualified_or_untrusted_assertion"] == 1


def test_reviewed_negative_candidate_is_not_an_empty_abstention():
    row = evaluate_case(CASES[3], Scripted("review"))
    assert row["status"] == "pass"
    assert row["abstained"] is False
    assert row["withheld_for_review_or_rejected"] is True


def test_abstentions_and_breakdowns_are_reported():
    result = run_quality(Scripted("empty"))
    assert result["negative_controls_evaluated"] == 9
    assert result["abstention_count"] == 9
    assert result["by_category"]["negation"]["abstentions"] == 3
    assert result["by_category"]["multiple_amounts"]["missed"] == 6
    assert result["by_language"]["fr"]["cases"] == 6
    gold = run_quality(Scripted())
    assert gold["by_category"]["multiple_amounts"]["matched"] == 6
    assert gold["by_category"]["multiple_amounts"]["literal_recall"] == 1
    assert gold["by_language"]["fr"]["literal_precision"] == 1
    assert gold["by_category"]["source_injection"]["unexpected_validated"] == 0


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
