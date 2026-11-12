"""Historical applied SQL receipts must be replayable without source invention."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.probe_historical_74_upgrade import (
    PR204,
    copy_historical_sql,
    historical_sources,
)


def test_all_74_deployed_original_sql_sources_are_fingerprint_verified() -> None:
    records = historical_sources()
    assert len(records) == 74
    assert [name for name, _, _ in records] == sorted(x[0] for x in records)
    assert len(set(name for name, _, _ in records)) == 74
    for filename, source, expected in records:
        assert filename.endswith(".sql")
        assert hashlib.sha256(source.read_bytes()).hexdigest() == expected
    assert PR204.name not in [row[0] for row in records]


def test_divergent_source_comes_from_recovered_original() -> None:
    rows = historical_sources()
    rights = next(x for x in rows if x[0].startswith("20261106092710_"))
    assert rights[1].as_posix().endswith(
        "db/historical_applied/20261106092710_caseproof_data_rights_ledger_shadow.sql"
    )
    docx = [r for r in rows if "document_wide_docx_editor_dev_authorization" in r[0]]
    assert len(docx) == 1
    assert "/historical_applied/" in docx[0][1].as_posix()


def test_historical_profiles_are_exact_and_do_not_change_repo(tmp_path: Path) -> None:
    sources = historical_sources()
    digest = copy_historical_sql(tmp_path, sources)
    assert len(digest) == 64
    assert len(list(tmp_path.glob("*.sql"))) == 74
    for name, original, _ in sources:
        assert (tmp_path / name).read_bytes() == original.read_bytes()
    with pytest.raises(ValueError, match="Duplicate historical"):
        copy_historical_sql(tmp_path, sources)


def test_only_real_local_upgrade_commands_are_used() -> None:
    source = (Path(__file__).resolve().parents[1] /
              "scripts/probe_historical_74_upgrade.py").read_text()
    assert '["supabase", "db", "reset", "--local", "--no-seed"]' in source
    assert '["supabase", "migration", "up", "--local"]' in source
    assert '"remote_database_modified": False' in source
    assert '"real_dev_schema_parity_verified": False' in source
    assert '"release_deployment_authorized": False' in source
    workflow = (Path(__file__).resolve().parents[1] /
                ".github/workflows/historical-74-upgrade-cli.yml").read_text()
    assert "version: 3.1.0" in workflow
    assert "secrets." not in workflow
    assert "pull_request:" in workflow
