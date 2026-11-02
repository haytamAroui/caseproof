"""Frozen viewer source authorization, exact scope and byte binding."""

import hashlib
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.dossier_viewer import create_dossier_viewer_router

RAW = b"%PDF-1.7\nsynthetic-only transport fixture"
HASH = hashlib.sha256(RAW).hexdigest()
SNAP = "a" * 64


class Store:
    def __init__(self):
        self.changed = False
        self.revoked = False
        self.client = SimpleNamespace(library=SimpleNamespace(read=self.read))

    def read(self, **kwargs):
        assert kwargs == {"bearer": "owner", "case_id": "case", "document_id": "doc", "version_id": "source"}
        return RAW[:-1] + b"X" if self.changed else RAW

    def reopen(self, bearer, case, brief, snapshot):
        if (bearer, case, brief, snapshot) != ("owner", "case", "brief", SNAP) or self.revoked:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        return {
            "sources": [
                {
                    "version_id": "source",
                    "document_id": "doc",
                    "media_type": "application/pdf",
                    "sha256": HASH,
                    "byte_length": len(RAW),
                }
            ],
            "findings": [
                {
                    "reference_id": "ref",
                    "version_id": "source",
                    "source_sha256": HASH,
                    "pdf_page": 1,
                    "page_mapping": "mapped",
                }
            ],
        }, b"draft"


def rig():
    store = Store()
    app = FastAPI()
    app.include_router(create_dossier_viewer_router(store))

    @app.exception_handler(AccessRejected)
    def denied(request, error):
        return JSONResponse({"error": error.code.value}, status_code=error.http_status)

    return store, TestClient(app)


BASE = f"/v2/matters/case/briefs/brief/dossier/snapshots/{SNAP}/references/ref/viewer"


def test_context_and_binary_bind_every_selector_and_original_bytes():
    store, client = rig()
    headers = {"Authorization": "Bearer owner"}
    view = client.get(BASE, headers=headers)
    assert view.status_code == 200
    assert view.json()["original_sha256"] == HASH
    assert view.json()["geometry_policy"] == "derived_pdf_text_only_legacy_raster_not_projected"
    raw = client.get(BASE + "/original", headers=headers)
    assert raw.content == RAW and raw.headers["x-caseproof-snapshot"] == SNAP
    assert raw.headers["x-caseproof-original-sha256"] == HASH
    assert raw.headers["content-disposition"].startswith("attachment")
    assert raw.headers["cache-control"] == "no-store"
    store.changed = True
    assert client.get(BASE + "/original", headers=headers).status_code == 503


@pytest.mark.parametrize(
    "path",
    [
        BASE.replace("/case/", "/foreign/"),
        BASE.replace("/brief/", "/other/"),
        BASE.replace(SNAP, "b" * 64),
        BASE.replace("/ref/", "/unknown/"),
    ],
)
def test_foreign_scope_and_reference_are_masked(path):
    _, client = rig()
    assert client.get(path, headers={"Authorization": "Bearer owner"}).status_code == 404


def test_revocation_and_unauthenticated_reads_are_denied():
    store, client = rig()
    assert client.get(BASE).status_code == 401
    assert client.get(BASE, headers={"Authorization": "Bearer foreign"}).status_code == 404
    store.revoked = True
    assert client.get(BASE + "/original", headers={"Authorization": "Bearer owner"}).status_code == 404
