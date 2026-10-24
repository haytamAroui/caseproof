"""Paired offline topology comparison; paid Requesty benchmark requires explicit opt-in.

All four synthetic files are held constant across strategies, but scripted responses
measure protocol/safety, NOT extraction benefit. Live mode is bounded and requires
a caller-owned durable StepJournal plus explicit billable-call consent.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from application.extraction.contracts import ExtractionError, Scope, StepJournal
from evals.document_corpus import CASES
from evals.document_extraction import evaluate
from scripts.extraction_fixtures import SCOPE

TOPOLOGIES = ("global_first", "segmented", "four_pass")
BILLABLE_CALL_CAP = len(CASES) * (2 + 1 + 4)


def compare_topologies(
    *,
    live: bool = False,
    journal: StepJournal | None = None,
    scope: Scope = SCOPE,
    run_id: str = "paired-corpus-v1",
    authorized_billable_calls: int = 0,
) -> dict[str, Any]:
    if live and authorized_billable_calls != BILLABLE_CALL_CAP:
        raise ExtractionError("explicit exact paid Requesty call cap acknowledgement required")
    results = {}
    for topology in TOPOLOGIES:
        results[topology] = evaluate(
            live=live, journal=journal, scope=scope,
            run_id=f"{run_id}:{topology}", topology=topology,
        )
    rows = {}
    for topology, report in results.items():
        cases = report["rows"]
        paid = [Decimal(str(r["reported_cost"])) for r in cases if r["reported_cost"] is not None]
        rows[topology] = {
            "exact_label_matches": sum(r["exact_labeled_matches"] for r in cases),
            "proposals": sum(r["proposals"] for r in cases),
            "cases": len(cases),
            "precision": (
                sum(r["exact_labeled_matches"] for r in cases) / sum(r["proposals"] for r in cases)
                if sum(r["proposals"] for r in cases) else None
            ),
            "recall": sum(r["exact_labeled_matches"] for r in cases) / len(cases),
            "reported_cost_total": str(sum(paid, Decimal(0))) if len(paid) == len(cases) else None,
            "elapsed_seconds": round(sum(r["elapsed_seconds"] for r in cases), 6),
            "configured_call_ceiling": report["max_calls"],
        }
    baseline = rows["global_first"]["recall"]
    return {
        "schema": "caseproof-topology-comparison-v1",
        "mode": "live_requesty_small_synthetic" if live else "scripted_safety_only",
        "live_quality_measured": live,
        "source_corpus_sha": results["global_first"]["corpus_manifest"],
        "provider_boundary": "Requesty_only" if live else "scripted_no_inference",
        "billable_call_cap": BILLABLE_CALL_CAP if live else 0,
        "strategies": rows,
        "four_pass_recall_delta": rows["four_pass"]["recall"] - baseline,
        "caveat": "Four synthetic labeled cases; not a production model-quality or economic benefit claim.",
    }


def main() -> None:
    import json

    print(json.dumps(compare_topologies(), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
