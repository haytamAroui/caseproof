"""Interactive demo app: real engine over the loopback API, fail-closed edges.

Synthetic in-test fixture only: no real sources, no lawyer content, no network.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from docx import Document
from fastapi.testclient import TestClient
from httpx import Response as TestResponse

from application.litigation.corpus import CORPUS_FORMAT_VERSION
from apps.api.demo_journey_app import create_demo_app
from tests.test_demo_belgian_dossier import BRIEF_TEXT, QUOTE_BAD, QUOTE_OK, RULE, SOURCE_TEXT, _corpus_entry


def _dossier(tmp_path: Path) -> Path:
    dossier = tmp_path / "dossier"
    (dossier / "corpus").mkdir(parents=True)
    (dossier / "rules").mkdir()
    (dossier / "corpus" / "corpus-manifest.toml").write_text(
        f'format = "{CORPUS_FORMAT_VERSION}"\n' + _corpus_entry(), encoding="utf-8"
    )
    (dossier / "corpus" / "synthetic-original.html").write_bytes(b"<html>synthetic</html>")
    (dossier / "corpus" / "synthetic-derived.txt").write_text(SOURCE_TEXT, encoding="utf-8")
    (dossier / "rules" / "regle.toml").write_text(RULE, encoding="utf-8")
    (dossier / "facts.json").write_text(
        json.dumps({"facts": [{"name": "fait_confirme", "value": True, "confirmed": True}]}), encoding="utf-8"
    )
    (dossier / "decisions.json").write_text(
        json.dumps({"decided_at": "2026-11-22T21:00:00+01:00", "decisions": []}), encoding="utf-8"
    )
    doc = Document()
    doc.add_paragraph(BRIEF_TEXT)
    doc.save(str(dossier / "brief.docx"))
    (dossier / "meta.json").write_text(
        json.dumps({"title": "fixture", "brief": "brief.docx"}), encoding="utf-8"
    )
    (dossier / "m2.json").write_text(
        json.dumps(
            {
                "case_id": "fixture-1",
                "brief_version_id": "brief-v1",
                "brief_text": BRIEF_TEXT,
                "references": [
                    {
                        "reference_id": "ref-ok",
                        "exhibit_label": "Pièce 1",
                        "exact_quote": QUOTE_OK,
                        "pdf_page": 1,
                    },
                    {
                        "reference_id": "ref-bad",
                        "exhibit_label": "Pièce 1",
                        "exact_quote": QUOTE_BAD,
                        "pdf_page": 1,
                    },
                ],
                "claims": [],
                "passages": [
                    {"passage_id": "p-bad", "observation_id": "citation:ref-bad", "text": QUOTE_BAD}
                ],
                "correction": {"passage_id": "p-bad", "after": QUOTE_OK, "rationale": "alignée"},
                "register_revision": 1,
                "exhibits": [
                    {
                        "exhibit_id": "ex-1",
                        "display_label": "Pièce 1",
                        "aliases": [],
                        "confirmed": True,
                        "pages": [{"source_id": "src-1", "version_id": "v1", "pdf_page": 1}],
                    }
                ],
                "sources": [
                    {
                        "source_id": "src-1",
                        "document_id": "doc-1",
                        "version_id": "v1",
                        "label": "pièce synthétique",
                        "synthetic": True,
                        "text": SOURCE_TEXT,
                    }
                ],
                "review": {"decisions": []},
            }
        ),
        encoding="utf-8",
    )
    return dossier


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_demo_app(_dossier(tmp_path)))


def _session(client: TestClient) -> str:
    session: str = client.get("/demo/api/state").json()["session"]
    return session


def _post(
    client: TestClient,
    path: str,
    payload: dict[str, Any] | bytes,
    session: str,
    content_type: str = "application/json",
) -> TestResponse:
    response: TestResponse = client.post(
        path,
        json=payload if content_type == "application/json" else None,
        content=payload if content_type != "application/json" else None,
        headers={
            "x-demo-session": session,
            "origin": "http://testserver",
            "content-type": content_type,
        },
    )
    return response


def test_index_and_assets_served(client: TestClient) -> None:
    assert client.get("/demo").status_code == 200
    assert client.get("/demo/assets/demo.js").status_code == 200
    assert client.get("/demo/assets/nope.js").status_code == 404


def test_guard_requires_session(client: TestClient) -> None:
    response = client.post("/demo/api/run", json={}, headers={"origin": "http://testserver"})
    assert response.status_code == 403
    assert response.json()["error"] == "session_rejected"


def test_full_journey(client: TestClient) -> None:
    session = _session(client)
    state = client.get("/demo/api/state").json()
    assert state["document"]["body_read"] is True
    assert state["document"]["extraction_validated_against_read_text"] is True

    run = _post(client, "/demo/api/run", {}, session)
    assert run.status_code == 200
    data = run.json()
    citations = {c["reference_id"]: c["state"] for c in data["findings"]["citations"]}
    assert citations == {"ref-ok": "exact_match", "ref-bad": "quote_not_found"}
    assert data["rule_results"][0]["status"] == "PASS"

    review = _post(
        client,
        "/demo/api/review",
        {
            "observation_id": "citation:ref-bad",
            "disposition": "confirmed_candidate",
            "rationale": "écart confirmé",
        },
        session,
    )
    assert review.status_code == 200
    assert review.json()["release_ready"] is False

    correction = _post(
        client,
        "/demo/api/correction",
        {
            "passage_id": "p-bad",
            "after": "six mois",
            "rationale": "citation alignée",
        },
        session,
    )
    assert correction.status_code == 200
    result = correction.json()
    assert result["flips"] == {"ref-bad": {"before": "quote_not_found", "after": "exact_match"}}
    assert result["snapshot"] != data["snapshot"]

    export = client.get("/demo/api/export.json", headers={"x-demo-session": session})
    assert export.status_code == 200
    payload = export.json()
    assert payload["demonstration"] is True and payload["not_legal_validation"] is True
    assert payload["release_ready"] is False
    assert payload["versions"][0]["after"] == "six mois"

    export_html = client.get("/demo/api/export.html", headers={"x-demo-session": session})
    assert export_html.status_code == 200
    assert "pas une validation juridique" in export_html.text


def test_review_before_run_rejected(client: TestClient) -> None:
    session = _session(client)
    response = _post(
        client,
        "/demo/api/review",
        {
            "observation_id": "citation:ref-bad",
            "disposition": "dismissed",
            "rationale": "x",
        },
        session,
    )
    assert response.status_code == 409
    assert response.json()["error"] == "run_first"


def test_export_before_run_rejected(client: TestClient) -> None:
    session = _session(client)
    response = client.get("/demo/api/export.json", headers={"x-demo-session": session})
    assert response.status_code == 409


def test_unknown_observation_rejected(client: TestClient) -> None:
    session = _session(client)
    assert _post(client, "/demo/api/run", {}, session).status_code == 200
    response = _post(
        client,
        "/demo/api/review",
        {
            "observation_id": "citation:inconnu",
            "disposition": "dismissed",
            "rationale": "x",
        },
        session,
    )
    assert response.status_code == 409


def test_waiver_on_pass_rule_rejected(client: TestClient) -> None:
    session = _session(client)
    assert _post(client, "/demo/api/run", {}, session).status_code == 200
    response = _post(
        client,
        "/demo/api/rule-decision",
        {
            "rule_id": "demo.test.regle",
            "disposition": "waived",
            "rationale": "x",
            "scope": "x",
        },
        session,
    )
    assert response.status_code == 422
    assert response.json()["error"] == "decision_rejected"


def test_upload_non_docx_rejected(client: TestClient) -> None:
    session = _session(client)
    response = _post(
        client, "/demo/api/document", b"not a word file", session, content_type="application/octet-stream"
    )
    assert response.status_code == 422
    assert response.json()["error"] == "not_a_docx"


def test_upload_clean_docx_is_actually_read(client: TestClient) -> None:
    session = _session(client)
    import io

    doc = Document()
    doc.add_paragraph(BRIEF_TEXT)
    buffer = io.BytesIO()
    doc.save(buffer)
    response = _post(
        client, "/demo/api/document", buffer.getvalue(), session, content_type="application/octet-stream"
    )
    assert response.status_code == 200
    assert response.json()["body_read"] is True
    assert response.json()["extraction_missing"] == []
    run = _post(client, "/demo/api/run", {}, session)
    assert run.status_code == 200


def _docx_bytes(text: str) -> bytes:
    import io

    doc = Document()
    doc.add_paragraph(text)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def test_uploaded_corrected_version_drives_findings(client: TestClient) -> None:
    """Picker upload of the clean corrected DOCX: the measured finding flips
    because the uploaded content matches the declared corrected version."""
    session = _session(client)
    corrected = _docx_bytes(BRIEF_TEXT.replace(QUOTE_BAD, QUOTE_OK))
    response = _post(
        client, "/demo/api/document", corrected, session, content_type="application/octet-stream"
    )
    assert response.status_code == 200
    assert response.json()["extraction_missing"] == []
    assert response.json()["active_version"].endswith("-corrige-1")
    run = _post(client, "/demo/api/run", {}, session)
    assert run.status_code == 200
    citations = {c["reference_id"]: c["state"] for c in run.json()["findings"]["citations"]}
    assert citations["ref-bad"] == "exact_match"
    assert run.json()["brief_version"].endswith("-corrige-1")


def test_uploaded_unrelated_clean_docx_blocks_run(client: TestClient) -> None:
    """A clean DOCX whose content matches neither the declared brief nor the
    declared corrected version cannot be verified: fail-closed, no guessing."""
    session = _session(client)
    response = _post(
        client,
        "/demo/api/document",
        _docx_bytes("Un texte sans aucun rapport."),
        session,
        content_type="application/octet-stream",
    )
    assert response.status_code == 200
    assert response.json()["extraction_missing"]
    run = _post(client, "/demo/api/run", {}, session)
    assert run.status_code == 422
    assert run.json()["error"] == "extraction_mismatch"


def test_no_stale_success_after_document_change(client: TestClient) -> None:
    """A verified/corrected result never survives a document change: exports
    and decisions are blocked until the new document is actually verified."""
    session = _session(client)
    assert _post(client, "/demo/api/run", {}, session).status_code == 200
    assert (
        _post(
            client,
            "/demo/api/correction",
            {"passage_id": "p-bad", "after": QUOTE_OK, "rationale": "alignée"},
            session,
        ).status_code
        == 200
    )
    headers = {"x-demo-session": session}
    assert client.get("/demo/api/export.json", headers=headers).status_code == 200
    corrected = _docx_bytes(BRIEF_TEXT.replace(QUOTE_BAD, QUOTE_OK))
    assert (
        _post(
            client, "/demo/api/document", corrected, session, content_type="application/octet-stream"
        ).status_code
        == 200
    )
    # Le succès précédent est caduc : export et relecture bloqués.
    assert client.get("/demo/api/export.json", headers=headers).status_code == 409
    assert client.get("/demo/api/export.html", headers=headers).status_code == 409
    assert (
        _post(
            client,
            "/demo/api/review",
            {"observation_id": "citation:ref-bad", "disposition": "dismissed", "rationale": "x"},
            session,
        ).status_code
        == 409
    )
    # Nouvelle exécution réelle sur le document courant : export à nouveau possible.
    assert _post(client, "/demo/api/run", {}, session).status_code == 200
    assert client.get("/demo/api/export.json", headers=headers).status_code == 200


def test_fact_confirmation_reevaluates_rules(client: TestClient) -> None:
    """Simulated reviewer fact confirmation: deterministic rules re-evaluate
    live on the updated facts — a PASS rule degrades when its fact is
    unconfirmed, and recovers when confirmed again."""
    session = _session(client)
    assert _post(client, "/demo/api/run", {}, session).status_code == 200

    response = _post(client, "/demo/api/facts", {"name": "inconnu", "confirmed": True}, session)
    assert response.status_code == 422

    response = _post(client, "/demo/api/facts", {"name": "fait_confirme", "confirmed": False}, session)
    assert response.status_code == 200
    data = response.json()
    assert data["facts"][0]["confirmed"] is False
    assert data["rule_results"][0]["status"] == "UNDETERMINED"

    response = _post(client, "/demo/api/facts", {"name": "fait_confirme", "confirmed": True}, session)
    assert response.status_code == 200
    assert response.json()["rule_results"][0]["status"] == "PASS"
