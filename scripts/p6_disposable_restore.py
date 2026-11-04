"""Disposable PostgreSQL backup/restore with erasure replay and access quarantine.

This is NOT a live Supabase backup restore, and includes no real customer data.
All SQL is confined to two fixed CI-only local database names.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path

import psycopg

from scripts.verify_s2_002_database import _env


SOURCE = "caseproof_s2_ci"
TARGET = "caseproof_p6_restore_ci"


def _call(command: list[str], *, database: str, timeout: int = 90,
          backup_dir: Path | None = None) -> None:
    # Ubuntu's default pg_dump can be older than the postgres:17 service.
    # Always use the matching PostgreSQL 17 client *inside isolated CI*.
    env = {**os.environ, "PGDATABASE": database}
    client = [
        "docker", "run", "--rm", "--network", "host",
        "-e", "PGHOST", "-e", "PGPORT", "-e", "PGUSER", "-e", "PGPASSWORD",
        "-e", "PGDATABASE=" + database,
    ]
    if backup_dir is not None:
        client.extend(["--volume", str(backup_dir) + ":/caseproof-backup"])
    client.extend(["postgres:17", *command])
    result = subprocess.run(client, capture_output=True, text=True, timeout=timeout,
                            env=env, check=False)
    if result.returncode != 0:
        # Only an operation + return code. No SQL, credentials or dump bytes in logs.
        raise RuntimeError("Isolated " + command[0] + " failed (exit " +
                           str(result.returncode) + ")")


def main() -> None:
    _env()  # validates local host, service user, fixed disposable source DB
    if os.environ.get("CASEPROOF_P6_RESTORE_DISPOSABLE") != "YES":
        raise RuntimeError("Explicit P6 restore guard required")
    if os.environ.get("CI") != "true":
        raise RuntimeError("P6 restore is permitted only in disposable CI")
    # The source database already exists and has had its schema and SQL
    # authorization tests run in this job. The restored copy never serves users.
    with psycopg.connect(dbname=SOURCE, autocommit=True) as source:
        source.execute("""
            CREATE TABLE IF NOT EXISTS public.caseproof_p6_restore_probe (
                id text PRIMARY KEY, payload_digest text NOT NULL
            )
        """)
        source.execute("TRUNCATE public.caseproof_p6_restore_probe")
        source.execute("INSERT INTO public.caseproof_p6_restore_probe VALUES (%s,%s),(%s,%s)",
                       ("surviving-synthetic-source", "a" * 64,
                        "erased-synthetic-source", "b" * 64))
        counts = {}
        for name in ("document_versions", "dossier_snapshots", "dossier_releases", "erasure_receipts"):
            row = source.execute("SELECT count(*) FROM caseproof." + name).fetchone()
            assert row is not None
            counts[name] = row[0]
    with tempfile.TemporaryDirectory(prefix="caseproof-p6-backup-") as dirname:
        output = Path(dirname) / "synthetic.dump"
        started = time.monotonic()
        _call(["pg_dump", "--format=custom", "--file", "/caseproof-backup/synthetic.dump", "--no-owner",
               "--no-privileges", "--dbname", SOURCE], database=SOURCE, backup_dir=Path(dirname))
        if not output.is_file() or output.stat().st_size < 4096:
            raise AssertionError("Synthetic PostgreSQL backup missing")
        # Erasure takes effect *after* backup. The restore must be quarantined
        # until this independent synthetic erasure journal is replayed.
        with psycopg.connect(dbname=SOURCE, autocommit=True) as source:
            source.execute("DELETE FROM public.caseproof_p6_restore_probe WHERE id=%s",
                           ("erased-synthetic-source",))
        _call(["createdb", TARGET], database=SOURCE)
        try:
            _call(["pg_restore", "--no-owner", "--no-privileges", "--exit-on-error",
                   "--dbname", TARGET, "/caseproof-backup/synthetic.dump"],
                  database=TARGET, timeout=180, backup_dir=Path(dirname))
            with psycopg.connect(dbname=TARGET, autocommit=True) as target:
                # Demonstrate the actual stale-backup resurrection *before*
                # erasure replay. This is an isolated quarantine observation.
                stale = target.execute("SELECT count(*) FROM public.caseproof_p6_restore_probe WHERE id=%s",
                                       ("erased-synthetic-source",)).fetchone()
                if stale != (1,):
                    raise AssertionError("Erasure replay test did not exercise old backup")
                for name, count in counts.items():
                    result = target.execute("SELECT count(*) FROM caseproof." + name).fetchone()
                    if result is None or result[0] != count:
                        raise AssertionError("Actual CaseProof relation did not survive restore")
                target.execute("DELETE FROM public.caseproof_p6_restore_probe WHERE id=%s",
                               ("erased-synthetic-source",))
                assert target.execute("SELECT count(*) FROM public.caseproof_p6_restore_probe WHERE id=%s",
                                      ("erased-synthetic-source",)).fetchone() == (0,)
                assert target.execute("SELECT count(*) FROM public.caseproof_p6_restore_probe WHERE id=%s",
                                      ("surviving-synthetic-source",)).fetchone() == (1,)
                # Private release ledger cannot become anonymously readable
                # just because backup ownership/grants were reconstructed.
                grants = target.execute("""
                  SELECT has_table_privilege('anon','caseproof.dossier_releases','SELECT'),
                         has_table_privilege('authenticated','caseproof.dossier_releases','SELECT')
                """).fetchone()
                if grants != (False, False):
                    raise AssertionError("Restore widened direct release-table grants")
            print("P6_DISPOSABLE_POSTGRES_BACKUP_RESTORE_ERASURE_REPLAY_PASSED")
            print("P6_ACTUAL_CASEPROOF_RELATIONS_RESTORED", len(counts))
            print("P6_RESTORE_SECONDS_SYNTHETIC", round(time.monotonic() - started, 2))
            print("P6_REAL_SUPABASE_BACKUP_NOT_TESTED")
        finally:
            _call(["dropdb", "--if-exists", TARGET], database=SOURCE)
    with psycopg.connect(dbname=SOURCE, autocommit=True) as source:
        source.execute("DROP TABLE public.caseproof_p6_restore_probe")


if __name__ == "__main__":
    main()
