"""M1 HTTP contract is synthetically composed; no signed cloud token claimed."""
from dataclasses import dataclass

from fastapi.testclient import TestClient

from application.litigation.library import EvidenceInventory, EvidencePreview, EvidenceRow
from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.litigation_evidence_app import create_evidence_app


@dataclass
class SyntheticRead:
    def inventory(self, *, bearer: str, case_id: str) -> EvidenceInventory:
        if bearer != "test-signed-only" or case_id != "matter-1":
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        return EvidenceInventory(
            (EvidenceRow("s1", "d1", "v1", "a" * 64, "text/plain", "ready",
                         "fixture", "rep", (), ()),),
            True, 0, 0,
        )

    def preview(self, *, bearer: str, case_id: str, source_id: str) -> EvidencePreview:
        self.inventory(bearer=bearer, case_id=case_id)
        if source_id != "s1":
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        return EvidencePreview(
            self.inventory(bearer=bearer, case_id=case_id).rows[0],
            "fictional sample source", ((0, 9, "text:0", None),),
        )


def test_unconfigured_api_has_no_content_or_upload_routes():
    client = TestClient(create_evidence_app())
    result = client.get("/v2/matters/anything/evidence")
    assert result.json() == {"status": "unavailable", "enabled": False}
    assert result.headers["cache-control"] == "no-store"
    assert client.post("/v2/matters/anything/evidence", json={"text": "secret"}).status_code == 405


def test_authenticated_inventory_returns_safe_lineage_without_raw_text():
    client = TestClient(create_evidence_app(SyntheticRead()))
    response = client.get(
        "/v2/matters/matter-1/evidence", headers={"Authorization": "Bearer test-signed-only"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["rows"][0]["original_sha256"] == "a" * 64
    assert "text" not in data["rows"][0]
    assert "fictional sample source" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_previews_return_untrusted_content_only_after_authorization():
    client = TestClient(create_evidence_app(SyntheticRead()))
    response = client.get(
        "/v2/matters/matter-1/evidence/s1",
        headers={"Authorization": "Bearer test-signed-only"},
    )
    assert response.status_code == 200
    assert response.json()["text"] == "fictional sample source"


def test_missing_bearer_and_foreign_case_denied_with_identical_content_masking():
    client = TestClient(create_evidence_app(SyntheticRead()))
    assert client.get("/v2/matters/matter-1/evidence").status_code == 401
    assert client.get(
        "/v2/matters/foreign/evidence",
        headers={"Authorization": "Bearer test-signed-only"},
    ).status_code == 404
    assert client.get(
        "/v2/matters/matter-1/evidence/unknown",
        headers={"Authorization": "Bearer test-signed-only"},
    ).status_code == 404
