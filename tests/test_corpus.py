"""Corpus ingestion foundations (roadmap task 4): fail-closed local loading.

All manifests and texts here are SYNTHETIC, never Belgian legal content.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from application.litigation.corpus import CORPUS_FORMAT_VERSION, CorpusError, load_corpus
from application.litigation.rule_results import RuleStatus
from application.litigation.suitability_rules import ConfirmedFact, evaluate_rule, load_rule


def _write_corpus(directory: Path, entries: list[dict[str, object]]) -> None:
    lines = [f'format = "{CORPUS_FORMAT_VERSION}"', ""]
    for entry in entries:
        original = directory / str(entry["original_file"])
        derived = directory / str(entry["derived_file"])
        original.write_bytes(b"synthetic original bytes " + str(entry["article"]).encode())
        derived.write_text("texte derive synthetique " + str(entry["article"]), encoding="utf-8")
        entry["original_sha256"] = hashlib.sha256(original.read_bytes()).hexdigest()
        lines.append("[[publication]]")
        for key, value in entry.items():
            rendered = str(value).lower() if isinstance(value, bool) else f'"{value}"'
            lines.append(f"{key} = {rendered}")
        lines.append("")
    (directory / "corpus-manifest.toml").write_text("\n".join(lines), encoding="utf-8")


def _entry(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "act": "synthetic-act-2026",
        "article": "1",
        "language": "fr",
        "version": "2026-01-01",
        "source_uri": "https://www.ejustice.just.fgov.be/eli/loi/2026/01/01/synthetic/moniteur",
        "acquired_at": "2026-11-22",
        "consolidated": False,
        "original_file": "original-1.pdf",
        "derived_file": "derived-1.txt",
    }
    base.update(overrides)
    return base


def test_load_valid_corpus(tmp_path: Path) -> None:
    _write_corpus(tmp_path, [_entry()])
    report = load_corpus(tmp_path)
    assert report.failures == ()
    assert report.ambiguous_versions == ()
    assert report.article_keys == {"synthetic-act-2026#1#fr#2026-01-01"}
    record = report.records[0]
    assert record.consolidated is False
    assert len(record.original_sha256) == 64
    assert "synthetique" in record.derived_text


def test_hash_mismatch_is_an_ingestion_failure(tmp_path: Path) -> None:
    _write_corpus(tmp_path, [_entry()])
    (tmp_path / "original-1.pdf").write_bytes(b"tampered")
    report = load_corpus(tmp_path)
    assert len(report.failures) == 1
    assert "hash mismatch" in report.failures[0]
    assert report.records == ()


def test_missing_file_is_an_ingestion_failure(tmp_path: Path) -> None:
    _write_corpus(tmp_path, [_entry()])
    (tmp_path / "derived-1.txt").unlink()
    report = load_corpus(tmp_path)
    assert len(report.failures) == 1
    assert "missing derived text file" in report.failures[0]


def test_ambiguous_versions_are_measured(tmp_path: Path) -> None:
    _write_corpus(tmp_path, [
        _entry(),
        _entry(version="2024-06-01", original_file="original-2.pdf", derived_file="derived-2.txt"),
    ])
    report = load_corpus(tmp_path)
    assert report.ambiguous_versions == ("synthetic-act-2026#1#fr",)
    assert len(report.article_keys) == 2


def test_duplicate_key_is_an_ingestion_failure(tmp_path: Path) -> None:
    _write_corpus(tmp_path, [
        _entry(),
        _entry(original_file="original-2.pdf", derived_file="derived-2.txt"),
    ])
    report = load_corpus(tmp_path)
    assert len(report.failures) == 1
    assert "duplicate" in report.failures[0]
    assert len(report.records) == 1


def test_missing_or_wrong_manifest_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(CorpusError):
        load_corpus(tmp_path)
    (tmp_path / "corpus-manifest.toml").write_text('format = "wrong"', encoding="utf-8")
    with pytest.raises(CorpusError):
        load_corpus(tmp_path)


def test_unknown_manifest_keys_rejected(tmp_path: Path) -> None:
    _write_corpus(tmp_path, [_entry(commentaire="typo")])
    report = load_corpus(tmp_path)
    assert len(report.failures) == 1
    assert "unknown keys" in report.failures[0]


def test_unsafe_paths_rejected(tmp_path: Path) -> None:
    _write_corpus(tmp_path, [_entry(derived_file="../escape.txt")])
    (tmp_path / ".." / "escape.txt") if False else None  # never written
    report = load_corpus(tmp_path)
    assert len(report.failures) == 1
    assert "unsafe corpus path" in report.failures[0]


def test_corpus_feeds_rule_evaluation(tmp_path: Path) -> None:
    _write_corpus(tmp_path, [_entry()])
    report = load_corpus(tmp_path)
    doc = """
[rule]
format = "caseproof-suitability-rule-format-v1"
id = "synthetic.example"
version = "0.1.0"
scope = "synthetic"
reference = "Synthetic Act, art. 1"

[article]
act = "synthetic-act-2026"
article = "1"
language = "fr"
version = "2026-01-01"

[condition]
fact = "deposit_paid"
op = "present"
"""
    rule = load_rule(doc)
    facts = {"deposit_paid": ConfirmedFact(name="deposit_paid", value=True, confirmed=True)}
    result = evaluate_rule(rule, facts, report.article_keys)
    assert result.status == RuleStatus.PASS
    empty = evaluate_rule(rule, facts, set())
    assert empty.status == RuleStatus.UNVERIFIED
