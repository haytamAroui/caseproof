"""Signed lawyer conditions inside the offline pack. FAKE-backed: auth, storage, DB, conditions store and source
previews are stand-ins; route, matching, pack build and cold replay are real code. Legacy packs must not change."""
from __future__ import annotations

import hashlib
import io
import json
from types import SimpleNamespace as NS
from zipfile import ZipFile

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from application.litigation.corpus import CorpusError
from application.litigation.legal_references import check_legal_references, load_corpus_config
from application.litigation.offline_legal_pack import verify_legal_pack
from apps.api.access_control import AccessRejected
from apps.api.offline_docx_check import parse_docx
from apps.api.signed_workbench_routes import create_signed_workbench_router
from tests.signed_composed_rig import docx_without_custom_xml
from tests.test_legal_reference_adversarial import ARTICLE, corpus
from tests.test_v2_conditions_route import FakeStore

SNAP = "a" * 64
H = {"Authorization": "Bearer synthetic"}
V = "33333333-3333-4333-8333-333333333333"
COND = {"id": "courrier", "label": "Courrier", "question": "", "trigger": ["Sur le fond"],
        "evidence": ["reçu"], "pieces": []}


def _row(sid, status="ready", warnings=()):
    return NS(source_id=sid, version_id=V, original_sha256="c" * 64, status=status, warnings=warnings, representation_id="r")


def build(tmp_path, monkeypatch, conditions, previews, store=None):
    from apps.api import litigation_evidence_search as les
    monkeypatch.setattr(les.AuthorizedEvidenceSearch, "_require_evidence", staticmethod(lambda _a: None))
    paragraphs = [f"Article 8.5 du Code civil : « {ARTICLE} ».", "Sur le fond, voir Pièce 1."]
    path = tmp_path / "p.docx"
    path.write_bytes(docx_without_custom_xml(paragraphs))
    config = load_corpus_config(corpus(tmp_path))
    text = parse_docx(path.read_bytes())["text"]
    obs = check_legal_references(text, config.records, config.act_aliases,
                                 chosen_versions=config.chosen_versions, strict=True, v3=True)
    run = NS(snapshot_hash=SNAP, representation_sha256=hashlib.sha256(text.encode()).hexdigest(),
             corpus_pack_sha256=config.pack_sha256, legal_observations=tuple(obs), suitability_observations=())
    entries = [NS(confirmed=True, display_label="Pièce 1", pages=[NS(source_id="s1")]),
               NS(confirmed=True, display_label="Pièce 2", pages=[NS(source_id="s2")])]
    bundle = NS(representation=NS(text=text, brief=NS(case_id="c", version_id="v", references=())),
                register=NS(entries=entries), previews=tuple(previews),
                source_scope=NS(declared_source_versions=tuple((p.row.source_id, V) for p in previews),
                                excluded_source_versions=()))
    access = NS(case_id="c")
    wb = NS(checker=NS(check=lambda **_: run, legal_corpus_for=lambda _c: config, _verified=lambda _b: None,
                       _scope=lambda _s, _c: access, store=NS(load_bundle=lambda **_: bundle, still_current=lambda **_: True)),
            store=NS(load_bundle=lambda **_: bundle, still_current=lambda **_: True),
            workspace=NS(state=lambda **_: {"snapshot_hash": SNAP, "decisions": []}))
    app = FastAPI()

    @app.exception_handler(AccessRejected)
    async def denied(request: Request, exc: AccessRejected) -> JSONResponse:
        return JSONResponse({"error": exc.code.value}, status_code=exc.http_status)

    store = store if store is not None else FakeStore()
    app.include_router(create_signed_workbench_router(lambda _b: wb, None, store))
    c = TestClient(app)
    if conditions is not None:
        assert c.post("/v2/matters/c/conditions", json={"expected_revision": 0, "conditions": conditions}, headers=H).status_code == 200
    return c


def pack(c):
    base = "/v2/matters/c/briefs/v/offline-pack"
    m = c.get(base + "/manifest", headers=H).json()
    r = c.get(base, headers=H)
    assert r.status_code == 200
    return r.content, m["checkpoint_sha256"]


def test_pack_without_conditions_has_no_section_and_replays(tmp_path, monkeypatch):
    c = build(tmp_path, monkeypatch, None, [])
    raw, cp = pack(c)
    body = verify_legal_pack(raw, expected_sha256=cp)
    assert "signed_conditions" not in body and "Conditions définies" not in ZipFile(io.BytesIO(raw)).read("report.html").decode()


def test_cleared_conditions_add_no_section(tmp_path, monkeypatch):
    c = build(tmp_path, monkeypatch, [COND], [])
    assert c.post("/v2/matters/c/conditions", json={"expected_revision": 1, "conditions": []}, headers=H).status_code == 200
    body = verify_legal_pack(pack(c)[0], expected_sha256=pack(c)[1])
    assert "signed_conditions" not in body


def test_partial_stays_undetermined_found_is_never_pass_and_replays(tmp_path, monkeypatch):
    previews = [NS(row=_row("s1"), text="Le courrier est bien reçu le 3 mars.", spans=((0, 40, "para", 1),)),
                NS(row=_row("s2", "partial", ("scan",)), text="x", spans=())]
    c = build(tmp_path, monkeypatch, [{**COND, "evidence": ["absentmot"]}], previews)
    raw, cp = pack(c)
    sec = verify_legal_pack(raw, expected_sha256=cp)["signed_conditions"]
    row = sec["anchors"][0]
    assert row["status"] == "UNDETERMINED" and row["pieces_not_read"] == ["Pièce 2"] and row["found"] == []
    assert "Pièces non lues" in ZipFile(io.BytesIO(raw)).read("report.html").decode()
    c2 = build(tmp_path, monkeypatch, [COND], previews, store=FakeStore())
    sec2 = verify_legal_pack(pack(c2)[0], expected_sha256=pack(c2)[1])["signed_conditions"]
    assert sec2["anchors"][0]["status"] == "UNDETERMINED" and sec2["anchors"][0]["found"]
    assert all(a["status"] != "PASS" for a in sec2["anchors"])


def test_replay_refuses_forged_sections(tmp_path, monkeypatch):
    previews = [NS(row=_row("s1"), text="Le courrier est bien reçu.", spans=((0, 30, "para", 1),)),
                NS(row=_row("s2", "partial", ("scan",)), text="x", spans=())]
    c = build(tmp_path, monkeypatch, [{**COND, "evidence": ["absentmot"]}], previews)
    raw, cp = pack(c)
    from application.litigation import offline_legal_pack as olp
    from application.litigation.signed_conditions_pack import validate_section
    body = verify_legal_pack(raw, expected_sha256=cp)
    sec = body["signed_conditions"]
    forged = json.loads(json.dumps(sec))
    forged["anchors"][0].update(status="UNVERIFIED", reason="condition_no_passage_found_in_every_piece_read")
    with pytest.raises(CorpusError):  # unread piece must not become a clean "no passage" result
        validate_section(body["brief_text"], forged)
    forged = json.loads(json.dumps(sec))
    forged["anchors"][0]["status"] = "PASS"
    with pytest.raises(CorpusError):
        validate_section(body["brief_text"], forged)
    forged = json.loads(json.dumps(sec))
    forged["spec_text"] = forged["spec_text"].replace("absentmot", "autre")
    with pytest.raises(CorpusError):
        validate_section(body["brief_text"], forged)
    forged = json.loads(json.dumps(sec))
    forged["anchors"][0]["sentence"] = "autre phrase"
    with pytest.raises(CorpusError):
        validate_section(body["brief_text"], forged)
    assert olp  # module imported for the real replay path above
