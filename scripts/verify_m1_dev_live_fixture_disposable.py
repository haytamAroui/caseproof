"""Actually execute dev-only fixture RPC cleanup against disposable PostgreSQL 17.

Separate from real protected Auth/Storage. This tests SQL rollback, privileges,
identity restrictions, no cross-run deletion and Storage-object cleanup ordering.
"""
from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from scripts.verify_s2_002_database import MIGRATION, SCHEMA_BOOTSTRAP, _env, _run

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "db/proposals/PIV-M1_DEV_atomic_private_grant_install.sql"
DEV_FIXTURE = ROOT / "db/proposals/PIV-M1_DEV_live_positive_fixture_rpc.sql"


def _count(env: dict[str, str], table: str) -> int:
    if table not in {
        "organizations", "organization_members", "cases", "documents",
        "document_versions", "_m1_matter_grants", "_dev_ci_fixture",
    }:
        raise ValueError("unexpected table")
    return int(_run(f"select count(*) from caseproof.{table}", env))


def main() -> None:
    env = _env()
    if (
        env.get("PGHOST") != "127.0.0.1"
        or env.get("PGPORT") != "5432"
        or any(x in env for x in ("PGHOSTADDR", "PGSERVICE", "PGOPTIONS"))
    ):
        raise RuntimeError("disposable PostgreSQL 17 CI only")
    if _run("select to_regclass('caseproof.cases') is null", env) != "t":
        raise RuntimeError("fresh isolated database required")
    _run(
        "begin;\n" + SCHEMA_BOOTSTRAP
        + "create role service_role nologin;\n"
        + "alter table auth.users add column email_confirmed_at timestamptz;\n"
        + MIGRATION.read_text(encoding="utf-8") + "\ncommit;", env,
    )
    _run(PRIVATE.read_text(encoding="utf-8"), env)
    _run(
        "create schema supabase_migrations; "
        "create table supabase_migrations.schema_migrations(version text primary key);"
        "insert into supabase_migrations.schema_migrations(version) values "
        "('20261027160745'),('20261027202734'),('20261027204343'); "
        "create schema storage;"
        "create table storage.buckets(id text primary key,public boolean not null);"
        "insert into storage.buckets(id,public) values('caseproof-originals-dev',false);"
        "create table storage.objects(bucket_id text not null,name text not null,"
        "primary key(bucket_id,name));", env,
    )
    # Cannot apply the dev-only SQL if private prerequisites are absent.
    _run(DEV_FIXTURE.read_text(encoding="utf-8"), env)
    for fn, args in (
        ("begin", "uuid,uuid,uuid,uuid,text,bigint"),
        ("revoke", "uuid,uuid"), ("cleanup", "uuid,uuid"),
    ):
        signature = f"public.caseproof_dev_fixture_{fn}({args})"
        for role in ("anon", "authenticated"):
            if _run(f"select has_function_privilege('{role}','{signature}',"
                    "'EXECUTE')", env) != "f":
                raise AssertionError("client can invoke privileged fixture writer")
        if _run(f"select has_function_privilege('service_role','{signature}',"
                "'EXECUTE')", env) != "t":
            raise AssertionError("admin service role cannot execute fixture")

    owner, guest, foreign = (uuid4() for _ in range(3))
    run, attempted, sha = uuid4(), uuid4(), "a" * 64
    users = (owner, guest, foreign)
    for actor in users:
        _run(
            "insert into auth.users(id,instance_id,email,email_confirmed_at) "
            f"values('{actor}','00000000-0000-4000-8000-000000000001',"
            f"'caseproof-ci-{actor}@example.com',now());", env,
        )

    call = (
        "select public.caseproof_dev_fixture_begin("
        f"'{run}','{owner}','{guest}','{foreign}','{sha}',13);"
    )
    _run("set role authenticated; " + call, env, should_pass=False)
    if _count(env, "cases") != 0:
        raise AssertionError("unprivileged user seeded a case")
    result = json.loads(_run(call, env))
    object_name = "/".join((
        result["org_id"], result["case_id"], result["document_id"],
        result["version_id"], sha,
    ))
    if [_count(env, table) for table in (
        "organizations", "organization_members", "cases", "documents",
        "document_versions", "_m1_matter_grants", "_dev_ci_fixture",
    )] != [2, 3, 1, 1, 1, 1, 1]:
        raise AssertionError("incomplete authorized fixture")
    # Existing fixture must not be overwritten or impersonated by another run.
    _run(call.replace(str(run), str(attempted)), env, should_pass=False)
    if _count(env, "cases") != 1:
        raise AssertionError("duplicate attempt modified original fixture")

    _run(
        "insert into storage.objects(bucket_id,name)"
        f"values('caseproof-originals-dev','{object_name}');", env,
    )
    cleanup = (
        "select public.caseproof_dev_fixture_cleanup("
        f"'{run}','{owner}');"
    )
    _run(cleanup, env, should_pass=False)
    if _count(env, "_dev_ci_fixture") != 1 or _count(env, "cases") != 1:
        raise AssertionError("failed cleanup partially removed fixture")
    if _run(
        f"select public.caseproof_dev_fixture_cleanup('{run}','{foreign}');",
        env,
    ) != "f":
        raise AssertionError("foreign fixture actor cleanup should be an idempotent miss")
    if _count(env, "cases") != 1:
        raise AssertionError("foreign actor deleted a fixture")

    _run("delete from storage.objects where bucket_id='caseproof-originals-dev';", env)
    if _run(cleanup, env) != "t" or _run(cleanup, env) != "f":
        raise AssertionError("cleanup/replay did not produce true/false")
    for table in ("organizations", "organization_members", "cases", "documents",
                  "document_versions", "_m1_matter_grants", "_dev_ci_fixture"):
        if _count(env, table):
            raise AssertionError(f"cleanup left exact synthetic rows in {table}")
    for actor in users:
        _run(f"delete from auth.users where id='{actor}';", env)
    if _run("select count(*) from auth.users", env) != "0":
        raise AssertionError("fixture auth rows still referenced after cleanup")
    print("M1_DEV_LIVE_FIXTURE_SQL_ROLLBACK_PRIVILEGES_STORAGE_FIRST_CLEANUP_PASSED")
    print("DISPOSABLE_POSTGRES_ONLY: NOT_REAL_SIGNED_SUPABASE_AUTH")


if __name__ == "__main__":
    main()
