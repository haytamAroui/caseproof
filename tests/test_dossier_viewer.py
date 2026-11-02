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
        self.page = 1
        self.mapping = "mapped"
        self.client = SimpleNamespace(library=SimpleNamespace(read=self.read, source=self.metadata))

    def metadata(self, **kwargs):
        return SimpleNamespace(sha256_hex=HASH), len(RAW)

    def read(self, **kwargs):
        assert kwargs == {"bearer": "owner", "case_id": "case", "document_id": "doc", "version_id": "source"}
        return RAW[:-1] + b"X" if self.changed else RAW

    def reopen_originals(self, bearer, case, brief, snapshot):
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
                    "pdf_page": self.page,
                    "page_mapping": self.mapping,
                }
            ],
        }, {"source": self.read(bearer=bearer, case_id=case, document_id="doc", version_id="source")}


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


@pytest.mark.parametrize("page", [None, True, 0, 201])
def test_mapped_reference_never_falls_back_to_exploration_page(page):
    store, client = rig()
    store.page = page
    for suffix in ("", "/original"):
        assert client.get(BASE + suffix, headers={"Authorization": "Bearer owner"}).status_code == 422


def test_unmapped_source_is_explicitly_explorable_without_a_target_page():
    store, client = rig()
    store.mapping = "unmapped"
    response = client.get(BASE, headers={"Authorization": "Bearer owner"})
    assert response.status_code == 200
    assert response.json()["page_mapping"] == "unmapped"
    assert response.json()["pdf_page"] is None


@pytest.mark.parametrize("mapping,page,valid", [
    ("mapped", 1, True), ("mapped", None, False),
    ("unmapped", None, True), ("conflicting", None, True),
    ("unmapped", 1, False), ("conflicting", 1, False),
])
def test_shared_viewer_model_enforces_page_mapping_invariant(mapping, page, valid):
    from pydantic import ValidationError

    from application.litigation.viewer_contract import ViewerContext
    payload = {"schema": "caseproof-viewer-v1", "case_id": "case", "brief_id": "brief",
               "snapshot_hash": SNAP, "reference_id": "ref", "version_id": "source",
               "original_sha256": HASH, "byte_length": len(RAW), "page_mapping": mapping,
               "pdf_page": page, "legacy_region_count": 0,
               "geometry_policy": "derived_pdf_text_only_legacy_raster_not_projected"}
    if valid:
        assert ViewerContext.model_validate(payload).pdf_page == page
    else:
        with pytest.raises(ValidationError):
            ViewerContext.model_validate(payload)
