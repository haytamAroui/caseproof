"""HTTPX end-to-end contract test with an injected signed, persistent-store test double.

This does NOT establish Supabase durability or a real four-file upload.
"""
import hashlib
from io import BytesIO
from uuid import UUID, uuid4
from zipfile import ZipFile

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.litigation_headless_verification import create_headless_review_router

NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def docx(text: str) -> bytes:
    out = BytesIO()
    with ZipFile(out, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", f'<w:document xmlns:w="{NS}"><w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>')
    return out.getvalue()


class ScopedStore:
    def __init__(self) -> None:
        self.files = {"draft": docx("Zie Stuk 12, p. 3 en Pièce 4, p. 2.")}
        self.entries = [
            {"label": "Stuk", "number": "12", "source_id": "pdf-text", "version_id": "v1"},
            {"label": "Pièce", "number": "4", "source_id": "pdf-scan", "version_id": "v2"},
        ]
        self.saved: dict[str, dict] = {}

    def authorize(self, bearer: str, case_id: str, brief_id: str = "draft") -> None:
        if bearer != "owner-token" or case_id != "case-1" or brief_id != "draft":
            raise ValueError("unauthorized synthetic fixture")

    def original_docx(self, *, bearer: str, case_id: str, brief_id: str) -> bytes:
        self.authorize(bearer, case_id, brief_id)
        return self.files[brief_id]

    def manifest(self, *, bearer: str, case_id: str) -> list[dict]:
        self.authorize(bearer, case_id)
        return self.entries

    def record(self, *, bearer: str, case_id: str, brief_id: str,
               reference_id: str, snapshot_hash: str, request_id: UUID,
               decision: str, rationale: str) -> dict:
        self.authorize(bearer, case_id, brief_id)
        key = str(request_id)
        row = {"reference_id": reference_id, "snapshot_hash": snapshot_hash,
               "request_id": key, "decision": decision, "rationale": rationale,
               "actor_id": "test-owner", "created_at": "2026-10-30T00:00:00Z"}
        if key in self.saved and self.saved[key] != row:
            raise ValueError("idempotency conflict")
        self.saved[key] = row
        return row

    def decisions(self, *, bearer: str, case_id: str, brief_id: str,
                  snapshot_hash: str) -> list[dict]:
        self.authorize(bearer, case_id, brief_id)
        return [x for x in self.saved.values() if x["snapshot_hash"] == snapshot_hash]


def test_headless_discovery_review_export_contract() -> None:
    store = ScopedStore()
    app = FastAPI()
    app.include_router(create_headless_review_router(store))
    client = TestClient(app)
    base = "/v2/matters/case-1/briefs/draft/verification"
    headers = {"Authorization": "Bearer owner-token"}
    discovered = client.get(base + "/discovery", headers=headers)
    assert discovered.status_code == 200
    data = discovered.json()
    assert [x["number"] for x in data["findings"]] == ["12", "4"]
    assert all(x["page_mapping"] == "page_unmapped" for x in data["findings"])
    assert all(x["ocr_crop"] is None for x in data["findings"])
    assert not data["recognition_coverage_complete"]
    body = {"snapshot_hash": data["snapshot_hash"], "reference_id": "ref-0000",
            "request_id": str(uuid4()), "decision": "CONFIRMED_SUPPORTED",
            "rationale": "Reviewed against original source"}
    reviewed = client.post(base + "/reviews", headers=headers, json=body)
    assert reviewed.status_code == 200
    assert reviewed.json()["actor_id"] == "test-owner"
    exported = client.get(base + "/export", headers=headers)
    assert exported.status_code == 200
    assert exported.json()["human_decisions"][0]["decision"] == "CONFIRMED_SUPPORTED"
    markdown = client.get(base + "/export?format=markdown", headers=headers)
    assert "CONFIRMED_SUPPORTED" in markdown.text
    assert hashlib.sha256(store.files["draft"]).hexdigest() == data["original_sha256"]


def test_unconfigured_api_fails_closed() -> None:
    app = FastAPI()
    app.include_router(create_headless_review_router())
    from fastapi.responses import JSONResponse

    from apps.api.access_control import AccessRejected

    @app.exception_handler(AccessRejected)
    def denied(_request, error):
        return JSONResponse({"error": error.code.value}, status_code=error.http_status)

    client = TestClient(app)
    response = client.get("/v2/matters/case-1/briefs/draft/verification/discovery",
                          headers={"Authorization": "Bearer owner-token"})
    assert response.status_code == 503
