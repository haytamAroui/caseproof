"""M1-B bearer-to-actual-RLS reader: disposable and real Auth integration.

Normal CI uses a synthetic verifier and a NON-BYPASSRLS login in localhost
PostgreSQL. The manual protected workflow invokes run_ephemeral_signed_probe()
with 3 genuinely signed, separately verified CaseProof-dev GoTrue sessions.
Both modes test the SAME actual DB reader and per-matter RLS predicates.
No real Supabase database migration, case rows or Storage writes are made.
"""
from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

import psycopg

from apps.api.access_control import (
    AccessFailure, AccessRejected, InvalidBearer, VerifiedSubject,
)
from apps.api.signed_private_matter_reader import SignedPrivateMatterReader
from scripts.verify_m1_private_rls import seed
from scripts.verify_s2_002_database import _env, _run
from scripts.verify_vault_integration import connect

ROLE = "caseproof_m1_reader"
PASS = "disposable_localhost_not_an_auth_or_db_secret"
ISSUER = "https://ldwmocpxwskvhoojndrd.supabase.co/auth/v1"


class Verifier(Protocol):
    def verify_bearer(self, token: str) -> VerifiedSubject: ...


class SyntheticVerifier:
    """Local fixture ONLY: never supplies proof of real signed Auth."""

    def __init__(self, subjects: dict[str, str]) -> None:
        self._subjects = subjects

    def verify_bearer(self, token: str) -> VerifiedSubject:
        if token not in self._subjects:
            raise InvalidBearer("invalid local-only fixture")
        now = datetime.now(UTC)
        return VerifiedSubject(
            self._subjects[token], ISSUER, "authenticated",
            now - timedelta(seconds=1), now + timedelta(minutes=10), False,
        )


def _only_local() -> dict[str, str]:
    env = _env()
    # libpq env variables may override the host/credentials!
    if (env.get("PGHOST") != "127.0.0.1"
            or env.get("PGPORT") != "5432"
            or env.get("PGPASSWORD") != "caseproof_ephemeral_ci"
            or "PGHOSTADDR" in env or "PGSERVICE" in env
            or "PGOPTIONS" in env):
        raise RuntimeError("only pinned localhost ephemeral PostgreSQL accepted")
    return env


def _bootstrap_reader_role() -> None:
    env = _only_local()
    _run(
        "do $$ begin if not exists (select 1 from pg_roles where rolname='"
        + ROLE +
        "') then create role " + ROLE + " login password '" + PASS + "'; "
        "end if; end $$; grant authenticated to " + ROLE + ";",
        env,
    )
    props = _run(
        "select (not rolsuper and not rolbypassrls and rolcanlogin)::text "
        "from pg_roles where rolname='" + ROLE + "'", env,
    )
    if props != "true":
        raise RuntimeError("disposable reader role is unexpectedly privileged")


def reader_connection() -> psycopg.Connection[object]:
    _only_local()
    return psycopg.connect(
        host="127.0.0.1", port=5432, dbname="caseproof_s2_ci",
        user=ROLE, password=PASS, sslmode="disable", connect_timeout=5,
        autocommit=False,
    )


def _must_mask(operation: object, code: AccessFailure) -> None:
    try:
        if not callable(operation):
            raise AssertionError("fixture requires callable")
        operation()
    except AccessRejected as exc:
        if exc.code != code:
            raise AssertionError("unexpected private access failure category") from None
    else:
        raise AssertionError("unauthorized case or original was visible")


def verify_three_subjects(
    *, tokens: tuple[str, str, str], subjects: tuple[str, str, str],
    verifier: Verifier,
) -> None:
    """Positive and adversarial live SQL-role queries for one verified trio."""
    _bootstrap_reader_role()
    try:
        actor_ids = tuple(UUID(x) for x in subjects)
    except ValueError:
        raise AssertionError("noncanonical verified subject unavailable") from None
    if len(set(actor_ids)) != 3 or any(x.int == 0 for x in actor_ids):
        raise AssertionError("three distinct signed identities required")
    a = seed(actor_id=actor_ids[0])
    b = seed(org=a.org, actor_id=actor_ids[1])
    c = seed(actor_id=actor_ids[2])
    reader = SignedPrivateMatterReader(
        verifier=verifier, connection_factory=reader_connection, issuer=ISSUER,
    )

    for bearer, fixture in zip(tokens, (a, b, c), strict=True):
        own = reader.read_case(bearer=bearer, case_id=str(fixture.case))
        if (own.case_id != str(fixture.case)
                or own.org_id != str(fixture.org) or own.case_revision < 1):
            raise AssertionError("signed subject read was not bound to its case")
        version = reader.read_version(
            bearer=bearer, case_id=str(fixture.case),
            document_id=str(fixture.document), version_id=str(fixture.version),
        )
        if (version.version_id != str(fixture.version)
                or version.sha256_hex != "a" * 64):
            raise AssertionError("signed evidence version mismatch")

    # A and B are SAME organization, DIFFERENT private matters. C is foreign.
    for bearer, foreign in (
        (tokens[0], b), (tokens[1], a), (tokens[2], a), (tokens[0], c),
    ):
        _must_mask(
            lambda bearer=bearer, foreign=foreign: reader.read_case(
                bearer=bearer, case_id=str(foreign.case),
            ),
            AccessFailure.RESOURCE_MASKED,
        )
        _must_mask(
            lambda bearer=bearer, foreign=foreign: reader.read_version(
                bearer=bearer, case_id=str(foreign.case),
                document_id=str(foreign.document), version_id=str(foreign.version),
            ),
            AccessFailure.RESOURCE_MASKED,
        )

    # Missing/altered bearer is never translated into a database claim.
    _must_mask(
        lambda: reader.read_case(bearer="invalid-signed-session", case_id=str(a.case)),
        AccessFailure.AUTHENTICATION_REQUIRED,
    )
    _must_mask(
        lambda: reader.read_case(bearer=tokens[0], case_id="not-a-uuid"),
        AccessFailure.RESOURCE_MASKED,
    )

    # Enforce the app read role, even if a caller accidentally injects a
    # postgres owner/superuser connection.
    unsafe = SignedPrivateMatterReader(
        verifier=verifier, connection_factory=connect, issuer=ISSUER,
    )
    _must_mask(
        lambda: unsafe.read_case(bearer=tokens[0], case_id=str(a.case)),
        AccessFailure.SERVICE_UNAVAILABLE,
    )

    # Effective RLS subject is SET LOCAL and disappears at COMMIT even
    # when the very same physical DB connection gets a second transaction.
    with reader_connection() as conn:
        conn.execute(
            "select set_config('request.jwt.claim.sub',%s,true)",
            (str(a.actor),),
        )
        if conn.execute("select auth.uid()::text").fetchone()[0] != str(a.actor):
            raise AssertionError("RLS test connection cannot bind subject")
        conn.commit()
        if conn.execute("select auth.uid()::text").fetchone()[0] is not None:
            raise AssertionError("claim leaked to a fresh transaction")
        conn.rollback()

    # Live current membership AND active matter grants must be re-read;
    # deny different actions independently of case access.
    with connect() as conn:
        conn.execute(
            "update caseproof.organization_members "
            "set actions=array['case:read']::text[] "
            "where org_id=%s and user_id=%s", (a.org, a.actor),
        )
    reader.read_case(bearer=tokens[0], case_id=str(a.case))
    _must_mask(
        lambda: reader.read_version(
            bearer=tokens[0], case_id=str(a.case),
            document_id=str(a.document), version_id=str(a.version),
        ),
        AccessFailure.RESOURCE_MASKED,
    )

    with connect() as conn:
        conn.execute(
            "update caseproof._m1_matter_grants "
            "set active=false,revision=revision+1 "
            "where org_id=%s and case_id=%s and user_id=%s",
            (b.org, b.case, b.actor),
        )
        conn.execute(
            "update caseproof.organization_members "
            "set active=false,membership_revision=membership_revision+1 "
            "where org_id=%s and user_id=%s", (c.org, c.actor),
        )
    for bearer, fx in ((tokens[1], b), (tokens[2], c)):
        _must_mask(
            lambda bearer=bearer, fx=fx: reader.read_case(
                bearer=bearer, case_id=str(fx.case),
            ), AccessFailure.RESOURCE_MASKED,
        )
    reader.read_case(bearer=tokens[0], case_id=str(a.case))


def run_synthetic() -> None:
    """CI acceptance WITHOUT claims about remote Auth or cloud database."""
    # Fresh IDs avoid collisions with preexisting disposable foundation
    # Auth fixtures; never reuse the foundation's canonical three users.
    ids = tuple(str(uuid4()) for _ in range(3))
    tokens = ("fixture-one", "fixture-two", "fixture-three")
    verify_three_subjects(
        tokens=tokens, subjects=ids,
        verifier=SyntheticVerifier(dict(zip(tokens, ids, strict=True))),
    )
    print("M1_SIGNED_READER_LOCAL_RLS_BOUNDARY_AND_REVOKE_PASSED")
    print("SYNTHETIC_VERIFIER_ONLY: no Supabase signed-user acceptance")


def main() -> int:
    try:
        if os.getenv("CASEPROOF_M1_LOCAL_ROLE_TEST") != "YES":
            print("Only explicit disposable local role verification allowed", file=sys.stderr)
            return 2
        run_synthetic()
        return 0
    except Exception as exc:
        print(f"M1_SIGNED_PRIVATE_READER_FAILED: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
