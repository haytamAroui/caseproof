"""Test exact source SQL in reviewed dependency order on official local Supabase.

This is a TEMPORARY unlinked fresh-install profile, not a released baseline.
No original migration is renamed; no linked database is contacted or repaired.
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
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.disposable_replay_candidate import PLAN, replay_plan
from scripts.probe_supabase_cli_local import (
    CLI_VERSION,
    assert_offline_cli_environment,
    error_category,
    execute,
)
from scripts.verify_migration_lineage import verify_lineage

SOURCE_DIR = Path(__file__).resolve().parents[1] / "supabase/migrations"
BASE_TIME = datetime(2026, 11, 12, tzinfo=UTC)
APPLY = re.compile(r"Applying migration ([0-9]{14}_[A-Za-z0-9_-]+\.sql)")
NO_REMOTE = (
    "SUPABASE_PROJECT_ID", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SECRET_KEY",
    "PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD", "PGPASSFILE",
    "PGSYSCONFDIR", "DIRECT_URL", "POSTGRES_PRISMA_URL",
)


def validate_environment(env: dict[str, str]) -> None:
    assert_offline_cli_environment(env)
    if any(env.get(key) for key in NO_REMOTE):
        raise RuntimeError("Database target or privileged key forbidden in local profile")


def temporary_aliases() -> list[tuple[Path, str]]:
    sources = replay_plan()
    manifest = json.loads(PLAN.read_text(encoding="utf-8"))
    moved = set(manifest["deferred_suffix"])
    if len(moved) != 23:
        raise ValueError("Expected 23 reviewed dependency deferrals")
    result: list[tuple[Path, str]] = []
    moved_index = 0
    for source in sources:
        if source.resolve().parent != SOURCE_DIR.resolve():
            raise ValueError("Profile source escaped tracked migration directory")
        if source.name in moved:
            stamp = (BASE_TIME + timedelta(minutes=moved_index)).strftime("%Y%m%d%H%M%S")
            original_label = source.name.split("_", 1)[1]
            alias = f"{stamp}_{original_label}"
            moved_index += 1
        else:
            # SQL inside the early M1 source checks the actual historical
            # 20261027160745 version in schema_migrations. Keep that version.
            alias = source.name
        result.append((source, alias))
    if moved_index != 23:
        raise ValueError("Not all reviewed dependency deferrals were processed")
    if len(result) != 74 or len({alias for _, alias in result}) != len(result):
        raise ValueError("Candidate file set changed; fresh profile needs review")
    if [name for _, name in result] != sorted(name for _, name in result):
        raise ValueError("Ephemeral alias order is nonmonotonic")
    return result


def copy_exact_sources(folder: Path, aliases: list[tuple[Path, str]]) -> str:
    folder.mkdir(parents=True, exist_ok=True)
    lineage_digest = hashlib.sha256()
    for original, alias in aliases:
        target = folder / alias
        if target.exists():
            raise ValueError("Duplicate temporary migration alias")
        original_data = original.read_bytes()
        shutil.copyfile(original, target)
        if target.read_bytes() != original_data:
            raise RuntimeError("Original SQL changed in temporary test profile")
        lineage_digest.update(original.name.encode() + b"\0")
        lineage_digest.update(alias.encode() + b"\0")
        lineage_digest.update(hashlib.sha256(original_data).digest())
    return lineage_digest.hexdigest()


def run_fresh_profile() -> dict[str, object]:
    env = dict(os.environ)
    validate_environment(env)
    version = subprocess.run(
        ["supabase", "--version"], env=env, capture_output=True,
        text=True, check=False, timeout=30,
    )
    if version.returncode or CLI_VERSION not in version.stdout:
        raise RuntimeError("Pinned Supabase CLI not installed")
    proof = verify_lineage()
    if proof["all_applied_sql_receipts_locatable"] is not True:
        raise RuntimeError("Historical migration evidence no longer verifies")
    aliases = temporary_aliases()
    report: dict[str, object] = {
        "scope": "temporary_unlinked_supabase_cli_full_stack",
        "cli_version": CLI_VERSION,
        "planned_source_count": len(aliases),
        "historical_receipts_verified": True,
        "original_migrations_modified": False,
        "migration_history_repaired": False,
        "upgrade_path_verified": False,
        "independent_security_approval": False,
        "live_database_modified": False,
    }
    with tempfile.TemporaryDirectory(prefix="caseproof-fresh-cli-") as temp:
        workdir = Path(temp).resolve()
        init = execute(["supabase", "init", "--yes"], workdir, env, 120)
        if init.returncode:
            return report | {
                "status": "CLI_INIT_FAILED",
                "error_category": error_category(init.stdout + init.stderr),
            }
        try:
            # Start the official stack with no application SQL.
            stack = execute(["supabase", "start"], workdir, env, 720)
            if stack.returncode:
                return report | {
                    "status": "LOCAL_STACK_FAILED",
                    "error_category": error_category(stack.stdout + stack.stderr),
                }
            by_alias = {alias: original.name for original, alias in aliases}
            digest = copy_exact_sources(
                workdir / "supabase/migrations", aliases
            )
            reset = execute(
                ["supabase", "db", "reset", "--local", "--no-seed"],
                workdir, env, 720,
            )
            output = reset.stdout + "\n" + reset.stderr
            observed = APPLY.findall(output)
            if reset.returncode == 0:
                if len(observed) != len(aliases) or set(observed) != set(by_alias):
                    return report | {
                        "status": "RESET_SUCCEEDED_BUT_APPLY_COUNT_UNPROVEN",
                        "observed_apply_count": len(observed),
                    }
                return report | {
                    "status": "FRESH_PROFILE_FULL_CLI_PASS",
                    "applied_count": len(observed),
                    "source_layout_sha256": digest,
                    "fresh_profile_verified": True,
                }
            failed = observed[-1] if observed else None
            return report | {
                "status": "FRESH_PROFILE_FULL_CLI_BLOCKED",
                "observed_apply_count": len(observed),
                "first_failed_source": by_alias.get(failed),
                "error_category": error_category(output),
                "source_layout_sha256": digest,
            }
        finally:
            execute(["supabase", "stop", "--no-backup"], workdir, env, 180)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run_fresh_profile()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "FRESH_PROFILE_FULL_CLI_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
