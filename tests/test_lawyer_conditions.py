"""Lawyer-defined conditions: retrieval for appraisal, never PASS; tampering and legacy replay."""
from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from application.litigation.corpus import CorpusError
from application.litigation.lawyer_conditions import R_FOUND, R_NONE
from application.litigation.offline_legal_pack import verify_legal_pack
from apps.api.offline_docx_check import check_offline_docx
from apps.api.offline_review import record_decisions
from tests.signed_composed_rig import docx_without_custom_xml
from tests.test_exhibit_coverage import make_pdf, reseal
from tests.test_legal_reference_adversarial import pdf_corpus

CONDITIONS = (
    'format = "caseproof-conditions-v1"\n'
    '[[condition]]\nid = "courrier-recu"\nlabel = "Courrier : réception établie"\n'
    'question = "Une pièce établit-elle que le courrier a été reçu ?"\n'
    'trigger = ["courrier", "brief"]\nevidence = ["reçu", "ontvangen"]\n')


def run(tmp_path: Path, paragraphs: list[str], conditions: str = CONDITIONS):
    d = tmp_path / "pieces"
    d.mkdir(parents=True, exist_ok=True)
    (d / "p1.pdf").write_bytes(make_pdf("Accuse: le courrier a ete re\u00e7u le lundi."))
    (d / "bordereau.toml").write_text('format = "caseproof-bordereau-v1"\n[[piece]]\nnumber = "1"\nlabel = "AR"\nfile = "p1.pdf"\n')
    (tmp_path / "conditions.toml").write_text(conditions, encoding="utf-8")
    p = tmp_path / "w.docx"
    p.write_bytes(docx_without_custom_xml(paragraphs))
    raw, cp = check_offline_docx(docx=p, corpus=pdf_corpus(tmp_path), exhibits=d, conditions=tmp_path / "conditions.toml")
    return raw, cp, verify_legal_pack(raw, expected_sha256=cp)


def cond_rows(body):
    return [r for r in body["references"] if r["reason"] in (R_FOUND, R_NONE)]


def test_trigger_anchors_a_row_that_is_never_pass_and_evidence_is_recorded(tmp_path):
    raw, _, body = run(tmp_path, ["Le courrier a été envoyé le 3 avril (pièce 1).", "Autre phrase sans rapport."])
    rows = cond_rows(body)
    assert len(rows) == 1 and rows[0]["status"] == "UNDETERMINED" and rows[0]["reason"] == R_FOUND
    assert body["review"]["check_engine"].endswith("v6") and body["condition_evidence"][0]["found"]
    assert "Condition définie par l" in zipfile.ZipFile(BytesIO(raw)).read("report.html").decode()
    assert all(r["status"] != "PASS" for r in rows)


def test_no_passage_is_unverified_not_absence_proof(tmp_path):
    (tmp_path / "pieces").mkdir()
    _, _, body = run(tmp_path, ["Le courrier recommandé est établi."], CONDITIONS.replace('"reçu", "ontvangen"', '"notifié"'))
    assert cond_rows(body)[0]["status"] == "UNVERIFIED" and cond_rows(body)[0]["reason"] == R_NONE


def test_conditions_need_exhibits_and_a_valid_file(tmp_path):
    p = tmp_path / "w.docx"
    p.write_bytes(docx_without_custom_xml(["Le courrier."]))
    (tmp_path / "c.toml").write_text(CONDITIONS)
    with pytest.raises(CorpusError, match="exhibit"):
        check_offline_docx(docx=p, corpus=pdf_corpus(tmp_path), conditions=tmp_path / "c.toml")
    bad = tmp_path / "bad.toml"
    bad.write_text('format = "caseproof-conditions-v1"\n[[condition]]\nid = "X"\nlabel = "a"\ntrigger = ["ab"]\nevidence = ["cd"]\n')
    with pytest.raises(CorpusError):
        run(tmp_path, ["Le courrier."], bad.read_text())


def test_tampering_with_resealed_exports_is_refused_with_an_untouched_control(tmp_path):
    raw, _, _ = run(tmp_path, ["Le courrier a été envoyé (pièce 1)."])
    z = zipfile.ZipFile(BytesIO(raw))
    control, control_sha = reseal(json.loads(z.read("review.json")), z.read("report.html"))
    verify_legal_pack(control, expected_sha256=control_sha)
    for edit in ("spec_trigger", "excerpt", "fabricated_hit", "drop_section", "sentence"):
        body = json.loads(z.read("review.json"))
        if edit == "spec_trigger":
            body["conditions"]["conditions"][0]["trigger"] = ["autre"]
        elif edit == "excerpt":
            body["condition_evidence"][0]["found"][0]["excerpt"] = "reçu par un tiers"
        elif edit == "fabricated_hit":
            body["condition_evidence"][0]["found"][0]["term"] = "inconnu"
            import hashlib
            f = body["condition_evidence"][0]["found"][0]
            f["excerpt"] = "autre"
            f["excerpt_sha256"] = hashlib.sha256(b"autre").hexdigest()
        elif edit == "drop_section":
            del body["conditions"]
            del body["condition_evidence"]
        else:
            body["condition_evidence"][0]["sentence"] = "Une autre phrase."
        data, sha = reseal(body, z.read("report.html"))
        with pytest.raises(CorpusError, match="rejected"):
            verify_legal_pack(data, expected_sha256=sha)


def test_decision_on_a_condition_row_is_local_and_binds_to_the_evidence(tmp_path):
    raw, cp, body = run(tmp_path, ["Le courrier a été envoyé (pièce 1)."])
    idx = next(i for i, r in enumerate(body["references"]) if r["reason"] == R_FOUND)
    raw2, cp2 = record_decisions(pack=raw, checkpoint=cp, decisions=[
        {"reference_index": idx, "action": "confirm", "reason": "", "reviewer_label": "local"}])
    after = verify_legal_pack(raw2, expected_sha256=cp2)
    assert after["conditions"] == body["conditions"] and after["condition_evidence"] == body["condition_evidence"]
    assert len(after["review"]["decisions"]) == 1 and after["review"]["release_authorized"] is False


def test_omitted_passage_flag_needs_a_reason_is_local_and_binds_to_the_finding(tmp_path):
    raw, cp, body = run(tmp_path, ["Le courrier a été envoyé (pièce 1)."])
    idx = next(i for i, r in enumerate(body["references"]) if r["reason"] == R_FOUND)
    with pytest.raises(CorpusError):
        record_decisions(pack=raw, checkpoint=cp, decisions=[
            {"reference_index": idx, "action": "omission", "reason": "", "reviewer_label": "local"}])
    raw2, cp2 = record_decisions(pack=raw, checkpoint=cp, decisions=[
        {"reference_index": idx, "action": "omission", "reason": "pièce 1, p. 2: accusé de réception non montré", "reviewer_label": "local"}])
    after = verify_legal_pack(raw2, expected_sha256=cp2)
    d = after["review"]["decisions"][0]
    assert d["action"] == "omission" and after["review"]["release_authorized"] is False
    assert "accusé de réception non montré" in zipfile.ZipFile(BytesIO(raw2)).read("report.html").decode()
    forged, sha = reseal({**after, "review": {**after["review"], "decisions": [{**d, "reason": ""}]}}, zipfile.ZipFile(BytesIO(raw2)).read("report.html"))
    with pytest.raises(CorpusError, match="rejected"):
        verify_legal_pack(forged, expected_sha256=sha)
