"""Suitability rule format v1 (roadmap task 5): loader and evaluator contract.

All rules and facts here are SYNTHETIC placeholders used to validate the
format and its semantics. They are not legal content and never evidence about
Belgian law.
"""
from __future__ import annotations

import pytest

from application.litigation.rule_results import RuleStatus
from application.litigation.suitability_rules import (
    FORMAT_VERSION,
    ConfirmedFact,
    RuleFormatError,
    evaluate_rule,
    load_rule,
)

VALID_DOC = f"""
[rule]
format = "{FORMAT_VERSION}"
id = "synthetic.example.deposit"
version = "0.1.0"
scope = "Synthetic example: deposit conditions over confirmed facts."
reference = "Synthetic Act, art. 1"

[article]
act = "synthetic-act-2026"
article = "1"
language = "fr"
version = "2026-01-01"

[condition]
all = [
  {{ fact = "deposit_paid", op = "eq", value = true }},
  {{ fact = "deposit_months", op = "le", value = 2 }},
]
"""

CORPUS = {"synthetic-act-2026#1#fr#2026-01-01"}


def _facts() -> dict[str, ConfirmedFact]:
    return {
        "deposit_paid": ConfirmedFact(name="deposit_paid", value=True, confirmed=True),
        "deposit_months": ConfirmedFact(name="deposit_months", value=2, confirmed=True),
    }


def test_load_valid_rule() -> None:
    rule = load_rule(VALID_DOC)
    assert rule.rule_id == "synthetic.example.deposit"
    assert rule.rule_version == "0.1.0"
    assert rule.article_key == "synthetic-act-2026#1#fr#2026-01-01"
    assert len(rule.source_sha256) == 64


def test_pass_over_confirmed_facts() -> None:
    result = evaluate_rule(load_rule(VALID_DOC), _facts(), CORPUS)
    assert result.status == RuleStatus.PASS
    assert result.reason == "condition_holds_over_confirmed_facts"
    assert dict(result.input_hashes).keys() == {"rule_source", "confirmed_facts"}
    assert {value for _, value in result.subresults} == {"holds"}


def test_fail_only_when_condition_violated() -> None:
    facts = _facts()
    facts["deposit_months"] = ConfirmedFact(name="deposit_months", value=5, confirmed=True)
    result = evaluate_rule(load_rule(VALID_DOC), facts, CORPUS)
    assert result.status == RuleStatus.FAIL
    assert result.reason == "condition_violated_over_confirmed_facts"


def test_missing_fact_is_undetermined_never_fail() -> None:
    facts = _facts()
    del facts["deposit_months"]
    result = evaluate_rule(load_rule(VALID_DOC), facts, CORPUS)
    assert result.status == RuleStatus.UNDETERMINED
    assert result.reason == "facts_unavailable_unconfirmed_or_incomparable"
    assert result.preconditions[0].met is False
    assert "deposit_months" in result.preconditions[0].detail


def test_unconfirmed_fact_is_undetermined_never_fail() -> None:
    facts = _facts()
    facts["deposit_paid"] = ConfirmedFact(name="deposit_paid", value=False, confirmed=False)
    result = evaluate_rule(load_rule(VALID_DOC), facts, CORPUS)
    assert result.status == RuleStatus.UNDETERMINED


def test_article_absent_from_corpus_is_reserved_unverified() -> None:
    result = evaluate_rule(load_rule(VALID_DOC), _facts(), set())
    assert result.status == RuleStatus.UNVERIFIED
    assert result.reason == "article_absent_from_chosen_corpus"


def test_unverified_never_produced_by_other_gaps() -> None:
    result = evaluate_rule(load_rule(VALID_DOC), {}, CORPUS)
    assert result.status == RuleStatus.UNDETERMINED  # missing facts, corpus present


def test_no_reason_mentions_legal_conclusion() -> None:
    for facts in (_facts(), {}):
        result = evaluate_rule(load_rule(VALID_DOC), facts, CORPUS)
        assert "legal" not in result.reason
        assert result.reason.islower()


def test_source_hash_tracks_document() -> None:
    other = load_rule(VALID_DOC.replace("0.1.0", "0.1.1"))
    assert other.source_sha256 != load_rule(VALID_DOC).source_sha256


@pytest.mark.parametrize(
    "mutation",
    [
        ("format = ", 'format = "wrong"'),  # wrong format marker
        ('id = "synthetic.example.deposit"', ""),  # missing id
        ('version = "0.1.0"', ""),  # missing version
        ('language = "fr"', 'language = "de"'),  # unsupported language
        ('op = "le"', 'op = "almost"'),  # unknown operator
        ("value = true", ""),  # missing comparison value
        ("[article]", "[artikel]"),  # missing article table
        ("[condition]", "[conditie]"),  # missing condition
    ],
)
def test_loader_fails_closed(mutation: tuple[str, str]) -> None:
    old, new = mutation
    assert old in VALID_DOC
    with pytest.raises(RuleFormatError):
        load_rule(VALID_DOC.replace(old, new, 1))


def test_invalid_toml_fails_closed() -> None:
    with pytest.raises(RuleFormatError):
        load_rule("this is = = not toml")


def test_nesting_depth_bounded() -> None:
    doc = VALID_DOC.replace(
        "all = [", "not = " * 12 + "{ all = [", 1
    ).replace("]", "]" + " }" * 12, 1)
    with pytest.raises(RuleFormatError):
        load_rule(doc)


def test_any_and_not_combinators() -> None:
    doc = VALID_DOC.replace(
        "all = [\n  { fact = \"deposit_paid\", op = \"eq\", value = true },"
        "\n  { fact = \"deposit_months\", op = \"le\", value = 2 },\n]",
        "any = [\n  { fact = \"deposit_paid\", op = \"eq\", value = false },\n"
        "  { not = { fact = \"deposit_months\", op = \"gt\", value = 2 } },\n]",
    )
    result = evaluate_rule(load_rule(doc), _facts(), CORPUS)
    assert result.status == RuleStatus.PASS  # second branch holds


def test_any_abstains_when_a_branch_is_unavailable() -> None:
    doc = VALID_DOC.replace(
        "all = [\n  { fact = \"deposit_paid\", op = \"eq\", value = true },"
        "\n  { fact = \"deposit_months\", op = \"le\", value = 2 },\n]",
        "any = [\n  { fact = " + '"unknown_fact"' + ", op = \"present\" },\n"
        "  { fact = \"deposit_paid\", op = \"eq\", value = true },\n]",
    )
    result = evaluate_rule(load_rule(doc), _facts(), CORPUS)
    assert result.status == RuleStatus.UNDETERMINED


def test_between_and_in_operators() -> None:
    doc = VALID_DOC.replace(
        "{ fact = \"deposit_months\", op = \"le\", value = 2 },",
        "{ fact = \"deposit_months\", op = \"between\", value = [1, 2] },",
    ).replace(
        "{ fact = \"deposit_paid\", op = \"eq\", value = true },",
        "{ fact = \"deposit_months\", op = \"in\", value = [1, 2, 3] },",
    )
    result = evaluate_rule(load_rule(doc), _facts(), CORPUS)
    assert result.status == RuleStatus.PASS


def test_outcomes_cannot_be_remapped() -> None:
    doc = VALID_DOC + '\n[outcomes]\non_false = "UNDETERMINED"\n'
    with pytest.raises(RuleFormatError):
        load_rule(doc)


def test_subresults_preserve_leaf_outcomes() -> None:
    facts = _facts()
    facts["deposit_months"] = ConfirmedFact(name="deposit_months", value=5, confirmed=True)
    result = evaluate_rule(load_rule(VALID_DOC), facts, CORPUS)
    outcomes = sorted(value for _, value in result.subresults)
    assert outcomes == ["holds", "violated"]
    keys = [key for key, _ in result.subresults]
    assert len(keys) == len(set(keys))  # enumerated keys stay unique


# --- Adversarial / fail-closed review cases ---


def test_bool_is_not_numeric() -> None:
    # Python True == 1 must NOT make a boolean fact satisfy a numeric rule.
    doc = VALID_DOC.replace(
        '{ fact = "deposit_paid", op = "eq", value = true },',
        '{ fact = "deposit_paid", op = "eq", value = 1 },',
    )
    result = evaluate_rule(load_rule(doc), _facts(), CORPUS)
    assert result.status == RuleStatus.UNDETERMINED
    assert any(value == "not_comparable" for _, value in result.subresults)


def test_numeric_operator_on_string_fact_abstains() -> None:
    facts = _facts()
    facts["deposit_months"] = ConfirmedFact(name="deposit_months", value="two", confirmed=True)
    result = evaluate_rule(load_rule(VALID_DOC), facts, CORPUS)
    assert result.status == RuleStatus.UNDETERMINED
    assert result.reason == "facts_unavailable_unconfirmed_or_incomparable"


def test_string_fact_never_satisfies_numeric_equality() -> None:
    facts = _facts()
    facts["deposit_months"] = ConfirmedFact(name="deposit_months", value="2", confirmed=True)
    result = evaluate_rule(load_rule(VALID_DOC), facts, CORPUS)
    assert result.status == RuleStatus.UNDETERMINED  # "2" is not 2


def test_non_finite_numbers_rejected_at_load() -> None:
    for bad in ("nan", "inf", "-inf"):
        with pytest.raises(RuleFormatError):
            load_rule(VALID_DOC.replace("value = 2", f"value = {bad}"))


def test_non_finite_fact_value_rejected() -> None:
    with pytest.raises(RuleFormatError):
        ConfirmedFact(name="deposit_months", value=float("nan"), confirmed=True)


def test_unknown_top_level_table_rejected() -> None:
    with pytest.raises(RuleFormatError):
        load_rule(VALID_DOC + "\n[artikle]\nact = 'x'\n")  # lawyer typo fails closed


def test_unknown_rule_key_rejected() -> None:
    with pytest.raises(RuleFormatError):
        load_rule(VALID_DOC.replace('scope = ', 'scop = ', 1).replace(
            '[rule]', '[rule]\nscope = "x"', 1))


def test_unknown_outcome_key_rejected() -> None:
    with pytest.raises(RuleFormatError):
        load_rule(VALID_DOC + '\n[outcomes]\non_maybe = "PASS"\n')


def test_mixed_type_in_list_rejected() -> None:
    doc = VALID_DOC.replace("value = [1, 2]", "value = [1, 'two']").replace(
        '{ fact = "deposit_months", op = "le", value = 2 },',
        '{ fact = "deposit_months", op = "in", value = [1, "two"] },',
    )
    with pytest.raises(RuleFormatError):
        load_rule(doc)


def test_corpus_keys_are_normalized() -> None:
    from application.litigation.suitability_rules import article_key
    key = article_key(" Synthetic-Act-2026 ", " 1", "FR", " 2026-01-01 ")
    assert key == "synthetic-act-2026#1#fr#2026-01-01"
    result = evaluate_rule(load_rule(VALID_DOC), _facts(), {key})
    assert result.status != RuleStatus.UNVERIFIED


def test_facts_must_be_typed_confirmed_facts() -> None:
    with pytest.raises(RuleFormatError):
        evaluate_rule(load_rule(VALID_DOC), {"deposit_paid": True}, CORPUS)  # type: ignore[dict-item]


def test_corpus_must_be_explicit_set() -> None:
    with pytest.raises(RuleFormatError):
        evaluate_rule(load_rule(VALID_DOC), _facts(), ["synthetic-act-2026#1#fr#2026-01-01"])  # type: ignore[arg-type]


def test_rule_version_carried_into_result() -> None:
    result = evaluate_rule(load_rule(VALID_DOC), _facts(), CORPUS)
    assert result.rule_version == "0.1.0"
    assert result.rule_id == "synthetic.example.deposit"


# --- Article identity: act + language + declared temporal version ---


def test_matching_versioned_key_passes() -> None:
    result = evaluate_rule(load_rule(VALID_DOC), _facts(), CORPUS)
    assert result.status == RuleStatus.PASS


def test_wrong_version_is_undetermined_never_pass() -> None:
    # Same act, same article, same language, different declared version:
    # the machine cannot decide across versions and must not silently PASS.
    corpus = {"synthetic-act-2026#1#fr#2024-06-01"}
    result = evaluate_rule(load_rule(VALID_DOC), _facts(), corpus)
    assert result.status == RuleStatus.UNDETERMINED
    assert result.reason == "article_version_mismatch_or_ambiguous"
    assert "2024-06-01" in dict(result.subresults)["corpus_versions"]


def test_ambiguous_versions_are_undetermined() -> None:
    corpus = {"synthetic-act-2026#1#fr#2024-06-01", "synthetic-act-2026#1#fr#2025-01-01"}
    result = evaluate_rule(load_rule(VALID_DOC), _facts(), corpus)
    assert result.status == RuleStatus.UNDETERMINED
    assert result.reason == "article_version_mismatch_or_ambiguous"


def test_version_undeclared_in_corpus_is_undetermined_not_unverified() -> None:
    result = evaluate_rule(load_rule(VALID_DOC), _facts(), {"synthetic-act-2026#1#fr"})
    assert result.status == RuleStatus.UNDETERMINED
    assert "version_undeclared_in_corpus" in dict(result.subresults)["corpus_versions"]


def test_absent_article_stays_unverified_regardless_of_other_versions() -> None:
    corpus = {"synthetic-act-2026#2#fr#2026-01-01", "other-act#1#fr#2026-01-01"}
    result = evaluate_rule(load_rule(VALID_DOC), _facts(), corpus)
    assert result.status == RuleStatus.UNVERIFIED
    assert result.reason == "article_absent_from_chosen_corpus"


def test_rule_without_article_version_rejected() -> None:
    with pytest.raises(RuleFormatError):
        load_rule(VALID_DOC.replace('version = "2026-01-01"\n', '', 1))


def test_hash_separator_in_identity_rejected() -> None:
    with pytest.raises(RuleFormatError):
        load_rule(VALID_DOC.replace('act = "synthetic-act-2026"', 'act = "synthetic#act"'))
