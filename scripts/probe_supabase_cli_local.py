"""Run real Supabase CLI migrations in a disposable, unlinked local project.

This is a negative acceptance checkpoint for the historical filename-order
failure, NOT a clean-install approval. Never target a hosted Supabase project.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from scripts.audit_migration_inventory import MIGRATIONS, local_inventory

CLI_VERSION = "3.1.0"
EXPECTED_FIRST_FAILURE = "20261030114000_m05_ocr_sidecar_cleanup_fk.sql"
APPLY_PATTERN = re.compile(r"Applying migration ([0-9]{14}_[A-Za-z0-9_-]+\.sql)")
FILE_PATTERN = re.compile(r"([0-9]{14}_[A-Za-z0-9_-]+\.sql)")
UNSAFE_ENV = (
    "SUPABASE_ACCESS_TOKEN", "SUPABASE_DB_PASSWORD", "DATABASE_URL",
    "POSTGRES_URL", "PGSERVICE", "PGSERVICEFILE", "PGHOSTADDR",
)
REMOTE_FLAGS = ("--linked", "--remote", "--db-url")


def assert_offline_cli_environment(environ: dict[str, str]) -> None:
    if environ.get("CI") != "true" or environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Must run inside isolated GitHub Actions CI")
    if any(environ.get(key) for key in UNSAFE_ENV):
        raise RuntimeError("Remote database credentials or routes are forbidden")


def execute(
    args: list[str], cwd: Path, environ: dict[str, str], timeout: int
) -> subprocess.CompletedProcess[str]:
    if any(item in REMOTE_FLAGS for item in args):
        raise RuntimeError("Cloud/linked Supabase CLI command forbidden")
    if args[:3] == ["supabase", "migration", "repair"]:
        raise RuntimeError("Migration history repair forbidden")
    return subprocess.run(
        args, cwd=cwd, env=environ, capture_output=True, text=True,
        check=False, timeout=timeout,
    )


def error_category(output: str) -> str:
   lowered = output.lower()
   if "does not exist" in lowered:
      return "MISSING_DATABASE_OBJECT"
   if "permission denied" in lowered:
      return "PERMISSION_DENIED"
   if "docker" in lowered or "container" in lowered:
      return "LOCAL_DOCKER_ERROR"
   if "error" in lowered or "failed" in lowered:
      return "CLI_ERROR"
   return "UNKNOWN_FAILURE"


def output_tail(output: str, limit: int = 2500) -> str:
   """Return the tail of a CLI output for failure diagnosis.

   A failed migration reports its own reason (the verification blocks in
   supabase/migrations raise specific messages), so the tail is what makes a
   replay failure diagnosable from the uploaded artifact alone. Any
   credential-shaped substring is redacted before it is recorded.
   """
   redacted = re.sub(r"(?i)(://[^:/\s]+:)[^@\s]+@", r"\1***@", output)
   redacted = re.sub(
      r"(?i)\b(password|secret|token|api[_-]?key|authorization)\b\s*[=:]\s*\S+",
      r"\1=***",
      redacted,
   )
   return redacted[-limit:]



def first_failing_file(output: str) -> str | None:
    matches = APPLY_PATTERN.findall(output)
    if matches:
        return matches[-1]
    files = FILE_PATTERN.findall(output)
    return files[-1] if files else None


def run_probe() -> dict[str, object]:
    environ = dict(os.environ)
    assert_offline_cli_environment(environ)
    v = subprocess.run(
        ["supabase", "--version"], capture_output=True, text=True,
        env=environ, timeout=20, check=False,
    )
    if v.returncode != 0 or CLI_VERSION not in v.stdout:
        raise RuntimeError("Pinned Supabase CLI version was not installed")
    names = sorted(p.name for p in MIGRATIONS.glob("*.sql"))
    if not names or len(names) != len(local_inventory()):
        raise RuntimeError("Tracked SQL migration inventory invalid")
    base: dict[str, object] = {
        "cli_version": CLI_VERSION,
        "scope": "isolated_unlinked_local_supabase_stack",
        "tracked_migrations": len(names),
        "remote_operation": False,
        "fresh_install_verified": False,
        "upgrade_path_verified": False,
        "live_database_modified": False,
    }
    with tempfile.TemporaryDirectory(prefix="caseproof-local-cli-") as folder:
        workdir = Path(folder).resolve()
        init = execute(["supabase", "init", "--yes"], workdir, environ, 120)
        if init.returncode:
            return base | {
                "status": "CLI_INIT_UNAVAILABLE",
                "error_category": error_category(init.stdout + init.stderr),
            }
        migrations = workdir / "supabase" / "migrations"
        migrations.mkdir(parents=True, exist_ok=True)
        try:
            # Boot first with EMPTY migrations so the local service starts.
            start = execute(["supabase", "start"], workdir, environ, 720)
            if start.returncode:
                return base | {
                    "status": "CLI_START_UNAVAILABLE",
                    "error_category": error_category(start.stdout + start.stderr),
                }
            for name in names:
                src, dst = MIGRATIONS / name, migrations / name
                shutil.copyfile(src, dst)
                if src.read_bytes() != dst.read_bytes():
                    raise RuntimeError("Migration changed in temporary workspace")
            reset = execute(
                ["supabase", "db", "reset", "--local", "--no-seed"],
                workdir, environ, 720,
            )
            output = reset.stdout + "\n" + reset.stderr
            if reset.returncode == 0:
                return base | {
                    "status": "CLI_NATURAL_ORDER_UNEXPECTED_SUCCESS",
                    "fresh_install_verified": True,
                }
            failed = first_failing_file(output)
            return base | {
                "status": (
                    "BLOCKED_CLI_NATURAL_ORDER_KNOWN_FAILURE"
                    if failed == EXPECTED_FIRST_FAILURE
                    else "BLOCKED_CLI_NATURAL_ORDER_NEW_FAILURE"
                ),
                "first_failed_migration": failed,
                "expected_first_failure": EXPECTED_FIRST_FAILURE,
                "error_category": error_category(output),
            }
        finally:
            # No link operation is ever issued in this temporary workspace.
            execute(["supabase", "stop", "--no-backup"], workdir, environ, 180)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_probe()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    # Known failure is a successful diagnostic, NOT a passing release gate.
    return 0 if result["status"] == "BLOCKED_CLI_NATURAL_ORDER_KNOWN_FAILURE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
