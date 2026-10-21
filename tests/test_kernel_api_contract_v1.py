"""Stage 0 API contract guard: method, schema and trust-boundary drift."""
import json
from pathlib import Path

from apps.api.kernel_v1 import create_kernel_app

ROOT = Path(__file__).resolve().parents[1]


def _contract():
    return json.loads((ROOT / "contracts" / "kernel-api.v1.json").read_text(encoding="utf-8"))


def test_versioned_api_surface():
    expected = _contract()
    actual = create_kernel_app().openapi()
    assert actual["info"]["title"] == expected["title"]
    routes = {
        path: sorted(method for method in operations if method in {
            "get", "post", "put", "patch", "delete",
        })
        for path, operations in actual["paths"].items()
    }
    assert routes == expected["routes"], "API route/method drift: review and version the contract"


def test_request_schemas_do_not_drift():
    actual = create_kernel_app().openapi()["components"]["schemas"]
    for schema_name, expected_required in _contract()["request_schemas"].items():
        assert schema_name in actual
        assert sorted(actual[schema_name].get("required", [])) == sorted(expected_required)
        assert actual[schema_name].get("additionalProperties") is False


def test_no_client_controlled_tenant_scope():
    document = create_kernel_app().openapi()
    for operations in document["paths"].values():
        for operation in operations.values():
            if not isinstance(operation, dict):
                continue
            for parameter in operation.get("parameters", []):
                assert parameter["name"].lower() not in {
                    "x-tenant-id", "tenant_id", "x-org-id",
                }, "Caller-controlled tenant identity is not authentication"


def test_unconfigured_scope_fails_closed():
    from fastapi.testclient import TestClient
    with TestClient(create_kernel_app()) as client:
        response = client.get("/v1/evidence-claims/unknown")
    assert response.status_code == 503
