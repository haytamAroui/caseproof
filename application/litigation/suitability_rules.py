"""Typed, versioned suitability rule format (roadmap task 5).

A suitability rule is a small deterministic check a lawyer writes over
CONFIRMED case facts, tied to one legal article of the case's chosen corpus.
This module defines the format, a fail-closed TOML loader and a deterministic
evaluator. It is deliberately small: the roadmap measures how long writing and
reviewing a few rules takes BEFORE any general rule editor is built, so there
is no editor, no inference and no natural-language understanding here.

- The lawyer owns the rule content. This module never invents, extends or
  reinterprets it, and no LLM sits anywhere in the evaluation path.
- Evaluation runs only over lawyer-confirmed facts. A fact that is missing,
  unconfirmed or of a type the predicate cannot compare makes the result
  UNDETERMINED, never FAIL: the machine cannot decide with absent or
  incomparable evidence.
- UNVERIFIED keeps its reserved contract meaning (rule result contract v1):
  the rule's article is absent from the case's chosen corpus. Suitability
  rules are the first rule family that can produce it, because they are the
  first family tied to a corpus article. A missing fact, an incomparable type,
  an unreadable file or any other evidentiary gap stays UNDETERMINED.
- PASS/FAIL describe only the evaluated condition over the confirmed facts,
  never a legal conclusion about the case.

One rule per TOML document. Unknown keys, unknown operators, non-finite
numbers and malformed values are rejected at load (fail closed). The document
hash and the hash of the facts read are recorded on every result as integrity
evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from application.litigation.rule_results import RulePrecondition, RuleResult, RuleStatus

FORMAT_VERSION = "caseproof-suitability-rule-format-v1"

_MAX_DEPTH = 8
_MAX_LEAVES = 64
_FACT_NAME = re.compile(r"[a-z][a-z0-9_]{0,63}")
_LANGUAGES = ("nl", "fr")
_OPS = ("eq", "ne", "lt", "le", "gt", "ge", "in", "between", "present")
_TOP_LEVEL_KEYS = {"rule", "article", "condition", "outcomes"}
_RULE_KEYS = {"format", "id", "version", "scope", "reference"}
_ARTICLE_KEYS = {"act", "article", "language", "version"}

ScalarValue = str | int | float | bool


class RuleFormatError(ValueError):
    """Malformed suitability rule document or evaluation input."""


def _family(value: Any) -> str | None:
    """Type family for comparisons; bool is NOT numeric here (True != 1)."""
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    return None


def _finite(value: Any) -> bool:
    return not isinstance(value, float) or math.isfinite(value)


@dataclass(frozen=True, slots=True)
class ConfirmedFact:
    """One case fact with its lawyer-confirmation state."""

    name: str
    value: ScalarValue
    confirmed: bool

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or _FACT_NAME.fullmatch(self.name) is None:
            raise RuleFormatError("fact names are bounded snake_case identifiers")
        if _family(self.value) is None or not _finite(self.value):
            raise RuleFormatError("fact values are finite strings, numbers or booleans")
        if type(self.confirmed) is not bool:
            raise RuleFormatError("confirmation state is an explicit boolean")


@dataclass(frozen=True, slots=True)
class _Leaf:
    fact: str
    op: str
    value: Any  # validated against op at load


@dataclass(frozen=True, slots=True)
class SuitabilityRule:
    """One validated suitability rule, exactly as the lawyer wrote it."""

    rule_id: str
    rule_version: str
    act: str
    article: str
    language: str
    article_version: str
    scope: str
    reference: str
    condition: Any  # validated predicate tree
    source_sha256: str

    @property
    def article_key(self) -> str:
        """Full corpus identity: act, article, language, declared version."""
        return article_key(self.act, self.article, self.language, self.article_version)

    @property
    def base_article_key(self) -> str:
        """Version-less identity, used only to detect version mismatch/ambiguity."""
        return article_key(self.act, self.article, self.language)


def article_key(act: str, article: str, language: str, version: str | None = None) -> str:
    """Canonical corpus identity key; corpus builders MUST use this same helper.

    With a version the key binds the declared temporal version of the text.
    The version is a declared token (for example the as-of date the corpus
    declared), matched verbatim: identity matching only, never applicability
    or entry-into-force reasoning, and never inferred from dates or hashes.
    """
    parts = [part.strip().lower() for part in (act, article, language)]
    if version is not None:
        parts.append(version.strip().lower())
    return "#".join(parts)


def _bounded_str(value: Any, name: str, limit: int) -> str:
    if not isinstance(value, str) or not 0 < len(value.strip()) <= limit:
        raise RuleFormatError(f"bounded non-empty string required for {name}")
    return value.strip()


def _validate_leaf(node: Mapping[str, Any]) -> _Leaf:
    if not set(node) <= {"fact", "op", "value"}:
        raise RuleFormatError("predicate leaves hold only fact, op and value")
    fact = node.get("fact")
    if not isinstance(fact, str) or _FACT_NAME.fullmatch(fact) is None:
        raise RuleFormatError("predicate leaves name a bounded snake_case fact")
    op = node.get("op")
    if op not in _OPS:
        raise RuleFormatError(f"unsupported predicate operator: {op!r}")
    value = node.get("value")
    if op == "present":
        if value is not None:
            raise RuleFormatError("'present' takes no comparison value")
    elif op == "in":
        if not isinstance(value, list) or not 1 <= len(value) <= 64:
            raise RuleFormatError("'in' takes a bounded non-empty list")
        families = {_family(v) for v in value}
        if None in families or len(families) != 1 or not all(_finite(v) for v in value):
            raise RuleFormatError("'in' list entries are finite values of one type family")
    elif op == "between":
        if (
            not isinstance(value, list)
            or len(value) != 2
            or not all(_family(v) == "number" and _finite(v) for v in value)
            or value[0] > value[1]
        ):
            raise RuleFormatError("'between' takes two ordered finite numbers")
    else:
        if _family(value) is None or not _finite(value):
            raise RuleFormatError(f"'{op}' takes one finite string, number or boolean")
        if op in ("lt", "le", "gt", "ge") and _family(value) != "number":
            raise RuleFormatError(f"'{op}' takes a numeric comparison value")
    return _Leaf(fact=fact, op=op, value=value)


def _validate_condition(node: Any, depth: int, leaves: list[_Leaf]) -> Any:
    if depth > _MAX_DEPTH:
        raise RuleFormatError("predicate nesting is bounded")
    if not isinstance(node, dict):
        raise RuleFormatError("predicate nodes are tables")
    combinators = [key for key in ("all", "any", "not") if key in node]
    if combinators:
        if len(node) != 1:
            raise RuleFormatError("a combinator node holds exactly one entry")
        key = combinators[0]
        if key in ("all", "any"):
            children = node[key]
            if not isinstance(children, list) or not 1 <= len(children) <= 32:
                raise RuleFormatError(f"'{key}' takes a bounded non-empty list of predicates")
            return {key: [_validate_condition(child, depth + 1, leaves) for child in children]}
        return {"not": _validate_condition(node["not"], depth + 1, leaves)}
    leaf = _validate_leaf(node)
    leaves.append(leaf)
    if len(leaves) > _MAX_LEAVES:
        raise RuleFormatError("the number of predicate leaves is bounded")
    return {"leaf": leaf}


def load_rule(document: str) -> SuitabilityRule:
    """Parse and fully validate one TOML rule document; fail closed on any defect."""
    if not isinstance(document, str) or not 0 < len(document) <= 64 * 1024:
        raise RuleFormatError("a rule document is a bounded TOML text")
    try:
        data = tomllib.loads(document)
    except tomllib.TOMLDecodeError as exc:
        raise RuleFormatError(f"invalid TOML: {exc}") from exc
    if not isinstance(data, dict):
        raise RuleFormatError("a rule document is a TOML table")
    if not set(data) <= _TOP_LEVEL_KEYS:
        raise RuleFormatError(f"unknown top-level tables: {sorted(set(data) - _TOP_LEVEL_KEYS)}")

    rule = data.get("rule")
    if not isinstance(rule, dict):
        raise RuleFormatError("missing [rule] table")
    if not set(rule) <= _RULE_KEYS:
        raise RuleFormatError(f"unknown [rule] keys: {sorted(set(rule) - _RULE_KEYS)}")
    if rule.get("format") != FORMAT_VERSION:
        raise RuleFormatError(f"format must be {FORMAT_VERSION!r}")
    rule_id = _bounded_str(rule.get("id"), "rule.id", 128)
    rule_version = _bounded_str(rule.get("version"), "rule.version", 64)
    scope = _bounded_str(rule.get("scope"), "rule.scope", 400)
    reference = _bounded_str(rule.get("reference"), "rule.reference", 256)

    article = data.get("article")
    if not isinstance(article, dict):
        raise RuleFormatError("missing [article] table")
    if not set(article) <= _ARTICLE_KEYS:
        raise RuleFormatError(f"unknown [article] keys: {sorted(set(article) - _ARTICLE_KEYS)}")
    act = _bounded_str(article.get("act"), "article.act", 256)
    article_id = _bounded_str(article.get("article"), "article.article", 64)
    language = article.get("language")
    if language not in _LANGUAGES:
        raise RuleFormatError("article.language is 'nl' or 'fr'")
    article_version = _bounded_str(article.get("version"), "article.version", 128)
    if any("#" in part for part in (act, article_id, language, article_version)):
        raise RuleFormatError("article identity parts must not contain '#'")

    condition = data.get("condition")
    if condition is None:
        raise RuleFormatError("missing [condition] predicate")
    leaves: list[_Leaf] = []
    validated = _validate_condition(condition, 1, leaves)
    if not leaves:
        raise RuleFormatError("a rule evaluates at least one fact predicate")

    outcomes = data.get("outcomes", {})
    if not isinstance(outcomes, dict):
        raise RuleFormatError("[outcomes] is a table")
    if not set(outcomes) <= {"on_true", "on_false"}:
        raise RuleFormatError("[outcomes] holds only on_true and on_false")
    if outcomes.get("on_true", "PASS") != "PASS" or outcomes.get("on_false", "FAIL") != "FAIL":
        raise RuleFormatError("suitability outcomes are PASS/FAIL; anything else is UNDETERMINED by construction")

    digest = hashlib.sha256(document.encode("utf-8")).hexdigest()
    return SuitabilityRule(
        rule_id=rule_id,
        rule_version=rule_version,
        act=act,
        article=article_id,
        language=language,
        article_version=article_version,
        scope=scope,
        reference=reference,
        condition=validated,
        source_sha256=digest,
    )


def _compare(op: str, actual: ScalarValue, expected: Any) -> bool | None:
    """Compare a fact value; None means the pairing is not decidable."""
    if op == "present":
        return True
    if op in ("in", "between"):
        member = expected[0]
        if _family(actual) != _family(member):
            return None
    elif _family(actual) != _family(expected):
        return None
    if op == "eq":
        return bool(actual == expected)
    if op == "ne":
        return bool(actual != expected)
    if op == "in":
        return bool(any(actual == member for member in expected))
    if op in ("lt", "le", "gt", "ge"):
        comparisons: dict[str, bool] = {"lt": actual < expected, "le": actual <= expected,
                                        "gt": actual > expected, "ge": actual >= expected}
        return comparisons[op]
    if op == "between":
        return bool(expected[0] <= actual <= expected[1])
    raise RuleFormatError(f"unsupported predicate operator: {op!r}")


def _eval(node: Any, facts: Mapping[str, ConfirmedFact], subresults: list[tuple[str, str]],
          unavailable: list[str], used: set[str]) -> bool | None:
    """Evaluate a validated predicate; None means evidence was unavailable or undecidable."""
    if "all" in node:
        outcomes = [_eval(child, facts, subresults, unavailable, used) for child in node["all"]]
        if any(o is None for o in outcomes):
            return None
        return all(outcomes)
    if "any" in node:
        outcomes = [_eval(child, facts, subresults, unavailable, used) for child in node["any"]]
        if any(o is None for o in outcomes):
            return None
        return any(outcomes)
    if "not" in node:
        inner = _eval(node["not"], facts, subresults, unavailable, used)
        return None if inner is None else not inner
    leaf: _Leaf = node["leaf"]
    index = len([key for key, _ in subresults])
    fact = facts.get(leaf.fact)
    if fact is None or not fact.confirmed:
        unavailable.append(leaf.fact)
        subresults.append((f"p{index}:fact:{leaf.fact}"[:64], "unavailable_or_unconfirmed"))
        return None
    used.add(leaf.fact)
    rendered = f"{leaf.fact} {leaf.op} {leaf.value!r}" if leaf.op != "present" else f"{leaf.fact} present"
    holds = _compare(leaf.op, fact.value, leaf.value)
    if holds is None:
        unavailable.append(leaf.fact)
        subresults.append((f"p{index}:{rendered}"[:64], "not_comparable"))
        return None
    subresults.append((f"p{index}:{rendered}"[:64], "holds" if holds else "violated"))
    return holds


def evaluate_rule(
    rule: SuitabilityRule,
    facts: Mapping[str, ConfirmedFact],
    corpus_articles: frozenset[str] | set[str],
) -> RuleResult:
    """Evaluate one rule over confirmed facts against the case's chosen corpus.

    corpus_articles holds the canonical article_key of every article present
    in the corpus chosen for the case (build keys with article_key()). Absence
    of the rule's article is UNVERIFIED, the reserved contract status; it
    never means the article does not exist.
    """
    if not isinstance(rule, SuitabilityRule):
        raise RuleFormatError("a validated SuitabilityRule is required")
    if not isinstance(corpus_articles, (set, frozenset)):
        raise RuleFormatError("the case's chosen corpus is an explicit set of article keys")
    if not all(isinstance(key, str) and key for key in corpus_articles):
        raise RuleFormatError("corpus article keys are non-empty strings")
    for name, fact in facts.items():
        if not isinstance(fact, ConfirmedFact) or fact.name != name:
            raise RuleFormatError(f"facts must be ConfirmedFact values keyed by their name: {name!r}")

    base_fields: dict[str, Any] = {
        "rule_id": rule.rule_id,
        "rule_version": rule.rule_version,
        "reference": rule.reference,
        "scope": rule.scope,
    }

    if rule.article_key not in corpus_articles:
        base_parts = rule.base_article_key.split("#")
        held_versions = sorted(
            (parts[3] if len(parts) > 3 else "(version_undeclared_in_corpus)")
            for key in corpus_articles
            if (parts := key.split("#"))[:3] == base_parts
        )
        if held_versions:
            # The corpus holds the article, but not at the version the rule
            # declares. Identity mismatch is UNDETERMINED: the machine cannot
            # decide across versions and never infers applicability.
            return RuleResult(
                **base_fields,
                status=RuleStatus.UNDETERMINED,
                preconditions=(RulePrecondition(
                    name="article_version_matches_corpus", met=False,
                    detail=(f"Rule declares version {rule.article_version!r}; corpus holds: "
                            + ", ".join(held_versions))[:400],),),
                input_hashes=(("rule_source", rule.source_sha256),),
                reason="article_version_mismatch_or_ambiguous",
                subresults=(("corpus_membership", "version_mismatch"),
                            ("corpus_versions", ", ".join(held_versions)[:400]),),
            )
        return RuleResult(
            **base_fields,
            status=RuleStatus.UNVERIFIED,
            preconditions=(RulePrecondition(
                name="article_in_chosen_corpus", met=False,
                detail="The rule's article is absent from the case's chosen corpus."),),
            input_hashes=(("rule_source", rule.source_sha256),),
            reason="article_absent_from_chosen_corpus",
            subresults=(("corpus_membership", "article_not_in_chosen_corpus"),),
        )

    subresults: list[tuple[str, str]] = []
    unavailable: list[str] = []
    used: set[str] = set()
    outcome = _eval(rule.condition, facts, subresults, unavailable, used)
    if not subresults:
        raise RuleFormatError("a validated rule always evaluates at least one predicate")

    facts_digest = hashlib.sha256(
        json.dumps({name: [facts[name].value, facts[name].confirmed]
                    for name in sorted(used)},
                   sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()

    confirmed_precondition = RulePrecondition(
        name="facts_confirmed",
        met=not unavailable,
        detail=("Every fact the rule reads is present, lawyer-confirmed and comparable."
                if not unavailable else
                "Unavailable, unconfirmed or incomparable: " + ", ".join(sorted(set(unavailable)))[:300]),
    )

    if outcome is None:
        status, reason = RuleStatus.UNDETERMINED, "facts_unavailable_unconfirmed_or_incomparable"
    elif outcome:
        status, reason = RuleStatus.PASS, "condition_holds_over_confirmed_facts"
    else:
        status, reason = RuleStatus.FAIL, "condition_violated_over_confirmed_facts"

    return RuleResult(
        **base_fields,
        status=status,
        preconditions=(confirmed_precondition,),
        input_hashes=(("rule_source", rule.source_sha256), ("confirmed_facts", facts_digest)),
        reason=reason,
        subresults=tuple(subresults),
    )
