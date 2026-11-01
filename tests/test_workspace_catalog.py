"""HTTP contract and composition tests; not live RLS acceptance."""
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.litigation_development_app import create_litigation_development_app
from apps.api.workspace_catalog import create_workspace_catalog_router

CASE = "11111111-1111-4111-8111-111111111111"
ROW = {"case_id": CASE, "case_revision": 1, "state": "open"}


class Catalog:
    def __init__(self, rows=None, denied=False):
        self.rows = [ROW] if rows is None else rows
        self.denied = denied
        self.tokens = []

    def list_matters(self, bearer):
        self.tokens.append(bearer)
        if self.denied:
            raise AccessRejected(AccessFailure.AUTHENTICATION_REQUIRED)
        return self.rows


def client(catalog):
    app = FastAPI()
    app.include_router(create_workspace_catalog_router(catalog))

    @app.exception_handler(AccessRejected)
    async def denied(request: Request, exc: AccessRejected):
        return JSONResponse({"error": exc.code.value}, status_code=exc.http_status)

    return TestClient(app)


def test_catalog_requires_signed_bearer_and_preserves_server_projection():
    catalog = Catalog()
    http = client(catalog)
    assert http.get("/v2/workspace/matters").status_code == 401
    assert catalog.tokens == []
    response = http.get("/v2/workspace/matters", headers={"Authorization": "Bearer signed"})
    assert response.status_code == 200
    assert response.json() == {"schema": "caseproof-workspace-matters-v1", "matters": [ROW]}
    assert catalog.tokens == ["signed"]


@pytest.mark.parametrize("rows", [
    [ROW, ROW], [ROW] * 101, [{**ROW, "case_revision": True}],
    [{**ROW, "case_revision": 0}], [{**ROW, "case_id": "wrong"}],
    [{**ROW, "case_id": "00000000-0000-0000-0000-000000000000"}],
    [{**ROW, "org_id": "private"}], [{**ROW, "state": ""}],
])
def test_invalid_catalog_fails_closed_without_exposing_rows(rows):
    response = client(Catalog(rows)).get("/v2/workspace/matters", headers={"Authorization": "Bearer signed"})
    assert response.status_code == 503
    assert CASE not in response.text


def test_empty_and_revoked_catalog_are_distinct():
    headers = {"Authorization": "Bearer signed"}
    assert client(Catalog([])).get("/v2/workspace/matters", headers=headers).json()["matters"] == []
    assert client(Catalog(denied=True)).get("/v2/workspace/matters", headers=headers).status_code == 401


def test_development_composition_mounts_fail_closed_with_security_headers():
    http = TestClient(create_litigation_development_app(), client=("127.0.0.1", 1234))
    response = http.get("/v2/workspace/matters", headers={"Authorization": "Bearer signed"})
    assert response.status_code == 503
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    foreign = TestClient(create_litigation_development_app(), client=("203.0.113.1", 1234))
    assert foreign.get("/v2/workspace/matters", headers={"Authorization": "Bearer signed"}).status_code == 403
