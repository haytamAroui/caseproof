"""API smoke tests; no external database or authentication required."""
from hashlib import sha256

from fastapi.testclient import TestClient

from apps.api.kernel_v1 import create_kernel_app


def test_reference_api_fails_closed_without_trusted_scope():
    with TestClient(create_kernel_app()) as client:
        assert client.post("/v1/sources", json={
            "document_id": "d1", "version_id": "v1", "sha256_hex": sha256(b"example").hexdigest(),
            "text": "example",
        }).status_code == 503


def test_reference_api_source_claim_verify_and_tenant_isolation():
    text = "100 units delivered"
    digest = sha256(text.encode()).hexdigest()
    from packages.evidence_kernel.domain.workflow import EvidenceWorkflow

    workflow = EvidenceWorkflow()
    with TestClient(create_kernel_app(workflow, trusted_scope=lambda: "tenant-a")) as client:
        source = {"document_id": "d1", "version_id": "v1", "sha256_hex": digest, "text": text}
        assert client.post("/v1/sources", json=source).status_code == 201
        claim = {
            "claim_id": "c1", "statement": "100 units delivered", "document_id": "d1",
            "version_id": "v1", "document_sha256": digest, "quote": "100 units",
        }
        assert client.post("/v1/evidence-claims", json=claim).status_code == 201
        check = client.post("/v1/evidence-claims/c1/verify")
        assert check.status_code == 200
        assert check.json()["status"] == "verified"
    with TestClient(create_kernel_app(workflow, trusted_scope=lambda: "tenant-b")) as client:
        assert client.get("/v1/evidence-claims/c1").status_code == 404


def test_invalid_source_digest_is_rejected():
    with TestClient(create_kernel_app(trusted_scope=lambda: "tenant-a")) as client:
        response = client.post("/v1/sources", json={
            "document_id": "d1", "version_id": "v1", "sha256_hex": "a" * 64, "text": "not matching",
        })
        assert response.status_code == 422
