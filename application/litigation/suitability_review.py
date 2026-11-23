"""Typed suitability rules applied to the articles a brief cites.

Offline and deterministic. The rules and the lawyer-confirmed facts are plain
files chosen for the matter (``suitability-rules/*.toml`` and
``confirmed-facts.toml`` next to the corpus). A rule runs only when the brief
cites its article and that article is in the chosen corpus; the result is the
lawyer's own condition evaluated on lawyer-confirmed facts, never a machine
legal conclusion. Missing or unconfirmed inputs are named, never guessed.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from application.litigation.suitability_rules import (
    ConfirmedFact,
    RuleFormatError,
    SuitabilityRule,
    article_key,
    evaluate_rule,
    load_rule,
)
from application.litigation.unified_review import LegalObservation, SuitabilityObservation

_MAX_RULES = 64
_MAX_FACTS = 512


@dataclass(frozen=True, slots=True)
class SuitabilityConfig:
    rules: tuple[SuitabilityRule, ...] = ()
    facts: tuple[tuple[ConfirmedFact, str], ...] = ()  # fact, provenance
    failures: tuple[str, ...] = ()


def load_suitability_config(directory: Path) -> SuitabilityConfig:
    rules: list[SuitabilityRule] = []
    failures: list[str] = []
    rule_dir = directory / "suitability-rules"
    if rule_dir.is_dir():
        for path in sorted(rule_dir.glob("*.toml"))[:_MAX_RULES]:
            try:
                rules.append(load_rule(path.read_text(encoding="utf-8")))
            except (RuleFormatError, UnicodeDecodeError) as exc:
                failures.append(f"{path.name}: {exc}")
    facts: list[tuple[ConfirmedFact, str]] = []
    facts_path = directory / "confirmed-facts.toml"
    if facts_path.is_file():
        try:
            data = tomllib.loads(facts_path.read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
            failures.append(f"confirmed-facts.toml: {exc}")
            data = {}
        entries = data.get("fact") or []
        for index, entry in enumerate(entries[:_MAX_FACTS] if isinstance(entries, list) else []):
            try:
                provenance = entry.get("provenance")
                if not isinstance(provenance, str) or not provenance.strip():
                    raise RuleFormatError("a fact needs a provenance (source, who confirmed)")
                facts.append((ConfirmedFact(
                    entry.get("name"), entry.get("value"), entry.get("confirmed")),
                    provenance.strip()[:300]))
            except (RuleFormatError, AttributeError) as exc:
                failures.append(f"fact {index}: {exc}")
    return SuitabilityConfig(tuple(rules), tuple(facts), tuple(failures))


def evaluate_suitability(
    legal: Iterable[LegalObservation], config: SuitabilityConfig,
    corpus_keys: frozenset[str],
) -> tuple[SuitabilityObservation, ...]:
    """Run each rule whose article the brief cites and the corpus holds."""
    facts = {fact.name: fact for fact, _ in config.facts}
    provenance = {fact.name: prov for fact, prov in config.facts}
    out: list[SuitabilityObservation] = []
    for rule in config.rules:
        base = article_key(rule.act, rule.article, rule.language)
        cited = tuple(sorted(
            o.reference_id for o in legal
            if o.corpus_key is not None
            and o.corpus_key.lower().startswith(base)
            and o.status in ("PASS", "FAIL")))
        if not cited:
            continue
        result = evaluate_rule(rule, facts, corpus_keys)
        missing = tuple(sorted({
            n.strip() for p in result.preconditions
            if not p.met and p.name == "facts_confirmed"
            for n in p.detail.split(":", 1)[-1].split(",") if n.strip()}))
        used = tuple(
            (f.name, str(f.value), f.confirmed, provenance.get(f.name, ""))
            for f in (facts[n] for n in sorted(facts)) if _read(rule, f.name))
        out.append(SuitabilityObservation(
            rule_id=result.rule_id, rule_version=result.rule_version,
            reference=result.reference, scope=result.scope,
            status=str(result.status), reason=result.reason,
            article_key=rule.article_key, cited_by=cited, missing=missing,
            facts=used, input_hashes=tuple(result.input_hashes),
            subresults=tuple(result.subresults)))
    return tuple(out)


def _read(rule: SuitabilityRule, name: str) -> bool:
    stack = [rule.condition]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if "leaf" in node and getattr(node["leaf"], "fact", None) == name:
                return True
            stack.extend(node.values())
        elif isinstance(node, (list, tuple)):
            stack.extend(node)
        elif getattr(node, "fact", None) == name:
            return True
    return False


def merge_authenticated_facts(
    config: SuitabilityConfig, rows: Iterable[dict[str, object]],
    *, require_authenticated: bool = True,
) -> SuitabilityConfig:
    """Facts entered through the signed session replace same-named file facts.

    Provenance names the verified actor, the source version and hash, the
    locator and the record time. It records who entered the value against which
    source version; it does not prove the value is true.
    """
    # With a signed fact ledger, a file can only DECLARE a fact: it is kept
    # visible but never counts as confirmed (named as missing in results).
    merged: dict[str, tuple[ConfirmedFact, str]] = {
        f.name: ((ConfirmedFact(f.name, f.value, False),
                  ("declared in file, not authenticated: " + p)[:300])
                 if require_authenticated else (f, p))
        for f, p in config.facts}
    failures = list(config.failures)
    for row in rows:
        try:
            fact = ConfirmedFact(str(row["name"]), row["value"], row["confirmed"])  # type: ignore[arg-type]
        except (RuleFormatError, KeyError) as exc:
            failures.append(f"signed fact refused: {exc}")
            continue
        merged[fact.name] = (fact, (
            f"authenticated signed session: actor {row['actor_id']}, source version "
            f"{row['source_version_id']} sha256 {str(row['source_sha256'])[:12]}, "
            f"{row['locator']}, recorded {row['recorded_at']}")[:300])
    return SuitabilityConfig(config.rules, tuple(merged.values()), tuple(failures))
