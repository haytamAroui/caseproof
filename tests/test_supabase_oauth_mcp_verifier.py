"""Supabase OAuth tokens require the pinned Auth /user validation boundary."""
import base64
import json
from uuid import uuid4

import pytest

from apps.api.access_control import IdentityServiceUnavailable, InvalidBearer
from apps.api.supabase_oauth_mcp_verifier import SupabaseOAuthBearerVerifier

PROJECT = "ldwmocpxwskvhoojndrd"
SUB = str(uuid4())
SESSION = str(uuid4())
ISSUER = f"https://{PROJECT}.supabase.co/auth/v1"
RESOURCE = "https://caseproof.example/mcp"
CLIENT = "approved-mcp-oauth-client-1"


def verifier(remote):
    return SupabaseOAuthBearerVerifier(PROJECT, remote, RESOURCE, frozenset({CLIENT}))


def token(payload=None, alg="RS256"):
    p = {"iss": ISSUER, "aud": "authenticated", "role": "authenticated",
         "client_id": CLIENT,
         "sub": SUB, "session_id": SESSION,
         "iat": 1000, "exp": 2000}
    p.update(payload or {})
    def enc(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")
    # These are deliberately *unsigned* fixture tokens. The remote identity
    # lookup is mocked; NO local test claims to validate a signature.
    return enc({"alg": alg, "typ": "JWT"}) + "." + enc(p) + ".test-signature"


class Identity:
    def __init__(self, accepted=True):
        self.accepted = accepted
        self.calls = 0

    def get_verified_user(self, bearer):
        self.calls += 1
        if not self.accepted:
            raise InvalidBearer("remote signature or session rejected")
        return {"id": SUB, "deleted_at": None, "is_anonymous": False}


def test_auth_remote_verification_then_claims():
    remote = Identity()
    provider = verifier(remote)
    result = provider.verify(token())
    assert remote.calls == 1
    assert result.subject == SUB and result.issuer == ISSUER
    assert result.audiences == (RESOURCE,)
    assert result.scopes == frozenset({"caseproof:reports:read"})


def test_unverified_jwt_must_never_be_accepted():
    remote = Identity(False)
    with pytest.raises(InvalidBearer):
        verifier(remote).verify(token())
    assert remote.calls == 1


@pytest.mark.parametrize("claim", [
    {"iss": "https://other.supabase.co/auth/v1"}, {"aud": "other"},
    {"client_id": "unapproved-mcp-client"}, {"client_id": None},
    {"role": "service_role"}, {"sub": str(uuid4())},
    {"session_id": "not-uuid"}, {"iat": "1000"}, {"exp": True},
    {"is_anonymous": True},
])
def test_invalid_claim_shape_or_subject(claim):
    remote = Identity()
    with pytest.raises(InvalidBearer):
        verifier(remote).verify(token(claim))


@pytest.mark.parametrize("alg", ["HS256", "none", "RS512"])
def test_insecure_algorithms_denied_before_user_lookup(alg):
    remote = Identity()
    with pytest.raises(InvalidBearer):
        verifier(remote).verify(token(alg=alg))
    assert remote.calls == 0


def test_remote_unavailability_fails_closed():
    class Offline:
        def get_verified_user(self, bearer):
            raise IdentityServiceUnavailable("down")
    with pytest.raises(IdentityServiceUnavailable):
        verifier(Offline()).verify(token())


def test_explicit_client_policy_required_and_standard_scopes_not_authority():
    remote = Identity()
    with pytest.raises(ValueError):
        SupabaseOAuthBearerVerifier(PROJECT, remote, RESOURCE, frozenset())
    # Standard Supabase OAuth scopes (OIDC identity claims) are not CaseProof
    # document read grants; no custom scope claim is needed or trusted.
    effective = verifier(remote).verify(token({"scope": "openid email"}))
    assert effective.scopes == frozenset({"caseproof:reports:read"})
    assert remote.calls == 1
