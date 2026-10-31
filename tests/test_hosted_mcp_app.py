"""Hosted MCP HTTP acceptance: auth, origin, protocol, revocation and release."""
from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from application.litigation.content_release import ContentRelease
from apps.api.hosted_mcp_app import (
    PROTOCOL,
    HostedMcpSettings,
    create_hosted_mcp_app,
)
from apps.api.hosted_mcp_oauth_boundary import VerifiedOAuthClaims

RESOURCE = "https://mcp.example.test/mcp"
ISSUER = "https://auth.example.test/"
TOKEN = "synthetic-authenticated-token"
DEFAULT = VerifiedOAuthClaims(
    subject="a3c8a7df-f46a-4984-8cb7-a491957a44a2", issuer=ISSUER,
    audiences=(RESOURCE,), scopes=frozenset({"caseproof:reports:read"}),
    expires_at=2000, issued_at=1000, bearer=TOKEN,
)
CASE = "matter"
BRIEF = "draft"
HASH = "a" * 64


class Verifier:
    def __init__(self) -> None:
        self.claims = DEFAULT
        self.calls = 0

    def verify(self, token: str) -> VerifiedOAuthClaims:
        self.calls += 1
        assert token == TOKEN
        return self.claims


class Gate:
    def __init__(self) -> None:
        self.granted = False
        self.calls = 0

    def resolve(self, *, subject, bearer, destination, case_id, brief_id, snapshot_hash):
        self.calls += 1
        assert subject == DEFAULT.subject and bearer == TOKEN
        assert destination == "lawyer-host"
        if not self.granted or case_id != CASE or brief_id != BRIEF or snapshot_hash != HASH:
            return None
        return ContentRelease(
            case_id=case_id, brief_id=brief_id, snapshot_hash=snapshot_hash, destination=destination,
            caller_digest=hashlib.sha256(TOKEN.encode()).hexdigest(),
            expires_at=datetime.now(UTC) + timedelta(minutes=1))


def setup(monkeypatch):
    from apps.api import hosted_mcp_app

    verifier = Verifier()
    gate = Gate()
    calls = []
    def dispatch(**kwargs):
        calls.append(kwargs)
        if kwargs["release"] is None:
            return {"isError": True, "error": "content_release_not_authorized"}
        return {"isError": False, "structuredContent": {"schema": "frozen", "case_id": CASE}}
    monkeypatch.setattr(hosted_mcp_app, "call_canonical_tool", dispatch)
    app = create_hosted_mcp_app(
        settings=HostedMcpSettings(
            resource=RESOURCE, issuer=ISSUER,
            allowed_origins=frozenset({"https://client.example.test"}),
            destination="lawyer-host"),
        verifier=verifier, releases=gate, store=None, clock=lambda: 1500)
    return TestClient(app), verifier, gate, calls


def headers(**extra):
    return {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": PROTOCOL, "Mcp-Method": "tools/call",
            "Mcp-Name": "caseproof_discover_references",
            **extra}


def body(method="tools/call", name="caseproof_discover_references", arguments=None):
    params = {"_meta": {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL,
        "io.modelcontextprotocol/clientCapabilities": {},
    }}
    if method == "tools/call":
        params.update({"name": name, "arguments": arguments or {
            "case_id": CASE, "brief_id": BRIEF, "snapshot_hash": HASH}})
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}


def test_oauth_metadata_and_unauthenticated_challenge(monkeypatch):
    client, verifier, gate, calls = setup(monkeypatch)
    meta = client.get("/.well-known/oauth-protected-resource")
    assert meta.status_code == 200
    assert meta.json()["resource"] == RESOURCE
    assert meta.json()["authorization_servers"] == [ISSUER]
    assert meta.headers["cache-control"] == "no-store"
    missing = client.post("/mcp", json=body(), headers={"Accept": "application/json, text/event-stream"})
    assert missing.status_code == 401
    assert 'resource_metadata="https://mcp.example.test/.well-known/oauth-protected-resource"' in missing.headers["www-authenticate"]
    assert client.get("/mcp").status_code == 405
    assert not calls and gate.calls == 0 and verifier.calls == 0


def test_stateless_discovery_and_closed_read_only_catalog(monkeypatch):
    client, _, gate, _ = setup(monkeypatch)
    for method in ("server/discover", "tools/list"):
        response = client.post("/mcp", json=body(method=method), headers={
            k: v for k, v in headers(**{"Mcp-Method": method}).items() if k != "Mcp-Name"})
        assert response.status_code == 200, response.text
        result = response.json()["result"]
        assert result["resultType"] == "complete"
        if method == "tools/list":
            assert {t["name"] for t in result["tools"]} == {
                "caseproof_discover_references", "caseproof_export_report"}
            assert all("review" not in t["name"] for t in result["tools"])
        assert gate.calls == 0


def test_per_call_host_release_and_revocation(monkeypatch):
    client, verifier, gate, calls = setup(monkeypatch)
    denied = client.post("/mcp", json=body(), headers=headers())
    assert denied.status_code == 200
    assert denied.json()["result"]["isError"] is True
    assert denied.json()["result"]["content"][0]["text"] == "content_release_not_authorized"
    gate.granted = True
    granted = client.post("/mcp", json=body(), headers=headers())
    assert granted.status_code == 200
    assert granted.json()["result"]["structuredContent"]["schema"] == "frozen"
    gate.granted = False
    revoked = client.post("/mcp", json=body(), headers=headers())
    assert revoked.json()["result"]["isError"] is True
    assert gate.calls == 3 and verifier.calls == 3
    assert len(calls) == 3 and calls[0]["release"] is None
    assert calls[1]["release"] is not None and calls[2]["release"] is None


def test_cross_matter_release_and_client_argument_injection_denied(monkeypatch):
    client, _, gate, calls = setup(monkeypatch)
    gate.granted = True
    other = body(arguments={"case_id": "other", "brief_id": BRIEF, "snapshot_hash": HASH})
    response = client.post("/mcp", json=other, headers=headers())
    assert response.json()["result"]["isError"] is True
    forged = body(arguments={"case_id": CASE, "brief_id": BRIEF, "snapshot_hash": HASH,
                            "bearer": TOKEN, "allow_document_content": True})
    response = client.post("/mcp", json=forged, headers=headers())
    # The host must refuse forged arguments BEFORE requesting any consent.
    assert response.status_code == 400
    assert response.json()["error"]["code"] == -32602
    assert len(calls) == 1 and gate.calls == 1


def test_bearer_scope_issuer_audience_and_expiry_fail_before_tools(monkeypatch):
    client, verifier, gate, calls = setup(monkeypatch)
    for mutated in (
        {"issuer": "https://evil.example/"},
        {"audiences": ("https://other.example/mcp",)},
        {"scopes": frozenset()},
        {"expires_at": 1500},
        {"issued_at": 1501},
        {"bearer": "other"},
    ):
        verifier.claims = replace(DEFAULT, **mutated)
        response = client.post("/mcp", json=body(), headers=headers())
        assert response.status_code == 401
    assert gate.calls == 0 and not calls


def test_header_meta_origin_json_and_session_violations(monkeypatch):
    client, _, gate, calls = setup(monkeypatch)
    cases = [
        ({"Origin": "https://evil.example"}, body(), 403),
        ({"MCP-Protocol-Version": "2025-11-25"}, body(), 400),
        ({"Mcp-Method": "tools/list"}, body(), 400),
        ({"Mcp-Name": "caseproof_export_report"}, body(), 400),
        ({"Mcp-Session-Id": "legacy-session"}, body(), 400),
    ]
    for extra, payload, status in cases:
        response = client.post("/mcp", json=payload, headers=headers(**extra))
        assert response.status_code == status
    bad = body()
    bad["params"]["_meta"]["io.modelcontextprotocol/protocolVersion"] = "2025-11-25"
    assert client.post("/mcp", json=bad, headers=headers()).status_code == 400
    assert not calls and gate.calls == 0
