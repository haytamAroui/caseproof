"""Protected GitHub Actions-only genuine signed Auth → disposable M1 RLS.

Creates 3 confirmed ephemeral dev identities via approved GoTrue Admin API,
signs in with Supabase Auth, verifies actual signed JWTs over the pinned
Supabase HTTPS endpoint, binds EXACT verified users to an ephemeral local
non-privileged PostgreSQL role, and always attempts Auth user deletion.

Does NOT deploy RLS to Supabase, touch live matters/Storage, or use privileged
service credentials for DB reads. Never log bearer, password, email, UUID or
provider response. This is a release BLOCKER, not production Auth approval.
"""
from __future__ import annotations

import os
import secrets
import sys
from collections.abc import Callable
from typing import Protocol

from apps.api.access_control import InvalidBearer
from apps.api.live_auth_probe import _tamper_signature
from apps.api.supabase_auth_verifier import (
    HttpsSupabaseUserLookup,
    SupabaseAuthUserVerifier,
)
from apps.api.supabase_password_signin import (
    PasswordCredentials,
    SupabasePasswordSignin,
)
from scripts.verify_dev_ephemeral_auth import (
    GoTrueDevAdmin,
    ISSUER,
    PROJECT_REF,
    UserAdmin,
)
from scripts.verify_m1_signed_private_reader import (
    _only_local,
    verify_three_subjects,
)

class ThreeSessionProbe(Protocol):
    def __call__(self, credentials: tuple[PasswordCredentials, ...]) -> None: ...


def ephemeral_private_probe(
    *, admin: UserAdmin, probe: ThreeSessionProbe,
) -> None:
    """Every successful creation is tracked and deleted, including failures."""
    created: list[str] = []
    failed_cleanup = False
    try:
        credentials: list[PasswordCredentials] = []
        for _ in range(3):
            email = f"caseproof-ci-{secrets.token_hex(15)}@example.com"
            password = secrets.token_urlsafe(36)
            user_id = admin.create_confirmed(email=email, password=password)
            created.append(user_id)
            credentials.append(PasswordCredentials(email, password))
        probe(tuple(credentials))
    finally:
        for user_id in reversed(created):
            try:
                admin.delete(user_id)
            except Exception:
                failed_cleanup = True
        if failed_cleanup:
            raise RuntimeError("ephemeral dev identity cleanup failed") from None


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError("missing protected manual workflow secret")
    return value


def main() -> int:
    try:
        if (os.getenv("CASEPROOF_M1_REAL_PRIVATE_TEST") != "YES"
                or os.getenv("GITHUB_REPOSITORY") != "haytamAroui/caseproof"
                or os.getenv("GITHUB_REF") != "refs/heads/main"):
            raise RuntimeError("protected CaseProof main-only manual run required")
        _only_local()  # Prove disposable DB before ANY remote admin requests.
        publishable = _required_env("CASEPROOF_DEV_PUBLISHABLE_KEY")
        admin = GoTrueDevAdmin(_required_env("CASEPROOF_DEV_AUTH_ADMIN_KEY"))
        signin = SupabasePasswordSignin(PROJECT_REF, publishable)
        verifier = SupabaseAuthUserVerifier(
            PROJECT_REF,
            HttpsSupabaseUserLookup(PROJECT_REF, publishable),
        )

        def probe(credentials: tuple[PasswordCredentials, ...]) -> None:
            if len(credentials) != 3:
                raise AssertionError("three independent accounts required")
            signed = tuple(signin.sign_in(x) for x in credentials)
            identities = tuple(verifier.verify_bearer(x.access_token) for x in signed)
            if len(set(x.subject_id for x in identities)) != 3:
                raise AssertionError("Auth did not issue distinct user sessions")
            for session, subject in zip(signed, identities, strict=True):
                if (session.user_id != subject.subject_id or subject.issuer != ISSUER
                        or subject.audience != "authenticated" or subject.human_authenticated):
                    raise AssertionError("Auth trust contract mismatch")
            try:
                verifier.verify_bearer(_tamper_signature(signed[0].access_token))
            except InvalidBearer:
                pass
            else:
                raise AssertionError("remote Auth accepted tampered signed JWT")
            verify_three_subjects(
                tokens=tuple(x.access_token for x in signed),
                subjects=tuple(x.subject_id for x in identities),
                verifier=verifier,
            )

        ephemeral_private_probe(admin=admin, probe=probe)
        print("M1_GENUINE_3_AUTH_IDENTITIES_TO_DISPOSABLE_NON_BYPASS_RLS_PASSED")
        print("M1_REAL_AUTH_EPHEMERAL_USERS_REMOVED")
        print("LIVE_SUPABASE_PRIVATE_MATTER_RLS_AND_STORAGE_NOT_DEPLOYED_OR_TESTED")
        return 0
    except Exception as exc:
        # This runner has secrets in memory. Never format external exception
        # messages, HTTP payloads, bearer tokens, UUIDs or local SQL in logs.
        print(f"M1_REAL_SIGNED_PRIVATE_PROBE_FAILED: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
