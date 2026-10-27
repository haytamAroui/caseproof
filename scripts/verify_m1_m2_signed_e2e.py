"""Protected ONE-CLICK M1 -> M2 signed-user acceptance on isolated Postgres.

Genuine remote CaseProof-dev Auth users are verified through Supabase /user.
The database/Vault/M2 graph remain the DISPOSABLE PostgreSQL/filesystem
fixtures installed by the protected GitHub workflow. No live M2 schema,
real Supabase Storage or customers are modified. Synthetic fixture SQL users
exist ONLY inside the ephemeral local CI database.
"""
from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from uuid import UUID, uuid4

from application.litigation.unified_review import ObservationReview, ReviewDisposition
from apps.api.access_control import AccessFailure, AccessRejected, InvalidBearer
from apps.api.litigation_check_service import AuthorizedLitigationChecker
from apps.api.live_auth_probe import _tamper_signature
from apps.api.supabase_auth_verifier import HttpsSupabaseUserLookup, SupabaseAuthUserVerifier
from apps.api.supabase_password_signin import PasswordCredentials, SupabasePasswordSignin
from scripts.verify_dev_ephemeral_auth import ISSUER, PROJECT_REF, GoTrueDevAdmin
from scripts.verify_m1_ephemeral_signed_private import ephemeral_private_probe
from scripts.verify_m1_signed_private_reader import _only_local, verify_three_subjects
from scripts.verify_m2_private_check_composition import M2CheckCompositionTests
from scripts.verify_vault_integration import connect


def _must_deny(action: object, *, expected: tuple[AccessFailure, ...]) -> None:
    if not callable(action):
        raise AssertionError("callable private operation required")
    try:
        action()
    except AccessRejected as error:
        if error.code not in expected:
            raise AssertionError("unexpected access failure category") from None
    else:
        raise AssertionError("unauthorized signed user could access private M2 case")


def run_signed_m1_m2(
    credentials: tuple[PasswordCredentials, ...],
    *,
    signin: SupabasePasswordSignin,
    verifier: SupabaseAuthUserVerifier,
    synthetic_only: bool = False,
) -> None:
    """One checked A/B/C trio drives M1 private RLS and persisted M2."""
    if len(credentials) != 3:
        raise AssertionError("three signed users required")
    sessions = tuple(signin.sign_in(c) for c in credentials)
    identities = tuple(verifier.verify_bearer(s.access_token) for s in sessions)
    subjects = tuple(i.subject_id for i in identities)
    tokens = tuple(s.access_token for s in sessions)
    if (
        len(set(subjects)) != 3
        or any(
            s.user_id != actor.subject_id
            or actor.issuer != ISSUER
            or actor.audience != "authenticated"
            or actor.human_authenticated
            for s, actor in zip(sessions, identities, strict=True)
        )
    ):
        raise AssertionError("remote signed-user trust mismatch")
    try:
        verifier.verify_bearer(_tamper_signature(tokens[0]))
    except InvalidBearer:
        pass
    else:
        raise AssertionError("remote Auth accepted tampered bearer")

    # Actual local non-BYPASSRLS login, exact-case matter grants, own version,
    # same-org ungranted case, foreign-org case and permission revocation.
    verify_three_subjects(tokens=tokens, subjects=subjects, verifier=verifier)
    print("PASS 1/5: " + ("three synthetic local sessions" if synthetic_only else
                           "three real Supabase Auth sessions") + " + private M1 RLS")

    # Reuse the real original-byte Vault, versioned brief, confirmation and
    # deterministic M2 fixture, then ADD the verified signed subjects as
    # explicit private actors. The client does NOT choose actor_id.
    case = M2CheckCompositionTests("test_full_private_graph_to_exhibit_vault_to_check_to_ledger")
    try:
        case.setUp()
        a, b = (UUID(x) for x in subjects[:2])
        with connect() as conn:
            for subject in (a, b):
                conn.execute(
                    "insert into caseproof.organization_members "
                    "(org_id,user_id,actions) values(%s,%s,%s)",
                    (
                        case.f.scope.org_id, subject,
                        ["case:read", "evidence:read", "finding:write", "review:request"],
                    ),
                )
            conn.execute(
                "insert into caseproof._m1_matter_grants "
                "(org_id,case_id,user_id,role,permissions) "
                "values(%s,%s,%s,'reviewer',%s)",
                (
                    case.f.scope.org_id, case.f.scope.case_id, a,
                    ["case:read", "evidence:read", "draft:check", "review:request"],
                ),
            )

        service = AuthorizedLitigationChecker(
            verifier=verifier, store=case.store, publisher=case.ledger,
            issuer=ISSUER, audience="authenticated",
            clock=lambda: datetime.now(UTC),
        )
        params = {
            "case_id": str(case.f.scope.case_id),
            "brief_version_id": str(case.brief_version),
        }
        run = service.check(bearer=tokens[0], **params)
        if (
            run.case_id != params["case_id"]
            or run.brief_version_id != params["brief_version_id"]
            or len(run.declared) != 1
            or run.declared != run.processed
            or run.incomplete
            or len(run.factual_observations) != 1
        ):
            raise AssertionError("private source-bound M2 run not complete")
        with connect() as conn:
            stored = conn.execute(
                "select count(*) from caseproof._m2_check_runs "
                "where org_id=%s and case_id=%s and snapshot_sha=%s",
                (case.f.scope.org_id, case.f.scope.case_id, run.snapshot_hash),
            ).fetchone()[0]
        if stored != 1:
            raise AssertionError("signed-user M2 check not durable")
        print("PASS 2/5: signed private Vault original -> pinned brief -> persisted check")

        for denied in (tokens[1], tokens[2]):
            _must_deny(
                lambda bearer=denied: service.check(bearer=bearer, **params),
                expected=(AccessFailure.RESOURCE_MASKED, AccessFailure.PERMISSION_DENIED),
            )
        _must_deny(
            lambda: service.check(bearer=_tamper_signature(tokens[0]), **params),
            expected=(AccessFailure.AUTHENTICATION_REQUIRED,),
        )
        print("PASS 3/5: same-org, foreign-org and forged signed session denied")

        decision = ObservationReview(
            "fact:money-1", subjects[0], ReviewDisposition.NEEDS_INFORMATION,
            "Synthetic verified private-source review; not legal approval",
        )
        state, replay = case.ledger.record(
            org_id=case.f.scope.org_id, actor_id=a, run=run,
            request_id=uuid4(), expected_revision=0, decision=decision,
        )
        if replay or state.revision != 1:
            raise AssertionError("signed-reviewer decision not durable")
        recovered = case.ledger.state(
            org_id=case.f.scope.org_id, actor_id=a, run=run,
        )
        if recovered.revision != 1 or recovered.packet != state.packet:
            raise AssertionError("M2 review was not safely reopened")
        print("PASS 4/5: signed reviewer disposition, audit and durable reopen")

        with connect() as conn:
            conn.execute(
                "update caseproof._m1_matter_grants "
                "set active=false,revision=revision+1 "
                "where org_id=%s and case_id=%s and user_id=%s",
                (case.f.scope.org_id, case.f.scope.case_id, a),
            )
        _must_deny(
            lambda: service.check(bearer=tokens[0], **params),
            expected=(AccessFailure.RESOURCE_MASKED, AccessFailure.PERMISSION_DENIED),
        )
        print("PASS 5/5: revoked private grant denies next signed check")
    finally:
        case.doCleanups()


def main() -> int:
    try:
        if (
            os.environ.get("CASEPROOF_M1M2_E2E") != "YES"
            or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or os.environ.get("GITHUB_REPOSITORY") != "haytamAroui/caseproof"
        ):
            raise RuntimeError("protected manual main-only workflow required")
        _only_local()  # Refuse any remote Postgres BEFORE Auth admin use.
        key = os.environ.get("CASEPROOF_DEV_PUBLISHABLE_KEY", "")
        admin_key = os.environ.get("CASEPROOF_DEV_AUTH_ADMIN_KEY", "")
        signin = SupabasePasswordSignin(PROJECT_REF, key)
        verifier = SupabaseAuthUserVerifier(
            PROJECT_REF, HttpsSupabaseUserLookup(PROJECT_REF, key),
        )
        admin = GoTrueDevAdmin(admin_key)
        ephemeral_private_probe(
            admin=admin,
            probe=lambda credentials: run_signed_m1_m2(
                credentials, signin=signin, verifier=verifier,
            ),
        )
        print("M1_M2_SIGNED_LOCAL_E2E_PASSED; temporary Auth users deleted")
        print("LIVE_M2_DB_STORAGE_NOT_TESTED; NOT_CUSTOMER_RELEASE")
        return 0
    except Exception as exc:
        # Never echo provider payloads, credentials, UUIDs, customer data or JWTs.
        print(f"M1_M2_SIGNED_E2E_FAILED: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
