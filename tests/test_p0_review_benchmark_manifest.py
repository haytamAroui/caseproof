"""Reproducible P0 seed manifest checks. No simulated human accuracy metrics."""
import json
from pathlib import Path

def test_seeded_fixture_provenance_and_no_claimed_human_results() -> None:
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "p0_review_benchmark_cases.json").read_text()
    )
    assert fixture["schema"] == "caseproof-seeded-review-benchmark-v1"
    assert fixture["label_status"] == "SYNTHETIC_AUTHOR_SEEDED_NOT_INDEPENDENTLY_ADJUDICATED"
    assert len({c["id"] for c in fixture["cases"]}) == len(fixture["cases"])
    assert {"NL-wrong-page", "FR-duplicate", "NL-wrong-version", "FR-OCR", "NL-negation", "FR-qualifier"} <= {
        c["id"] for c in fixture["cases"]
    }
    assert fixture["human_comparison_design"]["future_third_condition"] == "advisory_nli_not_enabled"
    assert "human_results" not in fixture
