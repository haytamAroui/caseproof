"""Project-pinned Supabase OAuth user-token verifier for the hosted MCP host.

The JWT envelope is UNTRUSTED until GoTrue /auth/v1/user has verified the
bearer against the pinned project. No local signature bypass, static tokens,
service_role key, raw user_metadata scopes, cookies or OAuth redirects.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from apps.api.access_control import IdentityServiceUnavailable, InvalidBearer
from apps.api.hosted_mcp_oauth_boundary import VerifiedOAuthClaims
from apps.api.supabase_auth_verifier import (
    HttpsSupabaseUserLookup,
    SupabaseUserLookup,
    _untrusted_claims,
)


@dataclass(frozen=True, slots=True)
class SupabaseOAuthBearerVerifier:
    project_ref: str
    user_lookup: SupabaseUserLookup

    @classmethod
    def live(cls, project_ref: str, publishable_key: str) -> SupabaseOAuthBearerVerifier:
        # The lookup pins the TLS endpoint to the exact project and accepts
        # *only* an unprivileged publishable API key.
        return cls(project_ref, HttpsSupabaseUserLookup(project_ref, publishable_key))

    def verify(self, token: str) -> VerifiedOAuthClaims:
        header, claims = _untrusted_claims(token)
        expected_issuer = f"https://{self.project_ref}.supabase.co/auth/v1"
        if (header.get("alg") not in ("RS256", "ES256") or
                claims.get("iss") != expected_issuer or
                claims.get("role") != "authenticated" or
                claims.get("is_anonymous") is True):
            raise InvalidBearer("Unsupported OAuth access token")
        # Accept a dedicated resource audience, not the generic 'authenticated'
        # session audience. Exactly who can obtain such tokens is an IdP setup gate.
        audiences = claims.get("aud")
        if type(audiences) is str:
            audiences = [audiences]
        if (type(audiences) is not list or not audiences or
                any(type(a) is not str or not a for a in audiences)):
            raise InvalidBearer("OAuth resource audience required")
        subject, session = claims.get("sub"), claims.get("session_id")
        try:
            if type(subject) is not str or type(session) is not str:
                raise ValueError("missing subject or session")
            UUID(subject)
            UUID(session)
        except ValueError:
            raise InvalidBearer("Invalid OAuth user identity") from None
        expires, issued, scopes = claims.get("exp"), claims.get("iat"), claims.get("scope")
        if (type(expires) is not int or type(issued) is not int or
                type(scopes) is not str or not scopes or len(scopes) > 1024):
            raise InvalidBearer("Invalid OAuth token lifetime/scope")
        # GoTrue validates JWT signature/issuer and returns the current user.
        # This must happen on EVERY request: no positive validation cache.
        try:
            user = self.user_lookup.get_verified_user(token)
        except (InvalidBearer, IdentityServiceUnavailable):
            raise
        except Exception:
            raise IdentityServiceUnavailable("OAuth identity service unavailable") from None
        if (user.get("id") != subject or user.get("deleted_at") or
                user.get("is_anonymous") is True or
                user.get("banned_until")):
            raise InvalidBearer("Inactive or mismatched OAuth user")
        return VerifiedOAuthClaims(
            subject=subject, issuer=expected_issuer, audiences=tuple(audiences),
            scopes=frozenset(scopes.split()), expires_at=expires, issued_at=issued,
            bearer=token)
