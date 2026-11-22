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
from apps.api.demo_journey_app import _resolve_exhibit_label, create_demo_app
from domains.disputes.exhibits import ExhibitEntry, ExhibitPage, ExhibitRegister
from tests.test_demo_belgian_dossier import QUOTE_BAD, QUOTE_OK, RULE, SOURCE_TEXT, _corpus_entry

# Brief de la fixture applicative : deux citations balisées (une exacte, une
# erronée) et une mention de loi autonome hors registre. L'extraction réelle
# doit retrouver ces trois références depuis le texte lu, sans déclaration.
APP_BRIEF = (
    f"Le preneur répond des dégradations : « {QUOTE_OK} » (Code civil, art. 1732). "
    f"Par ailleurs, le préavis serait de « {QUOTE_BAD} » (Code civil, art. 1732) selon le brief. "
    "Conformément à l'article 15 de la loi du 20 février 1991, le preneur conserve ses droits."
)


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
    doc.add_paragraph(APP_BRIEF)
    doc.save(str(dossier / "brief.docx"))
    (dossier / "meta.json").write_text(
        json.dumps({"title": "fixture", "brief": "brief.docx"}), encoding="utf-8"
    )
    (dossier / "m2.json").write_text(
        json.dumps(
            {
                "case_id": "fixture-1",
                "brief_version_id": "brief-v1",
                "brief_text": APP_BRIEF,
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
                        "aliases": ["Code civil"],
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


def test_hierarchical_citation_resolves_to_most_specific_exhibit() -> None:
    """A 'Code civil, ..., Section 2, art. 3' citation resolves to the Section 2
    exhibit (rightmost = most specific locator), not the general Code civil one;
    an unknown target stays unresolved, never guessed."""
    register = ExhibitRegister(
        1,
        (
            ExhibitEntry(
                "ex-section2",
                "Section 2 du Code civil (WALLEX)",
                (ExhibitPage("src-2", "v1", 1),),
                ("Section 2",),
                True,
            ),
            ExhibitEntry(
                "ex-code-civil",
                "Code civil, art. 1708 à 1762bis (WALLEX)",
                (ExhibitPage("src-1", "v1", 1),),
                ("Code civil",),
                True,
            ),
        ),
    )
    assert (
        _resolve_exhibit_label(register, "Code civil, Livre III, Titre VIII, Ch. II, Section 2, art. 3, §1er")
        == "Section 2"
    )
    assert _resolve_exhibit_label(register, "Code civil, art. 1732") == "Code civil"
    assert _resolve_exhibit_label(register, "Section 2, art. 10, §1er") == "Section 2"
    unknown = "article 15 de la loi du 20 février 1991"
    assert _resolve_exhibit_label(register, unknown) == unknown


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
    extraction = state["document"]["extraction"]
    assert extraction["mode"] == "deterministic_from_read_text"
    assert extraction["simulated"] is False
    assert [c["marker_id"] for c in extraction["citations"]] == ["cit-01", "cit-02", "cit-03"]

    run = _post(client, "/demo/api/run", {}, session)
    assert run.status_code == 200
    data = run.json()
    citations = {c["reference_id"]: c["state"] for c in data["findings"]["citations"]}
    assert citations == {
        "cit-01": "exact_match",
        "cit-02": "quote_not_found",
        "cit-03": "reference_unresolved",
    }
    assert data["rule_results"][0]["status"] == "PASS"

    review = _post(
        client,
        "/demo/api/review",
        {
            "observation_id": "citation:cit-02",
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
            "passage_id": "passage:cit-02",
            "after": "six mois",
            "rationale": "citation alignée",
        },
        session,
    )
    assert correction.status_code == 200
    result = correction.json()
    assert result["flips"] == {"cit-02": {"before": "quote_not_found", "after": "exact_match"}}
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
            "observation_id": "citation:cit-02",
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
    doc.add_paragraph(APP_BRIEF)
    buffer = io.BytesIO()
    doc.save(buffer)
    response = _post(
        client, "/demo/api/document", buffer.getvalue(), session, content_type="application/octet-stream"
    )
    assert response.status_code == 200
    assert response.json()["body_read"] is True
    assert len(response.json()["extraction"]["citations"]) == 3
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
    corrected = _docx_bytes(APP_BRIEF.replace(QUOTE_BAD, QUOTE_OK))
    response = _post(
        client, "/demo/api/document", corrected, session, content_type="application/octet-stream"
    )
    assert response.status_code == 200
    assert response.json()["active_version"].endswith("-corrige-1")
    run = _post(client, "/demo/api/run", {}, session)
    assert run.status_code == 200
    citations = {c["reference_id"]: c["state"] for c in run.json()["findings"]["citations"]}
    assert citations["cit-02"] == "exact_match"
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
    assert response.json()["extraction"]["citations"] == []
    run = _post(client, "/demo/api/run", {}, session)
    assert run.status_code == 422
    assert run.json()["error"] == "no_citations_detected"


def test_no_stale_success_after_document_change(client: TestClient) -> None:
    """A verified/corrected result never survives a document change: exports
    and decisions are blocked until the new document is actually verified."""
    session = _session(client)
    assert _post(client, "/demo/api/run", {}, session).status_code == 200
    assert (
        _post(
            client,
            "/demo/api/correction",
            {"passage_id": "passage:cit-02", "after": QUOTE_OK, "rationale": "alignée"},
            session,
        ).status_code
        == 200
    )
    headers = {"x-demo-session": session}
    assert client.get("/demo/api/export.json", headers=headers).status_code == 200
    corrected = _docx_bytes(APP_BRIEF.replace(QUOTE_BAD, QUOTE_OK))
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
            {"observation_id": "citation:cit-02", "disposition": "dismissed", "rationale": "x"},
            session,
        ).status_code
        == 409
    )
    # Nouvelle exécution réelle sur le document courant : export à nouveau possible.
    assert _post(client, "/demo/api/run", {}, session).status_code == 200
    assert client.get("/demo/api/export.json", headers=headers).status_code == 200


def _import_source(
    client: TestClient, session: str, content: bytes, params: dict[str, str] | None = None
) -> TestResponse:
    return client.post(
        "/demo/api/source",
        content=content,
        params=params or {},
        headers={
            "x-demo-session": session,
            "origin": "http://testserver",
            "content-type": "application/octet-stream",
        },
    )


IMPORT_PARAMS = {
    "act": "loi du 20 février 1991",
    "article": "15",
    "alias": "loi du 20 février 1991",
    "source_uri": "https://example.invalid/loi-1991-art15",
    "filename": "loi-1991-art15.txt",
}


def test_source_import_and_exhibit_confirmation(client: TestClient) -> None:
    """Free source import: declared provenance required, bytes hashed, exhibit
    starts UNCONFIRMED (citations stay ambiguous), simulated reviewer
    confirmation unblocks actual checking; every step invalidates prior runs."""
    session = _session(client)
    assert _post(client, "/demo/api/run", {}, session).status_code == 200

    missing = _import_source(client, session, b"texte sans en-tetes")
    assert missing.status_code == 422
    assert missing.json()["error"] == "declared_keys_required"

    unreadable = _import_source(client, session, b"\xff\xfe\x00\x01", IMPORT_PARAMS)
    assert unreadable.status_code == 422
    assert unreadable.json()["error"] == "not_text"

    text = "Article 15. Disposition synthétique de test pour l'import de source."
    imported = _import_source(client, session, text.encode(), IMPORT_PARAMS)
    assert imported.status_code == 200
    exhibit_id = imported.json()["exhibit_id"]
    assert imported.json()["exhibit_confirmed"] is False
    # L'import invalide le résultat précédent : export bloqué jusqu'au nouveau run.
    assert client.get("/demo/api/export.json", headers={"x-demo-session": session}).status_code == 409

    assert _import_source(client, session, text.encode(), IMPORT_PARAMS).status_code == 409

    run = _post(client, "/demo/api/run", {}, session)
    assert run.status_code == 200
    citations = {c["reference_id"]: c["state"] for c in run.json()["findings"]["citations"]}
    assert citations["cit-03"] == "reference_ambiguous"

    unknown = _post(client, "/demo/api/exhibits/confirm", {"exhibit_id": "ex-inconnu"}, session)
    assert unknown.status_code == 422

    confirmed = _post(client, "/demo/api/exhibits/confirm", {"exhibit_id": exhibit_id}, session)
    assert confirmed.status_code == 200
    run = _post(client, "/demo/api/run", {}, session)
    assert run.status_code == 200
    citations = {c["reference_id"]: c["state"] for c in run.json()["findings"]["citations"]}
    # La pièce est identifiée et confirmée ; il n'y a toujours aucune citation
    # textuelle à comparer : l'état nomme exactement ce qui a été vérifié.
    assert citations["cit-03"] == "reference_checked_no_quotation"

    state = client.get("/demo/api/state").json()
    assert any(e["exhibit_id"] == exhibit_id and e["confirmed"] for e in state["exhibits"])
    assert any(s["imported"] for s in state["sources"])


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
