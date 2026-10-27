"""Protected dev-only signed Auth -> PostgREST invoker-view smoke.

No database credentials or SQL claims. Verifies genuinely signed Supabase
sessions reach narrowly exposed read-only views under *user JWTs*. Requires
reviewed view deployment first; refuses fixtures/rows because no reviewed
actor-grant writer is installed yet. Does NOT close positive live RLS testing.
"""
from __future__ import annotations

import http.client
import json
import os
import sys
from typing import Protocol

from apps.api.access_control import InvalidBearer
from apps.api.live_auth_probe import _tamper_signature
from apps.api.supabase_auth_verifier import HttpsSupabaseUserLookup, SupabaseAuthUserVerifier
from apps.api.supabase_password_signin import PasswordCredentials, SupabasePasswordSignin
from scripts.verify_dev_ephemeral_auth import ISSUER, PROJECT_REF, GoTrueDevAdmin
from scripts.verify_m1_ephemeral_signed_private import ephemeral_private_probe

MAX_BODY = 32768
VIEWS = (
    "/rest/v1/caseproof_private_matters?select=case_id&limit=1",
    "/rest/v1/caseproof_private_source_versions?select=version_id&limit=1",
)


class GetView(Protocol):
    def __call__(self, *, view: str, key: str, token: str) -> tuple[int, object]: ...


def https_get_view(*, view: str, key: str, token: str) -> tuple[int, object]:
    if view not in VIEWS:
        raise ValueError("unapproved PostgREST endpoint")
    if not token or any(c in token for c in "\r\n") or len(token) > 8192:
        raise ValueError("invalid bearer transport")
    conn = http.client.HTTPSConnection(f"{PROJECT_REF}.supabase.co", timeout=10)
    try:
        conn.request(
            "GET", view,
            headers={
                "apikey": key,
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Cache-Control": "no-store",
            },
        )
        response = conn.getresponse()
        status = response.status
        content = response.read(MAX_BODY + 1)
    except (OSError, TimeoutError, http.client.HTTPException):
        raise RuntimeError("dev PostgREST unavailable") from None
    finally:
        conn.close()
    if len(content) > MAX_BODY:
        raise RuntimeError("dev PostgREST returned oversized payload")
    if status != 200:
        return status, None
    try:
        return status, json.loads(content.decode("utf-8"))
    except (ValueError, UnicodeError):
        raise RuntimeError("invalid PostgREST response") from None


def verify_signed_read_views(
    *, tokens: tuple[str, str, str], key: str, get: GetView,
) -> None:
    """Empty dev fixture: signed users see zero rows, forged bearer denied."""
    if len(set(tokens)) != 3 or any(not t for t in tokens):
        raise AssertionError("three independent real Auth tokens required")
    for view in VIEWS:
        for token in tokens:
            status, body = get(view=view, key=key, token=token)
            if status != 200 or body != []:
                raise AssertionError("signed user view missing or unauthorized data exposed")
        status, _ = get(
            view=view, key=key, token=_tamper_signature(tokens[0]),
        )
        if status not in (401, 403):
            raise AssertionError("invalid signed token accepted by live PostgREST")


def main() -> int:
    try:
        if (
            os.getenv("CASEPROOF_M1_SIGNED_REST_PROBE") != "YES"
            or os.getenv("GITHUB_REPOSITORY") != "haytamAroui/caseproof"
            or os.getenv("GITHUB_REF") != "refs/heads/main"
            or os.getenv("GITHUB_EVENT_NAME") != "workflow_dispatch"
        ):
            raise RuntimeError("protected main-only manual signed-view run required")
        key = os.getenv("CASEPROOF_DEV_PUBLISHABLE_KEY", "")
        secret = os.getenv("CASEPROOF_DEV_AUTH_ADMIN_KEY", "")
        if not key.startswith("sb_publishable_") or not secret:
            raise RuntimeError("existing protected Auth environment keys missing")
        signin = SupabasePasswordSignin(PROJECT_REF, key)
        verifier = SupabaseAuthUserVerifier(
            PROJECT_REF, HttpsSupabaseUserLookup(PROJECT_REF, key),
        )
        admin = GoTrueDevAdmin(secret)

        def check(credentials: tuple[PasswordCredentials, ...]) -> None:
            if len(credentials) != 3:
                raise AssertionError("three confirmed Auth users required")
            sessions = tuple(signin.sign_in(credential) for credential in credentials)
            subjects = tuple(verifier.verify_bearer(s.access_token) for s in sessions)
            if (
                len(set(subject.subject_id for subject in subjects)) != 3
                or any(
                    s.subject_id != subject.subject_id
                    or subject.issuer != ISSUER
                    or subject.audience != "authenticated"
                    for s, subject in zip(sessions, subjects, strict=True)
                )
            ):
                raise AssertionError("signed issuer or identity mismatch")
            try:
                verifier.verify_bearer(_tamper_signature(sessions[0].access_token))
            except InvalidBearer:
                pass
            else:
                raise AssertionError("remote Auth accepted forged bearer")
            verify_signed_read_views(
                tokens=tuple(s.access_token for s in sessions),
                key=key, get=https_get_view,
            )

        ephemeral_private_probe(admin=admin, probe=check)
        print("M1_DEV_REAL_SIGNED_AUTH_TO_POSTGREST_EMPTY_PRIVATE_VIEWS_PASSED")
        print("M1_DEV_EPHEMERAL_AUTH_USERS_REMOVED")
        print("POSITIVE_CASE_GRANTS_AND_REAL_PRIVATE_ORIGINALS_NOT_YET_TESTED")
        return 0
    except Exception as exc:
        # No remote error message, user IDs, email addresses, credentials or JWTs.
        print(f"M1_SIGNED_POSTGREST_VIEW_PROBE_FAILED: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
