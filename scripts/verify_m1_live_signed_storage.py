"""Real signed Supabase Auth → live private Storage denial acceptance.

Manual-only; reuses existing protected Auth environment secrets. Provisions and
deletes three confirmed users. With zero stored matters/grants in caseproof-dev,
all three MUST be denied attempted upload, while downloading the absent
synthetic object also fails. Downloading a missing object is NOT a proof of
existing-object SELECT isolation or positive custody.
"""
from __future__ import annotations

import hashlib
import os
import sys
from uuid import uuid4

from apps.api.signed_supabase_originals import (
    OriginalRef,
    PrivateStorageDenied,
    SignedOriginalsStorage,
)
from apps.api.supabase_auth_verifier import HttpsSupabaseUserLookup, SupabaseAuthUserVerifier
from apps.api.supabase_password_signin import PasswordCredentials, SupabasePasswordSignin
from scripts.verify_dev_ephemeral_auth import ISSUER, PROJECT_REF, GoTrueDevAdmin
from scripts.verify_m1_ephemeral_signed_private import ephemeral_private_probe


def verify_signed_denial(
    credentials: tuple[PasswordCredentials, ...],
    *,
    signin: SupabasePasswordSignin,
    verifier: SupabaseAuthUserVerifier,
    storage: SignedOriginalsStorage,
) -> None:
    sessions = tuple(signin.sign_in(x) for x in credentials)
    subjects = tuple(verifier.verify_bearer(s.access_token) for s in sessions)
    if len(subjects) != 3 or len({s.subject_id for s in subjects}) != 3:
        raise AssertionError("three verified distinct signed users required")
    if any(
        subject.subject_id != session.user_id
        or subject.issuer != ISSUER or subject.audience != "authenticated"
        for session, subject in zip(sessions, subjects, strict=True)
    ):
        raise AssertionError("Auth issuer/subject mismatch")
    data = b"CASEPROOF_DEV_STORAGE_DENY_FIXTURE_NO_CASE"
    ref = OriginalRef(
        uuid4(), uuid4(), uuid4(), uuid4(),
        hashlib.sha256(data).hexdigest(), "text/plain",
    )
    for session in sessions:
        try:
            storage.put_once(ref, session.access_token, data)
        except PrivateStorageDenied:
            pass
        else:
            raise AssertionError("ungranted user could upload private original")
        try:
            storage.get_verified(ref, session.access_token)
        except PrivateStorageDenied:
            pass
        else:
            raise AssertionError("ungranted user could download private original")
    print("LIVE_SIGNED_SUPABASE_STORAGE_NO_GRANT_UPLOAD_DENIED")
    print("MISSING_OBJECT_DOWNLOAD_DENIED_NOT_EXISTING_OBJECT_RLS_PROOF")


def main() -> int:
    try:
        if (
            os.getenv("CASEPROOF_DEV_LIVE_STORAGE_PROBE") != "YES"
            or os.getenv("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or os.getenv("GITHUB_REPOSITORY") != "haytamAroui/caseproof"
            or os.getenv("GITHUB_REF") != "refs/heads/main"
        ):
            raise RuntimeError("protected manual main-only Storage probe")
        key = os.environ.get("CASEPROOF_DEV_PUBLISHABLE_KEY", "")
        admin_key = os.environ.get("CASEPROOF_DEV_AUTH_ADMIN_KEY", "")
        storage = SignedOriginalsStorage(key)
        signin = SupabasePasswordSignin(PROJECT_REF, key)
        verifier = SupabaseAuthUserVerifier(
            PROJECT_REF, HttpsSupabaseUserLookup(PROJECT_REF, key),
        )
        admin = GoTrueDevAdmin(admin_key)
        ephemeral_private_probe(
            admin=admin,
            probe=lambda credentials: verify_signed_denial(
                credentials, signin=signin, verifier=verifier, storage=storage,
            ),
        )
        print("LIVE_STORAGE_AUTH_TEST_USERS_CLEANED")
        print("POSITIVE_SAME_MATTER_STORAGE_UPLOAD_NOT_YET_VERIFIED")
        return 0
    except Exception as exc:
        # Never include provider response, bearer, email, UUID, object name.
        print(f"LIVE_STORAGE_AUTH_PROBE_FAILED: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
