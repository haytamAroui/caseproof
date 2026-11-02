"""Historical inspection stays scoped and read-only while old bytes remain verifiable."""
import hashlib
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.dossier_viewer import create_dossier_viewer_router
from apps.api.signed_supabase_originals import PrivateStorageDenied

RAW = b"%PDF-1.7\nsynthetic historical source"
SHA = hashlib.sha256(RAW).hexdigest()
SNAP = "a" * 64
BASE = f"/v2/matters/case/briefs/brief/dossier/history/{SNAP}/references/ref/viewer"
HEADERS = {"Authorization": "Bearer owner"}


class OldVersionStore:
    def __init__(self):
        self.revoked = False
        self.missing = False
        self.corrupt = False
        self.reads = 0
        self.metadata_reads = 0
        self.client = SimpleNamespace(library=SimpleNamespace(source=self.metadata, read=self.read))

    def frozen_report(self, bearer, case, brief, snapshot, *, historical=False):
        if (bearer, case, brief, snapshot, historical) != ("owner", "case", "brief", SNAP, True) or self.revoked:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        region = {
            "region_id": "b" * 64, "original_sha256": SHA,
            "page_number": 1, "bbox": [10, 20, 30, 40],
            "image_size": [100, 200],
            "raster_provenance": {"crop_box": [0.0, 0.0, 100.0, 200.0],
                                  "rotation": 0, "user_unit": 1.0, "cropbox_rasterized": True}
        }
        return {
            "sources": [{"version_id": "old", "document_id": "doc",
                         "media_type": "application/pdf", "sha256": SHA,
                         "byte_length": len(RAW)}],
            "findings": [{"reference_id": "ref", "version_id": "old",
                          "source_sha256": SHA, "pdf_page": 1, "page_mapping": "mapped",
                          "visual_assessment": {"regions": [region]}}],
            "visual_pages": {"old:1": {"regions": [region]}}
        }

    def reopen_originals(self, *args):
        raise HTTPException(409, "current bundle B differs from historical A")

    def metadata(self, **kwargs):
        self.metadata_reads += 1
        if self.revoked or self.missing:
            raise PrivateStorageDenied("masked")
        assert kwargs == {"bearer": "owner", "case_id": "case",
                          "document_id": "doc", "version_id": "old"}
        return SimpleNamespace(sha256_hex=SHA), len(RAW)

    def read(self, **kwargs):
        self.reads += 1
        if self.revoked or self.missing:
            raise PrivateStorageDenied("masked")
        return RAW[:-1] + b"X" if self.corrupt else RAW


def rig():
    store = OldVersionStore()
    app = FastAPI()
    app.include_router(create_dossier_viewer_router(store))

    @app.exception_handler(AccessRejected)
    def denied(request, error):
        return JSONResponse({"error": error.code.value}, status_code=error.http_status)

    return store, TestClient(app)


def test_old_version_reopens_after_current_bundle_changes_without_current_read():
    store, client = rig()
    assert client.get(BASE.replace("/history/", "/snapshots/"), headers=HEADERS).status_code == 409
    context = client.get(BASE, headers=HEADERS)
    assert context.status_code == 200
    assert context.json()["version_id"] == "old"
    original = client.get(BASE + "/original", headers=HEADERS)
    assert original.status_code == 200 and original.content == RAW
    assert original.headers["x-caseproof-snapshot"] == SNAP
    assert original.headers["cache-control"] == "no-store"
    assert store.reads == 2  # One selected old source per context/original request, not N current sources.
    assert store.metadata_reads == 2


def test_provenance_regions_bind_to_historical_original_and_abstain_on_bad_geometry():
    store, client = rig()
    response = client.get(BASE + "/regions", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["regions"][0]["crop_box"] == [0, 0, 100, 200]
    original = store.frozen_report

    def unsupported(*args, **kwargs):
        report = original(*args, **kwargs)
        report["visual_pages"]["old:1"]["regions"][0]["raster_provenance"]["crop_box"] = [0.0, 0.0, 500.0, 100.0]
        return report
    store.frozen_report = unsupported
    result = client.get(BASE + "/regions", headers=HEADERS).json()
    assert result["regions"] == [] and result["unassessed_region_count"] == 1


def test_old_source_missing_corrupt_revoked_and_cross_scope_denied():
    store, client = rig()
    assert client.get(BASE + "/original").status_code == 401
    assert client.get(BASE.replace("/case/", "/foreign/"), headers=HEADERS).status_code == 404
    assert client.get(BASE, headers={"Authorization": "Bearer stranger"}).status_code == 404
    store.missing = True
    assert client.get(BASE + "/original", headers=HEADERS).status_code == 404
    store.missing = False
    store.corrupt = True
    assert client.get(BASE + "/original", headers=HEADERS).status_code == 503
    store.corrupt = False
    store.revoked = True
    assert client.get(BASE + "/original", headers=HEADERS).status_code == 404
    assert client.get(BASE + "/regions", headers=HEADERS).status_code == 404
