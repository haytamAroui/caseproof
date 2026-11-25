"""Adversarial benchmark metrics and scorecard (scripted CI mode = 0 LLM calls)."""
from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from typing import Any

from evals.litigation_qae_spike.contracts import ModelCandidate, VisualBox
from evals.litigation_qae_spike.engine import (
    index_document_blocks,
    run_two_tier_evaluation,
    verify_and_harden_candidate,
)
from evals.litigation_qae_spike.fixtures import (
    SpikeCaseFixture,
    all_spike_fixtures,
    build_case1_status_shift_reservation,
    build_case2_fr_nl_multiscalar_trap,
)


def evaluate_case_with_candidates(
    fixture: SpikeCaseFixture,
    candidates: tuple[ModelCandidate, ...] | None,
    *,
    raise_error: BaseException | None = None,
) -> dict[str, Any]:
    """Run Tier 1 + Tier 2 with scripted or fault-injected candidates."""

    def _provider(_payload: list[dict[str, Any]]) -> list[ModelCandidate]:
        if raise_error is not None:
            raise raise_error
        return list(candidates or ())

    return run_two_tier_evaluation(
        brief_text=fixture.brief_text,
        documents=fixture.documents,
        bordereau_entries=fixture.bordereau_entries,
        bordereau_confirmed=fixture.bordereau_confirmed,
        entity_links=fixture.entity_links,
        release=fixture.release,
        selected_blocks=fixture.selected_blocks,
        provider_fn=None if candidates is None and raise_error is None else _provider,
        reference_tokens=fixture.reference_tokens,
    )


def _run_adversarial_traps() -> dict[str, bool]:
    # Trap A: Mislabeled role on multi-scalar sentence (12.500 EUR labeled as amount_paid).
    c2 = build_case2_fr_nl_multiscalar_trap()
    mislabeled_candidates = (
        c2.clean_candidates[0],
        ModelCandidate(
            candidate_id="adv-multiscalar-mislabel",
            exhibit_id="piece-2",
            entity_id="FAC-2025-019",
            slot="amount_paid",
            signal="payment_source",
            raw_value="12.500,00 EUR",
            quote="Factuur FAC-2025-019 ten bedrage van 12.500,00 EUR, waarvan 2.500,00 EUR reeds betaald",
            polarity="affirmative",
            provider="scripted",
            model="scripted-adversarial",
            prompt_version="spike-v1",
        ),
    )
    res_mislabel = evaluate_case_with_candidates(c2, mislabeled_candidates)
    p0_mislabel = res_mislabel["tier2"]["p0_leads"]
    trap_multiscalar = bool(
        p0_mislabel
        and p0_mislabel[0].epistemic_level == "mechanically_grounded_lead"
        and p0_mislabel[0].human_semantic_support == "NOT_ASSESSED"
        and "MULTI_SCALAR_SENTENCE_ROLE_UNVERIFIED" in p0_mislabel[0].warnings
    )

    # Trap B: Quote truncated right before cross-block / cross-page French negation.
    neg_doc = index_document_blocks(
        exhibit_id="piece-neg",
        document_id="doc-neg",
        version_id="v1",
        representation_id="rep-neg",
        pages=[
            (1, [("Le montant de 12.500 EUR a été facturé", (VisualBox(1, 0.1, 0.2, 0.9, 0.3),))], False),
            (2, [("mais ce montant n'a jamais été payé.", (VisualBox(2, 0.1, 0.2, 0.9, 0.3),))], False),
        ],
    )
    truncated_cand = ModelCandidate(
        candidate_id="adv-truncated-neg",
        exhibit_id="piece-neg",
        entity_id="E-NEG",
        slot="amount_paid",
        signal="payment",
        raw_value="12.500 EUR",
        quote="Le montant de 12.500 EUR a été facturé",
        polarity="affirmative",
        provider="scripted",
        model="scripted-adversarial",
        prompt_version="spike-v1",
    )
    neg_lead, _ = verify_and_harden_candidate(truncated_cand, neg_doc)
    trap_cross_block_neg = bool(
        neg_lead is not None
        and "SURROUNDING_NEGATION_OR_RESERVATION_DETECTED" in neg_lead.warnings
        and "TRUNCATED_QUOTE_OMITTED_CONTEXT_CUE" in neg_lead.warnings
    )

    # Trap C: Tier-1 byte invariance across clean, mislabel, hallucinated quote, and provider crash.
    c1 = build_case1_status_shift_reservation()
    d_off = evaluate_case_with_candidates(c1, None)["tier1_digest"]
    d_clean = evaluate_case_with_candidates(c1, c1.clean_candidates)["tier1_digest"]
    hallucinated = (
        c1.clean_candidates[0],
        ModelCandidate(
            candidate_id="adv-hallucinated",
            exhibit_id="piece-1",
            entity_id="CTR-2026-01",
            slot="contract_status",
            signal="contract_status_source",
            raw_value="signed",
            quote="phrase inventée qui n'existe pas",
            polarity="affirmative",
            provider="scripted",
            model="scripted-adversarial",
            prompt_version="spike-v1",
        ),
    )
    d_hallucinated = evaluate_case_with_candidates(c1, hallucinated)["tier1_digest"]
    d_crash = evaluate_case_with_candidates(
        c1, None, raise_error=TimeoutError("simulated_provider_timeout")
    )["tier1_digest"]
    trap_tier1_invariance = len({d_off, d_clean, d_hallucinated, d_crash}) == 1

    return {
        "multiscalar_mislabel_flagged_never_proven": trap_multiscalar,
        "cross_block_truncated_negation_caught": trap_cross_block_neg,
        "tier1_byte_identical_across_all_runs": trap_tier1_invariance,
    }


def run_scripted_adversarial_benchmark() -> dict[str, Any]:
    """Execute the deterministic 3-case benchmark + adversarial boundary traps ($0)."""
    case_rows: list[dict[str, Any]] = []
    total_tp = 0
    total_fp = 0
    total_missed = 0
    total_burden = 0

    for fixture in all_spike_fixtures():
        off_res = evaluate_case_with_candidates(fixture, None)
        res = evaluate_case_with_candidates(fixture, fixture.clean_candidates)
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
        manifest = tier2["transmission_manifest"]
        coverage = asdict(res["coverage_manifest"])
        case_rows.append(
            {
                "case_id": fixture.case_id,
                "tier1_invariant": off_res["tier1_digest"] == res["tier1_digest"],
                "true_positives": tp,
                "false_positives": fp,
                "missed_cases": missed,
                "review_burden_total_leads": len(all_leads),
                "p0_leads": len(tier2["p0_leads"]),
                "deferred_leads": len(tier2["deferred_leads"]),
                "rejected_candidates": len(tier2["rejected_candidates"]),
                "transmission_chars_sent": manifest["total_chars_sent"],
                "full_bundle_chars": manifest["full_bundle_chars"],
                "coverage_manifest": coverage,
            }
        )

    traps = _run_adversarial_traps()
    precision = (total_tp / (total_tp + total_fp)) if (total_tp + total_fp) else None
    recall = (total_tp / (total_tp + total_missed)) if (total_tp + total_missed) else None

    return {
        "schema": "caseproof-litigation-qae-spike-v1",
        "mode": "scripted_adversarial_boundary_only",
        "billable_calls": 0,
        "reported_cost_usd": str(Decimal("0.00")),
        "tier1_byte_identical_across_all_runs": (
            all(r["tier1_invariant"] for r in case_rows)
            and traps["tier1_byte_identical_across_all_runs"]
        ),
        "summary": {
            "cases": len(case_rows),
            "true_positives": total_tp,
            "false_positives": total_fp,
            "missed_cases": total_missed,
            "precision": precision,
            "recall": recall,
            "review_burden_total_leads": total_burden,
        },
        "adversarial_traps": traps,
        "cases": case_rows,
        "caveat": (
            "Scripted synthetic adversarial evaluation validating mechanical boundaries, data minimization, "
            "coverage disclosure, and Tier-1 invariance only. Zero live LLM calls; not clinical/legal "
            "precision proof or customer-readiness acceptance."
        ),
    }
