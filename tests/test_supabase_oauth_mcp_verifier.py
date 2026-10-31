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


def token(payload=None, alg="RS256"):
    p = {"iss": ISSUER, "aud": RESOURCE, "role": "authenticated",
         "sub": SUB, "session_id": SESSION, "scope": "caseproof:reports:read",
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
    verifier = SupabaseOAuthBearerVerifier(PROJECT, remote)
    result = verifier.verify(token())
    assert remote.calls == 1
    assert result.subject == SUB and result.issuer == ISSUER
    assert result.audiences == (RESOURCE,)
    assert result.scopes == frozenset({"caseproof:reports:read"})


def test_unverified_jwt_must_never_be_accepted():
    remote = Identity(False)
    with pytest.raises(InvalidBearer):
        SupabaseOAuthBearerVerifier(PROJECT, remote).verify(token())
    assert remote.calls == 1


@pytest.mark.parametrize("claim", [
    {"iss": "https://other.supabase.co/auth/v1"}, {"aud": ""},
    {"role": "service_role"}, {"scope": ""}, {"sub": str(uuid4())},
    {"session_id": "not-uuid"}, {"iat": "1000"}, {"exp": True},
    {"is_anonymous": True},
])
def test_invalid_claim_shape_or_subject(claim):
    remote = Identity()
    with pytest.raises(InvalidBearer):
        SupabaseOAuthBearerVerifier(PROJECT, remote).verify(token(claim))


@pytest.mark.parametrize("alg", ["HS256", "none", "RS512"])
def test_insecure_algorithms_denied_before_user_lookup(alg):
    remote = Identity()
    with pytest.raises(InvalidBearer):
        SupabaseOAuthBearerVerifier(PROJECT, remote).verify(token(alg=alg))
    assert remote.calls == 0


def test_remote_unavailability_fails_closed():
    class Offline:
        def get_verified_user(self, bearer):
            raise IdentityServiceUnavailable("down")
    with pytest.raises(IdentityServiceUnavailable):
        SupabaseOAuthBearerVerifier(PROJECT, Offline()).verify(token())
