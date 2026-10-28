"""ClearBrief evidence UI and API reuse the checker-authorized exact brief sources."""
from __future__ import annotations

from dataclasses import replace

from fastapi.testclient import TestClient

from application.litigation.unified_review import SourceScope
from apps.api.litigation_development_app import create_litigation_development_app
from tests.test_litigation_evidence_search import CASE, DRAFT, search_rig

BASE = f"/v2/matters/{CASE}/briefs/{DRAFT}/sources"
HEADERS = {"Authorization": "Bearer signed-dev-fixture"}


def _client():
    search, store = search_rig()
    app = create_litigation_development_app(checker=search.checker)
    return TestClient(app, client=("127.0.0.1", 50000)), store


def test_signed_library_and_preview_use_same_versioned_brief():
    client, _ = _client()
    listing = client.get(BASE, headers=HEADERS)
    assert listing.status_code == 200
    result = listing.json()
    assert result["schema"] == "caseproof-clearbrief-brief-sources-v1"
    assert result["case_id"] == CASE and result["brief_version_id"] == DRAFT
    assert result["complete"] is True
    assert len(result["declared"]) == 1
    assert len(result["rows"]) == 1
    assert result["rows"][0]["source_id"] == "s1"
    assert "De betaling" not in listing.text
    preview = client.get(BASE + "/s1", headers=HEADERS)
    assert preview.status_code == 200
    data = preview.json()
    assert data["schema"] == "caseproof-clearbrief-brief-source-preview-v1"
    assert data["case_id"] == CASE and data["brief_version_id"] == DRAFT
    assert data["row"]["version_id"] == "v1"
    assert data["text"] == "De betaling is vastgesteld."
    assert data["claim_support"] == "not_assessed"
    assert preview.headers["cache-control"] == "no-store"


def test_unconfigured_or_unverified_sources_fail_closed():
    app = TestClient(create_litigation_development_app(), client=("127.0.0.1", 50000))
    assert app.get(BASE, headers=HEADERS).status_code == 503
    client, _ = _client()
    assert client.get(BASE).status_code == 401
    assert client.get(BASE, headers={"Authorization": "Bearer invalid"}).status_code == 401
    assert client.get(BASE + "/s2", headers=HEADERS).status_code == 404
    assert client.get(f"/v2/matters/foreign/briefs/{DRAFT}/sources",
                      headers=HEADERS).status_code == 404
    assert client.get(f"/v2/matters/{CASE}/briefs/foreign/sources",
                      headers=HEADERS).status_code == 503


def test_excluded_and_incomplete_denominator_visible():
    client, store = _client()
    current = store.load_bundle

    def partial(**kwargs):
        bundle = current(**kwargs)
        return replace(bundle, source_scope=SourceScope(
            (("s1", "v1"), ("s2", "v2")),
            (("s2", "v2"),),
        ))

    store.load_bundle = partial
    response = client.get(BASE, headers=HEADERS)
    assert response.status_code == 200
    result = response.json()
    assert result["complete"] is False
    assert result["excluded"] == [["s2", "v2"]]
    assert result["declared"] == [["s1", "v1"], ["s2", "v2"]]
    assert result["partial_count"] >= 1


def test_revoked_and_stale_sources_never_return_representation():
    client, store = _client()
    store.snapshot_current = False
    assert client.get(BASE, headers=HEADERS).status_code == 503
    assert client.get(BASE + "/s1", headers=HEADERS).status_code == 503
    store.snapshot_current = True
    original = store.current_access
    store.current_access = lambda subject_id, case_id: None
    assert client.get(BASE, headers=HEADERS).status_code == 404
    assert client.get(BASE + "/s1", headers=HEADERS).status_code == 404
    store.current_access = original


def test_browser_reuses_brief_source_route_not_org_wide_inventory():
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] /
           "apps/web/clearbrief/workspace.js").read_text()
    assert 'api(path()+"/sources")' in src
    assert 'api(path()+"/sources/"+encodeURIComponent(row.source_id))' in src
    assert "caseproof-clearbrief-brief-sources-v1" in src
    assert "caseproof-clearbrief-brief-source-preview-v1" in src
    assert "caseproof-evidence-preview-v1" not in src
