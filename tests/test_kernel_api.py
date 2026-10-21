from fastapi.testclient import TestClient
from apps.api.main import create_app
from packages.evidence_kernel.domain.store import InMemoryEvidenceStore


def client():
    return TestClient(create_app(InMemoryEvidenceStore()))


def payload():
    return {"claim_id": "c1", "statement": "Example claim", "source": {"document_id": "d1", "document_sha256": "a" * 64, "quote": "Example text", "page": 1}}


def test_health():
    assert client().get("/health").json() == {"status": "ok"}


def test_claim_round_trip_and_unverified_defaults():
    with client() as c:
        headers = {"X-Tenant-Id": "tenant-a"}
        result = c.post("/v1/claims", headers=headers, json=payload())
        assert result.status_code == 201, result.text
        assert result.json()["source_status"] == "unverified"
        assert result.json()["corroboration"] == "not_assessed"
        assert c.get("/v1/claims/c1", headers=headers).json() == result.json()


def test_missing_tenant_is_rejected():
    assert client().post("/v1/claims", json=payload()).status_code == 401


def test_tenant_isolation_in_store():
    with client() as c:
        assert c.post("/v1/claims", headers={"X-Tenant-Id": "a"}, json=payload()).status_code == 201
        assert c.get("/v1/claims/c1", headers={"X-Tenant-Id": "b"}).status_code == 404


def test_duplicate_claim_rejected():
    with client() as c:
        h = {"X-Tenant-Id": "a"}
        assert c.post("/v1/claims", headers=h, json=payload()).status_code == 201
        assert c.post("/v1/claims", headers=h, json=payload()).status_code == 409


def test_bad_source_digest_rejected():
    p = payload()
    p["source"]["document_sha256"] = "not-a-hash"
    assert client().post("/v1/claims", headers={"X-Tenant-Id": "a"}, json=p).status_code == 422
