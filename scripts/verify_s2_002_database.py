"""S2-002: real PostgreSQL negative tests on a DISPOSABLE CI database only.

Requires a one-job PostgreSQL service listening on localhost. This script
must NEVER be pointed to a shared Supabase project or non-test host.
The real caseproof-dev test remains BEGIN/ROLLBACK and leaves no tables.
"""

from __future__ import annotations

import os
import select
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = (ROOT / "db/proposals/S2-002_tenant_foundation.sql").read_text(encoding="utf-8")
TESTS = (ROOT / "db/proposals/S2-002_rls_rollback_test.sql").read_text(encoding="utf-8")
CASE = "aaaaaaaa-1111-4111-8111-111111111111"
SCHEMA_BOOTSTRAP = """
create role anon nologin;
create role authenticated nologin;
create schema auth;
create table auth.users(
 id uuid primary key, instance_id uuid not null,
 aud text, role text, email text,
 created_at timestamptz, updated_at timestamptz
);
create function auth.uid() returns uuid language sql stable as $$
 select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid
$$;
grant usage on schema auth to authenticated;
grant execute on function auth.uid() to authenticated;
"""


def _env() -> dict[str, str]:
    if os.environ.get("CASEPROOF_DISPOSABLE_DB") != "YES":
        raise RuntimeError("Database concurrency tests require explicit disposable DB flag")
    host = os.environ.get("PGHOST", "")
    if host not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("Refusing to run database fixture outside local ephemeral Postgres")
    if os.environ.get("PGDATABASE") != "caseproof_s2_ci":
        raise RuntimeError("Expected dedicated disposable caseproof_s2_ci database")
    if os.environ.get("PGUSER") != "postgres":
        raise RuntimeError("Expected isolated CI postgres superuser")
    return dict(os.environ)


def _cmd() -> list[str]:
    return [
        "psql", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1",
    ]


def _run(sql: str, env: dict[str, str], *, should_pass: bool = True) -> str:
    result = subprocess.run(
        _cmd(), input=sql, text=True, capture_output=True,
        env=env, timeout=30, check=False,
    )
    if should_pass and result.returncode != 0:
        raise AssertionError(f"PostgreSQL verification failed: {result.stderr[:2000]}")
    if not should_pass and result.returncode == 0:
        raise AssertionError("Negative database test unexpectedly succeeded")
    return result.stdout.strip()


def main() -> None:
    env = _env()
    # Committed fixture exists ONLY in this disposable GitHub Actions service
    # so two independent connections can test actual PostgreSQL row locking.
    result = _run("BEGIN;\n" + SCHEMA_BOOTSTRAP + PROPOSAL + TESTS + "\nCOMMIT;", env)
    if "S2-002_ROLLBACK_ONLY_RLS_TEST_PASSED" not in result:
        raise AssertionError("Required tenant/RLS test marker missing")
    print("S2-002 RLS, FK, grants and membership negative checks: PASS")

    # Two independent authenticated clients attempt unauthorized mutation.
    unauthorized = (
        "set role authenticated; "
        f"update caseproof.cases set case_revision=999 where id='{CASE}';"
    )
    for _ in range(2):
        _run(unauthorized, env, should_pass=False)
    if _run(
        f"select case_revision::text from caseproof.cases where id='{CASE}'", env
    ) != "1":
        raise AssertionError("Unauthorized update modified case revision")
    print("S2-002 unauthorized database mutation: PASS")

    # True multi-connection write competition, not a serial sequential fake:
    # transaction A takes the row lock and emits a marker before sleeping.
    # transaction B starts while A holds it; B must wait, then its stale
    # compare-and-swap predicate must match ZERO rows after A commits.
    transaction_a = (
        "begin; set local lock_timeout='10s'; "
        f"update caseproof.cases set case_revision=case_revision+1 "
        f"where id='{CASE}' and case_revision=1 returning case_revision; "
        "select 'LOCK_ACQUIRED_BY_A'; select pg_sleep(2.5); commit;"
    )
    tx_a = subprocess.Popen(
        _cmd(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, bufsize=1, env=env,
    )
    try:
        assert tx_a.stdin is not None and tx_a.stdout is not None
        tx_a.stdin.write(transaction_a)
        tx_a.stdin.close()
        ready, _, _ = select.select([tx_a.stdout], [], [], 12.0)
        if not ready:
            raise AssertionError("Concurrent writer A did not acquire row lock")
        output = tx_a.stdout.readline().strip()
        # UPDATE RETURNING row; the marker is on the next stdout line.
        if output != "2":
            raise AssertionError(f"Writer A failed to change initial revision: {output!r}")
        ready, _, _ = select.select([tx_a.stdout], [], [], 12.0)
        if not ready or tx_a.stdout.readline().strip() != "LOCK_ACQUIRED_BY_A":
            raise AssertionError("Writer A lock marker not received")

        transaction_b = (
            "begin; set local lock_timeout='10s'; "
            "with updated as ("
            "update caseproof.cases set case_revision=case_revision+1 "
            f"where id='{CASE}' and case_revision=1 returning id"
            ") select count(*) from updated; commit;"
        )
        started = time.monotonic()
        second = _run(transaction_b, env)
        elapsed = time.monotonic() - started
        if second != "0":
            raise AssertionError(f"Stale concurrent write unexpectedly succeeded: {second!r}")
        if elapsed < 0.7:
            raise AssertionError("Second writer did not observe contested row lock")
        if tx_a.wait(timeout=10) != 0:
            raise AssertionError("Writer A failed to commit")
    finally:
        if tx_a.poll() is None:
            tx_a.kill()
            tx_a.wait(timeout=10)
    if _run(
        f"select case_revision::text from caseproof.cases where id='{CASE}'", env
    ) != "2":
        raise AssertionError("Concurrent CAS did not leave precisely one committed revision")
    print("S2-002 concurrent compare-and-swap (2 connections, real row lock): PASS")

    # PostgreSQL exception blocks are implicit subtransactions. This
    # deliberately fails audit INSERT after mutating case state, and checks
    # the state mutation was automatically undone. It is NOT a production
    # privileged writer implementation; that remains S2-004.
    audit_failure_test = f"""
    do $test$
    declare
        old_revision bigint;
        old_state text;
        old_audit_count bigint;
    begin
        select case_revision, state into old_revision, old_state
        from caseproof.cases where id = '{CASE}';
        select count(*) into old_audit_count from caseproof.audit_events
        where case_id = '{CASE}';
        begin
            update caseproof.cases
            set state='evidence_grounded',case_revision=case_revision+1
            where id='{CASE}';
            insert into caseproof.audit_events(
               org_id,case_id,actor_type,actor_user_id,action,
               event_schema_version,correlation_id,input_sha256_hex
            ) values (
               'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','{CASE}',
               'human','11111111-1111-4111-8111-111111111111',
               'synthetic-transition','test-v1',gen_random_uuid(),'invalid-audit-digest'
            );
            raise exception 'audit insertion unexpectedly succeeded';
        exception when check_violation then
            null; -- subtransaction rolled back on audit constraint failure
        end;
        if (select case_revision from caseproof.cases where id='{CASE}') <> old_revision
           or (select state from caseproof.cases where id='{CASE}') <> old_state
           or (select count(*) from caseproof.audit_events where case_id='{CASE}')
                 <> old_audit_count then
            raise exception 'state or audit changed despite failed audit persistence';
        end if;
    end
    $test$;
    select 'AUDIT_FAILURE_ROLLBACK_PASSED';
    """
    if "AUDIT_FAILURE_ROLLBACK_PASSED" not in _run(audit_failure_test, env):
        raise AssertionError("Audit failure test marker missing")
    print("S2-002 rollback of state on failed audit insert: PASS")
    print("S2-002_DISPOSABLE_POSTGRES_NEGATIVE_TESTS_PASSED")


if __name__ == "__main__":
    main()
