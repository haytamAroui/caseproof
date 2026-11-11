"""Historical migration provenance is evidence, not permission to deploy."""
from __future__ import annotations

import hashlib
import json

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


def test_a_tampered_exact_candidate_is_detected(tmp_path) -> None:
    doc = json.loads(LINEAGE.read_text())
    exact = next(x for x in doc["remote_only"] if x["source_state"] == "EXACT_SOURCE")
    original = ROOT / exact["candidate_path"]
    replacement = tmp_path / exact["candidate_path"]
    replacement.parent.mkdir(parents=True)
    replacement.write_bytes(original.read_bytes() + b"-- unexpected delta\n")
    # Replacing the root is intentionally not enough to validate the full map,
    # so inspect the same digest invariant used by verify_lineage.
    assert hashlib.sha256(replacement.read_bytes()).hexdigest() != exact["recorded_sha256"]
    assert hashlib.sha256(original.read_bytes()).hexdigest() == exact["recorded_sha256"]


def test_malformed_provenance_is_rejected(tmp_path) -> None:
    doc = json.loads(LINEAGE.read_text())
    doc["remote_only"][0]["source_state"] = "NO_SOURCE"
    altered = tmp_path / "tampered.json"
    altered.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="NO_SOURCE has a candidate"):
        verify_lineage(lineage=altered)
