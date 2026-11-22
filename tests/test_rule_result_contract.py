"""Common per-rule result contract: projection mapping, invariants, fail-closed.

The projections never replace the existing checks; every test here also asserts
that the original granular state survives as a sub-result.
"""
from __future__ import annotations

import json
from dataclasses import replace

import pytest

from application.litigation.brief_checks import CitationCheckState, CitationObservation
from application.litigation.factual_values import (
    FactKind,
    FactObservation,
    FactRole,
    FactState,
)
from application.litigation.paraphrase_guard import guard_paraphrase
from application.litigation.rule_results import (
    CONTRACT_VERSION,
    RuleContractError,
    RuleResult,
    RuleStatus,
    citation_result,
    coverage_issue_result,
    fact_result,
    finding_results,
    finding_support_result,
    guard_result,
    run_rule_results,
    to_dict,
    to_json,
)
from tests.test_litigation_m2_unified_review import check as unified_check


def _citation(state: CitationCheckState) -> CitationObservation:
    return CitationObservation(
        reference_id="ref-1",
        state=state,
        exhibit_id="ex-1",
        source_id="src-1",
        source_version_id="v1",
        source_sha256="a" * 64,
        representation_id="repr-1",
        text_start=0,
        text_end=10,
        scope_note="exact quotation within the checked page representation only",
    )


def _fact(state: FactState) -> FactObservation:
    return FactObservation(
        claim_id="fact-money",
        reference_id="ref-1",
        kind=FactKind.MONEY,
        role=FactRole.PAYMENT,
        state=state,
        brief_token="€14500",
        source_token="€12500",
        source_id="src-1",
        source_version_id="v1",
        representation_id="repr-1",
        source_sha256="b" * 64,
        source_locator="pdf-page-1",
        source_pdf_page=1,
        source_start=0,
        source_end=10,
        explanation="synthetic",
    )


def _finding(**overrides):
    finding = {
        "reference_id": "ref-0000",
        "identity": "resolved",
        "identity_reason": None,
        "page_mapping": "mapped",
        "page_mapping_reason": None,
        "pdf_page": 1,
        "source_sha256": "c" * 64,
        "literal_assessment": {"state": "exact_match", "reason": "literal_in_checked_page_representation_only"},
        "visual_assessment": {"state": "not_assessed", "reason": "visual_not_run", "performed": False},
        "fidelity": "exact_match",
        "support": "not_assessed",
    }
    finding.update(overrides)
    return finding


@pytest.mark.parametrize("state", list(CitationCheckState))
def test_every_citation_state_maps_to_one_of_the_four_statuses(state):
    result = citation_result(_citation(state))
    assert result.status in set(RuleStatus)
    assert result.subresults == (("citation_state", state.value),)
    assert result.rule_version and result.reference == "ref-1" and result.scope


@pytest.mark.parametrize("state", list(FactState))
def test_every_fact_state_maps_to_one_of_the_four_statuses(state):
    result = fact_result(_fact(state))
    assert result.status in set(RuleStatus)
    assert ("fact_state", state.value) in result.subresults


@pytest.mark.parametrize("state,expected", [
    (CitationCheckState.EXACT_MATCH, RuleStatus.PASS),
    (CitationCheckState.QUOTE_NOT_FOUND, RuleStatus.FAIL),
    (CitationCheckState.MULTIPLE_MATCHES, RuleStatus.UNDETERMINED),
    (CitationCheckState.NO_QUOTATION, RuleStatus.UNDETERMINED),
    (CitationCheckState.OCR_UNRELIABLE, RuleStatus.UNDETERMINED),
    (CitationCheckState.REPRESENTATION_CONFLICT, RuleStatus.UNDETERMINED),
])
def test_citation_mapping_documented_values(state, expected):
    assert citation_result(_citation(state)).status is expected


@pytest.mark.parametrize("state", [
    CitationCheckState.REFERENCE_UNRESOLVED,
    CitationCheckState.REFERENCE_AMBIGUOUS,
    CitationCheckState.PAGE_UNMAPPED,
    CitationCheckState.SOURCE_UNAVAILABLE,
    CitationCheckState.INCOMPLETE_EXTRACTION,
])
def test_citation_precondition_failures_are_undetermined_not_fail(state):
    result = citation_result(_citation(state))
    assert result.status is RuleStatus.UNDETERMINED
    assert any(not p.met for p in result.preconditions)


@pytest.mark.parametrize("state,expected", [
    (FactState.MATCH, RuleStatus.PASS),
    (FactState.DIFFERENCE, RuleStatus.FAIL),
    (FactState.NEEDS_CONTEXT, RuleStatus.UNDETERMINED),
    (FactState.NOT_ASSESSED, RuleStatus.UNDETERMINED),
])
def test_fact_mapping(state, expected):
    result = fact_result(_fact(state))
    assert result.status is expected
    assert result.input_hashes[-1] == ("source_original_sha256", "b" * 64)


@pytest.mark.parametrize("identity,expected", [
    ("resolved", RuleStatus.PASS),
    ("not_in_inventory", RuleStatus.FAIL),
    ("ambiguous", RuleStatus.UNDETERMINED),
    ("source_missing", RuleStatus.UNDETERMINED),
    ("not_assessed", RuleStatus.UNDETERMINED),
])
def test_finding_identity_mapping(identity, expected):
    results = {r.rule_id: r for r in finding_results(_finding(identity=identity))}
    assert results["exhibit.identity"].status is expected
    assert results["exhibit.identity"].subresults == (("identity", identity),)


@pytest.mark.parametrize("mapping,expected", [
    ("mapped", RuleStatus.PASS),
    ("conflicting", RuleStatus.UNDETERMINED),
    ("unmapped", RuleStatus.UNDETERMINED),
])
def test_finding_page_mapping_mapping(mapping, expected):
    results = {r.rule_id: r for r in finding_results(_finding(page_mapping=mapping))}
    assert results["exhibit.page_mapping"].status is expected


@pytest.mark.parametrize("literal,expected", [
    ("exact_match", RuleStatus.PASS),
    ("quote_not_found", RuleStatus.FAIL),
    ("multiple_matches", RuleStatus.UNDETERMINED),
    ("translation_review_required", RuleStatus.UNDETERMINED),
    ("not_applicable", RuleStatus.UNDETERMINED),
    ("not_assessed", RuleStatus.UNDETERMINED),
])
def test_finding_literal_mapping(literal, expected):
    results = {r.rule_id: r for r in finding_results(
        _finding(literal_assessment={"state": literal, "reason": "synthetic"}))}
    assert results["fidelity.literal"].status is expected


@pytest.mark.parametrize("visual,reason,expected", [
    ("not_assessed", "visual_not_run", RuleStatus.UNDETERMINED),
    ("not_assessed", "uncalibrated_agreement", RuleStatus.UNDETERMINED),
    ("ocr_unreliable", "regional_ocr_unreliable", RuleStatus.UNDETERMINED),
    ("representation_conflict", "regional_representation_conflict", RuleStatus.UNDETERMINED),
])
def test_finding_visual_never_machine_pass(visual, reason, expected):
    results = {r.rule_id: r for r in finding_results(
        _finding(visual_assessment={"state": visual, "reason": reason, "performed": True}))}
    result = results["fidelity.visual"]
    assert result.status is expected
    assert result.status is not RuleStatus.PASS


def test_support_stays_pending_lawyer_disposition_machine_side():
    result = finding_support_result(_finding())
    assert result.status is RuleStatus.UNDETERMINED
    assert result.reason == "human_only_pending_lawyer_disposition"
    with pytest.raises(RuleContractError):
        finding_support_result(_finding(support="supported"))


def test_guard_projection_never_pass_or_fail():
    source = "Le paiement de €12500 a été effectué le 22 mai 2026."
    draft = f'Pièce 1, PDF p. 1 "{source}" Le paiement de €14500 a été effectué le 22 mai 2026.'
    advisory = guard_paraphrase(
        draft_region=draft,
        reference_start=0,
        reference_end=len(f'Pièce 1, PDF p. 1 "{source}"'),
        quoted_text=source,
        source_text_context=source,
        source_version_id="v1",
        source_sha256="d" * 64,
        pdf_page=1,
        ocr_uncertain=False,
        source_text_partial=False,
        draft_language="fr",
        source_language="fr",
    )
    assert advisory["state"] == "needs_manual_review"
    result = guard_result(advisory, reference="ref-1")
    assert result.status is RuleStatus.UNDETERMINED
    assert result.status not in {RuleStatus.PASS, RuleStatus.FAIL}
    quiet = guard_result({"state": "not_assessed", "anchor_basis": "unavailable"}, reference="ref-1")
    assert quiet.status is RuleStatus.UNDETERMINED  # not run: pending, not a missing basis


@pytest.mark.parametrize("issue,expected", [
    ("supported", RuleStatus.PASS),
    ("contradicted", RuleStatus.FAIL),
    ("qualified", RuleStatus.UNDETERMINED),
    ("unresolved", RuleStatus.UNDETERMINED),
    ("open", RuleStatus.UNDETERMINED),
])
def test_coverage_issue_mapping(issue, expected):
    result = coverage_issue_result(issue, subject="issue-1", manifest_version="coverage-v1", reason="synthetic")
    assert result.status is expected


def test_unified_run_projects_without_changing_the_run():
    run = unified_check()
    results = run_rule_results(run)
    kinds = {r.rule_id for r in results}
    assert kinds == {"citation.literal", "fact.value"}
    assert {r.status for r in results} == {RuleStatus.FAIL, RuleStatus.UNDETERMINED}
    citation = next(r for r in results if r.rule_id == "citation.literal")
    assert citation.subresults == (("citation_state", CitationCheckState.NO_QUOTATION.value),)
    assert all(
        dict(r.input_hashes).get("source_original_sha256") for r in results
    )
    # Projecting is a view: the frozen run itself is untouched.
    assert run.snapshot_hash == unified_check().snapshot_hash


def test_unverified_is_reserved_and_no_current_family_returns_it():
    # UNVERIFIED names exactly one thing: a legal article absent from the case's
    # chosen corpus. That rule family does not exist yet, so every current
    # projection resolves to PASS, FAIL or UNDETERMINED only.
    results = [citation_result(_citation(s)) for s in CitationCheckState]
    results += [fact_result(_fact(s)) for s in FactState]
    results += list(finding_results(_finding()))
    results += list(finding_results(_finding(identity="source_missing", page_mapping="unmapped")))
    results += [guard_result({"state": "not_assessed", "anchor_basis": "unavailable"}, reference="r")]
    results += [coverage_issue_result(s, subject="i", manifest_version="v", reason="r")
                for s in ("supported", "contradicted", "qualified", "unresolved", "open")]
    assert results and all(r.status is not RuleStatus.UNVERIFIED for r in results)
    # The contract still supports the reserved status for the future legal-corpus rule.
    reserved = RuleResult("legal.article_in_corpus", "future-legal-rules", RuleStatus.UNVERIFIED,
                          "art. 1382", "article presence in the declared corpus version", (),
                          (), "article_absent_from_selected_corpus", (("corpus_lookup", "absent"),))
    assert reserved.status is RuleStatus.UNVERIFIED
    # A missing basis keeps its granular reason instead of a generic status.
    unavailable = citation_result(_citation(CitationCheckState.SOURCE_UNAVAILABLE))
    assert unavailable.status is RuleStatus.UNDETERMINED
    assert unavailable.subresults == (("citation_state", "source_unavailable"),)


def test_unified_run_clean_case_is_all_pass_or_bounded():
    same = "Le paiement de €12500 a été effectué le 22 mai 2026."
    run = unified_check(same, same)
    results = run_rule_results(run)
    facts = [r for r in results if r.rule_id == "fact.value"]
    assert all(r.status is RuleStatus.PASS for r in facts)
    citation = next(r for r in results if r.rule_id == "citation.literal")
    assert citation.status is RuleStatus.UNDETERMINED  # no quotation: nothing literal to check


def test_projection_is_fail_closed_on_unknown_states():
    with pytest.raises(RuleContractError):
        finding_results(_finding(identity="some_future_state"))
    with pytest.raises(RuleContractError):
        finding_results(_finding(literal_assessment={"state": "bogus", "reason": "x"}))
    with pytest.raises(RuleContractError):
        guard_result({"state": "approved"}, reference="ref-1")
    with pytest.raises(RuleContractError):
        coverage_issue_result("perfect", subject="i", manifest_version="v", reason="r")
    bad = replace(_fact(FactState.MATCH), state="supposedly_matching")
    with pytest.raises(RuleContractError):
        fact_result(bad)


def test_contract_requires_reason_version_reference_and_subresults():
    base = to_dict(fact_result(_fact(FactState.MATCH)))
    for field in ("rule_id", "rule_version", "status", "reference", "scope", "reason"):
        assert base[field]
    with pytest.raises(RuleContractError):
        RuleResult("fact.value", "v", RuleStatus.PASS, "ref", "scope", (), (), "", (("a", "b"),))
    with pytest.raises(RuleContractError):
        RuleResult("fact.value", "v", RuleStatus.PASS, "ref", "scope", (), (), "reason", ())
    with pytest.raises(RuleContractError):
        RuleResult("fact.value", "v", RuleStatus.PASS, "ref", "scope", (),
                   (("source_original_sha256", "not-a-digest"),), "reason", (("a", "b"),))


def test_serialization_is_deterministic_and_names_contract():
    result = citation_result(_citation(CitationCheckState.EXACT_MATCH), brief_sha256="e" * 64)
    first, second = to_json(result), to_json(result)
    assert first == second
    data = json.loads(first)
    assert data["contract"] == CONTRACT_VERSION
    assert data["status"] == "PASS"
    assert data["input_hashes"]["brief_original_sha256"] == "e" * 64
    assert data["subresults"]["citation_state"] == "exact_match"


def test_native_text_case_without_ocr_still_yields_rule_results():
    # Reference case for product fit: native-text source, no OCR anywhere.
    brief = "Le paiement de €12500 a été effectué le 22 mai 2026."
    run = unified_check(brief, brief)
    assert all(x.state is FactState.MATCH for x in run.factual_observations)
    results = run_rule_results(run)
    # No OCR ran at all: no result reason may mention it, PASS or not.
    assert results and all("ocr" not in r.reason.casefold() for r in results)
    facts = [r for r in results if r.rule_id == "fact.value"]
    assert facts and all(r.status is RuleStatus.PASS for r in facts)


def test_malformed_source_digest_fails_closed_instead_of_vanishing():
    # Input hashes are integrity evidence: a corrupt digest must surface.
    bad_observation = replace(_citation(CitationCheckState.EXACT_MATCH), source_sha256="not-a-digest")
    with pytest.raises(RuleContractError):
        citation_result(bad_observation)
    with pytest.raises(RuleContractError):
        finding_results(_finding(source_sha256="not-a-digest"))
    # A genuinely absent digest is still allowed and simply omitted.
    result = citation_result(replace(_citation(CitationCheckState.EXACT_MATCH), source_sha256=None))
    assert dict(result.input_hashes) == {}
