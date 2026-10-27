"""Manual CaseProof DEV-only ephemeral REAL Supabase Auth test user lifecycle.

ONLY the official remote Supabase GoTrue Admin API creates/deletes identities.
Never use SQL INSERT into auth.users, commit passwords, or log credentials/JWTs.
No database RLS/grants/buckets are installed or changed by this smoke test.

Requires the development Auth-admin key supplied securely by GitHub Actions,
NOT available to PR workflows, frontend clients, or application HTTP routes.
"""
from __future__ import annotations

import http.client
import json
import os
import secrets
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from apps.api.live_auth_probe import SessionProbeResult, run_live_auth_probe
from apps.api.supabase_auth_verifier import (
    HttpsSupabaseUserLookup,
    SupabaseAuthUserVerifier,
)
from apps.api.supabase_password_signin import (
    PasswordCredentials,
    SupabasePasswordSignin,
)

PROJECT_REF = "ldwmocpxwskvhoojndrd"  # CaseProof dev. NEVER AZComply.
ISSUER = f"https://{PROJECT_REF}.supabase.co/auth/v1"
MAX_ADMIN_RESPONSE = 65536


class EphemeralAuthFailure(RuntimeError):
    """Generic failure, safe to display without provider response content."""


class UserAdmin(Protocol):
    def create_confirmed(self, *, email: str, password: str) -> str: ...
    def delete(self, user_id: str) -> None: ...


@dataclass(frozen=True, slots=True)
class GoTrueDevAdmin:
    """Trusted workflow-only API adapter, pinned to the CaseProof dev host."""

    key: str = field(repr=False)

    def __post_init__(self) -> None:
        # Modern server secret or legacy service_role JWT; NEVER publishable.
        if (
            type(self.key) is not str
            or len(self.key) < 30
            or not (self.key.startswith("sb_secret_") or self.key.startswith("eyJ"))
            or any(x.isspace() for x in self.key)
        ):
            raise EphemeralAuthFailure("dedicated_dev_admin_secret_required")

    def _request(
        self, method: str, path: str, payload: dict[str, object] | None,
    ) -> dict[str, object]:
        if method not in {"POST", "DELETE"}:
            raise EphemeralAuthFailure("unsupported_admin_request")
        if path != "/auth/v1/admin/users" and not (
            method == "DELETE" and path.startswith("/auth/v1/admin/users/")
        ):
            raise EphemeralAuthFailure("admin_path_not_allowed")
        conn = http.client.HTTPSConnection(f"{PROJECT_REF}.supabase.co", timeout=10)
        try:
            raw_request = json.dumps(payload).encode() if payload is not None else None
            conn.request(
                method, path, body=raw_request,
                headers={
                    "apikey": self.key,
                    "Authorization": f"Bearer {self.key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            response = conn.getresponse()
            status = response.status
            body = response.read(MAX_ADMIN_RESPONSE + 1)
        except (OSError, TimeoutError, http.client.HTTPException):
            raise EphemeralAuthFailure("dev_auth_admin_unreachable") from None
        finally:
            conn.close()
        if status not in (200, 201, 204) or len(body) > MAX_ADMIN_RESPONSE:
            # Provider response can include sensitive material. Do not expose it.
            raise EphemeralAuthFailure("dev_auth_admin_request_failed")
        if not body:
            return {}
        try:
            result: object = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeError):
            raise EphemeralAuthFailure("dev_auth_admin_invalid_response") from None
        if not isinstance(result, dict):
            raise EphemeralAuthFailure("dev_auth_admin_invalid_response")
        return result

    def create_confirmed(self, *, email: str, password: str) -> str:
        if not email.startswith("caseproof-ci-") or not email.endswith("@example.com"):
            raise EphemeralAuthFailure("only_reserved_test_email_allowed")
        obj = self._request(
            "POST", "/auth/v1/admin/users",
            {"email": email, "password": password, "email_confirm": True},
        )
        user_obj: object = obj.get("user", obj)
        if not isinstance(user_obj, dict) or not isinstance(user_obj.get("id"), str):
            raise EphemeralAuthFailure("dev_user_id_missing")
        user_id = user_obj["id"]
        try:
            UUID(user_id)
        except ValueError:
            raise EphemeralAuthFailure("dev_user_id_invalid") from None
        return user_id

    def delete(self, user_id: str) -> None:
        try:
            valid = str(UUID(user_id))
        except ValueError:
            raise EphemeralAuthFailure("refusing_unbounded_admin_delete") from None
        self._request("DELETE", f"/auth/v1/admin/users/{valid}", None)


def run_ephemeral_auth_probe(
    *, admin: UserAdmin,
    probe: Callable[[PasswordCredentials, PasswordCredentials], SessionProbeResult],
) -> None:
    """Create two separate accounts, verify genuine sign-ins and ALWAYS delete.

    An injected fake probe is allowed only for unit testing the cleanup
    choreography, NEVER as evidence that real Auth is running.
    """
    created: list[str] = []
    failed_cleanup = False
    try:
        credentials: list[PasswordCredentials] = []
        for _ in range(2):
            email = f"caseproof-ci-{secrets.token_hex(15)}@example.com"
            password = secrets.token_urlsafe(36)
            account_id = admin.create_confirmed(email=email, password=password)
            created.append(account_id)
            credentials.append(PasswordCredentials(email=email, password=password))
        receipt = probe(credentials[0], credentials[1])
        if (
            not receipt.signed_session_a_verified
            or not receipt.signed_session_b_verified
            or not receipt.altered_signature_rejected
            or receipt.project_issuer != ISSUER
            or receipt.user_a_id != created[0]
            or receipt.user_b_id != created[1]
        ):
            raise EphemeralAuthFailure("dev_signed_session_mismatch")
    finally:
        for user_id in reversed(created):
            try:
                admin.delete(user_id)
            except Exception:
                failed_cleanup = True
        if failed_cleanup:
            # Do NOT report success if deletion failed. A human must inspect
            # and remove ephemeral accounts using the Supabase Auth dashboard.
            raise EphemeralAuthFailure("ephemeral_user_cleanup_failed") from None


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise EphemeralAuthFailure("missing_required_dev_actions_secret")
    return value


def main() -> int:
    if os.getenv("CASEPROOF_EPHEMERAL_AUTH_TEST") != "YES":
        print("SKIPPED: manual ephemeral Auth smoke only")
        return 2
    try:
        publishable = _required("CASEPROOF_DEV_PUBLISHABLE_KEY")
        admin = GoTrueDevAdmin(_required("CASEPROOF_DEV_AUTH_ADMIN_KEY"))
        signin = SupabasePasswordSignin(PROJECT_REF, publishable)
        verifier = SupabaseAuthUserVerifier(
            PROJECT_REF, HttpsSupabaseUserLookup(PROJECT_REF, publishable),
        )

        def probe(a: PasswordCredentials, b: PasswordCredentials) -> SessionProbeResult:
            return run_live_auth_probe(signin, verifier, a, b, expected_issuer=ISSUER)

        run_ephemeral_auth_probe(admin=admin, probe=probe)
        print("CASEPROOF_DEV_EPHEMERAL_REAL_AUTH_SIGNIN_AND_TAMPER_REJECTION_PASSED")
        print("CASEPROOF_DEV_EPHEMERAL_AUTH_ACCOUNTS_REMOVED")
        print("M1-B/M2-B private-matter RLS, private Storage and persistence: NOT TESTED")
        return 0
    except Exception as exc:
        # Only print exception type, even if unexpected external library
        # raises a message containing credential/user data.
        print(f"CASEPROOF_DEV_EPHEMERAL_AUTH_FAILED: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
