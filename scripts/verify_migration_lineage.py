"""Verify sourced historical migration SQL against read-only applied receipts.

This checks source provenance. It neither executes SQL nor changes migration
history, and cannot prove fresh/upgrade replay or authorize a pilot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.audit_migration_inventory import (
    ROOT,
    SNAPSHOT,
    applied_inventory,
    local_inventory,
)

LINEAGE = ROOT / "docs/security/caseproof_dev_migration_lineage_20261111.json"
STATES = {"EXACT_SOURCE", "DIVERGENT_SOURCE", "NO_SOURCE"}


def verify_lineage(
    root: Path = ROOT,
    lineage: Path = LINEAGE,
    snapshot: Path = SNAPSHOT,
) -> dict[str, object]:
    doc = json.loads(lineage.read_text(encoding="utf-8"))
    if doc.get("schema") != "caseproof-applied-migration-lineage-v1":
        raise ValueError("Invalid migration provenance manifest schema")
    if doc.get("environment") != "caseproof-dev":
        raise ValueError("Unexpected applied migration environment")
    local = local_inventory(root / "supabase/migrations")
    remote = applied_inventory(snapshot)
    expected = remote.keys() - local.keys()
    listed: set[str] = set()
    totals = {key: 0 for key in STATES}
    for item in doc["remote_only"]:
        version = item["version"]
        if version in listed or version not in expected:
            raise ValueError(f"Duplicate or no longer outstanding migration: {version}")
        listed.add(version)
        if item["name"] != remote[version] or item["statement_count"] != 1:
            raise ValueError(f"Unverified applied migration receipt: {version}")
        sha = item["recorded_sha256"]
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ValueError(f"Invalid stored SQL fingerprint: {version}")
        state = item["source_state"]
        if state not in STATES:
            raise ValueError(f"Unrecognized source class: {version}")
        totals[state] += 1
        candidate = item["candidate_path"]
        if state == "NO_SOURCE":
            if candidate is not None:
                raise ValueError(f"NO_SOURCE has a candidate: {version}")
            continue
        if not isinstance(candidate, str):
            raise ValueError(f"Missing source path: {version}")
        path = (root / candidate).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError(f"Missing or unsafe candidate file: {version}")
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        same = digest == sha
        if same != (state == "EXACT_SOURCE"):
            raise ValueError(f"SQL source provenance changed: {version}")
        if state == "EXACT_SOURCE" and len(content.decode("utf-8")) != item["recorded_chars"]:
            raise ValueError(f"SQL source length changed: {version}")
    if listed != expected:
        raise ValueError(f"Incomplete migration provenance map: {sorted(expected - listed)}")
    return {
        "status": "BLOCKED_MIGRATION_HISTORY_DRIFT",
        "remote_only_versions": len(expected),
        "local_only_versions": len(local.keys() - remote.keys()),
        "exact_source_matches": totals["EXACT_SOURCE"],
        "divergent_sources": totals["DIVERGENT_SOURCE"],
        "missing_sources": totals["NO_SOURCE"],
        "historical_source_parity_verified": True,
        "fresh_replay_verified": False,
        "live_database_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-only", action="store_true",
                        help="Return 0 for a valid audit, while keeping release status BLOCKED")
    options = parser.parse_args()
    print(json.dumps(verify_lineage(), indent=2))
    return 0 if options.report_only else 2


if __name__ == "__main__":
    raise SystemExit(main())
