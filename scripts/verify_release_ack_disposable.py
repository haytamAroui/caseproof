"""Verify PR204 SQL fence under real disposable PostgreSQL connections.

Synthetic records only; this does not authorize live deployment.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.disposable_replay_candidate import disposable_environment

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "supabase/migrations/20261106210000_caseproof_release_acknowledgement_fence.sql"
ACTOR = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
DIGEST = "a" * 64
NOTICE = "I understand this reviewed release is not a court filing certificate."
PRELUDE = """
create role anon nologin;
create role authenticated nologin;
create schema caseproof;
create table caseproof.dossier_releases (
 release_id uuid primary key, actor_id uuid not null,
 snapshot_hash text not null, manifest jsonb not null
);
"""


def check_sql(source: str, env: dict[str, str], valid: bool) -> str:
    p = subprocess.run(
        ["psql", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1",
         "-v", "VERBOSITY=verbose"],
        input=source, capture_output=True, text=True,
        check=False, timeout=25, env=env,
    )
    if valid and p.returncode:
        raise AssertionError("Valid disposable SQL unexpectedly failed: " + p.stderr[:180])
    if not valid:
        if not p.returncode:
            raise AssertionError("Unauthorized release insert unexpectedly succeeded")
        if not re.search(r"\b42501\b", p.stderr):
            raise AssertionError("Failure was not SQLSTATE 42501 from release fence")
    return p.stdout.strip()


def release_id(n: int) -> str:
    return "00000000-0000-4000-8000-" + str(n).zfill(12)


def ack(n: int, timestamp: datetime) -> dict[str, str]:
    return {
        "schema": "caseproof-release-ack-v1",
        "intent": "AUTHORIZE_REVIEW_RECORD_RELEASE",
        "actor_id": ACTOR,
        "actor_label": "auditor@example.test",
        "actor_label_type": "confirmed_email",
        "release_id": release_id(n),
        "snapshot_hash": DIGEST,
        "release_type": "complete_review",
        "acknowledged_at": timestamp.isoformat(),
        "notice": NOTICE,
    }


def insert_release(n: int, receipt: dict[str, str] | None) -> str:
    manifest: dict[str, object] = {
        "review_completeness": {"release_type": "complete_review"},
    }
    if receipt is not None:
        manifest["release_acknowledgement"] = receipt
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    return (
        "insert into caseproof.dossier_releases"
        "(release_id,actor_id,snapshot_hash,manifest) values("
        + "'" + release_id(n) + "'::uuid,"
        + "'" + ACTOR + "'::uuid,"
        + "'" + DIGEST + "',"
        + "$caseproof_payload$" + payload + "$caseproof_payload$::jsonb);"
    )


def invalid_receipts(now: datetime) -> list[tuple[str, dict[str, str] | None]]:
    cases: list[tuple[str, dict[str, str] | None]] = [("missing", None)]
    changes = [
        ("actor_mismatch", "actor_id", release_id(800)),
        ("release_id_mismatch", "release_id", release_id(801)),
        ("snapshot_mismatch", "snapshot_hash", "b" * 64),
        ("scope_mismatch", "release_type", "partial_review"),
        ("wrong_schema", "schema", "not-approved"),
        ("wrong_intent", "intent", "AUTO_APPROVE"),
        ("empty_actor_label", "actor_label", ""),
        ("untrusted_label_type", "actor_label_type", "user_metadata"),
        ("short_notice", "notice", "OK"),
        ("expired_timestamp", "acknowledged_at", (now - timedelta(minutes=20)).isoformat()),
        ("future_timestamp", "acknowledged_at", (now + timedelta(minutes=10)).isoformat()),
        ("invalid_timestamp", "acknowledged_at", "yesterday"),
    ]
    for label, key, value in changes:
        record = ack(1, now)
        record[key] = value
        cases.append((label, record))
    extra = ack(1, now)
    extra["unexpected_field"] = "forged"
    cases.append(("extra_manifest_key", extra))
    return cases


def acceptance() -> dict[str, object]:
    env = disposable_environment()
    check_sql(PRELUDE, env, valid=True)
    original = SQL.read_text(encoding="utf-8")
    if "create trigger release_acknowledgement_fence" not in original:
        raise RuntimeError("Missing approved PR204 trigger SQL")
    check_sql(original, env, valid=True)
    now = datetime.now(UTC)
    check_sql(insert_release(1, ack(1, now)), env, valid=True)
    invalid = invalid_receipts(now)
    for number, (label, record) in enumerate(invalid, start=2):
        if record is not None and label != "release_id_mismatch":
            record["release_id"] = release_id(number)
        check_sql(insert_release(number, record), env, valid=False)
    count = check_sql("select count(*) from caseproof.dossier_releases;", env, valid=True)
    if count != "1":
        raise AssertionError("Invalid release row reached persistence")
    acl = check_sql(
        "select has_function_privilege('anon','caseproof.release_acknowledgement_fence()',"
        "'execute'),has_function_privilege('authenticated',"
        "'caseproof.release_acknowledgement_fence()','execute');",
        env, valid=True,
    )
    if acl != "f|f":
        raise AssertionError("Release fence executable by client database roles")
    return {
        "status": "RELEASE_ACK_DISPOSABLE_SQL_PASSED",
        "valid_releases_accepted": 1,
        "negative_42501_rejections": len(invalid),
        "anon_and_authenticated_execute_denied": True,
        "live_database_modified": False,
        "signed_live_export_verified": False,
        "pilot_deployment_authorized": False,
    }


def main() -> None:
    print(json.dumps(acceptance(), indent=2))


if __name__ == "__main__":
    main()
