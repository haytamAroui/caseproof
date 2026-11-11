"""Candidate SQL replay is a bounded disposable experiment, not release approval."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.audit_migration_inventory import MIGRATIONS
from scripts.disposable_replay_candidate import (
    PLAN,
    disposable_environment,
    replay_plan,
)


def test_candidate_is_complete_and_exactly_pinned() -> None:
    ordered = replay_plan()
    source = sorted(MIGRATIONS.glob("*.sql"))
    assert len(ordered) == len(source) == 73
    assert set(ordered) == set(source)
    assert len(ordered) == len(set(ordered))
    manifest = json.loads(PLAN.read_text())
    assert manifest["expected_sorted_files"] == [p.name for p in source]
    assert len(manifest["deferred_suffix"]) == 22


def test_known_ocr_table_dependency_is_ordered_correctly() -> None:
    names = [p.name for p in replay_plan()]
    assert names.index("20261030140000_caseproof_phase3_private_ocr_geometry.sql") < names.index(
        "20261030114000_m05_ocr_sidecar_cleanup_fk.sql"
    )


def test_candidate_does_not_silently_admit_new_migration(tmp_path: Path) -> None:
    document = json.loads(PLAN.read_text())
    document["expected_sorted_files"] = document["expected_sorted_files"][:-1]
    edited = tmp_path / "candidate.json"
    edited.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="Migration files"):
        replay_plan(edited)


def test_candidate_rejects_duplicate_deferred_item(tmp_path: Path) -> None:
    document = json.loads(PLAN.read_text())
    document["deferred_suffix"].append(document["deferred_suffix"][0])
    edited = tmp_path / "candidate.json"
    edited.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="Migration files"):
        replay_plan(edited)


def test_candidate_enforces_loopback_and_no_libpq_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASEPROOF_DISPOSABLE_DB", "YES")
    monkeypatch.setenv("PGHOST", "127.0.0.1")
    monkeypatch.setenv("PGDATABASE", "caseproof_s2_ci")
    monkeypatch.setenv("PGUSER", "postgres")
    monkeypatch.setenv("PGPORT", "5432")
    monkeypatch.delenv("PGSERVICE", raising=False)
    monkeypatch.delenv("PGSERVICEFILE", raising=False)
    monkeypatch.delenv("PGHOSTADDR", raising=False)
    monkeypatch.delenv("PGPASSFILE", raising=False)
    monkeypatch.delenv("PGSYSCONFDIR", raising=False)
    monkeypatch.setenv("PGHOSTADDR", "203.0.113.99")
    with pytest.raises(RuntimeError, match="alternate PostgreSQL host address"):
        disposable_environment()
    monkeypatch.delenv("PGHOSTADDR", raising=False)
    monkeypatch.setenv("PGSERVICE", "remote_connection")
    with pytest.raises(RuntimeError, match="service override"):
        disposable_environment()


def test_candidate_does_not_claim_supabase_fresh_install() -> None:
    source = (Path(__file__).resolve().parents[1] / "scripts/disposable_replay_candidate.py").read_text()
    assert '"supabase_cli_fresh_install_verified": False' in source
    assert '"upgrade_path_verified": False' in source
    assert '"live_database_modified": False' in source
