"""Natural-order migration diagnostic must never claim an approved deployment."""

from pathlib import Path

import pytest

from scripts.probe_migration_natural_order import (
    MIGRATIONS,
    PG_ERROR,
    matches_expected_blocker,
    probe_in_filename_order,
)
from scripts.verify_s2_002_database import _env


def test_probe_denies_non_disposable_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASEPROOF_DISPOSABLE_DB", "YES")
    monkeypatch.setenv("PGDATABASE", "caseproof_s2_ci")
    monkeypatch.setenv("PGUSER", "postgres")
    monkeypatch.setenv("PGHOST", "db.caseproof-dev.supabase.co")
    with pytest.raises(RuntimeError, match="Refusing"):
        _env()
    with pytest.raises(RuntimeError, match="Refusing"):
        probe_in_filename_order()


def test_probe_denies_missing_explicit_disposable_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CASEPROOF_DISPOSABLE_DB", raising=False)
    with pytest.raises(RuntimeError, match="explicit disposable DB"):
        _env()


def test_probe_is_true_natural_order_and_reports_blocked_state() -> None:
    source = (Path(__file__).resolve().parents[1] / "scripts/probe_migration_natural_order.py").read_text()
    assert 'paths = sorted(MIGRATIONS.glob("*.sql"))' in source
    assert "subprocess.run(" in source
    assert '"ON_ERROR_STOP=1"' in source
    assert "BLOCKED_NATURAL_ORDER_REPLAY" in source
    assert '"fresh_install_verified": False' in source
    assert '"upgraded_live_schema": False' in source
    assert "for path in paths:" in source
    assert MIGRATIONS.is_dir()
    assert len(list(MIGRATIONS.glob("*.sql"))) >= 73


def test_error_category_extracts_postgres_failure_without_sql_echo() -> None:
    example = "psql:/tmp/test.sql:2: ERROR: relation does not exist"
    assert PG_ERROR.findall(example) == ["relation does not exist"]


def test_disposable_workflow_runs_diagnostic_separately() -> None:
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/retention-disposable.yml").read_text()
    assert "natural-order-diagnostic:" in workflow
    assert "python -m scripts.probe_migration_natural_order --diagnostic" in workflow
    assert "caseproof_s2_ci" in workflow
    assert "postgres:17" in workflow
    assert "CASEPROOF_DEV_AUTH_ADMIN_KEY" not in workflow


def test_expected_known_blocker_is_explicitly_pinned() -> None:
    known = {
        "status": "BLOCKED_NATURAL_ORDER_REPLAY",
        "first_failed_migration": "20261030114000_m05_ocr_sidecar_cleanup_fk.sql",
    }
    assert matches_expected_blocker(known, "20261030114000_m05_ocr_sidecar_cleanup_fk.sql")
    assert not matches_expected_blocker(known, "other_migration.sql")
    assert not matches_expected_blocker({"status": "NATURAL_ORDER_PG_PROBE_PASSED_NOT_CLI"}, "20261030114000_m05_ocr_sidecar_cleanup_fk.sql")


def test_sidecar_migration_precedes_its_table_creator_in_local_history() -> None:
    cleanup = MIGRATIONS / "20261030114000_m05_ocr_sidecar_cleanup_fk.sql"
    creator = MIGRATIONS / "20261030140000_caseproof_phase3_private_ocr_geometry.sql"
    assert cleanup.name < creator.name
    assert "alter table caseproof.ocr_geometry_sidecars" in cleanup.read_text()
    assert "create table if not exists caseproof.ocr_geometry_sidecars" in creator.read_text()
    historical = (
        Path(__file__).resolve().parents[1]
        / "db/historical_applied/20261030111946_m05_test_run_registry_and_ocr_cleanup.sql"
    )
    assert "alter table caseproof.ocr_geometry_sidecars" in historical.read_text()

def test_probe_refuses_libpq_hostaddr_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASEPROOF_DISPOSABLE_DB", "YES")
    monkeypatch.setenv("PGHOST", "127.0.0.1")
    monkeypatch.setenv("PGHOSTADDR", "203.0.113.10")
    monkeypatch.setenv("PGDATABASE", "caseproof_s2_ci")
    monkeypatch.setenv("PGUSER", "postgres")
    monkeypatch.setenv("PGPORT", "5432")
    with pytest.raises(RuntimeError, match="alternate PostgreSQL host address"):
        probe_in_filename_order()


def test_probe_refuses_libpq_service_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASEPROOF_DISPOSABLE_DB", "YES")
    monkeypatch.setenv("PGHOST", "127.0.0.1")
    monkeypatch.delenv("PGHOSTADDR", raising=False)
    monkeypatch.setenv("PGSERVICE", "remote_provider")
    monkeypatch.setenv("PGDATABASE", "caseproof_s2_ci")
    monkeypatch.setenv("PGUSER", "postgres")
    monkeypatch.setenv("PGPORT", "5432")
    with pytest.raises(RuntimeError, match="connection service override"):
        probe_in_filename_order()
