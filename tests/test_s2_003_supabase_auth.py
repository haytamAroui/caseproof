"""S2-003 fail-closed Supabase Auth adapter tests.

All JWTs below are synthetic and UNSIGNED. The fake remote verifier is not
cryptographic proof and must never be registered with the live API. A separate
end-to-end signed-token test is mandatory before deployment.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from apps.api.access_control import (
    AccessFailure,
    AccessRejected,
    CaseAccessService,
    CaseAction,
    IdentityServiceUnavailable,
    InvalidBearer,
)
from apps.api.supabase_auth_verifier import (
    HttpsSupabaseUserLookup,
    SupabaseAuthUserVerifier,
)

REF = "ldwmocpxwskvhoojndrd"
ISSUER = f"https://{REF}.supabase.co/auth/v1"
USER = "11111111-1111-4111-8111-111111111111"
SESSION = "22222222-2222-4222-8222-222222222222"
NOW = datetime(2026, 10, 22, 12, tzinfo=UTC)


def jwt(*, header: dict[str, object] | None = None,
        claims: dict[str, object] | None = None) -> str:
    h = {"alg": "ES256", "typ": "JWT"} if header is None else header
    c = {
        "iss": ISSUER, "aud": "authenticated", "role": "authenticated",
        "sub": USER, "session_id": SESSION,
        "iat": int((NOW - timedelta(minutes=1)).timestamp()),
        "exp": int((NOW + timedelta(minutes=10)).timestamp()),
    }
    if claims is not None:
        c.update(claims)
    def enc(v: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(v).encode()).decode().rstrip("=")
    # Signature is NONFUNCTIONAL, remote verifier must be trusted.
    return enc(h) + "." + enc(c) + ".synthetic"


@dataclass
class FakeAuthUserLookup:
    """An Auth-server stand-in, not a JWT signature validator."""

    user: dict[str, object] = field(default_factory=lambda: {
        "id": USER, "deleted_at": None, "banned_until": None, "is_anonymous": False,
    })
    denied: bool = False
    offline: bool = False
    tokens_seen: list[str] = field(default_factory=list)

    def get_verified_user(self, token: str) -> dict[str, object]:
        self.tokens_seen.append(token)
        if self.denied:
            raise InvalidBearer("Auth server 401")
        if self.offline:
            raise IdentityServiceUnavailable("Auth offline")
        return self.user


def test_user_verified_only_after_remote_authenticated_user_lookup() -> None:
    fake = FakeAuthUserLookup()
    verifier = SupabaseAuthUserVerifier(REF, fake, lambda: NOW)
    token = jwt()
    v = verifier.verify_bearer(token)
    assert v.subject_id == USER
    assert v.issuer == ISSUER
    assert v.audience == "authenticated"
    assert v.expires_at == NOW + timedelta(minutes=10)
    assert v.human_authenticated is False
    assert fake.tokens_seen == [token]
    assert "role" not in v.__dataclass_fields__
    assert "tenant_id" not in v.__dataclass_fields__


@pytest.mark.parametrize(
    ("header", "mutations"),
    [
        ({"alg": "none"}, None),
        ({"alg": "HS512"}, None),
        (None, {"iss": "https://attacker.supabase.co/auth/v1"}),
        (None, {"aud": "service_role"}),
        (None, {"role": "service_role"}),
        (None, {"sub": "not-a-uuid"}),
        (None, {"session_id": "not-a-uuid"}),
        (None, {"exp": 0}),
        (None, {"exp": True}),
        (None, {"iat": "never"}),
        (None, {"iat": int((NOW + timedelta(hours=1)).timestamp())}),
        (None, {"exp": int(NOW.timestamp())}),
    ],
)
def test_forged_wrong_project_privilege_or_expired_claim_rejected_before_network(
    header: dict[str, object] | None, mutations: dict[str, object] | None
) -> None:
    fake = FakeAuthUserLookup()
    verifier = SupabaseAuthUserVerifier(REF, fake, lambda: NOW)
    with pytest.raises(InvalidBearer):
        verifier.verify_bearer(jwt(header=header, claims=mutations))
    assert fake.tokens_seen == []


@pytest.mark.parametrize("token", ["", "abc", "a.b", "a.b.c.d", "a" * 9000, "a.a.a"])
def test_malformed_or_oversized_token_rejected_without_http(token: str) -> None:
    fake = FakeAuthUserLookup()
    with pytest.raises(InvalidBearer):
        SupabaseAuthUserVerifier(REF, fake, lambda: NOW).verify_bearer(token)
    assert not fake.tokens_seen


@pytest.mark.parametrize(
    "user_data",
    [
        {"id": "99999999-9999-4999-8999-999999999999"},
        {"id": USER, "deleted_at": "2026-01-01T00:00:00Z"},
        {"id": USER, "banned_until": "2027-01-01T00:00:00Z"},
        {"id": USER, "is_anonymous": True},
        {},
    ],
)
def test_remote_user_mismatch_disabled_or_anonymous_never_grants_access(
    user_data: dict[str, object],
) -> None:
    fake = FakeAuthUserLookup(user=user_data)
    with pytest.raises(InvalidBearer):
        SupabaseAuthUserVerifier(REF, fake, lambda: NOW).verify_bearer(jwt())


def test_auth_401_is_rejected_and_auth_server_outage_is_unavailable() -> None:
    fake = FakeAuthUserLookup(denied=True)
    verifier = SupabaseAuthUserVerifier(REF, fake, lambda: NOW)
    with pytest.raises(InvalidBearer):
        verifier.verify_bearer(jwt())
    fake.denied = False
    fake.offline = True
    with pytest.raises(IdentityServiceUnavailable):
        verifier.verify_bearer(jwt())


def test_invalid_project_reference_denied_before_network_client_created() -> None:
    fake = FakeAuthUserLookup()
    for ref in ("azcomply", "https://ldwmocpxwskvhoojndrd.supabase.co", "x" * 40, ""):
        with pytest.raises(ValueError):
            SupabaseAuthUserVerifier(ref, fake)
        with pytest.raises(ValueError):
            HttpsSupabaseUserLookup(ref, "public")


class FakeHttpsResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self.body = body

    def read(self, limit: int) -> bytes:
        return self.body[:limit]


@dataclass
class FakeHttpsConnection:
    host: str
    timeout: float
    status: int = 200
    response_body: bytes = b'{"id":"11111111-1111-4111-8111-111111111111"}'
    method: str = ""
    path: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    closed: bool = False

    def request(self, method: str, path: str, headers: dict[str, str]) -> None:
        self.method = method
        self.path = path
        self.headers = headers

    def getresponse(self) -> FakeHttpsResponse:
        return FakeHttpsResponse(self.status, self.response_body)

    def close(self) -> None:
        self.closed = True


def test_https_transport_is_pinned_and_does_not_redirect_or_expose_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instances: list[FakeHttpsConnection] = []

    def connect(host: str, timeout: float) -> FakeHttpsConnection:
        conn = FakeHttpsConnection(host, timeout)
        instances.append(conn)
        return conn

    monkeypatch.setattr("apps.api.supabase_auth_verifier.http.client.HTTPSConnection", connect)
    lookup = HttpsSupabaseUserLookup(REF, "sb_publishable_test_key", 2.0)
    token = jwt()
    assert lookup.get_verified_user(token)["id"] == USER
    assert len(instances) == 1
    conn = instances[0]
    assert conn.host == f"{REF}.supabase.co"
    assert conn.timeout == 2.0
    assert conn.method == "GET"
    assert conn.path == "/auth/v1/user"
    assert conn.headers["Authorization"] == f"Bearer {token}"
    assert conn.headers["apikey"] == "sb_publishable_test_key"
    assert conn.closed
    assert "sb_publishable_test_key" not in repr(lookup)


@pytest.mark.parametrize(
    ("status", "body", "error"),
    [
        (401, b"{}", InvalidBearer),
        (403, b"{}", InvalidBearer),
        (302, b"{}", IdentityServiceUnavailable),
        (429, b"{}", IdentityServiceUnavailable),
        (503, b"{}", IdentityServiceUnavailable),
        (200, b"not-json", IdentityServiceUnavailable),
        (200, b"[]" , IdentityServiceUnavailable),
        (200, b"x" * 65537, IdentityServiceUnavailable),
    ],
)
def test_http_nonverified_response_never_returns_user(
    monkeypatch: pytest.MonkeyPatch, status: int, body: bytes,
    error: type[Exception],
) -> None:
    def connect(host: str, timeout: float) -> FakeHttpsConnection:
        return FakeHttpsConnection(host, timeout, status, body)
    monkeypatch.setattr("apps.api.supabase_auth_verifier.http.client.HTTPSConnection", connect)
    with pytest.raises(error):
        HttpsSupabaseUserLookup(REF, "sb_publishable_test_key").get_verified_user(jwt())


def test_nonhuman_login_can_never_request_approval_even_if_member_was_granted_permission() -> None:
    from apps.api.access_control import StoredCase, StoredMembership

    class LocalRepo:
        def lookup_case_membership(
            self, subject_id: str, case_id: str
        ) -> tuple[StoredCase, StoredMembership] | None:
            return (
                StoredCase(case_id, "org-a", 1, "someone-else"),
                StoredMembership(subject_id, "org-a", True, frozenset({
                    CaseAction.READ_CASE, CaseAction.REQUEST_APPROVAL
                })),
            )

    fake = FakeAuthUserLookup()
    service = CaseAccessService(
        SupabaseAuthUserVerifier(REF, fake, lambda: NOW),
        LocalRepo(), ISSUER, "authenticated", lambda: NOW,
    )
    assert service.authorize(jwt(), "case-a", CaseAction.READ_CASE).subject_id == USER
    with pytest.raises(AccessRejected) as exc:
        service.authorize(jwt(), "case-a", CaseAction.REQUEST_APPROVAL)
    assert exc.value.code is AccessFailure.PERMISSION_DENIED


def test_adapter_is_not_registered_with_live_v2_or_legacy_auth() -> None:
    from apps.api.main import create_app

    paths = create_app().openapi()["paths"]
    assert not any(name.startswith("/v2/") for name in paths)
    assert "/v1/claims" in paths
    assert HttpsSupabaseUserLookup.__name__ not in json.dumps(paths)
    assert isinstance(UUID(USER), UUID)


def test_expired_temporary_ban_does_not_permanently_block_identity() -> None:
    fake = FakeAuthUserLookup(user={
        "id": USER,
        "deleted_at": None,
        "banned_until": (NOW - timedelta(days=2)).isoformat(),
        "is_anonymous": False,
    })
    result = SupabaseAuthUserVerifier(REF, fake, lambda: NOW).verify_bearer(jwt())
    assert result.subject_id == USER
    assert result.human_authenticated is False
    assert len(fake.tokens_seen) == 1


@pytest.mark.parametrize("invalid_ban", [
    "not-a-timestamp", "2027-01-01T00:00:00", 1700000000,
])
def test_malformed_or_timezone_naive_ban_status_fails_closed(
    invalid_ban: object,
) -> None:
    fake = FakeAuthUserLookup(user={
        "id": USER, "deleted_at": None, "banned_until": invalid_ban,
        "is_anonymous": False,
    })
    with pytest.raises(IdentityServiceUnavailable):
        SupabaseAuthUserVerifier(REF, fake, lambda: NOW).verify_bearer(jwt())


def test_current_ban_is_still_rejected_even_with_200_auth_response() -> None:
    fake = FakeAuthUserLookup(user={
        "id": USER, "deleted_at": None, "banned_until": (NOW + timedelta(seconds=1)).isoformat(),
        "is_anonymous": False,
    })
    with pytest.raises(InvalidBearer):
        SupabaseAuthUserVerifier(REF, fake, lambda: NOW).verify_bearer(jwt())


@pytest.mark.parametrize("unsafe_key", [
    "", " ", "public", "sb_publishable_", "sb_publishable_short",
    "sb_secret_DEVELOPMENT_FIXTURE", "service_role",
    "eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.fake",
    "sb_publishable_test_key\\r\\nX-Injected: bad",
])
def test_auth_user_lookup_rejects_non_publishable_or_header_injection_key(
    unsafe_key: str,
) -> None:
    with pytest.raises(ValueError, match="publishable"):
        HttpsSupabaseUserLookup(REF, unsafe_key)
