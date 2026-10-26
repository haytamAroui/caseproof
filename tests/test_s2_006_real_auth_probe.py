"""Synthetic tests of REAL-session probe orchestration; not live JWT tests."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from apps.api.access_control import IdentityServiceUnavailable, InvalidBearer, VerifiedSubject
from apps.api.live_auth_probe import _tamper_signature, run_live_auth_probe
from apps.api.supabase_password_signin import (
    AuthAccessToken,
    PasswordCredentials,
    SupabasePasswordSignin,
)
from scripts.verify_s2_006_live_auth import main

PROJECT = "ldwmocpxwskvhoojndrd"
ISSUER = f"https://{PROJECT}.supabase.co/auth/v1"
A = "11111111-1111-4111-8111-111111111111"
B = "22222222-2222-4222-8222-222222222222"
NOW = datetime(2026, 10, 22, 12, tzinfo=UTC)


@dataclass
class FakePasswordSignin:
    users: dict[str, str] = field(default_factory=lambda: {"a@dev.invalid": A, "b@dev.invalid": B})
    tokens: dict[str, str] = field(default_factory=dict)

    def sign_in(self, credentials: PasswordCredentials) -> AuthAccessToken:
        sub = self.users[credentials.email]
        token = f"header.payload.{sub.replace('-', '')}"
        self.tokens[credentials.email] = token
        return AuthAccessToken(access_token=token, user_id=sub)


@dataclass
class FakeRemoteSignatureVerifier:
    """Simulates the server's accept/reject result, NOT cryptographic verification."""

    tokens: dict[str, str]
    server_issuer: str = ISSUER
    human: bool = False
    calls: list[str] = field(default_factory=list)

    def verify_bearer(self, token: str) -> VerifiedSubject:
        self.calls.append(token)
        if token not in self.tokens:
            raise InvalidBearer("signature mismatch")
        return VerifiedSubject(
            self.tokens[token], self.server_issuer, "authenticated",
            NOW, NOW + timedelta(minutes=10), self.human,
        )


def credentials() -> tuple[PasswordCredentials, PasswordCredentials]:
    return PasswordCredentials("a@dev.invalid", "secret-a"), PasswordCredentials(
        "b@dev.invalid", "secret-b"
    )


def _rig() -> tuple[FakePasswordSignin, FakeRemoteSignatureVerifier]:
    signin = FakePasswordSignin()
    # The two synthetic "JWTs" are known ONLY to the fake verifier.
    tokens = {
        f"header.payload.{A.replace('-', '')}": A,
        f"header.payload.{B.replace('-', '')}": B,
    }
    return signin, FakeRemoteSignatureVerifier(tokens)


def test_probe_verifies_distinct_subjects_and_mutated_signature_rejected() -> None:
    signin, verifier = _rig()
    a, b = credentials()
    result = run_live_auth_probe(signin, verifier, a, b, ISSUER)
    assert result.user_a_id == A
    assert result.user_b_id == B
    assert result.signed_session_a_verified
    assert result.signed_session_b_verified
    assert result.altered_signature_rejected
    assert len(verifier.calls) == 3
    assert verifier.calls[2] != verifier.calls[0]
    assert "password" not in repr(result).lower()
    assert "secret" not in repr(PasswordCredentials("a@dev.invalid", "secret"))


def test_probe_rejects_two_accounts_that_resolve_to_same_subject() -> None:
    signin, verifier = _rig()
    signin.users["b@dev.invalid"] = A
    a, b = credentials()
    with pytest.raises(AssertionError, match="Two separate development Auth accounts"):
        run_live_auth_probe(signin, verifier, a, b, ISSUER)


def test_probe_rejects_mismatched_trusted_issuer() -> None:
    signin, verifier = _rig()
    verifier.server_issuer = "https://other.supabase.co/auth/v1"
    with pytest.raises(AssertionError, match="does not match"):
        run_live_auth_probe(signin, verifier, *credentials(), ISSUER)


def test_probe_never_confuses_normal_password_login_with_human_attestation() -> None:
    signin, verifier = _rig()
    verifier.human = True
    with pytest.raises(AssertionError, match="human review"):
        run_live_auth_probe(signin, verifier, *credentials(), ISSUER)


def test_probe_rejects_wrong_server_identity_even_if_session_exists() -> None:
    signin, verifier = _rig()
    verifier.tokens[f"header.payload.{A.replace('-', '')}"] = str(uuid4())
    with pytest.raises(AssertionError, match="does not match"):
        run_live_auth_probe(signin, verifier, *credentials(), ISSUER)


def test_probe_rejects_server_falsely_accepting_tampered_signature() -> None:
    signin, verifier = _rig()

    class AcceptAnyTamper(FakeRemoteSignatureVerifier):
        def verify_bearer(self, token: str) -> VerifiedSubject:
            if token not in self.tokens:
                return VerifiedSubject(A, ISSUER, "authenticated", NOW, NOW + timedelta(minutes=10), False)
            return super().verify_bearer(token)

    with pytest.raises(AssertionError, match="modified JWT signature"):
        run_live_auth_probe(signin, AcceptAnyTamper(verifier.tokens), *credentials(), ISSUER)


@pytest.mark.parametrize("invalid", ["", "abc", "header.payload", "one.two.x", "a.b."])
def test_tamper_requires_real_signature_segment(invalid: str) -> None:
    with pytest.raises(ValueError):
        _tamper_signature(invalid)


def test_first_signature_character_changes_instead_of_padding_only() -> None:
    before = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.AAAAAAAAAAA"
    after = _tamper_signature(before)
    assert after != before
    assert after.split(".")[2][0] == "B"
    assert after.split(".")[2][1:] == before.split(".")[2][1:]
    assert _tamper_signature("a.b.BAAAA") == "a.b.AAAAA"


@dataclass
class FakeAuthHttpResponse:
    status: int
    payload: bytes

    def read(self, limit: int) -> bytes:
        return self.payload[:limit]


@dataclass
class FakeAuthHttpConnection:
    host: str
    timeout: float
    response: FakeAuthHttpResponse
    method: str = ""
    path: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    request_body: bytes = b""
    closed: bool = False

    def request(
        self, method: str, path: str, body: bytes, headers: dict[str, str]
    ) -> None:
        self.method = method
        self.path = path
        self.request_body = body
        self.headers = headers

    def getresponse(self) -> FakeAuthHttpResponse:
        return self.response

    def close(self) -> None:
        self.closed = True


def test_live_password_transport_is_project_pinned_and_returns_only_access_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = FakeAuthHttpResponse(
        200, json.dumps({
            "access_token": "signed.test.token",
            "token_type": "bearer",
            "user": {"id": A},
            "refresh_token": "sensitive-never-returned",
        }).encode(),
    )
    connections: list[FakeAuthHttpConnection] = []

    def connect(host: str, timeout: float) -> FakeAuthHttpConnection:
        c = FakeAuthHttpConnection(host, timeout, response)
        connections.append(c)
        return c

    monkeypatch.setattr("apps.api.supabase_password_signin.http.client.HTTPSConnection", connect)
    client = SupabasePasswordSignin(PROJECT, "sb_publishable_test_key", 2.5)
    token = client.sign_in(PasswordCredentials("a@dev.invalid", "private-password"))
    assert (token.access_token, token.user_id) == ("signed.test.token", A)
    assert "signed.test.token" not in repr(token)
    assert "private-password" not in repr(client)
    assert "sensitive-never-returned" not in repr(token)
    c = connections[0]
    assert c.host == f"{PROJECT}.supabase.co"
    assert c.path == "/auth/v1/token?grant_type=password"
    assert c.method == "POST"
    assert c.headers["apikey"] == "sb_publishable_test_key"
    assert c.headers["Content-Type"] == "application/json"
    assert json.loads(c.request_body) == {
        "email": "a@dev.invalid", "password": "private-password"
    }
    assert c.closed


@pytest.mark.parametrize(
    ("status", "payload", "exc"),
    [
        (400, b"{}", InvalidBearer),
        (401, b"{}", InvalidBearer),
        (403, b"{}", InvalidBearer),
        (302, b"{}", IdentityServiceUnavailable),
        (429, b"{}", IdentityServiceUnavailable),
        (500, b"{}", IdentityServiceUnavailable),
        (200, b"not json", IdentityServiceUnavailable),
        (200, b"[]", IdentityServiceUnavailable),
        (200, b'{"access_token": "x"}', IdentityServiceUnavailable),
        (200, b"x" * 65537, IdentityServiceUnavailable),
    ],
)
def test_password_transport_fail_closed(
    monkeypatch: pytest.MonkeyPatch, status: int, payload: bytes,
    exc: type[Exception],
) -> None:
    def connect(host: str, timeout: float) -> FakeAuthHttpConnection:
        return FakeAuthHttpConnection(host, timeout, FakeAuthHttpResponse(status, payload))

    monkeypatch.setattr("apps.api.supabase_password_signin.http.client.HTTPSConnection", connect)
    with pytest.raises(exc):
        SupabasePasswordSignin(PROJECT, "sb_publishable_test_key").sign_in(
            PasswordCredentials("a@dev.invalid", "private-password")
        )


def test_live_runner_does_not_make_network_calls_when_opt_in_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("CASEPROOF_LIVE_AUTH_TEST", raising=False)
    assert main() == 2
    output = capsys.readouterr()
    assert "SKIPPED" in output.out
    assert not output.err


def test_live_runner_without_credentials_fails_without_leaking_values(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("CASEPROOF_LIVE_AUTH_TEST", "YES")
    monkeypatch.delenv("CASEPROOF_DEV_PUBLISHABLE_KEY", raising=False)
    assert main() == 1
    output = capsys.readouterr()
    assert "S2-006_LIVE_AUTH_CHECK_FAILED: RuntimeError" in output.err
    assert "CASEPROOF_DEV_PUBLISHABLE_KEY" not in output.err


def test_live_probe_does_not_register_unauthenticated_v2_routes() -> None:
    from apps.api.main import create_app

    paths = create_app().openapi()["paths"]
    assert not any(name.startswith("/v2/") for name in paths)


@pytest.mark.parametrize("unsafe_key", [
    "", " ", "anonymous", "sb_publishable_", "sb_publishable_short",
    "sb_secret_DEVELOPMENT_FIXTURE", "service_role",
    "eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.fake",
    "sb_publishable_test_key\\r\\nX-Injected: bad",
])
def test_dev_password_transport_rejects_privileged_or_malformed_api_keys(
    unsafe_key: str,
) -> None:
    with pytest.raises(ValueError, match="publishable"):
        SupabasePasswordSignin(PROJECT, unsafe_key)


def test_publishable_validation_happens_before_auth_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    def forbidden_connect(host: str, timeout: float) -> FakeAuthHttpConnection:
        calls.append(host)
        raise AssertionError("network must not be contacted with secret key")
    monkeypatch.setattr("apps.api.supabase_password_signin.http.client.HTTPSConnection", forbidden_connect)
    with pytest.raises(ValueError):
        SupabasePasswordSignin(PROJECT, "sb_secret_leaked_service_key")
    assert calls == []


def test_manual_live_auth_workflow_scopes_secrets_to_final_probe_step() -> None:
    """Parse the JSON-form YAML workflow and enforce the security boundary."""
    workflow = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / ".github" / "workflows" / "s2-006-live-auth-sessions.yml"
        ).read_text(encoding="utf-8")
    )
    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert "env" not in workflow
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["jobs"]) == {"verify"}
    job = workflow["jobs"]["verify"]
    assert "env" not in job
    assert job["environment"] == "caseproof-dev-live-auth"
    assert job["if"] == (
        "${{ github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' "
        "&& github.repository == 'haytamAroui/caseproof' }}"
    )
    steps = job["steps"]
    assert len(steps) == 3
    assert steps[0]["uses"] == "actions/checkout@v7.0.1"
    assert steps[0]["with"] == {"ref": "main", "persist-credentials": False}
    assert steps[1]["run"] == "python3 -c 'import sys; assert sys.version_info >= (3, 11)'"
    for step in steps[:-1]:
        assert "env" not in step
    probe = steps[-1]
    assert "uses" not in probe
    assert probe["name"] == "Validate genuine, separate development Auth user sessions"
    assert probe["run"] == "python3 -m scripts.verify_s2_006_live_auth"
    required = {
        "CASEPROOF_DEV_PUBLISHABLE_KEY",
        "CASEPROOF_DEV_AUTH_A_EMAIL",
        "CASEPROOF_DEV_AUTH_A_PASSWORD",
        "CASEPROOF_DEV_AUTH_B_EMAIL",
        "CASEPROOF_DEV_AUTH_B_PASSWORD",
    }
    assert set(probe["env"]) == required | {"CASEPROOF_LIVE_AUTH_TEST"}
    assert probe["env"]["CASEPROOF_LIVE_AUTH_TEST"] == "YES"
    for key in required:
        assert probe["env"][key] == f"${{{{ secrets.{key} }}}}"
