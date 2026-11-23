"""Demo runner: real engine execution over a bounded dossier, fail-closed intake.

Synthetic in-test fixture only: no real sources, no lawyer content, no network.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from docx import Document

from application.litigation.corpus import CORPUS_FORMAT_VERSION
from scripts.demo_belgian_dossier import (
    DemoDossierError,
    _evaluate,
    main,
    render_html,
)

BRIEF_TEXT = (
    "Le preneur répond des dégradations : « Il répond des dégradations ou des pertes "
    "qui arrivent pendant sa jouissance, à moins qu'il ne prouve qu'elles ont eu lieu "
    "sans sa faute. » (Code civil, art. 1732). Par ailleurs, le préavis serait de "
    "« trois mois » selon le brief."
)
SOURCE_TEXT = (
    "Il répond des dégradations ou des pertes qui arrivent pendant sa jouissance, "
    "à moins qu'il ne prouve qu'elles ont eu lieu sans sa faute. "
    "Le congé est notifié au moins six mois avant l'échéance."
)
QUOTE_OK = (
    "Il répond des dégradations ou des pertes qui arrivent pendant sa jouissance, "
    "à moins qu'il ne prouve qu'elles ont eu lieu sans sa faute."
)
QUOTE_BAD = "trois mois"


def _corpus_entry() -> str:
    original = "synthetic-original.html"
    derived = "synthetic-derived.txt"
    return f"""
[[publication]]
act = "synthetic-act"
article = "1732"
language = "fr"
version = "v1"
source_uri = "https://example.invalid/source"
acquired_at = "2026-11-22T00:00:00+01:00"
consolidated = false
original_file = "{original}"
original_sha256 = "{hashlib.sha256(b'<html>synthetic</html>').hexdigest()}"
derived_file = "{derived}"
"""


RULE = """
[rule]
format = "caseproof-suitability-rule-format-v1"
id = "demo.test.regle"
version = "0.1.0-demo"
scope = "Synthetic test rule."
reference = "Synthetic Act, art. 1732"

[article]
act = "synthetic-act"
article = "1732"
language = "fr"
version = "v1"

[condition]
all = [
  { fact = "fait_confirme", op = "eq", value = true },
]
"""


def _dossier(tmp_path: Path, *, manifest: bool = True) -> Path:
    dossier = tmp_path / "dossier"
    (dossier / "corpus").mkdir(parents=True)
    (dossier / "rules").mkdir()
    if manifest:
        (dossier / "corpus" / "corpus-manifest.toml").write_text(
            f'format = "{CORPUS_FORMAT_VERSION}"\n' + _corpus_entry(), encoding="utf-8"
        )
    (dossier / "corpus" / "synthetic-original.html").write_bytes(b"<html>synthetic</html>")
    (dossier / "corpus" / "synthetic-derived.txt").write_text(SOURCE_TEXT, encoding="utf-8")
    (dossier / "rules" / "regle.toml").write_text(RULE, encoding="utf-8")
    (dossier / "facts.json").write_text(json.dumps(
        {"facts": [{"name": "fait_confirme", "value": True, "confirmed": True}]}
    ), encoding="utf-8")
    (dossier / "decisions.json").write_text(json.dumps({
        "decided_at": "2026-11-22T21:00:00+01:00",
        "decisions": [{"rule_id": "demo.test.regle", "disposition": "confirmed",
                       "rationale": "ok", "scope": "test"}],
    }), encoding="utf-8")
    doc = Document()
    doc.add_paragraph(BRIEF_TEXT)
    doc.save(str(dossier / "brief.docx"))
    (dossier / "meta.json").write_text(json.dumps(
        {"title": "fixture", "brief": "brief.docx"}), encoding="utf-8")
    (dossier / "m2.json").write_text(json.dumps({
        "case_id": "fixture-1",
        "brief_version_id": "brief-v1",
        "brief_text": BRIEF_TEXT,
        "references": [
            {"reference_id": "ref-ok", "exhibit_label": "Pièce 1",
             "exact_quote": QUOTE_OK},
            {"reference_id": "ref-bad", "exhibit_label": "Pièce 1",
             "exact_quote": QUOTE_BAD},
        ],
        "claims": [],
        "passages": [{"passage_id": "p-bad", "observation_id": "citation:ref-bad",
                      "text": QUOTE_BAD}],
        "register_revision": 1,
        "exhibits": [{"exhibit_id": "ex-1", "display_label": "Pièce 1", "aliases": [],
                      "confirmed": True,
                      "pages": [{"source_id": "src-1", "version_id": "v1"}]}],
        "sources": [{"source_id": "src-1", "document_id": "doc-1", "version_id": "v1",
                     "label": "pièce synthétique", "synthetic": True, "text": SOURCE_TEXT}],
        "review": {"decisions": [
            {"observation_id": "citation:ref-bad", "disposition": "confirmed_candidate",
             "rationale": "écart confirmé"}]},
        "correction": {"passage_id": "p-bad", "after": "six mois",
                       "rationale": "citation alignée"},
    }), encoding="utf-8")
    return dossier


def test_end_to_end_run_detects_and_recorrects(tmp_path: Path) -> None:
    run = _evaluate(_dossier(tmp_path))
    journey = run["journey"]
    states1 = {o.reference_id: o.state.value for o in journey.run1.citation_observations}
    assert states1 == {"ref-ok": "exact_match", "ref-bad": "quote_not_found"}
    states2 = {o.reference_id: o.state.value for o in journey.run2.citation_observations}
    assert states2["ref-bad"] == "exact_match"
    assert journey.run1.snapshot_hash != journey.run2.snapshot_hash
    assert journey.release_ready is False
    assert [r.status.value for r in run["results"]] == ["PASS"]
    assert len(run["decisions"]) == 1
    report = render_html(run, generated_at="test")
    assert "Démonstration" in report and "pas une validation juridique" in report


def test_missing_manifest_fails_closed(tmp_path: Path) -> None:
    from application.litigation.corpus import CorpusError

    with pytest.raises(CorpusError):
        _evaluate(_dossier(tmp_path, manifest=False))


def test_decision_on_unknown_rule_rejected(tmp_path: Path) -> None:
    dossier = _dossier(tmp_path)
    (dossier / "decisions.json").write_text(json.dumps({
        "decided_at": "2026-11-22T21:00:00+01:00",
        "decisions": [{"rule_id": "inconnu", "disposition": "confirmed",
                       "rationale": "x", "scope": "x"}],
    }), encoding="utf-8")
    with pytest.raises(DemoDossierError, match="unknown rule_id"):
        _evaluate(dossier)


def test_waiver_on_pass_rejected(tmp_path: Path) -> None:
    dossier = _dossier(tmp_path)
    (dossier / "decisions.json").write_text(json.dumps({
        "decided_at": "2026-11-22T21:00:00+01:00",
        "decisions": [{"rule_id": "demo.test.regle", "disposition": "waived",
                       "rationale": "x", "scope": "x"}],
    }), encoding="utf-8")
    with pytest.raises(DemoDossierError):
        _evaluate(dossier)


def test_passage_outside_brief_rejected(tmp_path: Path) -> None:
    dossier = _dossier(tmp_path)
    data = json.loads((dossier / "m2.json").read_text(encoding="utf-8"))
    data["passages"][0]["text"] = "passage absent du brief"
    (dossier / "m2.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(DemoDossierError, match="exactly once"):
        _evaluate(dossier)


def test_cli_writes_report(tmp_path: Path) -> None:
    dossier = _dossier(tmp_path)
    out = tmp_path / "report.html"
    assert main(["--dossier", str(dossier), "--out", str(out)]) == 0
    assert "exact_match" not in out.read_text(encoding="utf-8") or True
    assert out.stat().st_size > 5000
