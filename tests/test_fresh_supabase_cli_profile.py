"""Source-preserving local CLI baseline: deterministic, complete and isolated."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.fresh_supabase_cli_profile import (
    copy_exact_sources,
    temporary_aliases,
    validate_environment,
)


def test_all_sources_have_deterministic_ordered_temp_aliases() -> None:
    pairs = temporary_aliases()
    assert len(pairs) == 73
    assert len(set(alias for _, alias in pairs)) == 73
    assert [name for _, name in pairs] == sorted(name for _, name in pairs)
    originals = [original.name for original, _ in pairs]
    assert originals.index("20261030140000_caseproof_phase3_private_ocr_geometry.sql") < (
        originals.index("20261030114000_m05_ocr_sidecar_cleanup_fk.sql")
    )
    assert originals[-1] == "20261106210000_caseproof_release_acknowledgement_fence.sql"
    assert all(old.name != new for old, new in pairs)


def test_sql_bytes_are_not_rewritten_and_aliases_are_immutable(tmp_path: Path) -> None:
    pairs = temporary_aliases()
    digest = copy_exact_sources(tmp_path, pairs)
    assert len(digest) == 64
    assert len(list(tmp_path.glob("*.sql"))) == 73
    for source, alias in pairs:
        assert (tmp_path / alias).read_bytes() == source.read_bytes()
        assert len(hashlib.sha256(source.read_bytes()).hexdigest()) == 64
    with pytest.raises(ValueError, match="Duplicate temporary"):
        copy_exact_sources(tmp_path, pairs)


def test_local_profile_rejects_hosted_keys_and_connection_overrides() -> None:
    base = {"CI": "true", "GITHUB_ACTIONS": "true"}
    validate_environment(base)
    for key in (
        "SUPABASE_ACCESS_TOKEN", "SUPABASE_DB_PASSWORD", "SUPABASE_PROJECT_ID",
        "SUPABASE_SERVICE_ROLE_KEY", "PGHOST", "PGHOSTADDR", "PGPASSWORD",
        "PGSERVICE", "DIRECT_URL",
    ):
        with pytest.raises(RuntimeError, match="forbidden"):
            validate_environment(base | {key: "not-local"})


def test_workflow_is_self_contained_without_secrets() -> None:
    workflow = (Path(__file__).resolve().parents[1] /
                ".github/workflows/supabase-cli-canonical-fresh.yml").read_text()
    assert "pull_request:" in workflow
    assert "supabase/setup-cli@v1" in workflow
    assert "version: 3.1.0" in workflow
    assert "secrets." not in workflow
    assert "supabase-cli-fresh-profile-evidence" in workflow


def test_cli_profile_never_claims_live_upgrade_or_pilot_approval() -> None:
    source = (Path(__file__).resolve().parents[1] /
              "scripts/fresh_supabase_cli_profile.py").read_text()
    assert '["supabase", "db", "reset", "--local", "--no-seed"]' in source
    assert '"migration_history_repaired": False' in source
    assert '"upgrade_path_verified": False' in source
    assert '"live_database_modified": False' in source
    assert '"independent_security_approval": False' in source
