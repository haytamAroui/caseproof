"""Historical migration provenance is evidence, not permission to deploy."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.verify_migration_lineage import LINEAGE, ROOT, verify_lineage


def test_all_nineteen_unmatched_receipts_are_adjudicated() -> None:
    report = verify_lineage()
    assert report["status"] == "BLOCKED_MIGRATION_HISTORY_DRIFT"
    assert report["remote_only_versions"] == 19
    assert report["local_only_versions"] == 18
    assert report["exact_source_matches"] == 12
    assert report["divergent_sources"] == 4
    assert report["missing_sources"] == 3
    assert report["fresh_replay_verified"] is False


def test_a_tampered_exact_candidate_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = json.loads(LINEAGE.read_text())
    exact = next(x for x in doc["remote_only"] if x["source_state"] == "EXACT_SOURCE")
    original = (ROOT / exact["candidate_path"]).resolve()
    actual_read_bytes = Path.read_bytes

    def tamper(path: Path) -> bytes:
        content = actual_read_bytes(path)
        if path.resolve() == original:
            return content + b"-- unexpected migration change\\n"
        return content

    monkeypatch.setattr(Path, "read_bytes", tamper)
    with pytest.raises(ValueError, match="SQL source provenance changed"):
        verify_lineage()


def test_malformed_provenance_is_rejected(tmp_path) -> None:
    doc = json.loads(LINEAGE.read_text())
    doc["remote_only"][0]["source_state"] = "NO_SOURCE"
    altered = tmp_path / "tampered.json"
    altered.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="NO_SOURCE has a candidate"):
        verify_lineage(lineage=altered)
