"""Reconstruct exact 74 applied SQL receipts and test a pending PR204 upgrade.

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
from scripts.probe_supabase_cli_local import CLI_VERSION, error_category, execute
from scripts.verify_migration_lineage import LINEAGE, ROOT, SNAPSHOT, verify_lineage

PR204 = ROOT / "supabase/migrations/20261106210000_caseproof_release_acknowledgement_fence.sql"
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
    if len(documented) != 74 or len(snapshot["applied"]) != 74:
        raise ValueError("Expected immutable 74-record history")
    manifest: list[tuple[str, Path, str]] = []
    for item in snapshot["applied"]:
        version, name = item["version"], item["name"]
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
    if len(set(names)) != 74 or names != sorted(names):
        raise ValueError("Deployed history does not have unique sorted versions")
    if PR204.name in names:
        raise ValueError("PR204 release fence unexpectedly part of applied history")
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
                    "historical_profile_sha256": receipt,
                }
            if len(attempted) != 74 or set(attempted) != {x[0] for x in files}:
                return result | {
                    "status": "HISTORICAL_APPLY_COUNT_UNPROVEN",
                    "observed_apply_count": len(attempted),
                }
            shutil.copyfile(PR204, folder / PR204.name)
            if (folder / PR204.name).read_bytes() != PR204.read_bytes():
                raise RuntimeError("Pending PR204 SQL bytes changed")
            # Apply exactly the next pending migration without resetting.
            upgrade = execute(["supabase", "migration", "up", "--local"], root, env, 360)
            out = upgrade.stdout + "\n" + upgrade.stderr
            applied = APPLY.findall(out)
            if upgrade.returncode or PR204.name not in applied:
                return result | {
                    "status": "PR204_HISTORICAL_LOCAL_UPGRADE_BLOCKED",
                    "observed_pr204_apply": PR204.name in applied,
                    "error_category": error_category(out),
                    "historical_profile_sha256": receipt,
                }
            return result | {
                "status": "HISTORICAL_74_TO_75_LOCAL_UPGRADE_PASSED",
                "historical_applied_count": 74,
                "pr204_applied_count": 1,
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
    return 0 if report["status"] == "HISTORICAL_74_TO_75_LOCAL_UPGRADE_PASSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
