"""Opt-in S2-006 live test: two REAL Supabase Auth password sessions.

Environment (never commit values):
  CASEPROOF_DEV_PUBLISHABLE_KEY
  CASEPROOF_DEV_AUTH_A_EMAIL / CASEPROOF_DEV_AUTH_A_PASSWORD
  CASEPROOF_DEV_AUTH_B_EMAIL / CASEPROOF_DEV_AUTH_B_PASSWORD

This script does NOT create users, grant memberships, access the database,
or install schema. Configure two separate, already verified dev accounts
in Supabase Auth dashboard first. No secrets or JWTs are logged.
"""

from __future__ import annotations

import os
import sys

from apps.api.live_auth_probe import run_live_auth_probe
from apps.api.supabase_auth_verifier import (
    HttpsSupabaseUserLookup,
    SupabaseAuthUserVerifier,
)
from apps.api.supabase_password_signin import PasswordCredentials, SupabasePasswordSignin

PROJECT_REF = "ldwmocpxwskvhoojndrd"  # The dedicated CaseProof dev project, never AZComply.


def _required(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(f"Required development-only environment variable missing: {key}")
    return value


def main() -> int:
    # Fail before network if not explicitly enabled. Secrets are read only
    # from process environment, never command-line flags or repository files.
    if os.getenv("CASEPROOF_LIVE_AUTH_TEST") != "YES":
        print("SKIPPED: CASEPROOF_LIVE_AUTH_TEST=YES required")
        return 2
    try:
        publishable = _required("CASEPROOF_DEV_PUBLISHABLE_KEY")
        a = PasswordCredentials(
            _required("CASEPROOF_DEV_AUTH_A_EMAIL"),
            _required("CASEPROOF_DEV_AUTH_A_PASSWORD"),
        )
        b = PasswordCredentials(
            _required("CASEPROOF_DEV_AUTH_B_EMAIL"),
            _required("CASEPROOF_DEV_AUTH_B_PASSWORD"),
        )
        if a.email == b.email:
            raise ValueError("Two distinct dev test accounts required")
        signin = SupabasePasswordSignin(PROJECT_REF, publishable)
        verifier = SupabaseAuthUserVerifier(
            PROJECT_REF, HttpsSupabaseUserLookup(PROJECT_REF, publishable)
        )
        outcome = run_live_auth_probe(
            signin, verifier, a, b,
            expected_issuer=f"https://{PROJECT_REF}.supabase.co/auth/v1",
        )
        if (
            not outcome.signed_session_a_verified
            or not outcome.signed_session_b_verified
            or not outcome.altered_signature_rejected
        ):
            raise AssertionError("Incomplete real-session verification")
        # DO NOT print emails, subject IDs, bearer JWTs, refresh tokens or
        # credentials in CI logs. A yes/no proof is the entire visible output.
        print("S2-006_REAL_SIGNED_AUTH_SESSIONS_AND_TAMPER_REJECTION_PASSED")
        print("NOTE: Database tenant/RLS and session revocation remain UNVERIFIED by this script")
        return 0
    except Exception as exc:
        # No exception message: an HTTP library/server could embed sensitive
        # tokens, emails, passwords, user identifiers or provider response.
        print(f"S2-006_LIVE_AUTH_CHECK_FAILED: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
