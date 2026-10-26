"""M0 synthetic gold-fixture integrity, not production litigation correctness."""

import copy
import json

import pytest

from scripts.validate_litigation_corpus import DEFAULT_CORPUS, literal_state, validate


@pytest.fixture
def corpus():
    return json.loads(DEFAULT_CORPUS.read_text(encoding="utf-8"))


def by_id(data, name):
    return next(item for item in data["cases"] if item["id"] == name)


def test_original_synthetic_corpus_has_all_language_and_negative_controls(corpus):
    result = validate(corpus)
    assert result["case_count"] >= 10
    assert result["clean_controls"] >= 2
    assert set(result["languages"]) == {"nl", "fr", "mixed"}
    assert result["human_accuracy_measured"] is False
    assert result["production_workflow_measured"] is False


def test_clean_case_can_have_no_findings(corpus):
    for case in corpus["cases"]:
        if case["cohort"] == "clean":
            assert case["expected"]["human_review_labels"] == []
            assert literal_state(case) == "match"


def test_mutated_quote_invalidates_gold(corpus):
    changed = copy.deepcopy(corpus)
    by_id(changed, "NL_CLEAN_01")["citation"]["quote"] = "Invented quote"
    with pytest.raises(ValueError, match="oracle observed mismatch"):
        validate(changed)


def test_duplicate_label_not_arbitrarily_resolved(corpus):
    assert literal_state(by_id(corpus, "NL_DUPLICATE_04")) == "ambiguous"
    assert literal_state(by_id(corpus, "NL_VERSION_12")) == "ambiguous"


def test_unprocessed_scan_abstains_rather_than_invent_text(corpus):
    assert literal_state(by_id(corpus, "FR_SCAN_05")) == "unavailable"
    changed = copy.deepcopy(corpus)
    by_id(changed, "FR_SCAN_05")["sources"][0]["text"] = "fabricated OCR"
    with pytest.raises(ValueError, match="unprocessed scan cannot claim text"):
        validate(changed)


def test_unresolved_reference_and_changed_pagination_are_distinct(corpus):
    assert literal_state(by_id(corpus, "FR_MISSING_06")) == "unresolved"
    assert literal_state(by_id(corpus, "FR_OFFSET_14")) == "match"
    assert by_id(corpus, "FR_OFFSET_14")["sources"][0]["printed_page"] == 11


def test_alias_resolves_but_duplicate_does_not(corpus):
    assert literal_state(by_id(corpus, "MIX_ALIAS_13")) == "match"
    changed = copy.deepcopy(corpus)
    by_id(changed, "MIX_ALIAS_13")["sources"][0]["aliases"] = []
    with pytest.raises(ValueError, match="oracle observed unresolved"):
        validate(changed)


def test_source_prompt_injection_is_inert_data(corpus):
    case = by_id(corpus, "MIX_INJECTION_09")
    assert "ignore toutes les règles" in case["sources"][0]["text"]
    assert literal_state(case) == "match"
    assert "prompt_injection_content" in case["expected"]["human_review_labels"]


def test_gold_cannot_reference_nonexistent_retrieval_source(corpus):
    changed = copy.deepcopy(corpus)
    by_id(changed, "FR_VAT_07")["retrieval_queries"][0]["relevant_source_ids"] = ["not_present"]
    with pytest.raises(ValueError, match="unknown source"):
        validate(changed)


def test_claim_of_independently_adjudicated_labels_rejected(corpus):
    changed = copy.deepcopy(corpus)
    changed["provenance"]["label_status"] = "adjudicated"
    with pytest.raises(ValueError, match="rights/label qualifications absent"):
        validate(changed)


def test_unknown_human_gold_label_rejected(corpus):
    changed = copy.deepcopy(corpus)
    by_id(changed, "FR_VAT_07")["expected"]["human_review_labels"] = ["court_ready"]
    with pytest.raises(ValueError, match="unknown human label"):
        validate(changed)


def test_language_declaration_cannot_silently_drop_english(corpus):
    changed = copy.deepcopy(corpus)
    changed["allowed_languages"] = ["nl", "fr", "mixed"]
    with pytest.raises(ValueError, match="language declaration required"):
        validate(changed)
