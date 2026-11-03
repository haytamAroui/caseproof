"""F6 offline route acceptance: immutable output, authorization and actual bytes."""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
from uuid import uuid4

from docx import Document
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.dossier_export_release import _checked_artifacts, release_manifest
from apps.api.dossier_journey import canonical, create_dossier_router


SNAPSHOT = "a" * 64
CASE, BRIEF = str(uuid4()), str(uuid4())


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class SignedReleaseStore:
    def __init__(self):
        document = Document()
        document.add_paragraph("Pièce 1. Artificial case facts are not certified.")
        out = io.BytesIO()
        document.save(out)
        self.original = out.getvalue()
        self.report = {
            "schema": "caseproof-dossier-v1",
            "case_id": CASE,
            "brief_id": BRIEF,
            "snapshot_hash": SNAPSHOT,
            "bundle_signature": "b" * 64,
            "confirmation_id": str(uuid4()),
            "sources": [
                {"role": "draft", "version_id": BRIEF, "sha256": sha(self.original)}
            ],
            "coverage": {"checked": 0, "unresolved": 1,
                         "text_coverage_complete": False, "reference_recall_measured": False},
            "findings": [],
        }
        self.decisions = [{
            "reference_id": "ref-1", "decision": "CONFIRMED_QUALIFIED",
            "rationale": "Synthetic human reviewer", "reviewer_id": str(uuid4()),
            "request_id": str(uuid4()), "timestamp": "2026-11-03T07:00:00+00:00",
        }]
        self.active = BRIEF
        self.permitted = True
        self.saved = {}

    def current_draft_version(self, bearer, case):
        assert bearer == "signed" and case == CASE
        return self.active

    def reopen(self, bearer, case, brief, snapshot):
        assert bearer == "signed" and case == CASE and brief == BRIEF
        if snapshot != SNAPSHOT:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        return self.report, self.original

    def rpc(self, bearer, case, action, data=None):
        assert bearer == "signed" and case == CASE and action == "decisions"
        return {"decisions": self.decisions}

    def receipt(self, manifest):
        return hmac.new(b"synthetic-release-test-key", canonical(manifest).encode(), "sha256").hexdigest()

    def export_rpc(self, bearer, case, action, release_id, data):
        assert bearer == "signed" and case == CASE
        if not self.permitted:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        if action == "authorize":
            return {"authorized": True}
        if action == "status":
            existing = self.saved.get(release_id)
            return {"state": "absent"} if existing is None else dict(existing["status"])
        if action == "release":
            if data["human_decisions"] != self.decisions:
                raise AccessRejected(AccessFailure.RESOURCE_MASKED)
            manifest = data["manifest"]
            assert manifest["server_receipt"] == self.receipt(
                {k: v for k, v in manifest.items() if k != "server_receipt"}
            )
            for kind in ("json", "markdown", "docx"):
                raw = base64.b64decode(data["contents"][kind], validate=True)
                assert sha(raw) == manifest["artifacts"][kind]["sha256"]
            status = {
                "state": "released", "release_id": release_id,
                "brief_id": BRIEF, "snapshot_hash": SNAPSHOT,
                "manifest": manifest,
            }
            self.saved[release_id] = {"status": status, "contents": data["contents"]}
            return status
        if action == "list":
            return {"releases": [entry["status"] for entry in self.saved.values()]}
        if action == "artifact":
            saved = self.saved[release_id]
            return {"manifest": saved["status"]["manifest"],
                    "content_base64": saved["contents"][data["format"]]}
        raise AssertionError(action)


def client():
    store = SignedReleaseStore()
    app = FastAPI()
    app.include_router(create_dossier_router(store))

    @app.exception_handler(AccessRejected)
    def denied(request, error):
        return JSONResponse({"error": error.code.value}, status_code=error.http_status)

    return TestClient(app), store


def base():
    return f"/v2/matters/{CASE}/briefs/{BRIEF}/dossier/releases"


def header():
    return {"Authorization": "Bearer signed"}


def test_f6_preview_release_download_reopen_restart_and_historical():
    api, store = client()
    preview = api.get(base() + "/preview?snapshot_hash=" + SNAPSHOT, headers=header())
    assert preview.status_code == 200
    assert preview.json()["review_count"] == 1
    assert preview.json()["release_ready"] is True
    operation = str(uuid4())
    request = {"release_id": operation, "snapshot_hash": SNAPSHOT}
    released = api.post(base(), json=request, headers=header())
    assert released.status_code == 200
    receipt = released.json()
    assert receipt["state"] == "released"
    assert receipt["manifest"]["review_count"] == 1
    assert sha(store.original) == store.report["sources"][0]["sha256"]
    assert api.post(base(), json=request, headers=header()).json() == receipt
    assert api.get(base() + "/" + operation, headers=header()).status_code == 200
    assert len(api.get(base(), headers=header()).json()["releases"]) == 1
    for kind in ("json", "markdown", "docx"):
        response = api.get(base() + f"/{operation}/artifacts/{kind}", headers=header())
        assert response.status_code == 200
        assert sha(response.content) == receipt["manifest"]["artifacts"][kind]["sha256"]
        assert response.headers["X-CaseProof-Export-Size"] == str(len(response.content))
        if kind == "docx":
            reopened = Document(io.BytesIO(response.content))
            assert any("scoped review annotations" in p.text for p in reopened.paragraphs)
    # The original release remains immutable and authorized historical output
    # even if later corrections activate another draft.
    store.active = str(uuid4())
    assert api.get(base() + "/preview?snapshot_hash=" + SNAPSHOT,
                   headers=header()).status_code == 409
    assert api.get(base() + f"/{operation}/artifacts/docx", headers=header()).status_code == 200
    assert api.post(base(), json={"release_id": str(uuid4()),
                                 "snapshot_hash": SNAPSHOT}, headers=header()).status_code == 409
    # Reconstruct API router from same durable stand-in (simulates app restart).
    new_app = FastAPI()
    new_app.include_router(create_dossier_router(store))
    assert TestClient(new_app).get(
        base() + f"/{operation}/artifacts/docx", headers=header()
    ).content == api.get(base() + f"/{operation}/artifacts/docx", headers=header()).content


def test_f6_review_grants_and_absent_receipt_fail_closed():
    api, store = client()
    store.decisions = []
    assert api.get(base() + "/preview?snapshot_hash=" + SNAPSHOT,
                   headers=header()).json()["release_ready"] is False
    assert api.post(base(), json={"release_id": str(uuid4()),
                                 "snapshot_hash": SNAPSHOT}, headers=header()).status_code == 409
    store.permitted = False
    assert api.get(base() + "/preview?snapshot_hash=" + SNAPSHOT,
                   headers=header()).status_code in (403, 404)
    assert api.get(base(), headers=header()).status_code in (403, 404)


def test_f6_rejects_tampered_artifact_and_manifest_and_wrong_identity():
    api, store = client()
    operation = str(uuid4())
    result = api.post(base(), headers=header(),
                      json={"release_id": operation, "snapshot_hash": SNAPSHOT})
    assert result.status_code == 200
    saved = store.saved[operation]
    original = saved["contents"]["json"]
    saved["contents"]["json"] = base64.b64encode(b"changed bytes").decode()
    response = api.get(base() + f"/{operation}/artifacts/json", headers=header())
    assert response.status_code in (403, 404, 503)
    saved["contents"]["json"] = original
    saved["status"]["manifest"]["review_count"] = 999
    assert api.get(base() + f"/{operation}", headers=header()).status_code in (403, 404, 503)
    assert api.post(base(), headers=header(), json={
        "release_id": operation, "snapshot_hash": "f" * 64,
    }).status_code == 409


def test_f6_bounded_format_refuses_oversized_artifact(monkeypatch):
    api, store = client()
    import apps.api.dossier_export_release as service

    monkeypatch.setattr(service, "_checked_artifacts", lambda report, raw: (_ for _ in ()).throw(
        __import__("fastapi").HTTPException(422, "export exceeds supported size")))
    result = api.post(base(), headers=header(),
                      json={"release_id": str(uuid4()), "snapshot_hash": SNAPSHOT})
    assert result.status_code == 422
    assert not store.saved


def test_f6_release_manifest_is_explicitly_not_a_certificate():
    _, store = client()
    report = {**store.report, "human_decisions": store.decisions}
    artifacts = _checked_artifacts(report, store.original)
    m = release_manifest(report, artifacts)
    assert m["snapshot_hash"] == SNAPSHOT
    assert m["review_count"] == 1
    assert m["artifacts"]["docx"]["byte_length"] > 100
    assert any("not" in text.lower() for text in m["limitations"])
