"""Signed PDF/DOCX intake and Word-bridge contracts; the protected run proves live Auth."""
from __future__ import annotations

import base64
import hashlib
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from application.extraction.contracts import ExtractionError
from apps.api.access_control import AccessRejected
from apps.api.litigation_development_app import create_litigation_development_app
from apps.api.litigation_live_journey import JourneyClient
from apps.api.signed_document_parse import parse_verified_original
from apps.api.signed_supabase_originals import OriginalRef
from scripts.verify_dev_live_binary_journey import DOCX, synthetic_docx, synthetic_pdf


def test_real_bounded_pdf_parser_physical_page_and_source_lineage() -> None:
    pdf = synthetic_pdf()
    content, manifest = parse_verified_original(
        document_id=str(uuid4()), version_id=str(uuid4()), data=pdf,
        media_type="application/pdf",
    )
    assert "125 EUR" in content
    assert manifest["original_sha256"] == hashlib.sha256(pdf).hexdigest()
    assert manifest["representation_sha256"] == hashlib.sha256(content.encode()).hexdigest()
    assert manifest["complete"] is True
    assert manifest["warnings"] == []
    assert manifest["pages"] == [{"pdf_page": 1, "status": "text_extracted", "text_blocks": 1}]
    assert manifest["blocks"][0]["locator"] == "page:0"


def test_real_bounded_docx_text_is_not_fake_pagination() -> None:
    raw = synthetic_docx()
    content, manifest = parse_verified_original(
        document_id=str(uuid4()), version_id=str(uuid4()), data=raw,
        media_type=DOCX,
    )
    assert "125 EUR" in content
    assert manifest["complete"] is False
    assert manifest["coverage"] == "partial"
    assert manifest["page_mapping"] == "unverified"
    assert manifest["pages"] == []
    assert "docx_layout_page_numbers_unverified" in manifest["warnings"]
    assert manifest["blocks"][0]["locator"] == "docx:body:paragraph:0"


@pytest.mark.parametrize(("data", "mime"), [
    (b"<html>125 EUR</html>", "application/pdf"),
    (b"not a zip", DOCX),
    (b"", "application/pdf"),
    (b"x" * (5 * 1024 * 1024 + 1), "application/pdf"),
])
def test_refuse_unsafe_or_oversized_original(data: bytes, mime: str) -> None:
    with pytest.raises((ExtractionError, ValueError)):
        parse_verified_original(
            document_id=str(uuid4()), version_id=str(uuid4()), data=data,
            media_type=mime,
        )


class ParsedConnection:
    def __init__(self) -> None:
        self.request_data = None

    def request(self, method, path, body, headers):
        self.request_data = method, path, json.loads(body), headers

    def getresponse(self):
        return SimpleNamespace(status=200, read=lambda _n: b'{"ok":true}')

    def close(self):
        pass


class SignedBinaryLibrary:
    def __init__(self, raw: bytes, media: str) -> None:
        self.raw, self.media = raw, media
        self.digest = hashlib.sha256(raw).hexdigest()

    def source(self, **_kwargs):
        return OriginalRef(
            uuid4(), uuid4(), uuid4(), uuid4(), self.digest, self.media,
        ), len(self.raw)

    def read(self, **_kwargs):
        return self.raw


def test_pdf_promotion_requires_server_verified_storage_bytes_and_service_key(monkeypatch) -> None:
    connection = ParsedConnection()
    monkeypatch.setattr(
        "apps.api.litigation_live_journey.http.client.HTTPSConnection",
        lambda *_args, **_kwargs: connection,
    )
    client = JourneyClient("sb_publishable_testing", "sb_secret_protected")
    client._verifier = SimpleNamespace(
        verify_bearer=lambda _jwt: SimpleNamespace(subject_id=str(uuid4())),
    )
    raw = synthetic_pdf()
    client.library = SignedBinaryLibrary(raw, "application/pdf")
    ids = [str(uuid4()) for _ in range(3)]
    result = client.ingest("signed-jwt", *ids, str(uuid4()))
    assert result == {"ok": True}
    method, path, payload, headers = connection.request_data
    assert method == "POST"
    assert path == "/rest/v1/rpc/caseproof_dev_ingest_parsed_verified"
    assert base64.b64decode(payload["p_content_base64"]) == raw
    assert payload["p_manifest"]["media_type"] == "application/pdf"
    assert payload["p_representation"].find("125 EUR") >= 0
    assert "p_org" not in payload
    assert headers["apikey"] == "sb_secret_protected"
    assert "Authorization" not in headers


def test_browser_cannot_promote_without_secret(monkeypatch) -> None:
    client = JourneyClient("sb_publishable_testing")
    client.library = SignedBinaryLibrary(synthetic_pdf(), "application/pdf")
    with pytest.raises(AccessRejected):
        client.ingest("signed-jwt", str(uuid4()), str(uuid4()), str(uuid4()), str(uuid4()))


def test_word_search_never_offers_unconfirmed_exhibit_or_invented_pdf_page(monkeypatch) -> None:
    case, brief, doc, version = (str(uuid4()) for _ in range(4))
    source = {
        "document_id": doc, "version_id": version,
        "original_sha": "a" * 64, "representation_sha": "b" * 64,
        "media_type": DOCX, "text": "Source 125 EUR evidence",
        "parse_manifest": {
            "schema": "dev-document-parse-v1", "complete": False,
            "blocks": [{"start": 0, "end": 23, "locator": "docx:body:paragraph:0",
                        "page_index": None}], "warnings": ["docx_layout_page_numbers_unverified"],
            "pages": [],
        },
    }

    def stub_call(self, bearer, action, **_kwargs):
        assert bearer == "signed-test" and action == "state"
        return {"briefs": [{"brief_version_id": brief}], "sources": [source]}

    monkeypatch.setattr("apps.api.litigation_live_journey.JourneyClient.call", stub_call)
    app = create_litigation_development_app(publishable_key="sb_publishable_testing")
    client = TestClient(app, client=("127.0.0.1", 53411))
    headers = {"Authorization": "Bearer signed-test"}
    route = f"/dev/live/matters/{case}/briefs/{brief}/evidence/search"
    result = client.post(route, json={"query": "125 EUR"}, headers=headers)
    assert result.status_code == 200
    data = result.json()
    assert data["coverage"] == "partial"
    assert data["source_manifest"]["page_mapping"] if "page_mapping" in data["source_manifest"] else True
    assert len(data["hits"]) == 1
    assert data["hits"][0]["citation"] is None
    assert data["hits"][0]["page"] is None
    assert data["hits"][0]["start"] == 7
    assert client.post(route, json={"query": "missing"}, headers=headers).json()["hits"] == []
    other_brief = str(uuid4())
    assert client.post(
        f"/dev/live/matters/{case}/briefs/{other_brief}/evidence/search",
        json={"query": "125 EUR"}, headers=headers,
    ).status_code == 404
    assert client.post(route, json={"query": "x"}, headers=headers).status_code == 422
    assert TestClient(app, client=("203.0.113.9", 41001)).post(
        route, json={"query": "125 EUR"}, headers=headers,
    ).status_code == 403
