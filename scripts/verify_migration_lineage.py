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
    recovered_receipts = 0
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
        receipt = item.get("applied_receipt_path")
        if state == "EXACT_SOURCE":
            if receipt is not None or item.get("applied_receipt_verified"):
                raise ValueError(f"Exact source must not have a second receipt: {version}")
        else:
            if not isinstance(receipt, str) or not receipt.startswith("db/historical_applied/"):
                raise ValueError(f"Missing archived SQL receipt: {version}")
            expected_receipt = f"db/historical_applied/{version}_{remote[version]}.sql"
            if receipt != expected_receipt or item.get("applied_receipt_verified") is not True:
                raise ValueError(f"Receipt version or name changed: {version}")
            recovered_path = (root / receipt).resolve()
            if not recovered_path.is_relative_to(root.resolve()) or not recovered_path.is_file():
                raise ValueError(f"Missing or unsafe recovered SQL: {version}")
            recovered = recovered_path.read_bytes()
            if hashlib.sha256(recovered).hexdigest() != sha:
                raise ValueError(f"Archived SQL receipt tampered: {version}")
            if len(recovered.decode("utf-8")) != item["recorded_chars"]:
                raise ValueError(f"Archived SQL receipt length changed: {version}")
            recovered_receipts += 1
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
    matched_versions = remote.keys() & local.keys()
    shared = doc.get("matching_version_receipts")
    if not isinstance(shared, list):
        raise ValueError("Missing matching-version migration fingerprints")
    seen_shared: set[str] = set()
    exact_shared = 0
    divergent_shared = 0
    for entry in shared:
        version = entry["version"]
        name = entry["name"]
        if (version in seen_shared or version not in matched_versions
                or remote[version] != name or local[version] != name):
            raise ValueError(f"Unexpected shared-version migration: {version}")
        seen_shared.add(version)
        expected_path = f"supabase/migrations/{version}_{name}.sql"
        if entry["source_path"] != expected_path:
            raise ValueError(f"Unexpected source filename: {version}")
        path = (root / expected_path).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError(f"Missing same-version SQL: {version}")
        content = path.read_bytes()
        sha = entry["recorded_sha256"]
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ValueError(f"Invalid same-version SQL digest: {version}")
        exact = hashlib.sha256(content).hexdigest() == sha
        if entry["source_state"] == "EXACT_SOURCE":
            if not exact or entry.get("applied_receipt_path") is not None:
                raise ValueError(f"Same-version SQL source drift: {version}")
            exact_shared += 1
        elif entry["source_state"] == "DIVERGENT_SOURCE":
            if exact:
                raise ValueError(f"Unexpected source equivalence: {version}")
            expected_receipt = f"db/historical_applied/{version}_{name}.sql"
            if entry.get("applied_receipt_path") != expected_receipt:
                raise ValueError(f"Missing divergent same-version receipt: {version}")
            path = (root / expected_receipt).resolve()
            if not path.is_relative_to(root.resolve()) or not path.is_file():
                raise ValueError(f"Missing archived same-version SQL: {version}")
            archive = path.read_bytes()
            if hashlib.sha256(archive).hexdigest() != sha:
                raise ValueError(f"Applied same-version SQL receipt tampered: {version}")
            if len(archive.decode("utf-8")) != entry["recorded_chars"]:
                raise ValueError(f"Archived same-version SQL length changed: {version}")
            divergent_shared += 1
        else:
            raise ValueError(f"Unknown shared-version source state: {version}")
        if exact and len(content.decode("utf-8")) != entry["recorded_chars"]:
            raise ValueError(f"Same-version SQL length changed: {version}")
    if seen_shared != matched_versions:
        raise ValueError(f"Incomplete same-version history: {sorted(matched_versions - seen_shared)}")
    return {
        "status": "BLOCKED_MIGRATION_HISTORY_DRIFT",
        "remote_only_versions": len(expected),
        "local_only_versions": len(local.keys() - remote.keys()),
        "exact_source_matches": totals["EXACT_SOURCE"],
        "divergent_sources": totals["DIVERGENT_SOURCE"],
        "missing_sources": totals["NO_SOURCE"],
        "historical_source_parity_verified": True,
        "recovered_applied_sql_receipts": recovered_receipts,
        "all_unmatched_applied_sql_locatable": recovered_receipts + totals["EXACT_SOURCE"] == len(expected),
        "matching_version_receipts_checked": len(matched_versions),
        "matching_version_exact_sql": exact_shared,
        "matching_version_divergent_sql": divergent_shared,
        "all_applied_sql_receipts_locatable": (
            recovered_receipts + totals["EXACT_SOURCE"] + exact_shared + divergent_shared
            == len(remote)
        ),
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
