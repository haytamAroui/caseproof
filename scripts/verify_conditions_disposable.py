"""Disposable PostgreSQL behavioral check of installed Nov 24 migrations (20261124030604 & 20261124030659)
and the still-unapplied retention companion draft (db/proposals/SIGNED_matter_conditions_retention.sql),
never a shared database.

Stage 1 replays the repo's reviewed dependency-ordered candidate with its stub auth/storage
(scripts.disposable_replay_candidate), which installs 20261124030604_caseproof_signed_matter_conditions.sql
and 20261124030659_caseproof_signed_review_omission_disposition.sql from supabase/migrations/.
Stage 2 applies the companion retention draft (db/proposals/SIGNED_matter_conditions_retention.sql).
Stage 3 runs the SQL behaviour tests for conditions (append-only, compare-and-swap, denial, recorded history,
retention purge) AND 'omission' disposition (public.caseproof_dev_live_review -> _rights_legacy_live_review)
with zero skipped tests. Passing means they apply on that stub and behave as tested. It is NOT a Supabase CLI
replay, not PostgREST/GoTrue/Storage, not an upgrade path and not a migration release."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from scripts.disposable_replay_candidate import ROOT, disposable_environment, run_candidate

DRAFTS = ("db/proposals/SIGNED_matter_conditions_retention.sql",)
BEHAVIOR_TESTS = (
    "tests/test_conditions_sql_draft_local_pg.py",
    "tests/test_omission_disposition.py",
)
SCOPE = "isolated_postgresql_stub_not_supabase_cli"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    env = disposable_environment()
    report: dict[str, object] = {"scope": SCOPE, "supabase_cli_verified": False, "postgrest_gotrue_storage_verified": False,
                                 "shared_database_modified": False, "drafts": list(DRAFTS), "tests": list(BEHAVIOR_TESTS)}
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
            t = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rs", *BEHAVIOR_TESTS],
                               cwd=ROOT, env=env, text=True, capture_output=True, check=False, timeout=300)
            lines = t.stdout.splitlines()
            skipped = bool(lines) and " skipped" in lines[-1]
            report["status"] = ("DRAFTS_PASSED_ON_DISPOSABLE_STUB" if t.returncode == 0 and not skipped
                                else "BLOCKED_SQL_TESTS")
            report["pytest_tail"] = (t.stdout + "\n" + t.stderr)[-1000:]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "DRAFTS_PASSED_ON_DISPOSABLE_STUB" else 2


if __name__ == "__main__":
    raise SystemExit(main())
