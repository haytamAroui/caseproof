"""Tests for the synthetic 5-dossier Belgian FR/NL M5 benchmark harness (W3-03)."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.run_m5_fr_nl_benchmark import main, run_benchmark


def test_five_dossier_fr_nl_benchmark_catches_all_traps_with_zero_false_alarms() -> None:
    report = run_benchmark()
    assert report["synthetic_benchmark"] is True
    assert report["not_practitioner_m5_signoff"] is True
    assert report["dossier_count"] == 5
    assert report["seeded_traps_total"] == 6
    assert report["caught_traps_total"] == 6
    assert report["false_alarms_total"] == 0

    clean = next(d for d in report["dossiers"] if d["is_clean_control"])
    assert clean["false_alarms"] == 0


def test_benchmark_cli_writes_json_report(tmp_path: Path) -> None:
    out = tmp_path / "m5-bench.json"
    assert main(["--json-out", str(out)]) == 0
    parsed = json.loads(out.read_text(encoding="utf-8"))
    assert parsed["caught_traps_total"] == parsed["seeded_traps_total"]
    assert parsed["false_alarms_total"] == 0
