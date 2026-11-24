"""Disposable PostgreSQL check of the PROPOSED signed-conditions SQL drafts (db/proposals), never a shared database.

Stage 1 replays the repo's reviewed dependency-ordered candidate with its stub auth/storage (scripts.disposable_replay_candidate).
Stage 2 applies the two drafts. Stage 3 runs the SQL behaviour tests (append-only, compare-and-swap, denial, recorded
history, retention purge). Passing means: the drafts apply on that stub and behave as tested. It is NOT a Supabase CLI
replay, not PostgREST/GoTrue/Storage, not an upgrade path and not a migration release. Candidate-order qualification stays
separate from canonical migration readiness."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from scripts.disposable_replay_candidate import ROOT, disposable_environment, run_candidate

DRAFTS = ("db/proposals/SIGNED_matter_conditions.sql", "db/proposals/SIGNED_matter_conditions_retention.sql")
SCOPE = "isolated_postgresql_stub_not_supabase_cli"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    env = disposable_environment()
    report: dict[str, object] = {"scope": SCOPE, "supabase_cli_verified": False, "postgrest_gotrue_storage_verified": False,
                                 "shared_database_modified": False, "drafts": list(DRAFTS)}
    replay = run_candidate()
    report["candidate_replay"] = replay.get("status")
    if replay.get("status") != "DISPOSABLE_REPLAY_CANDIDATE_PASSED_NOT_SUPABASE_CLI":
        report["status"] = "BLOCKED_CANDIDATE_REPLAY"
        report["detail"] = replay
    else:
        failed = None
        for draft in DRAFTS:
            r = subprocess.run(["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-f", str(ROOT / draft)], env=env,
                               text=True, capture_output=True, check=False, timeout=60)
            if r.returncode != 0:
                failed = {"draft": draft, "error": r.stderr[:400]}
                break
        if failed:
            report["status"], report["detail"] = "BLOCKED_DRAFT_APPLY", failed
        else:
            t = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rs", "tests/test_conditions_sql_draft_local_pg.py"],
                               cwd=ROOT, env=env, text=True, capture_output=True, check=False, timeout=300)
            skipped = " skipped" in t.stdout.splitlines()[-1]
            report["status"] = ("DRAFTS_PASSED_ON_DISPOSABLE_STUB" if t.returncode == 0 and not skipped
                                else "BLOCKED_SQL_TESTS")
            report["pytest_tail"] = t.stdout[-600:]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "DRAFTS_PASSED_ON_DISPOSABLE_STUB" else 2


if __name__ == "__main__":
    raise SystemExit(main())
