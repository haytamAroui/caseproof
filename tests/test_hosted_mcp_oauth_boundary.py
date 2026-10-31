"""Host OAuth claim checks must fail closed before MCP content release."""
from dataclasses import replace

import pytest

from apps.api.hosted_mcp_oauth_boundary import (
    OAuthBoundaryRejected,
    VerifiedOAuthClaims,
    authorize_verified_claims,
)

CLAIMS = VerifiedOAuthClaims(
    subject="user-1",
    issuer="https://auth.example.test/",
    audiences=("https://mcp.example.test/",),
    scopes=frozenset({"caseproof:reports:read"}),
    expires_at=2000,
    issued_at=1000,
    bearer="signed-test-bearer",
)


def check(claims=CLAIMS, **kwargs):
    options = {
        "expected_issuer": "https://auth.example.test/",
        "resource_audience": "https://mcp.example.test/",
        "now": 1500,
    }
    options.update(kwargs)
    return authorize_verified_claims(claims, **options)


def test_valid_verified_claims():
    assert check() == "signed-test-bearer"


@pytest.mark.parametrize("mutation", [
    {"subject": ""},
    {"issuer": "https://other.example.test/"},
    {"audiences": ("https://other-resource.example.test/",)},
    {"audiences": ()},
    {"scopes": frozenset()},
    {"expires_at": 1500},
    {"issued_at": 1501},
    {"expires_at": 999},
    {"bearer": ""},
    {"bearer": " token "},
])
def test_claim_rejection(mutation):
    with pytest.raises(OAuthBoundaryRejected):
        check(replace(CLAIMS, **mutation))


@pytest.mark.parametrize("kwargs", [
    {"expected_issuer": ""},
    {"resource_audience": ""},
    {"required_scope": ""},
    {"now": True},
])
def test_configuration_and_clock_fail_closed(kwargs):
    with pytest.raises(OAuthBoundaryRejected):
        check(**kwargs)


def test_unverified_decoded_json_is_never_accepted():
    with pytest.raises(OAuthBoundaryRejected):
        check(CLAIMS.__dict__ if hasattr(CLAIMS, "__dict__") else {"sub": "user-1"})
