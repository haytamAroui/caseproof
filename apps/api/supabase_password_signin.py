"""S2-006: development-only password sign-in used to obtain REAL Auth JWTs.

This is a smoke-test transport, not an HTTP endpoint or an application login
session store. Only already-created, email-confirmed development users are
supported. Never print tokens, passwords, refresh tokens or Auth responses.
"""

from __future__ import annotations

import http.client
import json
from dataclasses import dataclass, field
from typing import Protocol

from apps.api.access_control import IdentityServiceUnavailable, InvalidBearer
from apps.api.supabase_auth_verifier import MAX_RESPONSE_BYTES, PROJECT_REF, PUBLISHABLE_KEY


@dataclass(frozen=True, slots=True)
class PasswordCredentials:
    email: str
    password: str = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.email, str) or not self.email.strip() or len(self.email) > 320:
            raise ValueError("Dev login email required")
        if not isinstance(self.password, str) or not self.password:
            raise ValueError("Dev login password required")


@dataclass(frozen=True, slots=True)
class AuthAccessToken:
    """Sensitive transient value; never serialize/log a session response."""

    access_token: str = field(repr=False)
    user_id: str

    def __post_init__(self) -> None:
        if not self.access_token or not self.user_id:
            raise ValueError("Auth session missing access token or subject")


class PasswordSignin(Protocol):
    def sign_in(self, credentials: PasswordCredentials) -> AuthAccessToken: ...


@dataclass(frozen=True, slots=True)
class SupabasePasswordSignin:
    project_ref: str
    publishable_key: str = field(repr=False)
    timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        if not PROJECT_REF.fullmatch(self.project_ref):
            raise ValueError("Exact trusted Supabase project reference required")
        if not isinstance(self.publishable_key, str) or not PUBLISHABLE_KEY.fullmatch(
            self.publishable_key
        ):
            raise ValueError("Only a Supabase sb_publishable_ key is allowed")
        if not 0.1 <= self.timeout_seconds <= 30.0:
            raise ValueError("Invalid HTTPS timeout")

    def sign_in(self, credentials: PasswordCredentials) -> AuthAccessToken:
        """Auth server issues the SIGNED token; no locally fabricated claims."""
        if not isinstance(credentials, PasswordCredentials):
            raise TypeError("Expected validated dev credentials")
        host = f"{self.project_ref}.supabase.co"
        conn = http.client.HTTPSConnection(host, timeout=self.timeout_seconds)
        try:
            body = json.dumps({
                "email": credentials.email,
                "password": credentials.password,
            }).encode("utf-8")
            conn.request(
                "POST", "/auth/v1/token?grant_type=password", body=body,
                headers={
                    "apikey": self.publishable_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            response = conn.getresponse()
            status = response.status
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        except (OSError, TimeoutError, http.client.HTTPException):
            raise IdentityServiceUnavailable("Dev Auth sign-in connection unavailable") from None
        finally:
            conn.close()
        if status in (400, 401, 403):
            raise InvalidBearer("Supabase rejected development credentials")
        if status != 200 or len(raw) > MAX_RESPONSE_BYTES:
            raise IdentityServiceUnavailable("Supabase Auth sign-in unavailable")
        try:
            data: object = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError):
            raise IdentityServiceUnavailable("Invalid Supabase Auth session response") from None
        if not isinstance(data, dict):
            raise IdentityServiceUnavailable("Unexpected Auth session response")
        token = data.get("access_token")
        token_type = data.get("token_type")
        user = data.get("user")
        if (
            not isinstance(token, str)
            or not token
            or token_type != "bearer"
            or not isinstance(user, dict)
            or not isinstance(user.get("id"), str)
        ):
            raise IdentityServiceUnavailable("Incomplete verified-session candidate")
        return AuthAccessToken(access_token=token, user_id=user["id"])
