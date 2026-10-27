"""M2 single-transaction private schema candidate: disposable PostgreSQL only.

This is NOT a Supabase migration or signed-user security test. The candidate
must fail closed on missing M1 private policies, injected permissive rules,
pre-existing M2 objects, and any nonempty dev fixture. Never target live DB.
"""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from scripts.verify_s2_002_database import (
    MIGRATION,
    SCHEMA_BOOTSTRAP,
    _env,
    _run,
)

ROOT = Path(__file__).resolve().parents[1]
M1 = ROOT / "db/proposals/PIV-M1_DEV_atomic_private_grant_install.sql"
M2 = ROOT / "db/proposals/PIV-M2_DEV_atomic_private_review_candidate.sql"
SOURCE = (
    ROOT / "db/proposals/PIV-M2_disposable_review_runs.sql",
    ROOT / "db/proposals/PIV-M2_disposable_brief_graph.sql",
    ROOT / "db/proposals/PIV-M2_disposable_correction_recheck.sql",
)
TABLE_COUNT = 11
TABLES = (
    "_m2_check_runs", "_m2_review_heads", "_m2_review_events",
    "_m2_review_receipts", "_m2_brief_versions", "_m2_brief_references",
    "_m2_brief_assertions", "_m2_brief_heads", "_m2_brief_events",
    "_m2_correction_plans", "_m2_correction_events",
)


def _contract_bytes(candidate: str) -> None:
    # M2 DDL is assembled directly from the three existing reviewed
    # disposable-source packets. Any silent proposal drift fails CI.
    for path in SOURCE:
        start = f"-- BEGIN PINNED SOURCE: {path.relative_to(ROOT)}\n"
        stop = f"\n-- END PINNED SOURCE: {path.relative_to(ROOT)}"
        if candidate.count(start) != 1 or candidate.count(stop) != 1:
            raise AssertionError("combined candidate missing bounded source")
        segment = candidate.split(start, 1)[1].split(stop, 1)[0].strip()
        source = path.read_text(encoding="utf-8")
        source = source.replace("begin;", "", 1)
        source = source.rsplit("commit;", 1)[0].strip()
        if segment != source:
            raise AssertionError("combined M2 candidate diverges from disposable source")


def _count(env: dict[str, str]) -> int:
    return int(_run(
        "select count(*) from pg_class c join pg_namespace n "
        "on n.oid=c.relnamespace where n.nspname='caseproof' "
        "and c.relkind in ('r','p') and left(c.relname,4)='_m2_'", env,
    ))


def _not_installed(env: dict[str, str]) -> None:
    if _count(env) != 0:
        raise AssertionError("failed M2 migration left partial tables")


def _check_schema(env: dict[str, str]) -> None:
    if _count(env) != TABLE_COUNT:
        raise AssertionError("partial or unknown M2 schema")
    for table in TABLES:
        effective = _run(
            "select c.relrowsecurity::text || ',' || "
            "has_table_privilege('authenticated',c.oid,'SELECT')::text || ',' || "
            "has_table_privilege('anon',c.oid,'SELECT')::text || ',' || "
            "has_table_privilege('authenticated',c.oid,'INSERT,UPDATE,DELETE')::text "
            "from pg_class c join pg_namespace n on n.oid=c.relnamespace "
            "where n.nspname='caseproof' and c.relname='" + table + "'", env,
        )
        if effective != "true,false,false,false":
            raise AssertionError("unreviewed M2 client access or missing RLS")
    if _run(
        "select count(*) from pg_policies where schemaname='caseproof' "
        "and tablename=any(array[" + ",".join(f"'{x}'" for x in TABLES) + "])", env,
    ) != "0":
        raise AssertionError("M2 tables acquired unexpected client policies")
    for role in ("anon", "authenticated"):
        _run(
            f"set role {role}; select count(*) from caseproof._m2_check_runs",
            env, should_pass=False,
        )


def _immutable_check(env: dict[str, str]) -> None:
    org, actor, case, doc, version, snapshot = (uuid4() for _ in range(6))
    payload = "[]"
    digest = "a" * 64
    other = "b" * 64
    # Disposable synthetic auth.user insert is STRICTLY local; real Auth
    # identities are only provisioned via GoTrue Admin API.
    _run(
        "begin; "
        f"insert into auth.users(id,instance_id) values('{actor}',"
        "'00000000-0000-4000-8000-000000000001'); "
        f"insert into caseproof.organizations(id,display_name) values('{org}',"
        "'Disposable M2 private gate'); "
        f"insert into caseproof.organization_members(org_id,user_id,actions) "
        f"values('{org}','{actor}',array['case:read','evidence:read']); "
        "insert into caseproof.cases(id,org_id,created_by_user,"
        f"effective_policy_version) values('{case}','{org}','{actor}',"
        "'disposable-test'); "
        "insert into caseproof.documents(id,org_id,case_id,source_label) "
        f"values('{doc}','{org}','{case}','test source'); "
        "insert into caseproof.document_versions("
        "id,org_id,document_id,version_number,original_sha256_hex,"
        f"byte_length,media_type) values('{version}','{org}','{doc}',1,"
        f"'{digest}',0,'text/plain'); "
        "insert into caseproof._m2_check_runs (org_id,case_id,snapshot_sha,"
        "payload_sha,payload,brief_version_id,case_revision,"
        "exhibit_revision,actor_id) values("
        f"'{org}','{case}','{other}','{digest}','{payload}',"
        f"'brief-v1',1,1,'{actor}'); "
        "commit;", env,
    )
    _run(
        "update caseproof._m2_check_runs "
        f"set payload='changed' where org_id='{org}' and case_id='{case}'",
        env, should_pass=False,
    )
    unchanged = _run(
        "select payload from caseproof._m2_check_runs "
        f"where org_id='{org}' and case_id='{case}'", env,
    )
    if unchanged != payload:
        raise AssertionError("M2 immutable check run mutated")
    # CAS heads are mutable server-only. Immutable run/events never are.
    _run(
        "set role authenticated; "
        f"select * from caseproof._m2_check_runs where case_id='{case}'",
        env, should_pass=False,
    )


def main() -> None:
    env = _env()
    if (
        env.get("PGHOST") != "127.0.0.1"
        or env.get("PGPORT") != "5432"
        or any(x in env for x in ("PGHOSTADDR", "PGSERVICE", "PGOPTIONS"))
    ):
        raise RuntimeError("M2 reviewer schema tests require pinned isolated localhost")
    candidate = M2.read_text(encoding="utf-8")
    _contract_bytes(candidate)
    if _run("select to_regclass('caseproof.cases') is null", env) != "t":
        raise RuntimeError("M2 reviewer gate requires a fresh PostgreSQL fixture")
    _run("begin;\n" + SCHEMA_BOOTSTRAP
         + MIGRATION.read_text(encoding="utf-8") + "\ncommit;", env)

    # No private M1 grants/policy? M2 DDL must not begin.
    _run(candidate, env, should_pass=False)
    _not_installed(env)

    m1 = M1.read_text(encoding="utf-8")
    _run(m1, env)

    # Rogue permissive M1 SELECT must block M2 before one table is created.
    _run(
        "create policy m2_attack_allow_every_case on caseproof.cases "
        "for select to authenticated using(true)", env,
    )
    _run(candidate, env, should_pass=False)
    _not_installed(env)
    _run("drop policy m2_attack_allow_every_case on caseproof.cases", env)

    # Existing Auth identity must trigger a migration/backfill review.
    user = uuid4()
    _run(
        "insert into auth.users(id,instance_id) "
        f"values('{user}','00000000-0000-4000-8000-000000000001')", env,
    )
    _run(candidate, env, should_pass=False)
    _not_installed(env)
    _run(f"delete from auth.users where id='{user}'", env)

    _run(candidate, env)
    _check_schema(env)

    # Blind retry forbidden; first schema must remain untouched.
    _run(candidate, env, should_pass=False)
    _check_schema(env)

    _immutable_check(env)
    print("M2_PRIVATE_REVIEW_ATOMIC_SCHEMA_ROLLBACK_RLS_IMMUTABLE_PASSED")
    print("DISPOSABLE_POSTGRES_ONLY: NOT_INSTALLED_IN_REAL_SUPABASE")
    print("SIGNED_M1_AUTH_PRIVATE_STORAGE_AND_REVIEW_APPROVAL_STILL_OPEN")


if __name__ == "__main__":
    main()
