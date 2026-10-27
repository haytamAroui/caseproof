"""Synthetic demo is local-only and is not a real authentication service."""
from fastapi.testclient import TestClient

from apps.word_addin.demo_app import app


def test_search_requires_demo_token_and_returns_confirmed_mapping():
    client = TestClient(app, client=("127.0.0.1", 50000))
    url = "/v2/matters/synthetic-matter/briefs/synthetic-brief/evidence/search"
    assert client.post(url, json={"query": "betaling"}).status_code == 401
    response = client.post(url, json={"query": "betaling"},
                           headers={"Authorization": "Bearer synthetic-demo-only"})
    assert response.status_code == 200
    hit = response.json()["hits"][0]
    assert hit["citation"]["label"] == "Stuk 1" and hit["citation"]["pdf_page"] == 1
    assert response.json()["coverage"] == "complete"


def test_remote_requests_cannot_access_synthetic_service():
    client = TestClient(app, client=("192.0.2.1", 50000))
    assert client.get("/index.html?demo=1").status_code == 403
