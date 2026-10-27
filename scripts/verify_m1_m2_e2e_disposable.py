"""PR-safe local-only test of the EXACT M1/M2 integration used by live Auth.

Uses purely synthetic bearer tokens and subject IDs to exercise the M2
composition. These tests NEVER claim real Supabase signed-user acceptance.
"""
from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from apps.api.access_control import InvalidBearer, VerifiedSubject
from apps.api.supabase_password_signin import AuthAccessToken, PasswordCredentials
from scripts.verify_dev_ephemeral_auth import ISSUER
from scripts.verify_m1_m2_signed_e2e import run_signed_m1_m2
from scripts.verify_m1_signed_private_reader import _only_local

TOKENS = (
    "header.payload.fixtureSignatureAAA",
    "header.payload.fixtureSignatureBBB",
    "header.payload.fixtureSignatureCCC",
)


class FixtureSignIn:
    def __init__(self, credentials: tuple[PasswordCredentials, ...],
                 subjects: tuple[str, ...]) -> None:
        self.lookup = {
            c.email: AuthAccessToken(token, sub)
            for c, token, sub in zip(credentials, TOKENS, subjects, strict=True)
        }

    def sign_in(self, credentials: PasswordCredentials) -> AuthAccessToken:
        return self.lookup[credentials.email]


class FixtureVerifier:
    """Dummy identity boundary, allowed ONLY by disposable CI entry point."""

    def __init__(self, subjects: tuple[str, ...]) -> None:
        self.subjects = dict(zip(TOKENS, subjects, strict=True))

    def verify_bearer(self, token: str) -> VerifiedSubject:
        if token not in self.subjects:
            raise InvalidBearer("unrecognized synthetic fixture")
        now = datetime.now(UTC)
        return VerifiedSubject(
            self.subjects[token], ISSUER, "authenticated",
            now - timedelta(seconds=1), now + timedelta(minutes=10), False,
        )


def main() -> None:
    if os.getenv("CASEPROOF_M1M2_FAKE_ONLY") != "YES":
        raise RuntimeError("explicit disposable synthetic-only flag required")
    _only_local()
    subjects = tuple(str(uuid4()) for _ in range(3))
    credentials = tuple(
        PasswordCredentials(f"fixture-{i}@example.invalid", "synthetic_only")
        for i in range(3)
    )
    run_signed_m1_m2(
        credentials, signin=FixtureSignIn(credentials, subjects),
        verifier=FixtureVerifier(subjects), synthetic_only=True,
    )
    print("M1_M2_FULL_LOCAL_COMPOSITION_PASSED")
    print("SYNTHETIC_BEARERS_ONLY; NOT_SIGNED_SUPABASE_ACCEPTANCE")


if __name__ == "__main__":
    main()
