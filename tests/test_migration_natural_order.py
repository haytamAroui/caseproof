"""Natural-order migration diagnostic must never claim an approved deployment."""

from pathlib import Path

import pytest

from scripts.probe_migration_natural_order import MIGRATIONS, PG_ERROR, probe_in_filename_order
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
