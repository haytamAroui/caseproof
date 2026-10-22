"""S2-004 real PostgreSQL proof of INTERNAL atomicity: disposable CI ONLY.

Requires scripts/verify_s2_002_database.py to have seeded the same one-job
PostgreSQL 17 database. Exercises the exact SQL reference function, not a
production DB-API adapter or a genuine signed session. NEVER run on Supabase.
"""

from __future__ import annotations

import re
import select
import subprocess
import time
from dataclasses import replace
from pathlib import Path
from uuid import UUID

from apps.api.internal_observation_contract import (
    InternalObservation,
    semantic_input_sha256,
)
from scripts.verify_s2_002_database import _cmd, _env, _run

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_SQL = (
    ROOT / "db/proposals/S2-004_disposable_observation.sql"
).read_text(encoding="utf-8")
A = UUID("11111111-1111-4111-8111-111111111111")
B = UUID("22222222-2222-4222-8222-222222222222")
CASE_A = UUID("aaaaaaaa-1111-4111-8111-111111111111")
CASE_B = UUID("bbbbbbbb-2222-4222-8222-222222222222")
ORG_A = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
CORRELATION = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


def observation(key: str, expected: int = 2, source: str = "a") -> InternalObservation:
    if not re.fullmatch(r"[a-z0-9_-]{1,40}", key):
        raise ValueError("only fixed synthetic test keys permitted")
    return InternalObservation(
        case_id=CASE_A,
        expected_case_revision=expected,
        expected_scope_version=1,
        expected_manifest_revision=1,
        expected_policy_version="test-v1",
        idempotency_key=key,
        observation_sha256=source * 64,
    )


def sql_call(
    command: InternalObservation, *,
    actor: UUID = A, fault: str | None = None
) -> str:
    """Fixed validated test data only. Production code MUST use DB bind params."""
    if fault not in (None, "audit", "receipt"):
        raise ValueError("invalid fault injection")
    if not re.fullmatch(r"[a-z0-9_-]{1,40}", command.idempotency_key):
        raise ValueError("unsafe fixture key")
    digest = semantic_input_sha256(actor, command)
    return (
        "select event_id::text || '|' || committed_revision::text || '|' "
        "|| idempotent_replay::text from "
        "caseproof._s2_004_disposable_observation("
        f"'{actor}','{command.case_id}',{command.expected_case_revision},"
        f"{command.expected_scope_version},{command.expected_manifest_revision},"
        f"'{command.expected_policy_version}','{command.idempotency_key}',"
        f"'{digest}','{CORRELATION}',"
        f"{'null' if fault is None else chr(39) + fault + chr(39)}"
        ");"
    )


def state(env: dict[str, str]) -> tuple[int, int, int, int]:
    q = (
        "select c.case_revision || '|' || "
        "(select count(*) from caseproof.audit_events a "
        "where a.action = 's2_004_internal_observation' and a.case_id = c.id) || '|' || "
        "(select count(*) from caseproof.idempotency_records i "
        "where i.operation='s2_004_internal_observation' and i.case_id=c.id) || '|' || "
        "(select count(*) from caseproof._s2_004_disposable_event_revisions er "
        "where er.case_id=c.id) "
        f"from caseproof.cases c where c.id='{CASE_A}';"
    )
    result = _run(q, env)
    return tuple(int(x) for x in result.split("|"))  # type: ignore[return-value]


def assert_state(env: dict[str, str], expected: tuple[int, int, int, int], label: str) -> None:
    current = state(env)
    if current != expected:
        raise AssertionError(f"{label}: revision/audit/receipt/event-binding counts {current} != {expected}")


def concurrent_call(
    env: dict[str, str], command_a: InternalObservation,
    command_b: InternalObservation, *, b_success: bool,
) -> tuple[str, str, float]:
    """Two actual psql connections: A holds membership lock; B races A."""
    tx_a_sql = (
        "begin; set local lock_timeout='10s'; "
        "do $lock$ begin "
        "perform 1 from caseproof.organization_members m "
        f"where m.org_id='{ORG_A}' and m.user_id='{A}' "
        "and m.active = true for update; "
        "end $lock$; "
        "select 'LOCK_ACQUIRED_A'; select pg_sleep(2.5); "
        + sql_call(command_a) + " commit;"
    )
    process = subprocess.Popen(
        _cmd(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, bufsize=1, env=env,
    )
    try:
        assert process.stdin is not None and process.stdout is not None
        process.stdin.write(tx_a_sql)
        process.stdin.close()
        ready, _, _ = select.select([process.stdout], [], [], 12.0)
        if not ready:
            raise AssertionError("Transaction A did not acquire membership lock")
        marker = process.stdout.readline().strip()
        if marker != "LOCK_ACQUIRED_A":
            raise AssertionError(f"Expected real lock marker, got {marker!r}")
        started = time.monotonic()
        second = _run(
            "set lock_timeout='10s'; " + sql_call(command_b),
            env,
            should_pass=b_success,
        )
        elapsed = time.monotonic() - started
        if elapsed < 0.7:
            raise AssertionError("Second connection did not wait on contested membership lock")
        if process.wait(timeout=12) != 0:
            raise AssertionError("First transaction failed instead of committing")
        first = process.stdout.read()
        return first, second, elapsed
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=12)


def main() -> None:
    env = _env()
    # Refuse running unless the existing S2-002 disposable suite already
    # created the exact synthetic data. This script never bootstraps a live DB.
    if state(env) != (2, 0, 0, 0):
        raise RuntimeError("S2-004 requires fresh S2-002 disposable CI fixtures")

    _run(REFERENCE_SQL, env)
    _run(
        "update caseproof.organization_members "
        "set active=true, actions=array['case:read','finding:write']::text[] "
        f"where org_id='{ORG_A}' and user_id='{A}';",
        env,
    )
    if _run(
        f"select active::text from caseproof.organization_members "
        f"where org_id='{ORG_A}' and user_id='{A}';", env
    ) != "true":
        raise AssertionError("Synthetic reviewer membership not enabled")

    base = observation("baseline")
    _run(sql_call(base, actor=B), env, should_pass=False)
    _run(sql_call(replace(base, case_id=CASE_B)), env, should_pass=False)
    # A member granted finding:write but NOT case:read must receive the
    # same masked P0002 as an unknown/foreign case, not permission-denied
    # 42501 which would reveal case existence.
    _run(
        "update caseproof.organization_members "
        "set actions=array['finding:write']::text[] "
        f"where org_id='{ORG_A}' and user_id='{A}';",
        env,
    )
    def masked(command: InternalObservation) -> None:
        call = sql_call(command)
        query = call.split(" from caseproof._s2_004_disposable_observation(", 1)[1]
        fixture = "caseproof._s2_004_disposable_observation(" + query
        assert _run(
            "do $mask$ begin perform 1 from " + fixture +
            " raise exception 'unmasked case lookup'; "
            "exception when sqlstate 'P0002' then null; end $mask$; "
            "select 'MASKED';", env,
        ) == "MASKED"
    masked(base)
    masked(replace(base, case_id=UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")))
    print("S2-004 action-only and unknown case masked identically: PASS")

    _run(
        "update caseproof.organization_members "
        "set actions=array['case:read']::text[] "
        f"where org_id='{ORG_A}' and user_id='{A}';",
        env,
    )
    _run(sql_call(base), env, should_pass=False)
    _run(
        "update caseproof.organization_members "
        "set actions=array['case:read','finding:write']::text[] "
        f"where org_id='{ORG_A}' and user_id='{A}';",
        env,
    )
    assert_state(env, (2, 0, 0, 0), "CROSS_TENANT_AND_PERMISSION_DENIAL")
    print("S2-004 cross-tenant and missing-grant denial: PASS")

    _run(sql_call(base, fault="audit"), env, should_pass=False)
    assert_state(env, (2, 0, 0, 0), "AUDIT_FAILURE")
    print("S2-004 AUDIT_FAILURE_RACE_FREE_ROLLBACK: PASS")
    _run(sql_call(base, fault="receipt"), env, should_pass=False)
    assert_state(env, (2, 0, 0, 0), "RECEIPT_FAILURE")
    print("S2-004 RECEIPT_FAILURE_RACE_FREE_ROLLBACK: PASS")

    first = _run(sql_call(base), env)
    event, rev, replay = first.split("|")
    if rev != "3" or replay != "false":
        raise AssertionError("Internal observation was not committed")
    assert_state(env, (3, 1, 1, 1), "FIRST_ATOMIC_COMMIT")
    retried = _run(sql_call(base), env)
    if retried != f"{event}|3|true":
        raise AssertionError("Committed observation was not exactly replayed")
    assert_state(env, (3, 1, 1, 1), "IDEMPOTENT_REPLAY")
    _run(sql_call(observation("baseline", source="b")), env, should_pass=False)
    _run(sql_call(observation("stale", expected=2)), env, should_pass=False)
    assert_state(env, (3, 1, 1, 1), "REPLAY_CONFLICT_AND_STALE_REVISION")
    print("S2-004 idempotent replay, conflict and stale revision: PASS")

    _run(
        "update caseproof.organization_members set active=false "
        f"where org_id='{ORG_A}' and user_id='{A}';", env,
    )
    _run(sql_call(base), env, should_pass=False)
    assert_state(env, (3, 1, 1, 1), "REVOKED_ACTOR_REPLAY_DENIAL")
    _run(
        "update caseproof.organization_members set active=true "
        f"where org_id='{ORG_A}' and user_id='{A}';", env,
    )
    print("S2-004 revoked membership cannot replay response: PASS")

    a, b, elapsed = concurrent_call(
        env, observation("race_same", expected=3),
        observation("race_same", expected=3), b_success=True,
    )
    if "|4|false" not in a or "|4|true" not in b:
        raise AssertionError(f"CONCURRENT_REPLAY did not share one event: {a!r}, {b!r}")
    match = re.search(r"([a-f0-9-]{36})\|4\|false", a)
    if match is None or b.strip() != f"{match.group(1)}|4|true":
        raise AssertionError("CONCURRENT_REPLAY event ID disagrees across sessions")
    assert_state(env, (4, 2, 2, 2), "CONCURRENT_REPLAY")
    print(f"S2-004 CONCURRENT_REPLAY across two real connections: PASS ({elapsed:.2f}s)")

    first_race, _, _ = concurrent_call(
        env, observation("race_unique_a", expected=4),
        observation("race_unique_b", expected=4), b_success=False,
    )
    if "|5|false" not in first_race:
        raise AssertionError("Competing writer did not commit first revision")
    assert_state(env, (5, 3, 3, 3), "CONCURRENT_DISTINCT_KEY_STALE_CAS")
    print("S2-004 concurrent CAS with distinct request keys: PASS")

    # Privileged attacker keeps schema+event but forges another legal
    # bigint revision. An event-id existence check alone misses this.
    _run(
        "update caseproof.idempotency_records "
        "set response_reference=jsonb_set(response_reference::jsonb,"
        "'{revision}','999'::jsonb)::text "
        "where operation='s2_004_internal_observation' "
        f"and case_id='{CASE_A}' and idempotency_key='baseline';", env,
    )
    _run(sql_call(base), env, should_pass=False)
    assert_state(env, (5, 3, 3, 3), "STRUCTURALLY_VALID_FORGED_REVISION")
    print("S2-004 structurally valid forged replay revision rejected: PASS")

    # Test actual post-commit receipt tampering: production authorization
    # would never grant this privileged UPDATE. Poisoned receipts fail closed.
    _run(
        "update caseproof.idempotency_records set response_reference='{}' "
        "where operation='s2_004_internal_observation' "
        f"and case_id='{CASE_A}' and idempotency_key='baseline';", env,
    )
    _run(sql_call(base), env, should_pass=False)
    assert_state(env, (5, 3, 3, 3), "CORRUPTED_RECEIPT_REPLAY")
    print("S2-004 corruption of idempotency receipt detected: PASS")

    print("S2-004_DISPOSABLE_ATOMIC_OBSERVATION_PASSED")


if __name__ == "__main__":
    main()
