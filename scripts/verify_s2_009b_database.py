"""S2-009b PostgreSQL 17 disposable-only vault ledger proof.

No Supabase endpoint, real object bytes, trusted actor, or production role.
Runs after the S2-002/007/004/008a/008a3 fixture scripts in ONE ephemeral DB.
"""

from __future__ import annotations

import re
import select
import subprocess
import time
from pathlib import Path
from uuid import UUID

from scripts.verify_s2_002_database import _cmd, _run
from scripts.verify_s2_007_disposable_tenancy import _isolated_postgres_env
from scripts.verify_s2_008a_database import ACTOR, CASE, ORG, VERSION

ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "db/proposals/S2-009b_disposable_vault_ledger.sql").read_text()
INTENT = "12345678-1234-4234-8234-1234567890ab"
FOREIGN = "bbbbbbbb-2222-4222-8222-222222222222"
OTHER_CASE = "aaaaaaaa-2121-4121-8121-aaaaaaaaaaaa"
OBJECT_KEY = (
    f"org/{UUID(ORG).hex}/case/{UUID(CASE).hex}/sources/"
    "0123456789abcdef0123456789abcdef"
)


def call(
    op: str, *, key: str | None = None, case: str = CASE, actor: str = ACTOR,
    intent: str = INTENT, sha: str | None = None, source_version: str | None = None,
    size: int | None = None, media: str | None = None,
    object_key: str | None = None, expected: int | None = None,
    reason: str | None = None, fault: str | None = None,
) -> str:
    if op not in {"stage", "verify", "unavailable"}:
        raise ValueError("fixture operation not allowlisted")
    if key is None:
        key = intent if op == "stage" else f"{op}-1"
    if not re.fullmatch(r"[a-z0-9-]{1,128}", key):
        raise ValueError("unsafe fixture request key")
    for identifier in (case, actor, intent):
        UUID(identifier)
    if op == "stage":
        sha = "a" * 64 if sha is None else sha
        source_version = VERSION if source_version is None else source_version
        size = 12 if size is None else size
        media = "text/plain" if media is None else media
        object_key = OBJECT_KEY if object_key is None else object_key
    if op == "verify":
        sha = "a" * 64 if sha is None else sha
        size = 12 if size is None else size
        expected = 1 if expected is None else expected
    if op == "unavailable":
        expected = 2 if expected is None else expected
        reason = "missing" if reason is None else reason

    def q(value: object) -> str:
        if value is None:
            return "null"
        if type(value) is int:
            return str(value)
        value = str(value)
        if not re.fullmatch(r"[a-zA-Z0-9/._:-]{1,256}", value):
            raise ValueError("unsafe test-only SQL input")
        return "'" + value + "'"

    args = {
        "p_actor": actor,
        "p_case": case,
        "p_intent": intent,
        "p_operation": op,
        "p_request_key": key,
        "p_correlation": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        "p_document_version": source_version,
        "p_object_key": object_key,
        "p_sha": sha,
        "p_byte_length": size,
        "p_media": media,
        "p_expected_intent_revision": expected,
        "p_reason": reason,
        "p_fault": fault,
    }
    params = ",".join(f"{name}=>{q(value)}" for name, value in args.items())
    return (
        "select resulting_state||'|'||resulting_intent_revision::text||'|'||"
        "resulting_case_revision::text||'|'||recorded_audit::text||'|'||"
        "idempotent_replay::text "
        "from caseproof._s2_009b_disposable_command(" + params + ");"
    )


def snapshot(env: dict[str, str]) -> tuple[int, int, int, int, int, str | None]:
    sql = (
        "select c.case_revision::text||'|'||"
        "(select count(*) from caseproof.audit_events a where a.case_id=c.id "
        "and a.action like 's2_009b_vault_%')::text||'|'||"
        "(select count(*) from caseproof.idempotency_records r where r.case_id=c.id "
        "and r.operation like 's2_009b_vault_%')::text||'|'||"
        "(select count(*) from caseproof._s2_009b_availability_events e "
        "where e.case_id=c.id)::text||'|'||"
        "(select count(*) from caseproof._s2_009b_vault_intents i "
        "where i.case_id=c.id)::text||'|'||"
        "coalesce((select state||':'||intent_revision::text "
        "from caseproof._s2_009b_vault_intents i "
        "where i.case_id=c.id and i.intent_id='" + INTENT + "'),'-') "
        "from caseproof.cases c where c.id='" + CASE + "';"
    )
    parts = _run(sql, env).split("|")
    return (int(parts[0]), int(parts[1]), int(parts[2]),
            int(parts[3]), int(parts[4]), parts[5])


def _blocked(env: dict[str, str], statement: str, label: str) -> None:
    _run(statement, env, should_pass=False)
    print(f"S2-009b {label}: PASS")


def _unchanged(env: dict[str, str], expected: tuple[int, int, int, int, int, str | None],
               label: str) -> None:
    actual = snapshot(env)
    if actual != expected:
        raise AssertionError(f"{label}: transaction partially committed {actual} != {expected}")


def _concurrent_replay(env: dict[str, str], sql: str, prefix: str) -> None:
    """Two real connections: A commits and holds membership lock; B replays."""
    marker = "VAULT_TX_LOCKED"
    tx_a = subprocess.Popen(
        _cmd(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, bufsize=1, env=env,
    )
    try:
        assert tx_a.stdin is not None and tx_a.stdout is not None
        tx_a.stdin.write(
            "begin; set local lock_timeout='12s'; "
            + sql + " select '" + marker + "'; select pg_sleep(2); commit;\n"
        )
        tx_a.stdin.close()
        ready, _, _ = select.select([tx_a.stdout], [], [], 15)
        if not ready:
            raise AssertionError("Vault transaction did not start")
        first = tx_a.stdout.readline().strip()
        if not first.startswith(prefix) or not first.endswith("|false"):
            raise AssertionError("First writer did not commit one expected event")
        ready, _, _ = select.select([tx_a.stdout], [], [], 15)
        if not ready or tx_a.stdout.readline().strip() != marker:
            raise AssertionError("Transaction lock marker absent")
        start = time.monotonic()
        replay = _run(sql, env)
        elapsed = time.monotonic() - start
        if (not replay.endswith("|true") or replay.rsplit("|", 1)[0]
                != first.rsplit("|", 1)[0] or elapsed < 0.7):
            raise AssertionError("Concurrent replay did not preserve one event and case revision")
        if tx_a.wait(timeout=8) != 0:
            raise AssertionError("First writer failed to commit")
    finally:
        if tx_a.poll() is None:
            tx_a.kill()
            tx_a.wait(timeout=5)


def main() -> None:
    env = _isolated_postgres_env()
    if _run("select to_regclass('caseproof._s2_009b_vault_intents') is null;", env) != "t":
        raise RuntimeError("S2-009b requires a fresh disposable-only schema")
    if _run(f"select count(*) from caseproof.document_versions where id='{VERSION}';", env) != "1":
        raise RuntimeError("Expected existing S2-002 synthetic source version")
    _run(SQL, env)
    original = snapshot(env)
    assert original[1:] == (0, 0, 0, 0, "-")

    _blocked(env, call("stage", fault="audit"), "pending audit failure rollback")
    _unchanged(env, original, "AUDIT_STAGE")
    _blocked(env, call("stage", fault="receipt"), "pending receipt failure rollback")
    _unchanged(env, original, "RECEIPT_STAGE")
    _blocked(env, call("stage", case=FOREIGN), "foreign case source denied")
    _unchanged(env, original, "FOREIGN_STAGE")
    _blocked(env, call("stage", case=OTHER_CASE), "same tenant other case wrong source")
    _unchanged(env, original, "OTHER_CASE")
    _blocked(env, call("stage", sha="b" * 64), "unmatched source hash denied")
    _unchanged(env, original, "WRONG_SOURCE")
    _blocked(env, call("stage", actor="33333333-3333-4333-8333-333333333333"),
             "missing reviewer action denied")

    committed = _run(call("stage"), env)
    state, revision, case_revision, audit_id, replay = committed.split("|")
    if (state, revision, replay) != ("pending", "1", "false"):
        raise AssertionError("Pending intent not created exactly once")
    a = snapshot(env)
    if a != (original[0] + 1, 1, 1, 0, 1, "pending:1"):
        raise AssertionError("Pending mutation not atomically audited/idempotent")
    # Retry submits a fresh random object key, but the DB persists the original.
    new_key = OBJECT_KEY[:-32] + "f" * 32
    replayed = _run(call("stage", object_key=new_key), env)
    if replayed != f"pending|1|{case_revision}|{audit_id}|true":
        raise AssertionError("Original pending intent receipt not faithfully replayed")
    original_key = _run(
        f"select object_key from caseproof._s2_009b_vault_intents where intent_id='{INTENT}';",
        env,
    )
    if original_key != OBJECT_KEY:
        raise AssertionError("Replay replaced immutable object key")
    _unchanged(env, a, "PENDING_REPLAY")
    print("S2-009b durable pending intent + same-ID replay: PASS")

    _blocked(env, call("verify", fault="audit"), "verification audit rollback")
    _blocked(env, call("verify", fault="availability"), "availability FK rollback")
    _blocked(env, call("verify", fault="receipt"), "verification receipt rollback")
    _unchanged(env, a, "VERIFICATION_FAILURE_ROLLBACK")
    _blocked(env, call("verify", sha="f" * 64), "wrong asserted readback digest")
    _blocked(env, call("verify", expected=0), "stale expected intent revision")
    _unchanged(env, a, "READBACK_PRECONDITION")

    verify = _run(call("verify"), env)
    vstate, vrevision, vcase_revision, vaudit, vreplay = verify.split("|")
    if (vstate, vrevision, vreplay) != ("verified", "2", "false"):
        raise AssertionError("Verified publication failed")
    b = snapshot(env)
    if b != (a[0] + 1, 2, 2, 1, 1, "verified:2"):
        raise AssertionError("Verified publication/audit/idempotency not atomic")
    same = _run(call("verify"), env)
    if same != f"verified|2|{vcase_revision}|{vaudit}|true":
        raise AssertionError("Verification receipt not replayed exactly")
    _unchanged(env, b, "VERIFICATION_REPLAY")
    _blocked(env, call("verify", key="stale-verifier", expected=1),
             "stale verifier with new key")
    _unchanged(env, b, "STALE_VERIFY")

    _blocked(env, call("unavailable", fault="audit"), "missing object audit rollback")
    _blocked(env, call("unavailable", fault="availability"), "missing object event FK rollback")
    _blocked(env, call("unavailable", fault="receipt"), "missing object receipt rollback")
    _unchanged(env, b, "UNAVAILABLE_FAILURE_ROLLBACK")

    unavailable = _run(call("unavailable"), env)
    ustate, urevision, ucase_revision, uaudit, ureplay = unavailable.split("|")
    if (ustate, urevision, ureplay) != ("unavailable", "3", "false"):
        raise AssertionError("Unavailability revision not committed")
    c = snapshot(env)
    if c != (b[0] + 1, 3, 3, 2, 1, "unavailable:3"):
        raise AssertionError("Loss event did not atomically invalidate case revision")
    if _run(call("unavailable"), env) != f"unavailable|3|{ucase_revision}|{uaudit}|true":
        raise AssertionError("Unavailability receipt replay failed")
    _unchanged(env, c, "UNAVAILABLE_REPLAY")
    _blocked(env, call("verify", key="restore-attempt", expected=3),
             "missing source cannot silently become verified")
    _unchanged(env, c, "UNAUTHORIZED_RESTORATION")
    print("S2-009b unavailable ledger event + aggregate revision: PASS")

    _blocked(env,
        "update caseproof._s2_009b_availability_events set reason='missing' "
        f"where intent_id='{INTENT}' and status='verified';",
        "append-only availability update denied")
    _blocked(env,
        f"delete from caseproof._s2_009b_availability_events where intent_id='{INTENT}';",
        "append-only availability delete denied")
    _blocked(env,
        "set role authenticated; select count(*) from caseproof._s2_009b_vault_intents;",
        "client role has no vault metadata grant")
    _blocked(env, call("unavailable", actor="22222222-2222-4222-8222-222222222222"),
             "cross-org actor cannot replay")
    _unchanged(env, c, "ROLE_AND_IMMUTABILITY")

    # Even a syntactically valid JSON receipt must match the immutable audit
    # + availability event; privilege needed to corrupt fixture is NOT granted.
    _run(
        "update caseproof.idempotency_records "
        "set response_reference=jsonb_set(response_reference::jsonb,"
        "'{intent_revision}','999'::jsonb)::text "
        "where operation='s2_009b_vault_verify' "
        f"and case_id='{CASE}' and idempotency_key='verify-1';", env,
    )
    _blocked(env, call("verify"), "forged saved receipt revision denied")
    _unchanged(env, c, "FORGED_RECEIPT")
    # A second stable UUIDv4 request races on two independent PostgreSQL
    # connections. Exactly one stage intent/audit/receipt commits.
    second_id = "87654321-4321-4321-8321-abcdefabcdef"
    second_key = OBJECT_KEY[:-32] + "0123456789abcdefabcdef0123456789"
    before_race = snapshot(env)
    _concurrent_replay(
        env, call("stage", intent=second_id, object_key=second_key), "pending|1|"
    )
    after_race = snapshot(env)
    if (after_race[0] != before_race[0] + 1
            or after_race[1] != before_race[1] + 1
            or after_race[2] != before_race[2] + 1
            or after_race[4] != before_race[4] + 1):
        raise AssertionError("Concurrent stage replay committed duplicate effects")
    print("S2-009b concurrent identical-key stage and replay across connections: PASS")

    print("S2-009b_DISPOSABLE_VAULT_LEDGER_PASSED")


if __name__ == "__main__":
    main()
