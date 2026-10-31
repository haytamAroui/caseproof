"""Negative controls for the author-only M0 NL/FR/EN synthetic gold audit."""
import copy
import json

import pytest

from scripts.audit_m0_trilingual import (
    DEFAULT_CORPUS,
    PRIOR_CORPUS,
    audit,
    expected_dimensions,
)


@pytest.fixture
def corpus_pair():
    return (
        json.loads(DEFAULT_CORPUS.read_text(encoding="utf-8")),
        json.loads(PRIOR_CORPUS.read_text(encoding="utf-8")),
    )


def by_id(data, case_id):
    return next(case for case in data["cases"] if case["id"] == case_id)


def test_trilingual_baseline_includes_preserved_v2_and_all_four_dimensions(corpus_pair):
    current, prior = corpus_pair
    result = audit(current, prior)
    assert result["legacy_v2_cases_unchanged"] == 19
    assert result["new_cases"] == 18
    assert result["total_cases"] == 37
    assert set(result["languages_new"]) == {"nl", "fr", "en", "mixed"}
    assert result["independent_human_review"] is False
    assert result["product_accuracy_measured"] is False
    assert result["actual_pdf_docx_ocr_tested"] is False
    assert result["m0_exit_signoff"] == "OPEN"


@pytest.mark.parametrize(
    ("case_id", "field", "state"),
    [
        ("NL_INCOMPLETE_20", "identity", "not_assessed"),
        ("NL_OFFSET_21", "page", "mapped"),
        ("NL_MISMATCH_22", "fidelity", "mismatch"),
        ("NL_SCAN_23", "fidelity", "ocr_unreliable"),
        ("FR_DUP_24", "identity", "ambiguous"),
        ("FR_NOQUOTE_27", "fidelity", "not_applicable"),
        ("EN_MISSING_28", "identity", "not_in_inventory"),
        ("MIX_TRANSLATION_32", "fidelity", "translation_review_required"),
        ("MIX_UNCONFIRMED_33", "identity", "not_assessed"),
        ("EN_WRONG_PRINTED_34", "page", "conflicting"),
        ("FR_SOURCE_MISSING_35", "identity", "source_missing"),
    ],
)
def test_named_boundaries_do_not_collapse(case_id, field, state, corpus_pair):
    current, _ = corpus_pair
    case = by_id(current, case_id)
    assert expected_dimensions(case)[field] == state
    assert case["expected_dimensions"]["semantic"] == "not_assessed"


def test_legacy_gold_is_immutable(corpus_pair):
    current, prior = copy.deepcopy(corpus_pair)
    current["cases"][0]["brief_text"] = "rewritten after calibration"
    with pytest.raises(ValueError, match="historical v2 cases changed"):
        audit(current, prior)


def test_inventory_completeness_is_not_assumed(corpus_pair):
    current, prior = copy.deepcopy(corpus_pair)
    case = by_id(current, "NL_INCOMPLETE_20")
    case["expected_dimensions"]["identity"] = "not_in_inventory"
    with pytest.raises(ValueError, match="independent contract oracle"):
        audit(current, prior)


def test_mistaken_source_page_cannot_be_mapped(corpus_pair):
    current, prior = copy.deepcopy(corpus_pair)
    by_id(current, "NL_OFFSET_21")["sources"][0]["pdf_page"] = 4
    with pytest.raises(ValueError, match="independent contract oracle"):
        audit(current, prior)


def test_three_page_spaces_are_not_interchangeable(corpus_pair):
    current, prior = copy.deepcopy(corpus_pair)
    case = by_id(current, "NL_OFFSET_21")
    assert case["citation"]["pdf_page"] == 3
    assert case["citation"]["printed_page_ref"] == 17
    assert case["citation"]["bundle_page_ref"] == 42
    case["citation"]["bundle_page_ref"] = 43
    with pytest.raises(ValueError, match="independent contract oracle"):
        audit(current, prior)


def test_translation_does_not_become_exact_match(corpus_pair):
    current, prior = copy.deepcopy(corpus_pair)
    by_id(current, "MIX_TRANSLATION_32")["expected_dimensions"]["fidelity"] = "exact_match"
    with pytest.raises(ValueError, match="independent contract oracle"):
        audit(current, prior)


def test_no_quote_does_not_auto_confirm_support(corpus_pair):
    current, _ = corpus_pair
    assert expected_dimensions(by_id(current, "EN_NOQUOTE_31"))["fidelity"] == "not_applicable"
    assert expected_dimensions(by_id(current, "EN_NOQUOTE_31"))["semantic"] == "not_assessed"


def test_absence_requires_confirmed_complete_inventory(corpus_pair):
    current, prior = copy.deepcopy(corpus_pair)
    by_id(current, "EN_MISSING_28")["inventory"]["status"] = "unconfirmed"
    with pytest.raises(ValueError, match="independent contract oracle"):
        audit(current, prior)


def test_fake_human_adjudication_is_rejected(corpus_pair):
    current, prior = copy.deepcopy(corpus_pair)
    current["provenance"]["label_status"] = "independently_reviewed"
    with pytest.raises(ValueError, match="independent label adjudication"):
        audit(current, prior)


def test_case_rights_must_stay_synthetic_and_cc0(corpus_pair):
    current, prior = copy.deepcopy(corpus_pair)
    by_id(current, "FR_CLEAN_25")["rights"]["customer_or_court_material"] = True
    with pytest.raises(ValueError, match="case-level synthetic rights"):
        audit(current, prior)


def test_fabricated_scan_text_is_rejected(corpus_pair):
    current, prior = copy.deepcopy(corpus_pair)
    by_id(current, "EN_SCAN_37")["sources"][0]["text"] = "fabricated OCR"
    with pytest.raises(ValueError, match="missing OCR cannot contain"):
        audit(current, prior)


def test_duplicate_gold_id_is_rejected(corpus_pair):
    current, prior = copy.deepcopy(corpus_pair)
    by_id(current, "FR_CLEAN_25")["id"] = "NL_OFFSET_21"
    with pytest.raises(ValueError, match="missing, repeated or reordered"):
        audit(current, prior)
