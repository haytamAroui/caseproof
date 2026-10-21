"""S2-003 — fail-closed server-to-Supabase Auth /user verification adapter.

The ONLY production trust boundary here is a project-pinned HTTPS request
to Supabase Auth, which verifies the bearer on its own server. Local JWT
parsing is untrusted and only checks the signed-claim fields AFTER a
successful Auth user response has confirmed the same user ID.

No raw JWTs, refresh tokens, secret/service keys, tenant role metadata,
case decisions, or approvals are stored. This module is not wired to a
live v2 endpoint. Human approval requires separate, verified attestation;
a normal Auth user is NOT automatically a trusted human reviewer.
"""

from __future__ import annotations

import base64
import binascii
import http.client
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from apps.api.access_control import (
    IdentityServiceUnavailable,
    InvalidBearer,
    VerifiedSubject,
)

PROJECT_REF = re.compile(r"^[a-z0-9]{20}$")
MAX_TOKEN_BYTES = 8192
MAX_RESPONSE_BYTES = 65536
ACCEPTED_ALGORITHMS = frozenset({"HS256", "RS256", "ES256"})


class SupabaseUserLookup(Protocol):
    def get_verified_user(self, jwt: str) -> Mapping[str, object]:
        """Must call the project-pinned Auth server, NOT decode JWT locally."""


@dataclass(frozen=True, slots=True)
class HttpsSupabaseUserLookup:
    """Project-pinned TLS client; no redirects, arbitrary host or service key."""

    project_ref: str
    publishable_key: str = field(repr=False)
    timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        if not PROJECT_REF.fullmatch(self.project_ref):
            raise ValueError("Supabase project reference must be exactly 20 lowercase alphanumerics")
        if not isinstance(self.publishable_key, str) or not self.publishable_key.strip():
            raise ValueError("Supabase publishable key required")
        if not (0.1 <= self.timeout_seconds <= 30.0):
            raise ValueError("TLS timeout must be within 0.1–30 seconds")

    def get_verified_user(self, jwt: str) -> Mapping[str, object]:
        host = f"{self.project_ref}.supabase.co"
        conn = http.client.HTTPSConnection(host, timeout=self.timeout_seconds)
        try:
            conn.request(
                "GET", "/auth/v1/user",
                headers={
                    "Authorization": f"Bearer {jwt}",
                    "apikey": self.publishable_key,
                    "Accept": "application/json",
                },
            )
            response = conn.getresponse()
            status = response.status
            body = response.read(MAX_RESPONSE_BYTES + 1)
        except (OSError, TimeoutError, http.client.HTTPException):
            raise IdentityServiceUnavailable("Auth verifier unreachable") from None
        finally:
            conn.close()

        if status in (400, 401, 403):
            raise InvalidBearer("Auth rejected bearer")
        if status != 200 or len(body) > MAX_RESPONSE_BYTES:
            raise IdentityServiceUnavailable("Auth did not return a bounded verified user")
        try:
            payload: object = json.loads(body.decode("utf-8"))
        except (UnicodeError, ValueError):
            raise IdentityServiceUnavailable("Malformed Auth response") from None
        if not isinstance(payload, dict):
            raise IdentityServiceUnavailable("Auth response must be a user object")
        return payload


def _untrusted_claims(token: str) -> tuple[Mapping[str, object], Mapping[str, object]]:
    """Untrusted envelope parsing only; NEVER authenticates a JWT signature."""
    if not isinstance(token, str) or not 0 < len(token.encode("utf-8")) <= MAX_TOKEN_BYTES:
        raise InvalidBearer("Invalid JWT size")
    parts = token.split(".")
    if len(parts) != 3 or not all(parts):
        raise InvalidBearer("Invalid JWT structure")
    decoded: list[Mapping[str, object]] = []
    try:
        for segment in parts[:2]:
            raw = base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
            if len(raw) > 4096:
                raise InvalidBearer("Oversized JWT segment")
            value: object = json.loads(raw.decode("utf-8"))
            if not isinstance(value, dict):
                raise InvalidBearer("Invalid JWT JSON object")
            decoded.append(value)
    except (ValueError, UnicodeError, binascii.Error):
        raise InvalidBearer("Malformed JWT") from None
    return decoded[0], decoded[1]


@dataclass(frozen=True, slots=True)
class SupabaseAuthUserVerifier:
    """Supabase-issued user token verification; cannot grant approval."""

    project_ref: str
    user_lookup: SupabaseUserLookup
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not PROJECT_REF.fullmatch(self.project_ref):
            raise ValueError("Invalid trusted project reference")

    def verify_bearer(self, token: str) -> VerifiedSubject:
        header, claims = _untrusted_claims(token)
        issuer = f"https://{self.project_ref}.supabase.co/auth/v1"
        if (
            header.get("alg") not in ACCEPTED_ALGORITHMS
            or claims.get("iss") != issuer
            or claims.get("aud") != "authenticated"
            or claims.get("role") != "authenticated"
        ):
            raise InvalidBearer("Unexpected issuer, audience or token algorithm")
        subject = claims.get("sub")
        session = claims.get("session_id")
        try:
            if not isinstance(subject, str) or not isinstance(session, str):
                raise ValueError("JWT subject/session is missing")
            UUID(subject)
            UUID(session)
        except ValueError:
            raise InvalidBearer("Invalid subject/session identity") from None
        exp = claims.get("exp")
        iat = claims.get("iat")
        if type(exp) is not int or type(iat) is not int:
            raise InvalidBearer("Invalid issued/expiry claims")
        now = self.clock()
        if now.tzinfo is None or now.utcoffset() != UTC.utcoffset(now):
            raise IdentityServiceUnavailable("Verifier clock is not UTC")
        if exp <= now.timestamp() or iat > now.timestamp() or iat >= exp:
            raise InvalidBearer("Expired or not-yet-issued token")

        # Critical: only the remote Auth service validates the signature
        # and returns the CURRENT project user. No local decoded claim is
        # trusted in place of this server verification.
        try:
            user = self.user_lookup.get_verified_user(token)
        except (InvalidBearer, IdentityServiceUnavailable):
            raise
        except Exception:
            raise IdentityServiceUnavailable("Auth verification failed") from None
        if not isinstance(user, Mapping):
            raise IdentityServiceUnavailable("Invalid verified user shape")
        if (
            user.get("id") != subject
            or user.get("deleted_at")
            or user.get("banned_until")
            or user.get("is_anonymous") is True
        ):
            raise InvalidBearer("Auth user mismatch or unavailable")

        return VerifiedSubject(
            subject_id=subject,
            issuer=issuer,
            audience="authenticated",
            verified_at=now,
            expires_at=datetime.fromtimestamp(exp, UTC),
            # Supabase login establishes user identity, NOT independent
            # human verification / separation-of-duties attestation.
            human_authenticated=False,
        )
