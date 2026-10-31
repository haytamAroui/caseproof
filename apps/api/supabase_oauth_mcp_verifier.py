"""Resource-bound Supabase OAuth client verifier for CaseProof MCP.

Supabase currently provides standard OAuth/OIDC scopes only. Its OAuth access
token has aud='authenticated' for existing RLS and a signed client_id. Do NOT
mistake OAuth's 'email'/'openid' scopes for authorization to legal documents.
A pinned *host policy* maps an approved OAuth client to this read-only MCP
resource. Every request revalidates the user via the pinned GoTrue /user endpoint.
The downstream signed bearer retains its original Supabase audience for RLS.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit
from uuid import UUID

from apps.api.access_control import IdentityServiceUnavailable, InvalidBearer
from apps.api.hosted_mcp_oauth_boundary import VerifiedOAuthClaims
from apps.api.supabase_auth_verifier import (
    PROJECT_REF,
    HttpsSupabaseUserLookup,
    SupabaseUserLookup,
    _untrusted_claims,
)

READ_PERMISSION = "caseproof:reports:read"


@dataclass(frozen=True, slots=True)
class SupabaseOAuthBearerVerifier:
    project_ref: str
    user_lookup: SupabaseUserLookup
    resource: str
    approved_client_ids: frozenset[str]

    def __post_init__(self) -> None:
        resource = urlsplit(self.resource)
        if (not PROJECT_REF.fullmatch(self.project_ref)
                or resource.scheme != "https" or not resource.netloc
                or resource.username or resource.password
                or resource.query or resource.fragment
                or not self.approved_client_ids
                or any(type(c) is not str or not 1 <= len(c) <= 200
                       or not c.isascii() or c.strip() != c for c in self.approved_client_ids)):
            raise ValueError("Pinned OAuth issuer, resource and approved client IDs required")

    @classmethod
    def live(cls, project_ref: str, publishable_key: str, *, resource: str,
             approved_client_ids: frozenset[str]) -> SupabaseOAuthBearerVerifier:
        # A new-format publishable key is the only permitted host API key.
        return cls(project_ref, HttpsSupabaseUserLookup(project_ref, publishable_key),
                   resource, approved_client_ids)

    def verify(self, token: str) -> VerifiedOAuthClaims:
        header, claims = _untrusted_claims(token)
        issuer = f"https://{self.project_ref}.supabase.co/auth/v1"
        # The 'authenticated' audience is intentional and required by Supabase
        # PostgREST RLS; resource access is defined by a server-held OAuth client
        # allowlist and a fresh, matter-bound HostContentGate decision.
        if (header.get("alg") not in ("RS256", "ES256")
                or claims.get("iss") != issuer
                or claims.get("aud") != "authenticated"
                or claims.get("role") != "authenticated"
                or claims.get("is_anonymous") is True
                or type(claims.get("client_id")) is not str
                or claims["client_id"] not in self.approved_client_ids):
            raise InvalidBearer("Unapproved or invalid OAuth client access token")
        subject, session = claims.get("sub"), claims.get("session_id")
        try:
            if type(subject) is not str or type(session) is not str:
                raise ValueError("missing subject or session")
            UUID(subject)
            UUID(session)
        except ValueError:
            raise InvalidBearer("Invalid OAuth user identity") from None
        expires, issued = claims.get("exp"), claims.get("iat")
        if (type(expires) is not int or type(issued) is not int
                or expires <= issued):
            raise InvalidBearer("Invalid OAuth token lifetime")
        # GoTrue verifies the signature and returns the current project user.
        # Fail closed on outage; no positive identity cache.
        try:
            user = self.user_lookup.get_verified_user(token)
        except (InvalidBearer, IdentityServiceUnavailable):
            raise
        except Exception:
            raise IdentityServiceUnavailable("OAuth identity service unavailable") from None
        if (user.get("id") != subject or user.get("deleted_at")
                or user.get("is_anonymous") is True or user.get("banned_until")):
            raise InvalidBearer("Inactive or mismatched OAuth user")
        # These are *effective local MCP policy bindings*, NOT claims minted by
        # Supabase. The host separately checks signed-user RLS and matter consent.
        return VerifiedOAuthClaims(
            subject=subject, issuer=issuer, audiences=(self.resource,),
            scopes=frozenset({READ_PERMISSION}), expires_at=expires,
            issued_at=issued, bearer=token, client_id=claims["client_id"])
