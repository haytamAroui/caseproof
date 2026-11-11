"""Natural-order SQL replay probe against disposable local PostgreSQL ONLY.

Attempts the actual filename-sorted source directory without skipping,
renaming, suppressing or hand-reordering any migration. This is a PostgreSQL
diagnostic, NOT a Supabase CLI fresh-install proof or migration authorization.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from scripts.audit_migration_inventory import MIGRATIONS, local_inventory
from scripts.verify_s2_002_database import SCHEMA_BOOTSTRAP, _env, _run

ROOT = Path(__file__).resolve().parents[1]
# Matches only the synthetic PostgreSQL/Supabase stubs used by the established
# disposable retention acceptance. No real provider credentials are involved.
STUBS = """
create role service_role nologin;
create schema extensions;
create extension pgcrypto with schema extensions;
alter table auth.users add column email_confirmed_at timestamptz;
create function auth.jwt() returns jsonb language sql stable as $$
 select coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb
$$;
create function auth.role() returns text language sql stable as $$
 select auth.jwt()->>'role'
$$;
grant usage on schema auth to anon,service_role;
grant execute on all functions in schema auth to anon,authenticated,service_role;
create schema supabase_migrations;
create table supabase_migrations.schema_migrations(version text primary key);
create schema storage;
create table storage.buckets(
 id text primary key,name text,public boolean,file_size_limit bigint,
 allowed_mime_types text[]
);
create table storage.objects(
 bucket_id text,name text,primary key(bucket_id,name)
);
alter table storage.objects enable row level security;
grant usage on schema storage to authenticated;
grant select,insert on storage.objects to authenticated;
"""
PG_ERROR = re.compile(r"(?m)^(?:psql:[^\n]*?:\d+:\s*)?ERROR:\s*(.*)$")


def probe_in_filename_order() -> dict[str, object]:
    env = _env()  # refuse any target other than caseproof_s2_ci on loopback
    inventory = local_inventory(MIGRATIONS)
    paths = sorted(MIGRATIONS.glob("*.sql"))
    if len(paths) != len(inventory) or not paths:
        raise RuntimeError("Invalid or missing migration files")
    _run(SCHEMA_BOOTSTRAP + STUBS, env)
    applied: list[str] = []
    for path in paths:
        # Never execute anything outside the canonical ordered source directory.
        if path.resolve().parent != MIGRATIONS.resolve():
            raise RuntimeError("Migration escaped canonical directory")
        result = subprocess.run(
            ["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-f", str(path)],
            env=env, capture_output=True, text=True, timeout=45, check=False,
        )
        if result.returncode:
            errors = PG_ERROR.findall(result.stderr)
            # Don't print complete SQL or raw stderr; failed SQL may contain data.
            error_category = errors[0][:180] if errors else "SQL execution rejected"
            return {
                "status": "BLOCKED_NATURAL_ORDER_REPLAY",
                "scope": "disposable_postgresql_stub_not_supabase_cli",
                "total_local_migrations": len(paths),
                "applied_count_before_failure": len(applied),
                "first_failed_migration": path.name,
                "error_category": error_category,
                "fresh_install_verified": False,
                "upgraded_live_schema": False,
            }
        # Reproduce the version receipt a migration runner records after each
        # successful script; several later migrations fail closed if it is absent.
        version = path.name.split("_", 1)[0]
        _run(
            f"insert into supabase_migrations.schema_migrations(version) values ('{version}');",
            env,
        )
        applied.append(path.name)
    return {
        "status": "NATURAL_ORDER_PG_PROBE_PASSED_NOT_CLI",
        "scope": "disposable_postgresql_stub_not_supabase_cli",
        "total_local_migrations": len(paths),
        "applied_count": len(applied),
        "fresh_install_verified": False,
        "upgraded_live_schema": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--diagnostic", action="store_true",
        help="Document blocker without approving release; default is a failing release gate",
    )
    args = parser.parse_args()
    # _env runs before opening output, so invalid connection settings fail closed.
    report = probe_in_filename_order()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if args.diagnostic:
        # Exit 0 means the diagnostic ran, NEVER that the release gate passed.
        return 0
    return 2  # no canonical Supabase CLI replay/upgrade proof has occurred


if __name__ == "__main__":
    raise SystemExit(main())
