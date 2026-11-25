"""Opt-in runner for the ADR 0039 isolated Tier-2 QAE adversarial evaluation spike.

Default execution is 100% scripted, makes ZERO network calls, costs $0.00, and validates
the three litigation test cases plus adversarial boundary traps and Tier-1 invariance.

Live mode (--live) fails closed unless ALL explicit budget/consent gates are satisfied:
  - CASEPROOF_LIVE_QAE_SPIKE=YES
  - REQUESTY_API_KEY (or CASEPROOF_REQUESTY_API_KEY)
  - --model <concrete provider/model>
  - --authorize-billable-calls matching exact preflight call count (len(fixtures) == 3)
  - --max-cost-usd <= 0.10
Raw brief/exhibit text is NEVER written to stdout/logs; only minimized excerpts are sent.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from collections.abc import Sequence
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.api.requesty_extraction import RequestyProvider
from evals.litigation_qae_spike.contracts import ModelCandidate, canonical_digest
from evals.litigation_qae_spike.engine import run_two_tier_evaluation
from evals.litigation_qae_spike.fixtures import SpikeCaseFixture, all_spike_fixtures
from evals.litigation_qae_spike.metrics import run_scripted_adversarial_benchmark

MAX_LIVE_COST_USD = Decimal("0.10")
MAX_OUTPUT_TOKENS = 512

_LIVE_SYSTEM_PROMPT = (
    "Extract proposed litigation claim/exhibit atoms as strict JSON: "
    '{"candidates":[{"exhibit_id":"...","entity_id":"...","slot":"contract_status|amount_paid|'
    'amount_claimed|credit_note_amount","signal":"...","raw_value":"...","quote":"exact verbatim substring",'
    '"polarity":"affirmative|negative|conditional|alleged|unknown"}]}. '
    "Only return verbatim substrings present in provided blocks. Never invent or infer."
)


class LiveSpikeError(RuntimeError):
    """Explicit fail-closed error for gated live evaluation."""


def _parse_cost_ceiling(raw: str) -> Decimal:
    try:
        val = Decimal(raw)
    except InvalidOperation as exc:
        raise LiveSpikeError("invalid --max-cost-usd decimal") from exc
    if not val.is_finite() or val <= 0 or val > MAX_LIVE_COST_USD:
        raise LiveSpikeError(f"--max-cost-usd must be > 0 and <= {MAX_LIVE_COST_USD}")
    return val


def _parse_candidates_json(raw_text: str, *, model: str, provider_id: str) -> list[ModelCandidate]:
    obj = json.loads(raw_text)
    items = obj.get("candidates")
    if not isinstance(items, list):
        raise LiveSpikeError("model reply missing candidates list")
    parsed: list[ModelCandidate] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        polarity = str(item.get("polarity") or "unknown")
        if polarity not in {"affirmative", "negative", "conditional", "alleged", "unknown"}:
            polarity = "unknown"
        parsed.append(
            ModelCandidate(
                candidate_id=f"live-{idx:03d}",
                exhibit_id=str(item.get("exhibit_id") or ""),
                entity_id=str(item.get("entity_id") or ""),
                slot=str(item.get("slot") or ""),
                signal=str(item.get("signal") or ""),
                raw_value=str(item.get("raw_value") or ""),
                quote=str(item.get("quote") or ""),
                polarity=polarity,  # type: ignore[arg-type]
                provider=provider_id,
                model=model,
                prompt_version="adr0039-live-spike-v1",
            )
        )
    return parsed


def _run_live_spike(
    *,
    fixtures: Sequence[SpikeCaseFixture],
    model: str,
    api_key: str,
    authorized_calls: int,
    max_cost_usd: Decimal,
) -> dict[str, Any]:
    if os.environ.get("CASEPROOF_LIVE_QAE_SPIKE") != "YES":
        raise LiveSpikeError("CASEPROOF_LIVE_QAE_SPIKE=YES environment opt-in required")
    if not model.strip():
        raise LiveSpikeError("--model required for live spike")
    if not api_key.strip():
        raise LiveSpikeError("REQUESTY_API_KEY or CASEPROOF_REQUESTY_API_KEY required")

    planned_calls = len(fixtures)
    if authorized_calls != planned_calls:
        raise LiveSpikeError(
            f"--authorize-billable-calls must equal exact preflight call count ({planned_calls})"
        )

    adapter = RequestyProvider(api_key=api_key, model=model)
    spent_usd = Decimal("0.00")
    rows: list[dict[str, Any]] = []
    total_tp = 0
    total_fp = 0
    total_missed = 0
    total_burden = 0
    all_tier1_invariant = True

    for fixture in fixtures:
        t0 = time.monotonic()
        off_res = run_two_tier_evaluation(
            brief_text=fixture.brief_text,
            documents=fixture.documents,
            bordereau_entries=fixture.bordereau_entries,
            bordereau_confirmed=fixture.bordereau_confirmed,
            entity_links=fixture.entity_links,
            release=fixture.release,
            selected_blocks=fixture.selected_blocks,
            provider_fn=None,
            reference_tokens=fixture.reference_tokens,
        )

        def _call_provider(
            payload_items: list[dict[str, Any]],
            *,
            case_id: str = fixture.case_id,
        ) -> list[ModelCandidate]:
            nonlocal spent_usd
            req_id = canonical_digest({"case_id": case_id, "blocks": len(payload_items), "model": model})
            reply = adapter.complete(
                _LIVE_SYSTEM_PROMPT,
                json.dumps({"blocks": payload_items}, ensure_ascii=False),
                request_id=req_id,
                max_tokens=MAX_OUTPUT_TOKENS,
            )
            if reply.cost is not None:
                spent_usd += Decimal(str(reply.cost))
                if spent_usd > max_cost_usd:
                    raise LiveSpikeError("live cost ceiling exceeded")
            return _parse_candidates_json(reply.text, model=reply.model, provider_id=reply.provider)

        res = run_two_tier_evaluation(
            brief_text=fixture.brief_text,
            documents=fixture.documents,
            bordereau_entries=fixture.bordereau_entries,
            bordereau_confirmed=fixture.bordereau_confirmed,
            entity_links=fixture.entity_links,
            release=fixture.release,
            selected_blocks=fixture.selected_blocks,
            provider_fn=_call_provider,
            reference_tokens=fixture.reference_tokens,
        )
        elapsed = round(time.monotonic() - t0, 4)
        tier1_invariant = off_res["tier1_digest"] == res["tier1_digest"]
        all_tier1_invariant = all_tier1_invariant and tier1_invariant

        tier2 = res["tier2"]
        all_leads = tier2["p0_leads"] + tier2["deferred_leads"]
        found_codes = {lead.rule_code for lead in all_leads}
        expected = set(fixture.expected_rule_codes)
        tp = len(found_codes & expected)
        fp = len(found_codes - expected)
        missed = len(expected - found_codes)
        total_tp += tp
        total_fp += fp
        total_missed += missed
        total_burden += len(all_leads)
        rows.append(
            {
                "case_id": fixture.case_id,
                "tier1_invariant": tier1_invariant,
                "true_positives": tp,
                "false_positives": fp,
                "missed_cases": missed,
                "review_burden_total_leads": len(all_leads),
                "rejected_candidates": len(tier2["rejected_candidates"]),
                "elapsed_seconds": elapsed,
                "transmission_manifest": tier2["transmission_manifest"],
                "coverage_manifest": asdict(res["coverage_manifest"]),
            }
        )

    precision = (total_tp / (total_tp + total_fp)) if (total_tp + total_fp) else None
    recall = (total_tp / (total_tp + total_missed)) if (total_tp + total_missed) else None
    return {
        "schema": "caseproof-litigation-qae-spike-v1",
        "mode": "live_requesty_annotated_synthetic",
        "model": model,
        "billable_calls": planned_calls,
        "reported_cost_usd": str(spent_usd),
        "tier1_byte_identical_across_all_runs": all_tier1_invariant,
        "summary": {
            "cases": len(rows),
            "true_positives": total_tp,
            "false_positives": total_fp,
            "missed_cases": total_missed,
            "precision": precision,
            "recall": recall,
            "review_burden_total_leads": total_burden,
        },
        "cases": rows,
        "caveat": "Small annotated synthetic cohort; measures boundary behavior and baseline cost/latency only.",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ADR 0039 isolated litigation QAE spike evaluation")
    parser.add_argument("--live", action="store_true", help="Run opt-in budgeted Requesty evaluation")
    parser.add_argument("--authorize-billable-calls", type=int, default=0)
    parser.add_argument("--model", type=str, default=os.environ.get("CASEPROOF_EXTRACTION_MODEL", ""))
    parser.add_argument("--max-cost-usd", type=str, default="0.05")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not args.live:
        print(json.dumps(run_scripted_adversarial_benchmark(), indent=2, ensure_ascii=False, allow_nan=False))
        return 0

    api_key = os.environ.get("CASEPROOF_REQUESTY_API_KEY", os.environ.get("REQUESTY_API_KEY", ""))
    result = _run_live_spike(
        fixtures=all_spike_fixtures(),
        model=args.model,
        api_key=api_key,
        authorized_calls=args.authorize_billable_calls,
        max_cost_usd=_parse_cost_ceiling(args.max_cost_usd),
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
