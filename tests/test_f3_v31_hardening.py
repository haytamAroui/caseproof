"""F3 v3.1 fail-closed regression tests on synthetic source content only."""
from __future__ import annotations

import json
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from application.litigation.frontend_contract import FindingView
from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.dossier_journey import InventoryConfirmation, PageConfirmation
from apps.api.signed_supabase_originals import PrivateStorageDenied
from apps.api.workspace_intake import WorkspaceIntake
from tests.test_dossier_journey import assess
from tests.test_dossier_viewer import BASE, rig
from tests.test_phase4_headless_api import docx


def _exception(citation: str = "Annex 9") -> dict[str, object]:
    return {"version": 1, "kind": "detector_miss", "citation": citation,
            "rationale": "Human identified a missing inventory entry",
            "review_state": "review_needed"}


def _body(**kwargs):
    return {"bundle_signature": "a" * 64, "request_id": str(uuid4()),
            "inventory_complete": False, "entries": [], **kwargs}


def test_review_needed_exceptions_are_versioned_bounded_and_incomplete():
    body = InventoryConfirmation.model_validate(_body(exceptions=[_exception()]))
    assert body.exceptions[0].review_state == "review_needed"
    assert body.model_dump()["exceptions"][0]["version"] == 1
    for broken in [
        _body(inventory_complete=True, exceptions=[_exception()]),
        _body(exceptions=[_exception(), _exception()]),
        _body(exceptions=[{**_exception(), "version": 2}]),
        _body(exceptions=[{**_exception(), "review_state": "verified"}]),
        _body(exceptions=[{**_exception(), "source_version_id": "invented"}]),
        _body(exceptions=[{**_exception(), "citation": ""}]),
    ]:
        with pytest.raises(ValidationError):
            InventoryConfirmation.model_validate(broken)


def test_pending_exception_prevents_fabricated_inventory_absence():
    sources = [{"role": "exhibit", "version_id": "version",
                "document_id": "doc", "sha256": "a" * 64, "page_count": 6}]
    payload = {"inventory_complete": True,
               "entries": [{"label": "stuk", "number": "1", "source_version_id": "version", "pages": []}],
               "exceptions": [_exception()]}
    report = assess(docx("Stuk 9, PDF p. 6."), sources, {"payload": payload})
    assert report["findings"][0]["identity"] == "not_assessed"
    assert report["findings"][0]["technical_check"] == "unresolved"
    assert report["coverage"]["inventory_exceptions_pending"] == 1
    assert not report["coverage"]["inventory_confirmed_complete"]


@pytest.mark.parametrize("label", ["4", "04", "iv", "IV", "MCMXCIX"])
def test_literal_page_labels_supported_by_confirmation_and_finding_projection(label):
    mapped = PageConfirmation(space="printed", label=label, pdf_page=6,
                              rationale="Inspected physical PDF page six")
    assert mapped.label == label
    sources = [{"role": "exhibit", "version_id": "version",
                "document_id": "doc", "sha256": "a" * 64, "page_count": 6}]
    confirmation = {"payload": {"inventory_complete": True, "entries": [{
        "label": "stuk", "number": "1", "source_version_id": "version", "pages": [mapped.model_dump()]}]}}
    report = assess(docx(f"Stuk 1, printed p. {label}."), sources, confirmation)
    finding = report["findings"][0]
    assert finding["page_mapping"] == "mapped"
    assert finding["pdf_page"] == 6
    assert finding["page_spaces"]["printed"]["value"] == label
    assert FindingView.model_validate(finding).page_mapping == "mapped"


@pytest.mark.parametrize("label", ["", "IC", "Iiv", "XIIII", "iv ", "Ⅳ", "4a", "1000000", "../4"])
def test_unsafe_page_labels_abstain(label):
    with pytest.raises(ValidationError):
        PageConfirmation(space="printed", label=label, pdf_page=6,
                         rationale="Inspected physical PDF page six")


def test_roman_does_not_become_a_physical_pdf_offset():
    report = assess(docx("Stuk 1, PDF p. iv."),
                    [{"role": "exhibit", "version_id": "version", "document_id": "doc",
                      "sha256": "a" * 64, "page_count": 6}],
                    {"payload": {"inventory_complete": True, "entries": [{
                        "label": "stuk", "number": "1", "source_version_id": "version", "pages": []}]}})
    assert report["findings"][0]["pdf_page"] is None
    assert report["coverage"]["checked"] == 0


def test_printed_four_to_physical_six_can_open_source_viewer():
    store, client = rig()
    store.page = 6
    report = assess(docx("Stuk 1, printed p. 4."), [{
        "role": "exhibit", "version_id": "source", "document_id": "doc",
        "sha256": "a" * 64, "page_count": 6}], {"payload": {
        "inventory_complete": True, "entries": [{
            "label": "stuk", "number": "1", "source_version_id": "source",
            "pages": [{"space": "printed", "label": "4", "pdf_page": 6,
                       "rationale": "Read printed four on physical page six"}]}]}})
    assert report["findings"][0]["pdf_page"] == 6
    response = client.get(BASE, headers={"Authorization": "Bearer owner"})
    assert response.status_code == 200
    assert response.json()["page_mapping"] == "mapped"
    assert response.json()["pdf_page"] == 6
    original = client.get(BASE + "/original", headers={"Authorization": "Bearer owner"})
    assert original.status_code == 200
    assert original.headers["cache-control"] == "no-store"
    store.revoked = True
    assert client.get(BASE + "/original", headers={"Authorization": "Bearer owner"}).status_code == 404


def test_partial_readback_reports_each_source_without_fabricating_success(monkeypatch):
    import apps.api.workspace_intake as module
    from tests.test_workspace_intake import CASE, command

    c = command()
    source_rows = [dict(f.model_dump(exclude={"content_base64"}),
                        document_id=str(uuid4()), version_id=str(uuid4())) for f in c.files]
    originals = {r["version_id"]: __import__("base64").b64decode(f.content_base64)
                 for r, f in zip(source_rows, c.files, strict=True)}
    client, store = Mock(), Mock()
    client.bundle_manifest.return_value = {"sources": source_rows}
    store.rpc.return_value = {"bundle_signature": "a" * 64, "confirmation": None}
    store.sources.side_effect = AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
    def read(**args):
        version = args["version_id"]
        if version == source_rows[1]["version_id"]:
            raise PrivateStorageDenied("missing or masked")
        if version == source_rows[2]["version_id"]:
            return originals[version] + b"corrupt"
        return originals[version]
    client.library.read.side_effect = read
    connection = Mock()
    connection.getresponse.return_value.status = 200
    connection.getresponse.return_value.read.return_value = json.dumps(
        [{"version_id": source_rows[0]["version_id"]}]).encode()
    monkeypatch.setattr(module.http.client, "HTTPSConnection", Mock(return_value=connection))
    receipt = WorkspaceIntake(client, store).context("signed-fixture", CASE)
    assert not receipt.readback_complete
    assert [row.readback for row in receipt.sources] == [
        "verified", "unknown", "integrity_mismatch", "verified"]
    assert all(row.processing == "unavailable" for row in receipt.sources)
    assert client.library.read.call_count == 4
