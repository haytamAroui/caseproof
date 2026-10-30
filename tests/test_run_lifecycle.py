"""Offline tests for M0.5 fixture ownership primitives."""
from pathlib import Path
from uuid import UUID

import pytest

from tests.fixtures.run_lifecycle import ROLES, RunManifest, credentials, new_run_id


def test_unique_run_credentials():
    first, second = new_run_id(), new_run_id()
    assert first != second
    for run_id in (first, second):
        UUID(run_id)
        actors = credentials(run_id)
        assert set(actors) == set(ROLES)
        assert len({email for email, _ in actors.values()}) == 3
        assert len({password for _, password in actors.values()}) == 3
        assert all(run_id in email for email, _ in actors.values())
    assert set(x[0] for x in credentials(first).values()).isdisjoint(
        x[0] for x in credentials(second).values()
    )


def test_manifest_roundtrip_and_strict_fields(tmp_path: Path):
    manifest = RunManifest(new_run_id())
    manifest.users["owner"] = new_run_id()
    path = tmp_path / "run.json"
    manifest.save(path)
    restored = RunManifest.load(path)
    assert restored == manifest
    assert path.stat().st_mode & 0o077 == 0


def test_invalid_run_rejected():
    with pytest.raises(ValueError):
        credentials("not-a-run")
