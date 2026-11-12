"""The migration audit must expose drift rather than silently accept replay."""
from __future__ import annotations

import pytest

from scripts.audit_migration_inventory import (
    applied_inventory,
    compare_migration_history,
    local_inventory,
)


def test_known_historical_drift_is_explicitly_blocked() -> None:
    local = local_inventory()
    applied = applied_inventory()
    report = compare_migration_history(local, applied)
    assert report["status"] == "BLOCKED_MIGRATION_HISTORY_DRIFT"
    assert report["local_count"] == 74
    assert report["applied_count"] == 76
    # Restoring the historically applied Phase 4 ledger eliminated one gap,
    # but timestamp and missing-SQL history must not be silently repaired.
    assert local["20261030150030"] == applied["20261030150030"]
    assert report["only_remote"]
    assert report["only_local"]


def test_exact_inventory_is_supported_and_duplicates_fail(tmp_path) -> None:
    assert compare_migration_history({"20260101000000": "test"}, {"20260101000000": "test"})["status"] == "HISTORY_INVENTORY_MATCH"
    (tmp_path / "20260101000000_first.sql").write_text("select 1;")
    (tmp_path / "20260101000000_duplicate.sql").write_text("select 2;")
    with pytest.raises(ValueError, match="Duplicate local"):
        local_inventory(tmp_path)


def test_detects_version_and_name_drifts() -> None:
    report = compare_migration_history(
        {"20260101000000": "old", "20260101000001": "local"},
        {"20260101000000": "new", "20260101000002": "remote"},
    )
    assert report["status"] == "BLOCKED_MIGRATION_HISTORY_DRIFT"
    assert len(report["name_mismatch"]) == 1
    assert len(report["only_remote"]) == 1
    assert len(report["only_local"]) == 1
