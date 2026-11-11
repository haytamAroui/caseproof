"""Test a version-pinned dependency-ordered migration candidate in disposable PG17.

This candidate exposes the previously implicit CI order as a reviewed manifest.
It is NOT the Supabase CLI's filename-order replay, not an upgrade-path proof
and never rewrites applied migration history.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from scripts.audit_migration_inventory import MIGRATIONS, local_inventory
from scripts.probe_migration_natural_order import PG_ERROR, STUBS
from scripts.verify_s2_002_database import SCHEMA_BOOTSTRAP, _env, _run

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs/security/disposable_replay_candidate_v1.json"


def replay_plan(plan_path: Path = PLAN) -> list[Path]:
    document = json.loads(plan_path.read_text(encoding="utf-8"))
    if document.get("schema") != "caseproof-disposable-replay-candidate-v1":
        raise ValueError("Unexpected disposable replay candidate schema")
    expected = document["expected_sorted_files"]
    suffix = document["deferred_suffix"]
    actual = sorted(p.name for p in MIGRATIONS.glob("*.sql"))
    inventory = local_inventory(MIGRATIONS)
    if (not actual or actual != expected or len(inventory) != len(actual)
            or not isinstance(suffix, list) or len(suffix) != len(set(suffix))
            or any(name not in actual for name in suffix)):
        raise ValueError("Migration files or deferred order changed; review candidate")
    prefix = [name for name in expected if name not in suffix]
    proposed = prefix + suffix
    if len(set(proposed)) != len(actual) or set(proposed) != set(actual):
        raise ValueError("Candidate does not install each migration exactly once")
    return [MIGRATIONS / name for name in proposed]


def disposable_environment() -> dict[str, str]:
    env = _env()
    if env.get("PGHOSTADDR") not in (None, "", "127.0.0.1", "::1"):
        raise RuntimeError("Refusing alternate PostgreSQL host address")
    if env.get("PGSERVICE") or env.get("PGSERVICEFILE"):
        raise RuntimeError("Refusing PostgreSQL service override")
    if env.get("PGPORT") != "5432":
        raise RuntimeError("Expected ephemeral PostgreSQL port 5432")
    if env.get("PGPASSFILE") or env.get("PGSYSCONFDIR"):
        raise RuntimeError("Refusing external PostgreSQL connection configuration")
    return env


def run_candidate() -> dict[str, object]:
    env = disposable_environment()
    paths = replay_plan()
    _run(SCHEMA_BOOTSTRAP + STUBS, env)
    count = 0
    for path in paths:
        if path.resolve().parent != MIGRATIONS.resolve():
            raise RuntimeError("Candidate SQL escaped tracked migrations")
        process = subprocess.run(
            ["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-f", str(path)],
            env=env, text=True, capture_output=True, check=False, timeout=45,
        )
        if process.returncode != 0:
            errors = PG_ERROR.findall(process.stderr)
            return {
                "status": "BLOCKED_DISPOSABLE_REPLAY_CANDIDATE",
                "scope": "isolated_postgresql_stub_not_supabase_cli",
                "installed_before_failure": count,
                "total_planned": len(paths),
                "first_failed_migration": path.name,
                "error_category": errors[0][:180] if errors else "SQL execution rejected",
                "supabase_cli_fresh_install_verified": False,
                "upgrade_path_verified": False,
                "live_database_modified": False,
            }
        version = path.name.split("_", 1)[0]
        _run(
            f"insert into supabase_migrations.schema_migrations(version) values ('{version}')",
            env,
        )
        count += 1
    return {
        "status": "DISPOSABLE_REPLAY_CANDIDATE_PASSED_NOT_SUPABASE_CLI",
        "scope": "isolated_postgresql_stub_not_supabase_cli",
        "installed_count": count,
        "total_planned": len(paths),
        "supabase_cli_fresh_install_verified": False,
        "upgrade_path_verified": False,
        "live_database_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = run_candidate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    # Passing means this PostgreSQL candidate applied, NOT a released schema.
    return 0 if report["status"] == "DISPOSABLE_REPLAY_CANDIDATE_PASSED_NOT_SUPABASE_CLI" else 2


if __name__ == "__main__":
    raise SystemExit(main())
