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
from apps.api.release_completeness import release_policy

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
            "findings": [{"reference_id": "ref-1", "literal": "Pièce 1"}],
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


def test_f6_replay_and_history_verify_receipt_not_just_new_writes():
    api, store = client()
    operation = str(uuid4())
    request = {"release_id": operation, "snapshot_hash": SNAPSHOT}
    assert api.post(base(), headers=header(), json=request).status_code == 200
    assert api.get(base(), headers=header()).status_code == 200
    manifest = store.saved[operation]["status"]["manifest"]
    manifest["review_count"] = 900
    # An untrusted direct RPC caller can write a forged manifest to a private
    # table in a broken installation. No API path may present it as released.
    for method, path in (
        ("POST", base()),
        ("GET", base()),
        ("GET", base() + "/" + operation),
        ("GET", base() + "/" + operation + "/artifacts/json"),
    ):
        response = (
            api.post(path, headers=header(), json=request)
            if method == "POST" else api.get(path, headers=header())
        )
        assert response.status_code in (403, 404, 503), (method, path, response.text)


def test_f6_manifest_digest_is_independently_verified_on_read():
    api, store = client()
    operation = str(uuid4())
    request = {"release_id": operation, "snapshot_hash": SNAPSHOT}
    assert api.post(base(), headers=header(), json=request).status_code == 200
    manifest = store.saved[operation]["status"]["manifest"]
    manifest["finding_count"] = 700
    # Even a receipt recalculated over mutated values cannot make the original
    # frozen content hash agree with the changed manifest.
    unsigned = {k: v for k, v in manifest.items() if k != "server_receipt"}
    manifest["server_receipt"] = store.receipt(unsigned)
    response = api.get(base() + "/" + operation, headers=header())
    assert response.status_code in (403, 404, 503)


def test_f6_release_manifest_links_exact_preserved_pdf_and_physical_page():
    _, store = client()
    exhibit = str(uuid4())
    source_hash = "d" * 64
    report = {**store.report, "human_decisions": store.decisions}
    report["sources"] = [
        *store.report["sources"],
        {"role": "exhibit", "version_id": exhibit, "sha256": source_hash},
    ]
    report["findings"] = [{
        "reference_id": "ref-0001", "version_id": exhibit,
        "page_mapping": "mapped", "pdf_page": 6,
    }, {
        "reference_id": "ref-0002", "version_id": exhibit,
        "page_mapping": "unmapped", "pdf_page": None,
    }]
    # Derivative generation uses the complete canonical findings contract;
    # link projection is separately tested with minimalist synthetic locators.
    artifacts = _checked_artifacts(
        {**store.report, "human_decisions": store.decisions}, store.original
    )
    report["human_decisions"] = [{**store.decisions[0], "reference_id": "ref-0001"}]
    manifest = release_manifest(report, artifacts)
    links = manifest["reference_links"]
    assert len(links) == 2
    assert links[0]["reference_id"] == "ref-0001"
    assert links[0]["source_version_id"] == exhibit
    assert links[0]["original_sha256"] == source_hash
    assert links[0]["pdf_page"] == 6
    assert links[0]["page_space"] == "physical_pdf_page"
    assert links[0]["viewer_path"] == f"/matters/{CASE}/briefs/{BRIEF}?snapshot={SNAPSHOT}&finding=ref-0001"
    assert links[1]["pdf_page"] is None
    assert links[1]["page_space"] == "unmapped"
    source_links = manifest["source_links"]
    assert source_links[1]["original_path"] == (
        f"/v2/matters/{CASE}/briefs/{BRIEF}/dossier/history/{SNAPSHOT}"
        f"/sources/{exhibit}/original"
    )
    # No URL supplied by a finding was trusted as a release destination.
    assert all(x["viewer_path"].startswith("/matters/") for x in links)


def test_release_manifest_rejects_malformed_frozen_report_fields():
    import pytest

    _, store = client()
    valid = {**store.report, "human_decisions": store.decisions}
    malformed = [
        {**valid, "case_id": None},
        {**valid, "coverage": []},
        {**valid, "findings": [None]},
        {**valid, "findings": [{}]},
        {**valid, "findings": [{"reference_id": "r", "visual_assessment": None}]},
        {**valid, "findings": [{"reference_id": "r", "visual_assessment": {"regions": [None]}}]},
        {**valid, "sources": [{"role": "draft", "version_id": [], "sha256": "a"}]},
        {**valid, "sources": [{"role": "draft", "version_id": "x"}]},
        {**valid, "sources": [{"role": "draft", "version_id": "x", "sha256": "invalid"}]},
        {**valid, "sources": valid["sources"] * 2},
        {**valid, "findings": [{"reference_id": "r", "version_id": []}]},
    ]
    for report in malformed:
        with pytest.raises(AccessRejected):
            release_manifest(report, {})


def test_release_preview_and_commit_fail_closed_for_malformed_frozen_report():
    api, store = client()
    store.report["coverage"] = []
    preview = api.get(base() + "/preview", headers=header(), params={"snapshot_hash": SNAPSHOT})
    assert preview.status_code == 503
    release = api.post(base(), headers=header(), json={
        "release_id": str(uuid4()), "snapshot_hash": SNAPSHOT,
    })
    assert release.status_code == 503
    assert not store.saved


def test_t30_t34_policy_counts_unique_findings_not_duplicate_review_rows():
    _, store = client()
    report = {**store.report, "human_decisions": [store.decisions[0], dict(store.decisions[0])]}
    report["findings"] = [
        {"reference_id": "ref-1"}, {"reference_id": "ref-2"}, {"reference_id": "ref-3"}
    ]
    policy = release_policy(report)
    assert policy["scope"] == "partial"
    assert (policy["total_findings"], policy["required_findings"],
            policy["reviewed_findings"], policy["unreviewed_findings"]) == (3, 3, 1, 2)
    assert policy["unreviewed_reference_ids"] == ["ref-2", "ref-3"]
    assert policy["reason_codes"] == ["UNREVIEWED_FINDINGS"]
    assert not policy["review_complete"]


def test_t30_no_findings_or_orphan_reviews_never_look_complete():
    import pytest

    _, store = client()
    empty = {**store.report, "findings": [], "human_decisions": []}
    assert release_policy(empty)["reason_codes"] == ["NO_FINDINGS"]
    assert not release_policy(empty)["can_release"]
    with pytest.raises(AccessRejected):
        release_policy({**empty, "human_decisions": store.decisions})
    with pytest.raises(AccessRejected):
        release_policy({**store.report, "human_decisions": [
            store.decisions[0], {**store.decisions[0], "reference_id": "ref-2"}
        ]})


def test_t31_partial_preview_requires_acknowledged_commit_and_rechecks():
    api, store = client()
    store.report["findings"].append({"reference_id": "ref-2", "literal": "Pièce 2"})
    p = api.get(base() + "/preview", headers=header(), params={"snapshot_hash": SNAPSHOT})
    assert p.status_code == 200
    assert p.json()["release_policy"]["scope"] == "partial"
    assert p.json()["release_policy"]["unreviewed_findings"] == 1
    assert p.json()["can_release"] is True
    command = {"release_id": str(uuid4()), "snapshot_hash": SNAPSHOT}
    assert api.post(base(), headers=header(), json=command).status_code == 409
    assert not store.saved
    command["acknowledge_partial"] = True
    result = api.post(base(), headers=header(), json=command)
    assert result.status_code == 200
    assert result.json()["manifest"]["release_policy"]["scope"] == "partial"
    docx_response = api.get(
        base() + "/" + command["release_id"] + "/artifacts/docx", headers=header()
    )
    assert docx_response.status_code == 200
    doc = Document(io.BytesIO(docx_response.content))
    text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
    assert "PARTIAL RELEASE WARNING" in text
    assert "Unreviewed detected findings: 1" in text
    json_response = api.get(
        base() + "/" + command["release_id"] + "/artifacts/json", headers=header()
    )
    assert json_response.json()["release_policy"]["scope"] == "partial"
    md_response = api.get(
        base() + "/" + command["release_id"] + "/artifacts/markdown", headers=header()
    )
    assert b'Human finding-review completeness' in md_response.content
    assert api.get(base() + "/" + command["release_id"], headers=header()).status_code == 200


def test_t31_preview_is_not_a_commit_authorization_after_ledger_changes():
    api, store = client()
    p = api.get(base() + "/preview", headers=header(), params={"snapshot_hash": SNAPSHOT})
    assert p.json()["release_policy"]["scope"] == "complete"
    store.decisions = []
    command = {"release_id": str(uuid4()), "snapshot_hash": SNAPSHOT}
    assert api.post(base(), headers=header(), json=command).status_code == 409
    assert not store.saved
    store.decisions = [{**store.report.get("human_decisions", [{}])[0],
                        "reference_id": "ref-1"}] if store.report.get("human_decisions") else []
    store.permitted = False
    assert api.post(base(), headers=header(), json=command).status_code in (403, 404)
    assert not store.saved


def test_t32_legacy_manifest_without_policy_keeps_exact_historical_bytes():
    api, store = client()
    operation = str(uuid4())
    assert api.post(base(), headers=header(), json={
        "release_id": operation, "snapshot_hash": SNAPSHOT,
    }).status_code == 200
    saved = store.saved[operation]
    original_bytes = saved["contents"]["docx"]
    # A legacy frozen receipt can legitimately lack new additive fields.
    old = saved["status"]["manifest"]
    old.pop("release_policy")
    old["limitations"] = old["limitations"][:-1] if old["limitations"][-1].startswith(
        "Review completeness counts") else old["limitations"]
    old["manifest_sha256"] = sha(canonical({
        k: v for k, v in old.items() if k not in ("manifest_sha256", "server_receipt")
    }).encode())
    old["server_receipt"] = store.receipt({
        k: v for k, v in old.items() if k != "server_receipt"
    })
    assert api.get(base() + "/" + operation, headers=header()).status_code == 200
    response = api.get(base() + "/" + operation + "/artifacts/docx", headers=header())
    assert response.status_code == 200
    assert base64.b64encode(response.content).decode() == original_bytes
