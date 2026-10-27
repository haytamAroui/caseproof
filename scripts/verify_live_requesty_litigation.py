"""Opt-in, low-budget LIVE Requesty smoke: NL / FR / EN synthetic litigation excerpts.

This is a provider connectivity + candidate quality evaluation, NOT an approval,
legal-fact verdict, tenant integration, durable audit or production benchmark.
No real client content, model response, API token or JWT is logged or uploaded.
The only network request is the production Requesty-only adapter.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from application.extraction.contracts import (
    ClaimSlot,
    EntityScope,
    ExtractionConfig,
    ExtractionError,
    ExtractionProvider,
    ExtractionRequest,
    OutcomeUnknown,
    ProviderRejected,
    ProviderReply,
)
from application.extraction.journal import MemoryJournal
from application.extraction.pipeline import EvidenceIntelligence
from apps.api.requesty_extraction import RequestyProvider
from scripts.extraction_fixtures import SCOPE, source

# At most three POSTs, one per language. No retry, repair or parallel dispatch.
MAX_CALLS = 3
MAX_OUTPUT_TOKENS = 384
MAX_SOURCE_CHARS = 320
MAX_REPORTED_USD = Decimal("0.02")
RESULT_PATH = Path("requesty-smoke-result.json")
PROJECT = "caseproof-model-smoke-v1"


@dataclass(frozen=True)
class Fixture:
    lang: str
    text: str
    expected_value: str


FIXTURES = (
    Fixture("nl", "Het dossier vermeldt: betaling van EUR 125,00 bevestigd op 12 mei 2026.", "125,00"),
    Fixture("fr", "Le dossier indique : paiement de EUR 125,00 confirmé le 12 mai 2026.", "125,00"),
    Fixture("en", "The file states: payment of EUR 125.00 confirmed on 12 May 2026.", "125.00"),
)


class LiveProbeError(ValueError):
    """Generic non-secret smoke test failure code."""


class SmokeLiteralPolicy:
    """Probe-only lexicon. Never assert legal truth or deploy as dispute policy."""

    namespace = "synthetic-legal-smoke"
    version = PROJECT
    signals = ("amount_mentioned",)

    def validate(
        self, signal: str, slot: str, quote: str, value: str, kind: str
    ) -> tuple[str, str]:
        if signal != "amount_mentioned" or slot != signal or kind != "synthetic_legal_note":
            return "rejected", "probe_schema_or_kind_mismatch"
        # This probe tests exact scalar extraction, not merely whether the
        # model echoed a full source sentence containing the expected number.
        if not re.fullmatch(r"\d{1,6}[.,]\d{2}", value):
            return "rejected", "probe_non_scalar_amount"
        if value not in quote:
            return "rejected", "probe_value_not_in_exact_quote"
        if not re.search(r"\b(?:betaling|paiement|payment)\b", quote, re.IGNORECASE):
            return "needs_review", "probe_context_unrecognized"
        return "validated", "probe_exact_literal_candidate"


def safe_provider_diagnostic(exc: Exception) -> str:
    """Return only known, non-sensitive diagnostic codes; never echo raw exceptions."""
    message = str(exc)
    if isinstance(exc, ProviderRejected):
        return (
            message if re.fullmatch(r"requesty_http_4[0-9]{2}", message)
            else "requesty_provider_rejected"
        )
    if isinstance(exc, OutcomeUnknown):
        if re.fullmatch(r"requesty_http_5[0-9]{2}", message):
            return message
        if message in {
            "requesty_http_other",
            "requesty_transport_dns",
            "requesty_transport_timeout",
            "requesty_transport_tls",
            "requesty_transport_other",
        }:
            return message
        return "requesty_outcome_unknown_unclassified"
    if isinstance(exc, ExtractionError):
        return {
            "unexpected Requesty model identity": "requesty_model_identity_mismatch",
            "incomplete Requesty completion": "requesty_incomplete_response",
            "non-extraction response": "requesty_non_extraction_response",
            "invalid Requesty response envelope": "requesty_invalid_response_envelope",
            "invalid response JSON": "requesty_invalid_response_json",
            "provider output budget exceeded": "requesty_output_budget_exceeded",
        }.get(message, "requesty_response_validation_failed")
    return "requesty_unexpected_client_exception"


class BudgetedProvider:
    """Never call a different provider, retry or exceed three bounded dispatches."""

    def __init__(self, delegate: ExtractionProvider) -> None:
        self.delegate = delegate
        self.identity = delegate.identity
        self.model = delegate.model
        self.calls = 0
        self.last_diagnostic: str | None = None

    def complete(
        self, system: str, payload: str, *, request_id: str, max_tokens: int
    ) -> ProviderReply:
        if self.calls >= MAX_CALLS or max_tokens > MAX_OUTPUT_TOKENS:
            raise LiveProbeError("provider_call_budget_exceeded")
        if len(payload) > 2400 or len(system) > 3000:
            raise LiveProbeError("unexpected_prompt_size")
        self.calls += 1  # dispatch reservation happens BEFORE network
        self.last_diagnostic = None
        try:
            return self.delegate.complete(
                system, payload, request_id=request_id, max_tokens=max_tokens
            )
        except Exception as exc:
            self.last_diagnostic = safe_provider_diagnostic(exc)
            raise


def request_for(fixture: Fixture) -> ExtractionRequest:
    if fixture.lang not in {"nl", "fr", "en"} or not 0 < len(fixture.text) <= MAX_SOURCE_CHARS:
        raise LiveProbeError("invalid_fixed_fixture")
    if fixture.expected_value not in fixture.text:
        raise LiveProbeError("gold_not_in_fixed_fixture")
    src = source("source-" + fixture.lang, fixture.text)
    return ExtractionRequest(
        scope=SCOPE,
        run_id="requesty-smoke-" + fixture.lang,
        sources=(src,),
        entities=(EntityScope("E1", "synthetic_legal_note", src.source_id,
                              0, len(src.content), True),),
        slots=(ClaimSlot("E1", "amount_mentioned", (src.source_id,)),),
        config=ExtractionConfig(
            topology="segmented", max_calls=1, max_input_chars=MAX_SOURCE_CHARS,
            max_output_tokens=MAX_OUTPUT_TOKENS, repair_passes=0, max_concurrency=1,
        ),
    )


def evaluate_fixture(fixture: Fixture, provider: ExtractionProvider) -> dict[str, Any]:
    req = request_for(fixture)
    report = EvidenceIntelligence(provider, MemoryJournal(), SmokeLiteralPolicy()).run(req)
    valid = [a for a in report.atoms
             if a.state == "validated" and a.signal == "amount_mentioned"
             and a.start is not None and a.end is not None
             and a.quote == req.sources[0].content[a.start:a.end]
             and fixture.expected_value == a.value
             and a.source_id == req.sources[0].source_id]
    counts: dict[str, int] = {}
    for atom in report.atoms:
        counts[atom.state] = counts.get(atom.state, 0) + 1
    schema_counts: dict[str, int] = {}
    for atom in report.atoms:
        for issue in atom.schema_issues:
            schema_counts[issue] = schema_counts.get(issue, 0) + 1
    reasons: dict[str, int] = {}
    for atom in report.atoms:
        if atom.state != "validated":
            reasons[atom.reason] = reasons.get(atom.reason, 0) + 1
    usage = report.telemetry
    if len(usage) > 1:
        raise LiveProbeError("unexpected_multiple_provider_calls")
    tokens_in = usage[0].get("input_tokens") if usage else None
    tokens_out = usage[0].get("output_tokens") if usage else None
    cost = usage[0].get("cost") if usage else None
    # Only typed, bounded aggregate usage is exposed. No quotes, prompts, output.
    if cost is not None:
        try:
            amount = Decimal(str(cost))
        except InvalidOperation:
            raise LiveProbeError("invalid_cost_telemetry") from None
        if not amount.is_finite() or amount < 0:
            raise LiveProbeError("invalid_cost_telemetry")
    return {
        "language": fixture.lang,
        "status": "pass" if valid and report.extraction_complete
                  else "candidate_quality_gap" if report.extraction_complete
                  else "provider_or_schema_failure",
        "validated_grounded_gold_candidates": len(valid),
        "candidate_state_counts": counts,
        "candidate_reason_counts": reasons,
        "candidate_schema_issue_counts": schema_counts,
        "failure_codes": sorted(set(row["reason"] for row in report.failures)),
        "source_verified": bool(valid),
        "human_review_required": True,
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
        "reported_usd": str(cost) if cost is not None else None,
    }


def run_probe(provider: ExtractionProvider) -> dict[str, Any]:
    guarded = BudgetedProvider(provider)
    rows: list[dict[str, Any]] = []
    spent = Decimal("0")
    budget_state = "reported_under_cap"
    for fixture in FIXTURES:
        try:
            row = evaluate_fixture(fixture, guarded)
        except OutcomeUnknown:
            row = {"language": fixture.lang, "status": "outcome_unknown"}
        except ExtractionError:
            row = {"language": fixture.lang, "status": "extraction_error"}
        # Unexpected Python/programming exceptions intentionally fail the workflow
        # with a sanitized status at the entrypoint; no unsafe automatic retries.
        if row["status"] != "pass":
            row["provider_diagnostic"] = guarded.last_diagnostic or "pipeline_or_schema_rejected"
        rows.append(row)
        # Paid response usage must be counted even when the extraction quality
        # fails; unknown cost must never be reported as a verified zero charge.
        cost = row.get("reported_usd")
        if cost is None:
            budget_state = "cost_telemetry_unavailable"
        else:
            spent += Decimal(cost)
            if spent > MAX_REPORTED_USD:
                budget_state = "reported_cost_cap_exceeded"
        if row["status"] != "pass" or budget_state != "reported_under_cap":
            break
    ok = len(rows) == len(FIXTURES) and all(r["status"] == "pass" for r in rows)
    ok = ok and budget_state == "reported_under_cap"
    return {
        "schema": PROJECT,
        "synthetic_only": True,
        "provider": provider.identity,
        "model": provider.model,
        "max_model_calls": MAX_CALLS,
        "max_output_tokens_per_call": MAX_OUTPUT_TOKENS,
        "model_calls_reserved": guarded.calls,
        "reported_total_usd": str(spent) if budget_state != "cost_telemetry_unavailable" else None,
        "cost_gate": budget_state,
        "quality_gate": "pass" if ok else "not_passed",
        "legal_decision": "not_assessed",
        "customer_ready": False,
        "cases": rows,
    }


def write_result(report: dict[str, Any]) -> None:
    RESULT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    if os.environ.get("CASEPROOF_LIVE_REQUESTY_TEST") != "YES":
        print("SKIPPED: CASEPROOF_LIVE_REQUESTY_TEST=YES required")
        return 2
    try:
        key = os.environ.get("CASEPROOF_REQUESTY_API_KEY", "")
        model = os.environ.get("CASEPROOF_EXTRACTION_MODEL", "")
        if not key or not model:
            raise LiveProbeError("protected_requesty_secret_and_model_required")
        provider = RequestyProvider(api_key=key, model=model, timeout=25)
        report = run_probe(provider)
        write_result(report)
        # Safe, compact telemetry only; never print responses/keys/quoted sources.
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0 if report["quality_gate"] == "pass" else 1
    except Exception as exc:
        # Don't trust unbounded exceptions: provider response might include secrets.
        fallback = {"schema": PROJECT, "synthetic_only": True,
                    "quality_gate": "not_passed", "failure_type": type(exc).__name__,
                    "customer_ready": False}
        write_result(fallback)
        print("CASEPROOF_LIVE_REQUESTY_TEST_FAILED: " + type(exc).__name__, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
