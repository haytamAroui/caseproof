"""Fail-closed OAuth bearer claim boundary for a future hosted MCP transport.

This module deliberately does NOT decode or verify JWT signatures. A trusted OAuth
resource-server middleware must verify issuer, signature, expiry, audience, and
revocation before constructing VerifiedOAuthClaims. No network host is mounted.
"""
from __future__ import annotations

from dataclasses import dataclass


class OAuthBoundaryRejected(ValueError):
    """An OAuth identity cannot be used for a CaseProof MCP request."""


@dataclass(frozen=True, slots=True)
class VerifiedOAuthClaims:
    subject: str
    issuer: str
    audiences: tuple[str, ...]
    scopes: frozenset[str]
    expires_at: int
    issued_at: int
    bearer: str


def authorize_verified_claims(
    claims: VerifiedOAuthClaims,
    *,
    expected_issuer: str,
    resource_audience: str,
    now: int,
    required_scope: str = "caseproof:reports:read",
) -> str:
    """Authorize already-verified claims; never accept arbitrary decoded JWT JSON."""
    if not isinstance(claims, VerifiedOAuthClaims):
        raise OAuthBoundaryRejected("verified claims required")
    if not expected_issuer or not resource_audience or not required_scope:
        raise OAuthBoundaryRejected("OAuth resource configuration required")
    if not claims.subject or not claims.issuer or claims.issuer != expected_issuer:
        raise OAuthBoundaryRejected("issuer or subject rejected")
    if not claims.audiences or resource_audience not in claims.audiences:
        raise OAuthBoundaryRejected("resource audience rejected")
    if required_scope not in claims.scopes:
        raise OAuthBoundaryRejected("scope rejected")
    if not isinstance(now, int) or isinstance(now, bool):
        raise OAuthBoundaryRejected("invalid clock")
    if (not isinstance(claims.expires_at, int) or not isinstance(claims.issued_at, int)
            or isinstance(claims.expires_at, bool) or isinstance(claims.issued_at, bool)
            or claims.expires_at <= now or claims.issued_at > now
            or claims.expires_at <= claims.issued_at):
        raise OAuthBoundaryRejected("token lifetime rejected")
    if not claims.bearer or claims.bearer.strip() != claims.bearer:
        raise OAuthBoundaryRejected("verified bearer required")
    return claims.bearer
