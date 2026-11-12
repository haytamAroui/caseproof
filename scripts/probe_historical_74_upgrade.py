"""Reconstruct the immutable 74-record applied history and test the pending upgrade.

The recorded `caseproof-dev` history now holds 76 applied migrations. The
previously verified 74-record base is still reconstructed byte-for-byte and
replayed in a local Supabase CLI profile, and the two migrations applied after
that base (the PR204 release-acknowledgement fence and the platform hardening
migration) are then applied on top of it without a reset. That proves the
upgrade path from the previously recorded history to the current one.

Local Supabase CLI only: no live access, no writes to historical migrations,
and no claim of schema parity with the currently running shared dev project.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from scripts.fresh_supabase_cli_profile import validate_environment
from scripts.probe_supabase_cli_local import CLI_VERSION, error_category, execute, output_tail
from scripts.verify_migration_lineage import LINEAGE, ROOT, SNAPSHOT, verify_lineage

PR204 = ROOT / "supabase/migrations/20261106210000_caseproof_release_acknowledgement_fence.sql"
HARDENING = ROOT / "supabase/migrations/20261113000000_caseproof_platform_hardening.sql"
PENDING = (PR204, HARDENING)
BASE_COUNT = 74
HISTORY_COUNT = 76
APPLY = re.compile(r"Applying migration ([0-9]{14}_[A-Za-z0-9_-]+\.sql)")


def historical_sources() -> list[tuple[str, Path, str]]:
    report = verify_lineage()
    if report["all_applied_sql_receipts_locatable"] is not True:
        raise ValueError("Migration lineage verification failed")
    ledger = json.loads(LINEAGE.read_text(encoding="utf-8"))
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    documented = {
        item["version"]: item for item in (
            ledger["remote_only"] + ledger["matching_version_receipts"]
        )
    }
    if len(documented) != HISTORY_COUNT or len(snapshot["applied"]) != HISTORY_COUNT:
        raise ValueError(f"Expected immutable {HISTORY_COUNT}-record history")
    pending_versions = {pending.name.split("_", 1)[0] for pending in PENDING}
    manifest: list[tuple[str, Path, str]] = []
    for item in snapshot["applied"]:
        version, name = item["version"], item["name"]
        if version in pending_versions:
            continue
        receipt = documented[version]
        if receipt["name"] != name:
            raise ValueError("Historical migration names no longer match")
        if receipt["source_state"] == "EXACT_SOURCE":
            path = receipt.get("source_path") or receipt["candidate_path"]
        else:
            path = receipt["applied_receipt_path"]
        absolute = (ROOT / path).resolve()
        if not absolute.is_relative_to(ROOT.resolve()) or not absolute.is_file():
            raise ValueError("Missing or unsafe applied SQL source path")
        sql = absolute.read_bytes()
        sha = hashlib.sha256(sql).hexdigest()
        if sha != receipt["recorded_sha256"]:
            raise ValueError("Historical SQL source fingerprint mismatch")
        if len(sql.decode("utf-8")) != receipt["recorded_chars"]:
            raise ValueError("Historical SQL character count mismatch")
        filename = f"{version}_{name}.sql"
        manifest.append((filename, absolute, sha))
    names = [name for name, _, _ in manifest]
    if len(set(names)) != BASE_COUNT or names != sorted(names):
        raise ValueError("Deployed history does not have unique sorted versions")
    for pending in PENDING:
        if pending.name in names:
            raise ValueError(
                f"Pending migration unexpectedly part of applied history: {pending.name}"
            )
    return manifest


def copy_historical_sql(folder: Path, manifest: list[tuple[str, Path, str]]) -> str:
    folder.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256()
    for filename, original, digest in manifest:
        dest = folder / filename
        if dest.exists():
            raise ValueError("Duplicate historical destination")
        shutil.copyfile(original, dest)
        if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
            raise RuntimeError("Historical applied SQL changed while copying")
        fingerprint.update(filename.encode("utf-8") + b"\0" + bytes.fromhex(digest))
    return fingerprint.hexdigest()


def probe_historical_upgrade() -> dict[str, object]:
    env = dict(os.environ)
    validate_environment(env)
    version = subprocess.run(
        ["supabase", "--version"], env=env, capture_output=True,
        text=True, timeout=30, check=False,
    )
    if version.returncode or CLI_VERSION not in version.stdout:
        raise RuntimeError("Pinned Supabase CLI version unavailable")
    files = historical_sources()
    result: dict[str, object] = {
        "scope": "isolated_local_reconstruction_of_recorded_dev_history",
        "cli_version": CLI_VERSION,
        "historical_statements": len(files),
        "historical_sql_receipts_verified": True,
        "real_dev_schema_parity_verified": False,
        "signed_live_release_verified": False,
        "release_deployment_authorized": False,
        "remote_database_modified": False,
    }
    with tempfile.TemporaryDirectory(prefix="caseproof-historical-cli-") as tmp:
        root = Path(tmp).resolve()
        init = execute(["supabase", "init", "--yes"], root, env, 120)
        if init.returncode:
            return result | {
                "status": "HISTORICAL_PROFILE_INIT_FAILED",
                "error_category": error_category(init.stdout + init.stderr),
            }
        try:
            started = execute(["supabase", "start"], root, env, 720)
            if started.returncode:
                return result | {
                    "status": "HISTORICAL_LOCAL_STACK_FAILED",
                    "error_category": error_category(started.stdout + started.stderr),
                }
            folder = root / "supabase/migrations"
            receipt = copy_historical_sql(folder, files)
            reset = execute(
                ["supabase", "db", "reset", "--local", "--no-seed"],
                root, env, 720,
            )
            output = reset.stdout + "\n" + reset.stderr
            attempted = APPLY.findall(output)
            if reset.returncode:
                return result | {
                    "status": "HISTORICAL_74_FULL_CLI_REPLAY_BLOCKED",
                    "observed_apply_count": len(attempted),
                    "first_failed_version": attempted[-1] if attempted else None,
                    "error_category": error_category(output),
                    "cli_output_tail": output_tail(output),
                    "historical_profile_sha256": receipt,
                }
            if len(attempted) != BASE_COUNT or set(attempted) != {x[0] for x in files}:
                return result | {
                    "status": "HISTORICAL_APPLY_COUNT_UNPROVEN",
                    "observed_apply_count": len(attempted),
                }
            for pending in PENDING:
                shutil.copyfile(pending, folder / pending.name)
                if (folder / pending.name).read_bytes() != pending.read_bytes():
                    raise RuntimeError(f"Pending SQL bytes changed: {pending.name}")
            # Apply exactly the next pending migrations without resetting.
            upgrade = execute(["supabase", "migration", "up", "--local"], root, env, 360)
            out = upgrade.stdout + "\n" + upgrade.stderr
            applied = APPLY.findall(out)
            pending_names = {pending.name for pending in PENDING}
            if upgrade.returncode or not pending_names.issubset(set(applied)):
                return result | {
                    "status": "PENDING_HISTORICAL_LOCAL_UPGRADE_BLOCKED",
                    "observed_pending_apply": sorted(pending_names & set(applied)),
                    "error_category": error_category(out),
                    "cli_output_tail": output_tail(out),
                    "historical_profile_sha256": receipt,
                }
            return result | {
                "status": "HISTORICAL_74_TO_76_LOCAL_UPGRADE_PASSED",
                "historical_applied_count": BASE_COUNT,
                "pending_applied_count": len(PENDING),
                "historical_profile_sha256": receipt,
                "historical_replay_verified": True,
                "local_upgrade_path_verified": True,
            }
        finally:
            execute(["supabase", "stop", "--no-backup"], root, env, 180)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = probe_historical_upgrade()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "HISTORICAL_74_TO_76_LOCAL_UPGRADE_PASSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
