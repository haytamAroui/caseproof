"""Lawyer conditions on the signed path. FAKE-backed: auth, storage, Postgres and the conditions store are stand-ins
(an in-memory store that mimics compare-and-swap and hash checks); the route, matching and contract code are real.
The SQL side is a draft checked separately on a local disposable PostgreSQL."""
from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from application.litigation.corpus import CorpusError
from application.litigation.signed_conditions import (
    R_PARTIAL,
    canonical_text,
    load_stored,
    match_conditions,
    normalise_input,
)
from apps.api.access_control import AccessRejected
from apps.api.signed_workbench_routes import ConflictError, create_signed_workbench_router

H = {"Authorization": "Bearer synthetic"}
BRIEF = "Le courrier du 3 mars a été envoyé. La somme de 100 euros est due."
V = "11111111-1111-1111-1111-111111111111"


def preview(source_id: str, text: str, *, status="ready", warnings=(), rep="r1", spans=()):
    row = SimpleNamespace(source_id=source_id, version_id=V, original_sha256="e" * 64, status=status,
                          warnings=tuple(warnings), representation_id=rep)
    return SimpleNamespace(row=row, text=text, spans=tuple(spans))


class FakeStore:
    def __init__(self):
        self.rows = []

    def read(self, bearer, case):
        if not self.rows:
            return None
        text, sha = self.rows[-1]
        return {"revision": len(self.rows), "spec_text": text, "spec_sha256": sha}

    def append(self, bearer, case, expected, text, sha):
        assert hashlib.sha256(text.encode()).hexdigest() == sha
        if expected != len(self.rows):
            raise ConflictError
        self.rows.append((text, sha))
        return len(self.rows)


@pytest.fixture(autouse=True)
def _fake_evidence_auth(monkeypatch):
    from apps.api.litigation_evidence_search import AuthorizedEvidenceSearch
    monkeypatch.setattr(AuthorizedEvidenceSearch, "_require_evidence", staticmethod(lambda _a: None))  # fake auth, labelled


def client(store, previews, labels):
    entries = [SimpleNamespace(confirmed=True, display_label=lab, pages=[SimpleNamespace(source_id=sid)])
               for sid, lab in labels.items()]
    bundle = SimpleNamespace(
        representation=SimpleNamespace(text=BRIEF, brief=SimpleNamespace(case_id="c", version_id="b", references=())),
        register=SimpleNamespace(entries=entries), previews=tuple(previews),
        source_scope=SimpleNamespace(declared_source_versions=tuple((p.row.source_id, V) for p in previews),
                                     excluded_source_versions=()))
    checker = SimpleNamespace(
        _verified=lambda _b: None, _scope=lambda _s, _c: SimpleNamespace(case_id="c"),
        store=SimpleNamespace(load_bundle=lambda **_: bundle, still_current=lambda **_: True))
    wb = SimpleNamespace(checker=checker)
    app = FastAPI()

    @app.exception_handler(AccessRejected)
    async def denied(request: Request, exc: AccessRejected) -> JSONResponse:
        return JSONResponse({"error": exc.code.value}, status_code=exc.http_status)

    app.include_router(create_signed_workbench_router(lambda _b: wb, None, store))
    return TestClient(app)


COND = {"id": "courrier", "label": "Courrier", "question": "Reçu ?", "trigger": ["courrier"],
        "evidence": ["reçu", "ontvangen"], "pieces": []}
BODY = {"expected_revision": 0, "conditions": [COND]}
URL = "/v2/matters/c/conditions"
M = "/v2/matters/c/briefs/b/conditions"


def test_save_read_back_and_compare_and_swap():
    store = FakeStore()
    c = client(store, [], {})
    assert c.get(URL, headers=H).json()["revision"] == 0
    saved = c.post(URL, json=BODY, headers=H).json()
    assert saved["revision"] == 1 and len(saved["spec_sha256"]) == 64
    assert c.get(URL, headers=H).json()["conditions"][0]["trigger"] == ["courrier"]
    assert c.post(URL, json=BODY, headers=H).status_code == 409
    assert c.post(URL, json={**BODY, "expected_revision": 1}, headers=H).json()["revision"] == 2


def test_invalid_input_refused_before_the_store_and_bearer_required():
    store = FakeStore()
    c = client(store, [], {})
    bad = {**BODY, "conditions": [{**COND, "trigger": ["x"]}]}
    assert c.post(URL, json=bad, headers=H).status_code == 422
    assert c.post(URL, json={**BODY, "extra": 1}, headers=H).status_code == 422
    assert store.rows == []
    assert c.post(URL, json=BODY).status_code == 401
    assert c.get(URL).status_code == 401


def test_tampered_stored_spec_fails_closed():
    store = FakeStore()
    c = client(store, [], {})
    c.post(URL, json=BODY, headers=H)
    text, sha = store.rows[-1]
    store.rows[-1] = (text.replace("courrier", "courriel"), sha)
    assert c.get(URL, headers=H).status_code == 503


def test_no_store_wired_fails_closed():
    assert client(None, [], {}).get(URL, headers=H).status_code == 503


def test_matches_found_is_undetermined_with_provenance_and_never_pass():
    store = FakeStore()
    p = preview("s1", "Accusé. Le courrier a bien été reçu par la banque. Fin.",
                spans=[(0, 60, "para", 2)])
    c = client(store, [p], {"s1": "Pièce 1"})
    c.post(URL, json=BODY, headers=H)
    body = c.get(M, headers=H).json()
    a = body["anchors"][0]
    assert (a["status"], a["reason"]) == ("UNDETERMINED", "condition_passages_found_appraisal_required")
    f = a["found"][0]
    assert (f["piece"], f["pdf_page"], f["term"], f["original_sha256"]) == ("Pièce 1", 3, "reçu", "e" * 64)
    assert body["coverage"]["by_status"]["PASS"] == 0


def test_no_passage_is_unverified_only_when_every_targeted_piece_was_read():
    store = FakeStore()
    read = preview("s1", "Rien d'utile ici.")
    bad = preview("s2", "texte", status="partial", warnings=("scan",))
    c = client(store, [read], {"s1": "Pièce 1"})
    c.post(URL, json=BODY, headers=H)
    assert c.get(M, headers=H).json()["anchors"][0]["status"] == "UNVERIFIED"
    c2 = client(store, [read, bad], {"s1": "Pièce 1", "s2": "Pièce 2"})
    a = c2.get(M, headers=H).json()["anchors"][0]
    assert (a["status"], a["reason"]) == ("UNDETERMINED", R_PARTIAL) and a["pieces_not_read"] == ["Pièce 2"]
    c3 = client(store, [], {})
    assert c3.get(M, headers=H).json()["anchors"][0]["status"] == "UNDETERMINED"  # nothing read at all


def test_piece_filter_naming_an_unknown_piece_is_not_a_clean_no_result():
    spec = normalise_input([{**COND, "pieces": ["Pièce 9"]}])
    out = match_conditions(BRIEF, spec, [preview("s1", "Rien.")], {"s1": "Pièce 1"})
    a = out["anchors"][0]
    assert a["status"] == "UNDETERMINED" and a["pieces_not_read"] == ["pièce 9"]


def test_canonical_text_roundtrip_and_hash():
    spec = normalise_input([COND])
    text, digest = canonical_text(spec)
    assert hashlib.sha256(text.encode()).hexdigest() == digest == spec["spec_sha256"]
    assert load_stored(text, digest)["conditions"][0]["id"] == "courrier"
    with pytest.raises(CorpusError):
        load_stored(text + " ", digest)


def test_denied_caller_gets_404_never_an_empty_list():
    from apps.api.signed_supabase_originals import PrivateStorageDenied

    class Denied:
        def read(self, b, c): raise PrivateStorageDenied("no")
        def append(self, *a): raise PrivateStorageDenied("no")
    c = client(Denied(), [], {})
    assert c.get(URL, headers=H).status_code == 404
    assert c.post(URL, json=BODY, headers=H).status_code == 404
    assert c.get(M, headers=H).status_code == 404


def test_lawyer_can_clear_conditions_last_one_included():
    store = FakeStore()
    c = client(store, [], {})
    assert c.post(URL, json=BODY, headers=H).json()["revision"] == 1
    cleared = c.post(URL, json={"expected_revision": 1, "conditions": []}, headers=H)
    assert cleared.status_code == 200, cleared.text
    state = cleared.json()
    assert state["revision"] == 2 and state["conditions"] == []
    assert c.get(URL, headers=H).json()["conditions"] == []
    m = c.get(M, headers=H).json()
    assert m["anchors"] == [] and m["coverage"]["conditions"] == 0
    text, sha = store.rows[-1]
    assert load_stored(text, sha)["conditions"] == [] and canonical_text(normalise_input([])) == (text, sha)
    with pytest.raises(CorpusError):
        load_stored(text.replace("[]", "[ ]"), hashlib.sha256(text.replace("[]", "[ ]").encode()).hexdigest())
