"""Opt-in REAL CaseProof-dev Supabase Auth -> actual remote PostgreSQL RLS test.

NOT a production grant issuance path, migration runner, release certificate, or
customer data route. Enabled only in a protected, main-only GitHub environment.
Uses randomly generated temporary identities, matter rows, and an ephemeral
non-BYPASSRLS login. All credentials stay inside the runner's process memory.
Never print provider responses, SQL, user IDs, passwords or bearer tokens.
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.live_auth_probe import _tamper_signature
from apps.api.signed_private_matter_reader import APP_DB_ROLE, SignedPrivateMatterReader
from apps.api.supabase_auth_verifier import HttpsSupabaseUserLookup, SupabaseAuthUserVerifier
from apps.api.supabase_password_signin import PasswordCredentials, SupabasePasswordSignin
from scripts.verify_dev_ephemeral_auth import ISSUER, PROJECT_REF, GoTrueDevAdmin

TEST_FLAG = "CASEPROOF_M1_LIVE_PRIVATE_DB_ACCEPTANCE"
ADMIN_DSN = "CASEPROOF_DEV_DB_ADMIN_DSN"
CA_CERT = "CASEPROOF_DEV_DB_CA_PEM"
PREFIX = "caseproof-ci-"
EXPECTED_MIGRATION = "20261027160745"


@dataclass(frozen=True)
class Fixture:
    org: UUID
    actor: UUID
    matter: UUID
    document: UUID
    version: UUID
    digest: str


def require_protected_execution(env: dict[str, str]) -> None:
    if not (
        env.get(TEST_FLAG) == "YES"
        and env.get("GITHUB_REPOSITORY") == "haytamAroui/caseproof"
        and env.get("GITHUB_REF") == "refs/heads/main"
        and env.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
        and env.get("CASEPROOF_M1_LIVE_DB_APPROVED") == "YES"
    ):
        raise RuntimeError("protected main-only explicit live-db approval required")


def validated_admin_dsn(raw: str) -> tuple[str, str]:
    """Bind the test to one project's admin connection in direct/session mode.

    No transaction pooler, libpq service file, startup SQL options, hostaddr
    override or alternate project. Caller supplies a secret DSN, never a URL
    assembled from user-controlled data.
    """
    if not raw:
        raise RuntimeError("protected dev DB connection unavailable")
    try:
        args = conninfo_to_dict(raw)
    except (ValueError, psycopg.ProgrammingError):
        raise RuntimeError("invalid protected dev DB connection") from None
    if set(args) - {"host", "port", "dbname", "user", "password", "sslmode"}:
        raise RuntimeError("unexpected libpq connection options")
    host = args.get("host", "")
    direct = host == f"db.{PROJECT_REF}.supabase.co"
    pool = bool(re.fullmatch(r"aws-[0-9]+-eu-central-1\.pooler\.supabase\.com", host))
    if not (direct or pool):
        raise RuntimeError("not the pinned CaseProof dev DB hostname")
    if (
        args.get("port") != "5432"
        or args.get("dbname") != "postgres"
        or args.get("user") != ("postgres" if direct else f"postgres.{PROJECT_REF}")
        or not args.get("password")
        or args.get("sslmode") not in (None, "verify-full")
    ):
        raise RuntimeError("dev DB must use verified-TLS direct or session-mode admin")
    return raw, "direct" if direct else "pool"


def _connect(dsn: str, root: str) -> psycopg.Connection[object]:
    return psycopg.connect(
        dsn, sslmode="verify-full", sslrootcert=root,
        connect_timeout=12, autocommit=False,
    )


def _live_preflight(conn: psycopg.Connection[object]) -> None:
    role = conn.execute(
        "select current_user, "
        "(select rolbypassrls from pg_roles where rolname=current_user)"
    ).fetchone()
    if role != ("postgres", True):
        raise RuntimeError("unexpected non-admin fixture setup role")
    versions = conn.execute(
        "select version from supabase_migrations.schema_migrations "
        "where version=%s", (EXPECTED_MIGRATION,)
    ).fetchall()
    if len(versions) != 1:
        raise RuntimeError("exact installed M1 dev migration not found")
    legacy = conn.execute(
        "select count(*) from pg_policies where schemaname='caseproof' "
        "and policyname in ('tenant_case_read',"
        "'tenant_document_read','tenant_document_version_read')"
    ).fetchone()
    expected_policies = conn.execute(
        "select count(*) from pg_policies where schemaname='caseproof' "
        "and (tablename,policyname) in ("
        "('cases','m1_private_case_read'),"
        "('documents','m1_private_document_read'),"
        "('document_versions','m1_private_document_version_read'),"
        "('_m1_matter_grants','m1_own_private_grant_read'))"
    ).fetchone()
    if legacy != (0,) or expected_policies != (4,):
        raise RuntimeError("private-matter policy fingerprint changed")
    rogue = conn.execute(
        "select count(*) from pg_policies where schemaname='caseproof' "
        "and tablename in ('cases','documents','document_versions',"
        "'_m1_matter_grants') and cmd in ('ALL','SELECT') "
        "and policyname not in ('m1_private_case_read',"
        "'m1_private_document_read','m1_private_document_version_read',"
        "'m1_own_private_grant_read')"
    ).fetchone()
    if rogue != (0,):
        raise RuntimeError("unreviewed overlapping RLS policy")
    rows = conn.execute(
        "select (select count(*) from auth.users), "
        "(select count(*) from caseproof.organizations), "
        "(select count(*) from caseproof.organization_members), "
        "(select count(*) from caseproof.cases), "
        "(select count(*) from caseproof._m1_matter_grants)"
    ).fetchone()
    # Test deliberately refuses to modify any project holding user/customer data.
    if rows != (0, 0, 0, 0, 0):
        raise RuntimeError("dev DB no longer empty: live fixture refused")
    existing_role = conn.execute(
        "select 1 from pg_roles where rolname=%s", (APP_DB_ROLE,)
    ).fetchone()
    if existing_role:
        raise RuntimeError("runtime role already exists: test will not alter it")
    conn.rollback()


def _create_ephemeral_login(conn: psycopg.Connection[object], password: str) -> None:
    if len(password) < 40:
        raise RuntimeError("invalid ephemeral login credential")
    conn.execute(
        sql.SQL("create role {} with login inherit nocreatedb nocreaterole "
                "noreplication nobypassrls connection limit 4 password {}").format(
            sql.Identifier(APP_DB_ROLE), sql.Literal(password),
        )
    )
    conn.execute(
        sql.SQL("grant authenticated to {}").format(sql.Identifier(APP_DB_ROLE))
    )
    conn.commit()


def _drop_ephemeral_login(conn: psycopg.Connection[object]) -> None:
    conn.execute(
        sql.SQL("drop role if exists {}").format(sql.Identifier(APP_DB_ROLE))
    )
    conn.commit()


def _assert_ephemeral_role(conn: psycopg.Connection[object]) -> None:
    """Enforce read-only current role, inherited roles and installed RLS."""
    observed = conn.execute(
        "select current_user,session_user,"
        "(select rolsuper or rolbypassrls from pg_roles where rolname=current_user),"
        "pg_has_role(current_user,'authenticated','MEMBER'),"
        "exists(select 1 from pg_roles r where (r.rolsuper or r.rolbypassrls)"
        " and pg_has_role(current_user,r.oid,'MEMBER')),"
        "(select count(*) from pg_class c join pg_namespace n "
        "on n.oid=c.relnamespace where n.nspname='caseproof' "
        "and c.relname in ('cases','documents','document_versions',"
        "'_m1_matter_grants','organization_members') and c.relrowsecurity),"
        "exists(select 1 from pg_class c join pg_namespace n "
        "on n.oid=c.relnamespace where n.nspname='caseproof' "
        "and c.relname in ('cases','documents','document_versions',"
        "'_m1_matter_grants','organization_members') and "
        "(pg_has_role(current_user,c.relowner,'MEMBER') or "
        "has_table_privilege(current_user,c.oid,'INSERT,UPDATE,DELETE,"
        "TRUNCATE,TRIGGER,REFERENCES')))"
    ).fetchone()
    if observed != (APP_DB_ROLE, APP_DB_ROLE, False, True, False, 5, False):
        raise RuntimeError("ephemeral DB login has unexpected RLS/role authority")
    conn.rollback()


def _seed_fixtures(
    conn: psycopg.Connection[object], actors: tuple[UUID, UUID, UUID],
) -> tuple[Fixture, Fixture, Fixture]:
    first, foreign = uuid4(), uuid4()
    fixtures: list[Fixture] = []
    try:
        for index, actor in enumerate(actors):
            org = first if index < 2 else foreign
            if index != 1:
                conn.execute(
                    "insert into caseproof.organizations (id,display_name) "
                    "values (%s,%s)",
                    (org, f"CaseProof TEST ONLY {org}"),
                )
            matter, document, version = uuid4(), uuid4(), uuid4()
            digest = hashlib.sha256(f"synthetic-only-{version}".encode()).hexdigest()
            conn.execute(
                "insert into caseproof.organization_members "
                "(org_id,user_id,actions) values(%s,%s,%s)",
                (org, actor, ["case:read", "evidence:read"]),
            )
            conn.execute(
                "insert into caseproof.cases "
                "(id,org_id,created_by_user,effective_policy_version) "
                "values(%s,%s,%s,'live-m1-dev-test-only')",
                (matter, org, actor),
            )
            conn.execute(
                "insert into caseproof.documents "
                "(id,org_id,case_id,source_label) values(%s,%s,%s,%s)",
                (document, org, matter, "Synthetic test source only"),
            )
            conn.execute(
                "insert into caseproof.document_versions "
                "(id,org_id,document_id,version_number,original_sha256_hex,"
                "byte_length,media_type) values(%s,%s,%s,1,%s,0,'text/plain')",
                (version, org, document, digest),
            )
            conn.execute(
                "insert into caseproof._m1_matter_grants "
                "(org_id,case_id,user_id,role,permissions) "
                "values(%s,%s,%s,'reviewer',%s)",
                (org, matter, actor, ["case:read", "evidence:read"]),
            )
            _audit(conn, org, matter, "dev_test_grant_seeded")
            fixtures.append(Fixture(org, actor, matter, document, version, digest))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return fixtures[0], fixtures[1], fixtures[2]


def _audit(conn: psycopg.Connection[object], org: UUID, matter: UUID, action: str) -> None:
    conn.execute(
        "insert into caseproof.audit_events "
        "(org_id,case_id,actor_type,action,event_schema_version,"
        "correlation_id,input_sha256_hex) "
        "values(%s,%s,'service',%s,'dev-test-v1',%s,%s)",
        (org, matter, action, uuid4(), hashlib.sha256(action.encode()).hexdigest()),
    )


def _remove_fixtures(
    conn: psycopg.Connection[object], fixtures: tuple[Fixture, Fixture, Fixture],
) -> None:
    # No CASCADE, table truncate, broad org delete or deletion of other users.
    # Preflight required an empty database; delete only in-memory created UUIDs.
    cases = [f.matter for f in fixtures]
    versions = [f.version for f in fixtures]
    documents = [f.document for f in fixtures]
    orgs = list({f.org for f in fixtures})
    conn.execute("delete from caseproof.audit_events where case_id=any(%s)", (cases,))
    conn.execute("delete from caseproof.document_versions where id=any(%s)", (versions,))
    conn.execute("delete from caseproof.documents where id=any(%s)", (documents,))
    conn.execute("delete from caseproof._m1_matter_grants where case_id=any(%s)", (cases,))
    conn.execute("delete from caseproof.cases where id=any(%s)", (cases,))
    for f in fixtures:
        conn.execute(
            "delete from caseproof.organization_members "
            "where org_id=%s and user_id=%s", (f.org, f.actor),
        )
    conn.execute(
        "delete from caseproof.organizations where id=any(%s)", (orgs,)
    )
    conn.commit()


def _denied(run: Callable[[], object], code: AccessFailure) -> None:
    try:
        run()
    except AccessRejected as exc:
        if exc.code != code:
            raise AssertionError("unexpected access rejection category") from None
    else:
        raise AssertionError("private matter unexpectedly accessible")


def _check_access(
    *, tokens: tuple[str, str, str], fixtures: tuple[Fixture, Fixture, Fixture],
    verifier: SupabaseAuthUserVerifier,
    connect_reader: Callable[[], psycopg.Connection[object]],
    connect_admin: Callable[[], psycopg.Connection[object]],
) -> None:
    reader = SignedPrivateMatterReader(
        verifier=verifier, connection_factory=connect_reader, issuer=ISSUER,
    )
    for token, f in zip(tokens, fixtures, strict=True):
        case = reader.read_case(bearer=token, case_id=str(f.matter))
        version = reader.read_version(
            bearer=token, case_id=str(f.matter), document_id=str(f.document),
            version_id=str(f.version),
        )
        if case.case_id != str(f.matter) or version.sha256_hex != f.digest:
            raise AssertionError("allowed case/version read mismatch")
    for token, foreign in (
        (tokens[0], fixtures[1]),
        (tokens[1], fixtures[0]),
        (tokens[2], fixtures[0]),
        (tokens[0], fixtures[2]),
    ):
        _denied(
            lambda t=token, f=foreign: reader.read_case(bearer=t, case_id=str(f.matter)),
            AccessFailure.RESOURCE_MASKED,
        )
        _denied(
            lambda t=token, f=foreign: reader.read_version(
                bearer=t, case_id=str(f.matter), document_id=str(f.document),
                version_id=str(f.version),
            ),
            AccessFailure.RESOURCE_MASKED,
        )
    _denied(
        lambda: reader.read_case(
            bearer=_tamper_signature(tokens[0]), case_id=str(fixtures[0].matter),
        ),
        AccessFailure.AUTHENTICATION_REQUIRED,
    )
    _denied(
        lambda: reader.read_case(bearer="", case_id=str(fixtures[0].matter)),
        AccessFailure.AUTHENTICATION_REQUIRED,
    )

    # Fail if a pooled physical connection retains another verified actor.
    with connect_reader() as conn:
        conn.execute(
            "select set_config('request.jwt.claim.sub',%s,true)",
            (str(fixtures[0].actor),),
        )
        if conn.execute("select auth.uid()::text").fetchone() != (
            str(fixtures[0].actor),
        ):
            raise AssertionError("cannot bind verified actor to RLS")
        conn.commit()
        if conn.execute("select auth.uid()::text").fetchone() != (None,):
            raise AssertionError("transaction-local claim leaked")
        conn.rollback()

    with connect_admin() as conn:
        f = fixtures[0]
        conn.execute(
            "update caseproof.organization_members "
            "set actions=array['case:read']::text[], "
            "membership_revision=membership_revision+1 "
            "where org_id=%s and user_id=%s", (f.org, f.actor),
        )
        _audit(conn, f.org, f.matter, "dev_test_org_evidence_revoked")
        conn.commit()
    reader.read_case(bearer=tokens[0], case_id=str(fixtures[0].matter))
    _denied(
        lambda: reader.read_version(
            bearer=tokens[0], case_id=str(fixtures[0].matter),
            document_id=str(fixtures[0].document),
            version_id=str(fixtures[0].version),
        ),
        AccessFailure.RESOURCE_MASKED,
    )
    with connect_admin() as conn:
        for f, table, where, audit_action in (
            (fixtures[1], "caseproof._m1_matter_grants",
             "org_id=%s and case_id=%s and user_id=%s", "dev_test_grant_revoked"),
            (fixtures[2], "caseproof.organization_members",
             "org_id=%s and user_id=%s", "dev_test_membership_revoked"),
        ):
            if table.endswith("_m1_matter_grants"):
                conn.execute(
                    "update caseproof._m1_matter_grants "
                    "set active=false,revision=revision+1 where " + where,
                    (f.org, f.matter, f.actor),
                )
            else:
                conn.execute(
                    "update caseproof.organization_members "
                    "set active=false,membership_revision=membership_revision+1 "
                    "where " + where,
                    (f.org, f.actor),
                )
            _audit(conn, f.org, f.matter, audit_action)
        conn.commit()
    for token, f in ((tokens[1], fixtures[1]), (tokens[2], fixtures[2])):
        _denied(
            lambda t=token, x=f: reader.read_case(bearer=t, case_id=str(x.matter)),
            AccessFailure.RESOURCE_MASKED,
        )
    reader.read_case(bearer=tokens[0], case_id=str(fixtures[0].matter))


def run() -> None:
    env = dict(os.environ)
    require_protected_execution(env)
    dsn, connection_kind = validated_admin_dsn(env.get(ADMIN_DSN, ""))
    publishable = env.get("CASEPROOF_DEV_PUBLISHABLE_KEY", "")
    admin_key = env.get("CASEPROOF_DEV_AUTH_ADMIN_KEY", "")
    root_pem = env.get(CA_CERT, "")
    if (
        not publishable.startswith("sb_publishable_")
        or not admin_key
        or "BEGIN CERTIFICATE" not in root_pem
        or len(root_pem) > 18000
    ):
        raise RuntimeError("missing protected dev Auth or TLS CA secrets")
    auth_admin = GoTrueDevAdmin(admin_key)
    signin = SupabasePasswordSignin(PROJECT_REF, publishable)
    verifier = SupabaseAuthUserVerifier(
        PROJECT_REF, HttpsSupabaseUserLookup(PROJECT_REF, publishable),
    )
    password = secrets.token_urlsafe(48)
    created: list[str] = []
    fixtures: tuple[Fixture, Fixture, Fixture] | None = None
    role_created = False
    cleanup_errors: list[str] = []

    with tempfile.TemporaryDirectory(prefix="caseproof-m1-ca-") as dirname:
        path = Path(dirname) / "db-ca.pem"
        path.write_text(root_pem, encoding="ascii")
        path.chmod(0o600)

        def admin_conn() -> psycopg.Connection[object]:
            return _connect(dsn, str(path))

        def reader_conn() -> psycopg.Connection[object]:
            login = APP_DB_ROLE if connection_kind == "direct" else (
                f"{APP_DB_ROLE}.{PROJECT_REF}"
            )
            remote = make_conninfo(
                dsn, user=login, password=password,
            )
            return _connect(remote, str(path))

        try:
            with admin_conn() as conn:
                _live_preflight(conn)
                _create_ephemeral_login(conn, password)
                role_created = True
            with reader_conn() as conn:
                _assert_ephemeral_role(conn)
            credentials: list[PasswordCredentials] = []
            for _ in range(3):
                email = f"{PREFIX}{secrets.token_hex(16)}@example.com"
                pwd = secrets.token_urlsafe(40)
                identity = auth_admin.create_confirmed(email=email, password=pwd)
                created.append(identity)
                credentials.append(PasswordCredentials(email=email, password=pwd))
            signed = tuple(signin.sign_in(item) for item in credentials)
            subjects = tuple(verifier.verify_bearer(item.access_token) for item in signed)
            if len(set(s.subject_id for s in subjects)) != 3 or any(
                s.subject_id != created[i] or s.issuer != ISSUER
                or s.audience != "authenticated" or s.human_authenticated
                for i, s in enumerate(subjects)
            ):
                raise AssertionError("remote signed user identity mismatch")
            with admin_conn() as conn:
                fixtures = _seed_fixtures(conn, tuple(UUID(x) for x in created))
            _check_access(
                tokens=tuple(item.access_token for item in signed),
                fixtures=fixtures, verifier=verifier,
                connect_reader=reader_conn, connect_admin=admin_conn,
            )
        finally:
            # Remote Auth accounts reference membership FKs: remove DB first.
            if fixtures is not None:
                try:
                    with admin_conn() as conn:
                        _remove_fixtures(conn, fixtures)
                except Exception:
                    cleanup_errors.append("dev_fixture_cleanup")
            if role_created:
                try:
                    with admin_conn() as conn:
                        _drop_ephemeral_login(conn)
                except Exception:
                    cleanup_errors.append("ephemeral_db_role_cleanup")
            for identity in reversed(created):
                try:
                    auth_admin.delete(identity)
                except Exception:
                    cleanup_errors.append("dev_auth_user_cleanup")
            if cleanup_errors:
                raise RuntimeError(
                    "LIVE_DEV_CLEANUP_FAILED: manual dashboard investigation required"
                ) from None
    print("M1_DEV_REAL_SIGNED_USERS_TO_LIVE_PRIVATE_DB_RLS_PASSED")
    print("M1_DEV_EPHEMERAL_DB_AND_AUTH_FIXTURES_REMOVED")
    print("M1_C_HUMAN_SECURITY_APPROVAL_AND_STORAGE_M2_WORD_STILL_OPEN")


def main() -> int:
    try:
        run()
    except Exception as exc:
        # External exceptions often embed credentials; redact entire message.
        print(f"M1_LIVE_DB_PRIVATE_ACCEPTANCE_FAILED: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
