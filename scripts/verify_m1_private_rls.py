"""M1-B default-private RLS policy negative/positive acceptance on PostgreSQL.

This tests PostgreSQL *authorization policy behavior only*. Synthetic
request.jwt.claim.sub set on isolated local CI is NOT signed Supabase Auth.
Do not use the fixture role setup or SQL claims in live database sessions.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from scripts.verify_s2_002_database import _env, _run
from scripts.verify_vault_integration import connect

SQL = Path(__file__).resolve().parents[1] / "db/proposals/PIV-M1_default_private_rls_candidate.sql"


@dataclass(frozen=True)
class Fixture:
    org: UUID
    actor: UUID
    case: UUID
    document: UUID
    version: UUID


def seed(*, org: UUID | None = None, read_evidence: bool = True,
         actor_id: UUID | None = None) -> Fixture:
    scope, actor, case, document, version = (
        org or uuid4(), actor_id or uuid4(), uuid4(), uuid4(), uuid4(),
    )
    actions = ["case:read"] + (["evidence:read"] if read_evidence else [])
    with connect() as conn:
        conn.execute(
            "insert into auth.users(id,instance_id) values(%s,%s)",
            (actor, UUID(int=1)),
        )
        if org is None:
            conn.execute(
                "insert into caseproof.organizations(id,display_name) "
                "values(%s,'Synthetic private tenant')",
                (scope,),
            )
        conn.execute(
            "insert into caseproof.organization_members "
            "(org_id,user_id,actions) values(%s,%s,%s)",
            (scope, actor, actions),
        )
        conn.execute(
            "insert into caseproof.cases "
            "(id,org_id,created_by_user,effective_policy_version) "
            "values(%s,%s,%s,'m1-private-fixture')",
            (case, scope, actor),
        )
        conn.execute(
            "insert into caseproof.documents(id,org_id,case_id,source_label) "
            "values(%s,%s,%s,'synthetic-private-evidence')",
            (document, scope, case),
        )
        conn.execute(
            "insert into caseproof.document_versions("
            "id,org_id,document_id,version_number,"
            "original_sha256_hex,byte_length,media_type) "
            "values(%s,%s,%s,1,%s,13,'text/plain')",
            (version, scope, document, "a" * 64),
        )
        conn.execute(
            "insert into caseproof._m1_matter_grants("
            "org_id,case_id,user_id,role,permissions) "
            "values(%s,%s,%s,'reviewer',%s)",
            (scope, case, actor, ["case:read", "evidence:read"]),
        )
    return Fixture(scope, actor, case, document, version)


def role_sql(actor: UUID | None, query: str) -> str:
    claim = (
        f"set local request.jwt.claim.sub='{actor}'; "
        if actor is not None else ""
    )
    return (
        "begin; set local role authenticated; " + claim +
        query.rstrip(";") + "; commit;"
    )


def count(actor: UUID | None, relation: str) -> int:
    if relation not in {
        "cases", "documents", "document_versions", "_m1_matter_grants",
        "audit_events",
    }:
        raise AssertionError("unrecognized fixture table")
    return int(_run(
        role_sql(actor, f"select count(*) from caseproof.{relation}"), _env(),
    ))


def assert_counts(actor: UUID, expected: tuple[int, int, int, int]) -> None:
    observed = tuple(count(actor, table) for table in (
        "cases", "documents", "document_versions", "_m1_matter_grants",
    ))
    if observed != expected:
        raise AssertionError(f"default-private RLS counts {observed} != {expected}")


def main() -> None:
    env = _env()
    _run(SQL.read_text(encoding="utf-8"), env)

    a1 = seed()
    a2 = seed(org=a1.org)
    b1 = seed()
    other = uuid4()  # no member/grant exists for this identity

    # Positive cases AND same-org other-matter isolation.
    for actor in (a1.actor, a2.actor, b1.actor):
        assert_counts(actor, (1, 1, 1, 1))
    assert_counts(other, (0, 0, 0, 0))
    if count(None, "cases") != 0:
        raise AssertionError("missing JWT subject could list private matters")

    # Session-local PostgreSQL role and JWT claim must not leak across
    # transactions on a reused connection. Tests a DB property, not Auth.
    isolated = _run(
        role_sql(a1.actor, "select count(*) from caseproof.cases") + "\n" +
        role_sql(None, "select count(*) from caseproof.cases") + "\n" +
        role_sql(b1.actor, "select count(*) from caseproof.cases"), env,
    )
    if isolated.splitlines() != ["1", "0", "1"]:
        raise AssertionError("session-scoped claim/role leaked across transactions")

    # No direct role access to audit data or record mutation, even with
    # a well-formed synthetic subject claim.
    for role_statement in (
        "select count(*) from caseproof.audit_events",
        f"update caseproof.cases set case_revision=999 where id='{a1.case}'",
        "select count(*) from caseproof._m1_exhibit_heads",
        "delete from caseproof._m1_matter_grants",
    ):
        _run(role_sql(a1.actor, role_statement), env, should_pass=False)
    for role in ("anon",):
        _run(
            f"set role {role}; select count(*) from caseproof.cases",
            env, should_pass=False,
        )

    # Case read and evidence read permissions are distinct. Org action AND
    # exact active matter grant must both exist; no org-wide fallback.
    with connect() as conn:
        conn.execute(
            "update caseproof.organization_members set actions=array['case:read']::text[] "
            "where org_id=%s and user_id=%s",
            (a2.org, a2.actor),
        )
    assert_counts(a2.actor, (1, 0, 0, 1))

    with connect() as conn:
        conn.execute(
            "update caseproof.organization_members "
            "set actions=array['case:read','evidence:read']::text[] "
            "where org_id=%s and user_id=%s",
            (a2.org, a2.actor),
        )
        conn.execute(
            "update caseproof._m1_matter_grants "
            "set permissions=array['evidence:read']::text[],revision=revision+1 "
            "where org_id=%s and case_id=%s and user_id=%s",
            (a2.org, a2.case, a2.actor),
        )
    assert_counts(a2.actor, (0, 0, 0, 1))

    # Revoked per-case assignment or membership denies all private rows.
    with connect() as conn:
        conn.execute(
            "update caseproof._m1_matter_grants "
            "set active=false,revision=revision+1 "
            "where org_id=%s and case_id=%s and user_id=%s",
            (a1.org, a1.case, a1.actor),
        )
        conn.execute(
            "update caseproof.organization_members "
            "set active=false,membership_revision=membership_revision+1 "
            "where org_id=%s and user_id=%s",
            (b1.org, b1.actor),
        )
    assert_counts(a1.actor, (0, 0, 0, 0))
    assert_counts(b1.actor, (0, 0, 0, 0))

    # Verify former organization-wide policies were actually replaced.
    query = (
        "select count(*) from pg_policies "
        "where schemaname='caseproof' and policyname in ("
        "'tenant_case_read','tenant_document_read',"
        "'tenant_document_version_read')"
    )
    if _run(query, env) != "0":
        raise AssertionError("legacy permissive org-wide read policy still installed")

    # An unexpected permissive policy must make a future rollout abort
    # transactionally, not silently OR itself with the private restrictions.
    _run(
        "create policy m1_sabotage_orgwide_select on caseproof.cases "
        "for select to authenticated using (true)", env,
    )
    try:
        _run(SQL.read_text(encoding="utf-8"), env, should_pass=False)
    finally:
        _run(
            "drop policy m1_sabotage_orgwide_select on caseproof.cases", env,
        )
    # No policies were silently left downgraded after the failed rollout.
    if _run(query, env) != "0":
        raise AssertionError("failed migration restored legacy org-wide policy")

    print("M1_PRIVATE_RLS_SAME_ORG_CASE_ISOLATION_ACTION_REVOKE_POOL_RESET_PASSED")
    print("Synthetic SQL JWT claim did NOT validate a real signed Auth session")


if __name__ == "__main__":
    main()
