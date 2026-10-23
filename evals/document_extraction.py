"""Bounded synthetic-only evaluator. --live-requesty opts into at most eight calls.

No customer paths, custom prompts, uploads or model-default selection. A live
run requires separately configured Requesty credentials/model. Default is an
explicit scripted safety/recovery check, not model performance evidence.
"""

from __future__ import annotations

import json
import time
from decimal import Decimal
from typing import Any

from application.documents.intake import DocumentIntelligence
from application.extraction.contracts import (
    ExtractionConfig,
    ExtractionError,
    ExtractionProvider,
    Scope,
    StepJournal,
    Vocabulary,
    digest,
)
from application.extraction.journal import MemoryJournal
from apps.api.requesty_extraction import RequestyProvider
from domains.construction.extraction_rules import ConstructionEvidencePolicy
from domains.finance.extraction_rules import FinanceEvidencePolicy
from evals.document_corpus import CASES
from infrastructure.parsers.limited import LimitedDocumentParser
from scripts.extraction_fixtures import SCOPE, ScriptedProvider, envelope


def evaluate(
    *,
    live: bool = False,
    journal: StepJournal | None = None,
    scope: Scope = SCOPE,
    run_id: str = "offline-eval-v1",
) -> dict[str, Any]:
    if live and (journal is None or isinstance(journal, MemoryJournal)):
        raise ExtractionError("live evaluation requires a durable scoped journal")
    live_provider = RequestyProvider.from_environment() if live else None
    rows = []
    for case in CASES:
        policy: Vocabulary = (
            ConstructionEvidencePolicy() if case.entity_kind == "variation" else FinanceEvidencePolicy()
        )
        proposal = {
            "entity_id": "E1",
            "source_id": case.case_id,
            "quote": case.quote,
            "statement": "Synthetic labeled observation",
            "slot": case.signal,
            "signal": case.signal,
            "value": case.value,
            "polarity": case.polarity,
            "relation": "supports",
        }
        provider: ExtractionProvider = (
            live_provider if live_provider else ScriptedProvider(envelope([proposal]))
        )
        parser = LimitedDocumentParser()
        document = case.captured()
        started = time.monotonic()
        result = DocumentIntelligence(
            parser, provider, journal if journal is not None else MemoryJournal(), policy
        ).run(
            scope=scope,
            run_id=run_id + ":" + case.case_id,
            documents=(document,),
            assignments=(case.assignment,),
            slots=(case.slot,),
            config=ExtractionConfig(
                topology="global_first", max_calls=2, max_output_tokens=512, repair_passes=0
            ),
        )
        # global-first requires scout+targeted; fixed four fixtures => at most 8 calls, no repair/retry.
        elapsed = time.monotonic() - started
        report = result.extraction
        atoms = report.atoms if report else ()
        anchored = [
            a
            for a in atoms
            if a.start is not None
            and a.reason not in {"step_scope_mismatch", "entity_or_claim_attribution_failed"}
        ]
        correct = [
            a
            for a in anchored
            if (a.source_id, a.entity_id, a.slot, a.signal, a.value, a.polarity, a.quote)
            == (case.case_id, "E1", case.signal, case.signal, case.value, case.polarity, case.quote)
        ]
        costs = [t["cost"] for t in report.telemetry] if report else []
        actual_cost = (
            str(sum((Decimal(v) for v in costs), Decimal(0)))
            if costs and all(v is not None for v in costs)
            else None
        )
        rows.append(
            {
                "case": case.case_id,
                "source_sha": document.source.sha256_hex,
                "parser": parser.identity,
                "provider": provider.identity,
                "model": provider.model,
                "status": result.status,
                "proposals": len(atoms),
                "exact_anchored": len(anchored),
                "exact_labeled_matches": len(correct),
                "label_recall": len(correct) / 1,
                "anchor_resolution_rate": len(anchored) / len(atoms) if atoms else None,
                "exact_label_precision": len(correct) / len(atoms) if atoms else None,
                "negative_false_validation": sum(a.state == "validated" for a in atoms)
                if case.polarity == "negative"
                else None,
                "approval_count": int(result.approved or bool(report and report.approved)),
                "elapsed_seconds": round(elapsed, 6),
                "reported_cost": actual_cost,
                "telemetry": list(report.telemetry) if report else [],
            }
        )
    return {
        "schema": "caseproof-document-eval-v1",
        "mode": "live_requesty" if live else "scripted_safety_only",
        "live_quality_measured": live and any(row["proposals"] for row in rows),
        "corpus_manifest": digest(
            [
                {
                    "case": c.case_id,
                    "sha": c.captured().source.sha256_hex,
                    "quote": c.quote,
                    "signal": c.signal,
                    "value": c.value,
                    "polarity": c.polarity,
                }
                for c in CASES
            ]
        ),
        "caveat": "Four synthetic cases, strict exact-span labels; not statistically representative customer accuracy.",
        "rows": rows,
    }


def main() -> None:
    print(json.dumps(evaluate(), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
