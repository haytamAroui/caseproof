"""A real Supabase CLI probe must never reach hosted databases."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.probe_supabase_cli_local import (
    EXPECTED_FIRST_FAILURE,
    assert_offline_cli_environment,
    error_category,
    execute,
    first_failing_file,
)


def test_cli_probe_requires_isolated_ci() -> None:
    with pytest.raises(RuntimeError, match="GitHub Actions"):
        assert_offline_cli_environment({"CI": "true"})
    assert_offline_cli_environment({"CI": "true", "GITHUB_ACTIONS": "true"})


def test_remote_credentials_and_routing_are_rejected() -> None:
    clean = {"CI": "true", "GITHUB_ACTIONS": "true"}
    for key in ("SUPABASE_ACCESS_TOKEN", "SUPABASE_DB_PASSWORD", "DATABASE_URL",
                "PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE"):
        with pytest.raises(RuntimeError, match="forbidden"):
            assert_offline_cli_environment(clean | {key: "unsafe"})


def test_hosted_cli_commands_are_blocked_before_execution(tmp_path: Path) -> None:
    for args in (
        ["supabase", "db", "reset", "--linked"],
        ["supabase", "db", "reset", "--remote"],
        ["supabase", "db", "reset", "--db-url", "fake"],
        ["supabase", "migration", "repair"],
    ):
        with pytest.raises(RuntimeError, match="forbidden"):
            execute(args, tmp_path, {}, 1)


def test_known_error_extracts_exact_filename() -> None:
    output = (
        "Applying migration 20261030113000_m05_test_run_registry.sql...\n"
        f"Applying migration {EXPECTED_FIRST_FAILURE}...\n"
        "ERROR: relation caseproof.ocr_geometry_sidecars does not exist\n"
    )
    assert first_failing_file(output) == EXPECTED_FIRST_FAILURE
    assert error_category(output) == "MISSING_DATABASE_OBJECT"


def test_only_local_version_pinned_workflow_is_allowed() -> None:
    workflow = (Path(__file__).resolve().parents[1] /
                ".github/workflows/supabase-cli-local-replay.yml").read_text()
    assert "supabase/setup-cli@v1" in workflow
    assert "version: 3.1.0" in workflow
    assert "secrets." not in workflow
    assert "pull_request:" in workflow
    source = (Path(__file__).resolve().parents[1] /
              "scripts/probe_supabase_cli_local.py").read_text()
    assert '["supabase", "db", "reset", "--local", "--no-seed"]' in source
    assert '"remote_operation": False' in source
    assert '"live_database_modified": False' in source
