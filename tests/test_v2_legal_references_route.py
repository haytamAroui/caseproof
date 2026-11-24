"""The product frontend reads cited-article results under /v2, same run as the /dev route.

Auth, storage and Postgres are faked (labelled): this proves route wiring, the
contract validation and fail-closed behaviour, not the live signed identity path.
"""
from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from application.litigation.legal_references import check_legal_references, load_corpus_config
from apps.api.offline_docx_check import parse_docx
from apps.api.signed_workbench_routes import create_signed_workbench_router
from tests.signed_composed_rig import docx_without_custom_xml
from tests.test_legal_reference_adversarial import ARTICLE, corpus

SNAP = "a" * 64


def _client(tmp_path, paragraphs, *, with_corpus=True):
    path = tmp_path / "p.docx"
    path.write_bytes(docx_without_custom_xml(paragraphs))
    config = load_corpus_config(corpus(tmp_path))
    text = parse_docx(path.read_bytes())["text"]
    legal = check_legal_references(text, config.records, config.act_aliases,
                                   chosen_versions=config.chosen_versions, strict=True, v3=True)
    run = SimpleNamespace(snapshot_hash=SNAP, representation_sha256=hashlib.sha256(text.encode()).hexdigest(),
                          corpus_pack_sha256=config.pack_sha256 if with_corpus else None,
                          legal_observations=tuple(legal), suitability_observations=())
    checker = SimpleNamespace(check=lambda **_: run, legal_corpus_for=lambda _c: config if with_corpus else None,
                              _verified=lambda _b: None, _scope=lambda _s, _c: SimpleNamespace(case_id="c"))
    wb = SimpleNamespace(checker=checker, workspace=None, store=SimpleNamespace(
        load_bundle=lambda **_: SimpleNamespace(representation=SimpleNamespace(text=text))))
    from fastapi import Request
    from fastapi.responses import JSONResponse

    from apps.api.access_control import AccessRejected
    app = FastAPI()

    @app.exception_handler(AccessRejected)
    async def denied(request: Request, exc: AccessRejected) -> JSONResponse:
        return JSONResponse({"error": exc.code.value}, status_code=exc.http_status)

    app.include_router(create_signed_workbench_router(lambda _b: wb))
    return TestClient(app), legal


H = {"Authorization": "Bearer synthetic"}
BASE = "/v2/matters/c/briefs/v/legal-references"


def test_v2_route_returns_contract_and_matches_dev_route(tmp_path):
    client, legal = _client(tmp_path, [f"Article 8.5 du Code civil : « {ARTICLE} »."])
    body = client.get(BASE, headers=H).json()
    assert body["schema"] == "caseproof-legal-references-v1"
    dev = client.get("/dev/signed/matters/c/briefs/v/legal-references", headers=H).json()
    assert [(r["reference_id"], r["status"], r["reason"]) for r in body["references"]] == \
        [(r["reference_id"], r["status"], r["reason"]) for r in dev["references"]]
    assert body["coverage"]["detected"] == len(legal) >= 1
    assert all(r["claim_support"] == "not_assessed" for r in body["references"])
    assert body["suitability"] == []


def test_v2_requires_a_bearer(tmp_path):
    client, _ = _client(tmp_path, [f"Article 8.5 du Code civil : « {ARTICLE} »."])
    assert client.get(BASE).status_code == 401


def test_v2_passage_is_side_by_side_and_bound_to_the_frozen_hash(tmp_path):
    client, legal = _client(tmp_path, [f"Article 8.5 du Code civil : « {ARTICLE} »."])
    rid = legal[0].reference_id
    body = client.get(f"{BASE}/{rid}/passage", headers=H).json()
    assert body["schema"] == "caseproof-legal-passage-v1"
    assert ARTICLE in body["article_text"]
    a, b = body["citation_span"]
    assert body["brief_excerpt"][a:b] == legal[0].raw_text
    assert client.get(f"{BASE}/nope/passage", headers=H).status_code in (403, 404)


def test_passage_marks_only_this_rows_quotation_and_lists_other_findings_separately(tmp_path):
    false_quote = "la preuve est toujours inutile"
    client, legal = _client(tmp_path, [
        f"Article 8.5 du Code civil : « {ARTICLE} ». Article 8.5 du Code civil : « {false_quote} »."])
    assert len(legal) == 2
    first = client.get(f"{BASE}/{legal[0].reference_id}/passage", headers=H).json()
    ex = first["brief_excerpt"]
    a, b = first["quote_span"]
    assert ex[a:b] == legal[0].quote and false_quote not in ex[a:b]
    others = first["other_findings"]
    assert [o["reference_id"] for o in others] == [legal[1].reference_id]
    oa, ob = others[0]["quote_span"]
    assert ex[oa:ob] == false_quote and others[0]["status"] != first["status"]


def test_v2_no_corpus_means_no_pass(tmp_path):
    client, _ = _client(tmp_path, [f"Article 8.5 du Code civil : « {ARTICLE} »."], with_corpus=False)
    # The fake run still carries observations; the contract refuses a PASS without a chosen corpus.
    r = client.get(BASE, headers=H)
    assert r.status_code != 200 or all(x["status"] != "PASS" for x in r.json()["references"])


@pytest.mark.parametrize("status", ["PASS", "FAIL"])
def test_contract_rejects_inconsistent_counts(status):
    from application.litigation.workspace_contract import LegalCoverageView
    with pytest.raises(ValueError):
        LegalCoverageView(detected=2, by_status={"PASS": 1, "FAIL": 0, "UNVERIFIED": 0, "UNDETERMINED": 0},
                          analysed="x", not_analysed=[])
    with pytest.raises(ValueError):
        LegalCoverageView(detected=1, by_status={"PASS": 1, "FAIL": 0, "UNVERIFIED": 0}, analysed=status, not_analysed=[])


def test_review_state_from_the_real_blocker_builder_fits_the_product_contract(tmp_path):
    """The /v2 review state the React screen reads is validated by the same pydantic contract."""
    from application.litigation.review_blockers import review_blockers
    from application.litigation.workspace_contract import ClearbriefReviewReceipt, ClearbriefReviewState
    _, legal = _client(tmp_path, [f"Article 8.5 du Code civil : « {ARTICLE} »."])
    run = SimpleNamespace(snapshot_hash=SNAP, citation_observations=(), factual_observations=(),
                          legal_observations=tuple(legal), suitability_observations=(),
                          event_observations=(), passage_flags=(), incomplete=(), excluded=())
    state = {"schema": "caseproof-clearbrief-review-v1", "case_id": "c", "brief_version_id": "v",
             "snapshot_hash": SNAP, "revision": 0, "decisions": [],
             "blocker_inventory": review_blockers(run, ()), "release_authorized": False}
    ClearbriefReviewState.model_validate(state)
    ClearbriefReviewReceipt.model_validate({"schema": "caseproof-clearbrief-review-receipt-v1",
                                            "snapshot_hash": SNAP, "revision": 1, "replayed": False,
                                            "release_authorized": False})
    with pytest.raises(ValueError):
        ClearbriefReviewState.model_validate({**state, "release_authorized": True})


def test_offline_pack_manifest_matches_download_and_replays(tmp_path, monkeypatch):
    from application.litigation.offline_legal_pack import verify_legal_pack
    from apps.api import litigation_evidence_search as les
    monkeypatch.setattr(les.AuthorizedEvidenceSearch, "_require_evidence", staticmethod(lambda _a: None))
    # Fake ports (labelled): bench with the review state and the current-store check the pack route needs.
    from types import SimpleNamespace as NS
    path = tmp_path / "p2.docx"
    path.write_bytes(docx_without_custom_xml([f"Article 8.5 du Code civil : « {ARTICLE} »."]))
    config = load_corpus_config(corpus(tmp_path))
    text = parse_docx(path.read_bytes())["text"]
    obs = check_legal_references(text, config.records, config.act_aliases,
                                 chosen_versions=config.chosen_versions, strict=True, v3=True)
    run = NS(snapshot_hash=SNAP, representation_sha256=hashlib.sha256(text.encode()).hexdigest(),
             corpus_pack_sha256=config.pack_sha256, legal_observations=tuple(obs), suitability_observations=())
    access = NS(case_id="c")
    wb = NS(checker=NS(check=lambda **_: run, legal_corpus_for=lambda _c: config, _verified=lambda _b: None,
                       _scope=lambda _s, _c: access),
            store=NS(load_bundle=lambda **_: NS(representation=NS(text=text)), still_current=lambda **_: True),
            workspace=NS(state=lambda **_: {"snapshot_hash": SNAP, "decisions": []}))
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    from apps.api.access_control import AccessRejected
    app = FastAPI()

    @app.exception_handler(AccessRejected)
    async def denied(request: Request, exc: AccessRejected) -> JSONResponse:
        return JSONResponse({"error": exc.code.value}, status_code=exc.http_status)

    app.include_router(create_signed_workbench_router(lambda _b: wb))
    c = TestClient(app)
    base = "/v2/matters/c/briefs/v/offline-pack"
    m = c.get(base + "/manifest", headers=H).json()
    r = c.get(base, headers=H)
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/zip")
    assert hashlib.sha256(r.content).hexdigest() == m["sha256"] == r.headers["X-CaseProof-Pack-SHA256"]
    assert len(r.content) == m["byte_length"] == int(r.headers["X-CaseProof-Pack-Size"])
    assert r.headers["X-CaseProof-Snapshot"] == m["snapshot_hash"] == SNAP
    assert verify_legal_pack(r.content, expected_sha256=m["checkpoint_sha256"])["references"]
    assert c.get(base).status_code == 401 and c.get(base + "/manifest").status_code == 401
