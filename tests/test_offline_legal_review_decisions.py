"""Local decisions, carry-over and recheck for the offline legal-reference slice (synthetic corpus)."""
from __future__ import annotations

import hashlib
import json
import socket
from pathlib import Path

import pytest

from application.litigation.corpus import CORPUS_FORMAT_VERSION, CorpusError
from application.litigation.offline_legal_pack import verify_legal_pack
from apps.api.offline_docx_check import check_offline_docx
from apps.api.offline_review import recheck, record_decisions
from tests.signed_composed_rig import docx_without_custom_xml

TEXT = "Article synthétique de contrôle uniquement."


def _corpus(tmp_path: Path, text: str = TEXT, name: str = "corpus") -> Path:
    corpus = tmp_path / name
    corpus.mkdir()
    (corpus / "source.txt").write_text(text)
    (corpus / "article.txt").write_text(text)
    entry = {"act": "synthetic-civ", "article": "12", "language": "fr", "version": "v1",
             "source_uri": "urn:synthetic:offline-test", "acquired_at": "2026-11-23", "consolidated": True,
             "original_file": "source.txt", "derived_file": "article.txt",
             "original_sha256": hashlib.sha256(text.encode()).hexdigest(), "source_artifact_kind": "synthetic"}
    lines = ["format = " + json.dumps(CORPUS_FORMAT_VERSION), "[[publication]]"]
    lines += [k + " = " + (str(v).lower() if isinstance(v, bool) else json.dumps(v)) for k, v in entry.items()]
    (corpus / "corpus-manifest.toml").write_text("\n".join(lines))
    (corpus / "act-aliases.toml").write_text(
        '[act_aliases]\n"C.civ." = "synthetic-civ"\n[chosen_versions]\n"synthetic-civ" = "v1"\n')
    return corpus


def _word(tmp_path: Path, quote: str, name: str = "brief.docx") -> Path:
    path = tmp_path / name
    path.write_bytes(docx_without_custom_xml([f"Article 12 du Code civil : « {quote} »."]))
    return path


def _first(tmp_path: Path, monkeypatch, quote: str):
    monkeypatch.setattr(socket, "socket", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no network")))
    corpus = _corpus(tmp_path)
    raw, cp = check_offline_docx(docx=_word(tmp_path, quote, "a.docx"), corpus=corpus)
    return corpus, raw, cp


def test_decision_is_attributed_locally_bound_and_replays(tmp_path, monkeypatch):
    corpus, raw, cp = _first(tmp_path, monkeypatch, "invented quotation")
    assert verify_legal_pack(raw, expected_sha256=cp)["references"][0]["status"] == "FAIL"
    new, cp2 = record_decisions(pack=raw, checkpoint=cp, decisions=[
        {"reference_index": 0, "action": "reject", "reason": "Citation inexacte, à corriger.",
         "reviewer_label": "Me Test (libellé local)"}])
    body = verify_legal_pack(new, expected_sha256=cp2)
    decision = body["review"]["decisions"][0]
    assert decision["attribution"] == "local_unauthenticated_label" and body["review"]["release_authorized"] is False
    assert body["review"]["prior_checkpoint"] == cp and body["references"][0]["status"] == "FAIL"
    import io
    from zipfile import ZipFile
    html = ZipFile(io.BytesIO(new)).read("report.html").decode()
    assert "Décision locale : reject" in html and "non authentifié" in html
    # The earlier export is unchanged and still replays alone, showing the decision as required.
    html0 = ZipFile(io.BytesIO(raw)).read("report.html").decode()
    assert "Décision requise" in html0
    verify_legal_pack(raw, expected_sha256=cp)


def test_decision_requires_reason_label_and_a_real_unanswered_finding(tmp_path, monkeypatch):
    _corpus_path, raw, cp = _first(tmp_path, monkeypatch, "invented quotation")
    for bad in ({"reference_index": 0, "action": "waive", "reason": " ", "reviewer_label": "x"},
                {"reference_index": 0, "action": "confirm", "reason": "", "reviewer_label": ""},
                {"reference_index": 0, "action": "approve", "reason": "x", "reviewer_label": "x"},
                {"reference_index": 5, "action": "confirm", "reason": "", "reviewer_label": "x"}):
        with pytest.raises(CorpusError):
            record_decisions(pack=raw, checkpoint=cp, decisions=[bad])
    new, cp2 = record_decisions(pack=raw, checkpoint=cp, decisions=[
        {"reference_index": 0, "action": "confirm", "reason": "", "reviewer_label": "L"}])
    with pytest.raises(CorpusError):
        record_decisions(pack=new, checkpoint=cp2, decisions=[
            {"reference_index": 0, "action": "reject", "reason": "x", "reviewer_label": "L"}])


def test_tampered_decision_or_wrong_checkpoint_is_rejected(tmp_path, monkeypatch):
    _c, raw, cp = _first(tmp_path, monkeypatch, "invented quotation")
    new, cp2 = record_decisions(pack=raw, checkpoint=cp, decisions=[
        {"reference_index": 0, "action": "reject", "reason": "r", "reviewer_label": "L"}])
    with pytest.raises(CorpusError):
        verify_legal_pack(new, expected_sha256=cp)
    with pytest.raises(CorpusError):
        record_decisions(pack=new, checkpoint=cp, decisions=[
            {"reference_index": 0, "action": "reject", "reason": "r", "reviewer_label": "L"}])


def test_recheck_keeps_decision_only_for_identical_finding(tmp_path, monkeypatch):
    corpus, raw, cp = _first(tmp_path, monkeypatch, "invented quotation")
    decided, cp2 = record_decisions(pack=raw, checkpoint=cp, decisions=[
        {"reference_index": 0, "action": "qualify", "reason": "à reformuler", "reviewer_label": "L"}])
    # Same Word again: identical finding keeps its decision, marked carried.
    same, cp3 = recheck(docx=tmp_path / "a.docx", corpus=corpus, prior_pack=decided, prior_checkpoint=cp2)
    body = verify_legal_pack(same, expected_sha256=cp3)
    assert body["review"]["decisions"][0]["origin"] == "carried"
    assert body["review"]["decisions"][0]["carried_from"] == cp2 and body["review"]["revision"] == 2
    # Corrected Word: the finding changes, so the old decision no longer answers it but stays visible.
    fixed, cp4 = recheck(docx=_word(tmp_path, TEXT, "b.docx"), corpus=corpus, prior_pack=decided,
                         prior_checkpoint=cp2)
    body = verify_legal_pack(fixed, expected_sha256=cp4)
    assert body["references"][0]["status"] == "PASS" and body["review"]["decisions"] == []
    assert body["review"]["superseded"][0]["action"] == "qualify"
    assert body["review"]["prior_checkpoint"] == cp2


def test_new_corpus_pack_never_inherits_old_decision(tmp_path, monkeypatch):
    corpus, raw, cp = _first(tmp_path, monkeypatch, "invented quotation")
    decided, cp2 = record_decisions(pack=raw, checkpoint=cp, decisions=[
        {"reference_index": 0, "action": "confirm", "reason": "", "reviewer_label": "L"}])
    other = _corpus(tmp_path, text=TEXT + " Version bis.", name="corpus2")
    out, cp3 = recheck(docx=tmp_path / "a.docx", corpus=other, prior_pack=decided, prior_checkpoint=cp2)
    body = verify_legal_pack(out, expected_sha256=cp3)
    assert body["review"]["decisions"] == [] and len(body["review"]["superseded"]) == 1
    assert body["corpus_pack_sha256"] != json.loads(
        __import__("zipfile").ZipFile(__import__("io").BytesIO(decided)).read("review.json"))["corpus_pack_sha256"]


def test_recheck_refuses_forged_prior_review(tmp_path, monkeypatch):
    corpus, raw, cp = _first(tmp_path, monkeypatch, "invented quotation")
    with pytest.raises(CorpusError):
        recheck(docx=tmp_path / "a.docx", corpus=corpus, prior_pack=raw, prior_checkpoint="0" * 64)
