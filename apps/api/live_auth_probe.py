"""S2-006: run real signed Auth session checks, without persisting tokens.

No Supabase user provisioning, local signing key, case write or HTTP endpoint.
The supplied Signin must issue actual project sessions when run in dev;
synthetic Signin is permitted ONLY in isolated unit tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from apps.api.access_control import InvalidBearer, VerifiedSubject
from apps.api.supabase_password_signin import (
    AuthAccessToken,
    PasswordCredentials,
    PasswordSignin,
)


class SessionVerifier(Protocol):
    def verify_bearer(self, token: str) -> VerifiedSubject: ...


@dataclass(frozen=True, slots=True)
class SessionProbeResult:
    """Non-sensitive verification receipts only (no bearer or email)."""

    project_issuer: str
    user_a_id: str
    user_b_id: str
    signed_session_a_verified: bool
    signed_session_b_verified: bool
    altered_signature_rejected: bool


def _tamper_signature(token: str) -> str:
    parts = token.split(".")
    if len(parts) != 3 or len(parts[2]) < 2:
        raise ValueError("Cannot test malformed signed JWT")
    # Change the FIRST base64url character of the signature to guarantee
    # altered decoded bytes; modifying final character can change padding
    # bits without changing the signature.
    parts[2] = ("A" if parts[2][0] != "A" else "B") + parts[2][1:]
    return ".".join(parts)


def run_live_auth_probe(
    signin: PasswordSignin,
    verifier: SessionVerifier,
    user_a: PasswordCredentials,
    user_b: PasswordCredentials,
    expected_issuer: str,
) -> SessionProbeResult:
    """Obtain and remotely verify two real sessions, then test signature tamper.

    The caller must supply production-compatible Supabase Auth transport and
    REAL, project-issued, separate development user credentials. In-memory
    doubles cannot establish authenticity; tests of this function only
    establish orchestration behavior.
    """
    sessions: list[AuthAccessToken] = [signin.sign_in(user_a), signin.sign_in(user_b)]
    subjects = [verifier.verify_bearer(s.access_token) for s in sessions]
    for session, subject in zip(sessions, subjects, strict=True):
        if subject.subject_id != session.user_id or subject.issuer != expected_issuer:
            raise AssertionError("Project Auth session identity does not match verification")
        if subject.human_authenticated:
            raise AssertionError("Password login cannot by itself authorize human review")
    if subjects[0].subject_id == subjects[1].subject_id:
        raise AssertionError("Two separate development Auth accounts required")

    tampered = _tamper_signature(sessions[0].access_token)
    try:
        verifier.verify_bearer(tampered)
    except InvalidBearer:
        pass
    else:
        raise AssertionError("Project Auth accepted a modified JWT signature")

    return SessionProbeResult(
        project_issuer=expected_issuer,
        user_a_id=subjects[0].subject_id,
        user_b_id=subjects[1].subject_id,
        signed_session_a_verified=True,
        signed_session_b_verified=True,
        altered_signature_rejected=True,
    )
