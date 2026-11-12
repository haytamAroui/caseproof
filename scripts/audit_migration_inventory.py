"""Compare versioned local SQL history to a READ-ONLY remote migration snapshot.

This script never connects to a database, runs SQL, alters history or approves
release. Nonzero exit is intentional when drift remains unresolved.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
SNAPSHOT = ROOT / "docs" / "security" / "caseproof_dev_applied_migrations_20261112.json"
VERSION = re.compile(r"^[0-9]{14}$")
NAME = re.compile(r"^[a-z0-9_]+$")


def _validate(version: str, name: str) -> None:
    if not VERSION.fullmatch(version) or not NAME.fullmatch(name):
        raise ValueError("Invalid migration version/name in inventory")


def local_inventory(directory: Path = MIGRATIONS) -> dict[str, str]:
    found: dict[str, str] = {}
    for file in sorted(directory.glob("*.sql")):
        if "_" not in file.stem:
            raise ValueError("Invalid migration filename")
        version, name = file.stem.split("_", 1)
        _validate(version, name)
        if version in found:
            raise ValueError("Duplicate local migration version")
        found[version] = name
    return found


def applied_inventory(path: Path = SNAPSHOT) -> dict[str, str]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != "caseproof-migration-inventory-v1":
        raise ValueError("Unrecognized migration snapshot")
    found: dict[str, str] = {}
    for row in document["applied"]:
        version, name = row["version"], row["name"]
        _validate(version, name)
        if version in found:
            raise ValueError("Duplicate remote migration version")
        found[version] = name
    return found


def compare_migration_history(
    local: dict[str, str], applied: dict[str, str]
) -> dict[str, object]:
    only_remote = [
        {"version": v, "name": applied[v]} for v in sorted(applied.keys() - local.keys())
    ]
    only_local = [
        {"version": v, "name": local[v]} for v in sorted(local.keys() - applied.keys())
    ]
    name_mismatch = [
        {"version": v, "local_name": local[v], "applied_name": applied[v]}
        for v in sorted(local.keys() & applied.keys()) if local[v] != applied[v]
    ]
    blocked = bool(only_remote or only_local or name_mismatch)
    return {
        "status": "BLOCKED_MIGRATION_HISTORY_DRIFT" if blocked else "HISTORY_INVENTORY_MATCH",
        "local_count": len(local),
        "applied_count": len(applied),
        "only_remote": only_remote,
        "only_local": only_local,
        "name_mismatch": name_mismatch,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    args = parser.parse_args()
    report = compare_migration_history(local_inventory(), applied_inventory(args.snapshot))
    print(json.dumps(report, indent=2))
    return 2 if report["status"] != "HISTORY_INVENTORY_MATCH" else 0


if __name__ == "__main__":
    raise SystemExit(main())
