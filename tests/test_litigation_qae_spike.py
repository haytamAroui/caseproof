"""Tests for ADR 0039 isolated Tier-2 QAE adversarial evaluation spike."""
from __future__ import annotations

import json
from dataclasses import asdict

import pytest

from evals.litigation_qae_spike.contracts import (
    ContentReleaseGrant,
    EntityLinkProof,
    LawyerActionState,
    ModelCandidate,
    VisualBox,
)
from evals.litigation_qae_spike.engine import (
    apply_lawyer_action,
    build_minimized_transmission,
    index_document_blocks,
    reconcile_litigation_leads,
    record_source_open,
    run_two_tier_evaluation,
    shortlist_uncited_exhibits,
    verify_and_harden_candidate,
)
from evals.litigation_qae_spike.fixtures import (
    build_case1_status_shift_reservation,
    build_case2_fr_nl_multiscalar_trap,
    build_case3_cross_exhibit_credit_note,
)
from evals.litigation_qae_spike.metrics import (
    evaluate_case_with_candidates,
    run_scripted_adversarial_benchmark,
)
from scripts.run_litigation_qae_spike import LiveSpikeError
from scripts.run_litigation_qae_spike import main as spike_cli_main


def test_case1_status_shift_and_cross_page_reservation_detected() -> None:
    fixture = build_case1_status_shift_reservation()
    res = evaluate_case_with_candidates(fixture, fixture.clean_candidates)
    p0 = res["tier2"]["p0_leads"]
    assert len(p0) == 1
    lead = p0[0]
    assert lead.rule_code == "STATUS_SHIFT_CANDIDATE"
    assert lead.epistemic_level == "mechanically_grounded_lead"
    assert lead.human_semantic_support == "NOT_ASSESSED"
    assert "SURROUNDING_NEGATION_OR_RESERVATION_DETECTED" in lead.warnings
    assert "TRUNCATED_QUOTE_OMITTED_CONTEXT_CUE" in lead.warnings
    exhibit_lead = res["tier2"]["exhibit_leads"][0]
    assert "validation préalable" in exhibit_lead.surrounding_context
    assert exhibit_lead.spanned_pages == (1,)


def test_case2_fr_nl_multiscalar_trap_blocks_false_certainty_on_mislabeled_role() -> None:
    fixture = build_case2_fr_nl_multiscalar_trap()
    mislabeled = (
        fixture.clean_candidates[0],
        ModelCandidate(
            candidate_id="adv-mislabel-paid",
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
    res = evaluate_case_with_candidates(fixture, mislabeled)
    p0 = res["tier2"]["p0_leads"]
    assert len(p0) == 1
    lead = p0[0]
    assert lead.rule_code == "BILINGUAL_SCALAR_DIFFERENCE_CANDIDATE"
    assert lead.epistemic_level == "mechanically_grounded_lead"
    assert lead.human_semantic_support == "NOT_ASSESSED"
    assert "MULTI_SCALAR_SENTENCE_ROLE_UNVERIFIED" in lead.warnings
    assert "SURROUNDING_NEGATION_OR_RESERVATION_DETECTED" in lead.warnings


def test_case3_uncited_credit_note_and_honest_coverage_denominators() -> None:
    fixture = build_case3_cross_exhibit_credit_note()
    shortlisted, excluded = shortlist_uncited_exhibits(
        cited_exhibit_ids={"piece-3"},
        reference_tokens=fixture.reference_tokens,
        documents={k: v for k, v in fixture.documents.items() if k != "brief"},
    )
    assert "piece-7" in shortlisted
    assert "piece-8" in excluded

    res = evaluate_case_with_candidates(fixture, fixture.clean_candidates)
    p0 = res["tier2"]["p0_leads"]
    assert len(p0) == 1
    assert p0[0].rule_code == "CROSS_EXHIBIT_CONFLICT_CANDIDATE"
    cov = res["coverage_manifest"]
    assert "piece-7" in cov.exhibits_read_by_qae
    assert "piece-8" in cov.excluded_by_preselection
    assert "piece-8" in cov.unread_exhibits
    assert "piece-9#p1" in cov.unreadable_ocr_pages
    assert cov.zero_p0_means_clean is False


def test_refinement1_bordereau_confirmed_still_flags_unconfirmed_entity_link() -> None:
    fixture = build_case3_cross_exhibit_credit_note()
    res = run_two_tier_evaluation(
        brief_text=fixture.brief_text,
        documents=fixture.documents,
        bordereau_entries=fixture.bordereau_entries,
        bordereau_confirmed=True,
        entity_links=(),  # No explicit entity link proof across Pièce 3 & Pièce 7
        release=fixture.release,
        selected_blocks=fixture.selected_blocks,
        provider_fn=lambda _payload: fixture.clean_candidates,
        reference_tokens=fixture.reference_tokens,
    )
    lead = res["tier2"]["p0_leads"][0]
    assert lead.entity_link_status == "unconfirmed_bordereau_insufficient"
    assert "ENTITY_LINK_UNCONFIRMED_BORDEREAU_INSUFFICIENT" in lead.warnings


def test_refinement2_cross_block_negation_and_missing_visual_boxes() -> None:
    doc = index_document_blocks(
        exhibit_id="piece-x",
        document_id="doc-x",
        version_id="v1",
        representation_id="rep-x",
        pages=[
            (1, [("La facture a été émise le 12 mars 2026", ())], False),
            (2, [("mais elle n'a jamais été payée à ce jour.", (VisualBox(2, 0.1, 0.2, 0.9, 0.3),))], False),
        ],
    )
    cand = ModelCandidate(
        candidate_id="c-cross-neg",
        exhibit_id="piece-x",
        entity_id="FAC-1",
        slot="amount_paid",
        signal="payment",
        raw_value="12 mars 2026",
        quote="La facture a été émise le 12 mars 2026",
        polarity="affirmative",
        provider="scripted",
        model="scripted-adv",
        prompt_version="spike-v1",
    )
    lead, err = verify_and_harden_candidate(cand, doc)
    assert err is None and lead is not None
    assert "SURROUNDING_NEGATION_OR_RESERVATION_DETECTED" in lead.warnings
    assert "TRUNCATED_QUOTE_OMITTED_CONTEXT_CUE" in lead.warnings
    assert lead.visual_anchor_status == "visual_anchor_unavailable"
    assert "VISUAL_ANCHOR_UNAVAILABLE" in lead.warnings


def test_refinement3_open_pdf_is_access_only_and_reject_waive_never_confirm_support() -> None:
    state = LawyerActionState(lead_id="rec-1", bound_source_sha256="a" * 64)
    opened = record_source_open(state, opened_at="2026-11-25T23:55:00Z")
    assert opened.source_opened_at == "2026-11-25T23:55:00Z"
    assert opened.human_semantic_support == "NOT_ASSESSED"

    rejected = apply_lawyer_action(opened, expected_source_sha256="a" * 64, action="reject_lead", actor_id="lawyer-1")
    waived = apply_lawyer_action(opened, expected_source_sha256="a" * 64, action="waive", actor_id="lawyer-1")
    assert rejected.human_semantic_support == "NOT_ASSESSED"
    assert waived.human_semantic_support == "NOT_ASSESSED"

    confirmed = apply_lawyer_action(
        opened, expected_source_sha256="a" * 64, action="confirm_discrepancy", actor_id="lawyer-1"
    )
    assert confirmed.human_semantic_support == "CONFIRMED_CONTRADICTED"

    with pytest.raises(ValueError, match="stale source snapshot"):
        apply_lawyer_action(opened, expected_source_sha256="b" * 64, action="qualify", actor_id="lawyer-1")


def test_refinement4_review_budget_defers_without_dropping_or_masking() -> None:
    fixture = build_case3_cross_exhibit_credit_note()
    brief_leads = []
    exhibit_leads = []
    # Two distinct factual discrepancies on the same fixture, capped to max_p0=1.
    for eid, p_cand, b_val, e_val in (
        ("FAC-2025-042", "Note de crédit / Creditnota relative à FAC-2025-042", "12 500 EUR", "2.500,00 EUR"),
        ("FAC-2025-099", "Facture FAC-2025-099 : maintenance annuelle séparée", "5 000 EUR", "3.000,00 EUR"),
    ):
        b_doc = index_document_blocks(
            exhibit_id="brief",
            document_id=f"db-{eid}",
            version_id="v1",
            representation_id=f"rb-{eid}",
            pages=[(1, [(f"Réclamation {eid} : {b_val}", (VisualBox(1, 0.1, 0.1, 0.9, 0.2),))], False)],
        )
        b_lead, _ = verify_and_harden_candidate(
            ModelCandidate("b-" + eid, "brief", eid, "amount_claimed", "claim", b_val, f"Réclamation {eid} : {b_val}", "affirmative", "s", "m", "v"),
            b_doc,
        )
        e_doc = fixture.documents["piece-7"] if eid == "FAC-2025-042" else fixture.documents["piece-3"]
        slot = "amount_claimed"
        e_lead, _ = verify_and_harden_candidate(
            ModelCandidate("e-" + eid, e_doc.exhibit_id, eid, slot, "src", e_val, p_cand, "affirmative", "s", "m", "v"),
            e_doc,
        )
        assert b_lead is not None and e_lead is not None
        brief_leads.append(b_lead)
        exhibit_leads.append(e_lead)

    p0, deferred = reconcile_litigation_leads(
        brief_leads=brief_leads,
        exhibit_leads=exhibit_leads,
        entity_links=(
            EntityLinkProof("FAC-2025-042", ("brief", "piece-7"), "explicit_reference_id", reference_token="FAC-2025-042"),
            EntityLinkProof("FAC-2025-099", ("brief", "piece-3"), "explicit_reference_id", reference_token="FAC-2025-099"),
        ),
        bordereau_confirmed=True,
        max_p0=1,
    )
    assert len(p0) == 1
    assert len(deferred) == 1
    assert deferred[0].priority == "deferred"


def test_refinement5_data_minimization_and_zero_raw_text_in_manifest() -> None:
    fixture = build_case1_status_shift_reservation()
    unauthorized = ContentReleaseGrant(
        release_id="rel-deny",
        matter_id="m-1",
        destination="eu-zero-retention-eval",
        retention_policy="unknown",
        max_total_chars=600,
        authorized=False,
    )
    with pytest.raises(PermissionError):
        build_minimized_transmission(
            documents=fixture.documents,
            selected_blocks=fixture.selected_blocks,
            release=unauthorized,
        )

    payload_items, manifest = build_minimized_transmission(
        documents=fixture.documents,
        selected_blocks=fixture.selected_blocks,
        release=fixture.release,
    )
    assert len(payload_items) == 2
    assert 0 < manifest.total_chars_sent < manifest.full_bundle_chars
    serialized = json.dumps(asdict(manifest))
    assert "envoyé pour signature" not in serialized
    assert "conseil d'administration" not in serialized


def test_tier1_byte_invariant_on_provider_crash_timeout_and_hallucination() -> None:
    fixture = build_case1_status_shift_reservation()
    off = evaluate_case_with_candidates(fixture, None)
    clean = evaluate_case_with_candidates(fixture, fixture.clean_candidates)
    crashed = evaluate_case_with_candidates(fixture, None, raise_error=TimeoutError("network_timeout"))
    assert off["tier1_digest"] == clean["tier1_digest"] == crashed["tier1_digest"]
    assert crashed["coverage_manifest"].model_status == "failed_or_unavailable"
    assert crashed["coverage_manifest"].exhibits_read_by_qae == ()


def test_live_cli_fails_closed_without_explicit_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CASEPROOF_LIVE_QAE_SPIKE", raising=False)
    monkeypatch.delenv("REQUESTY_API_KEY", raising=False)
    with pytest.raises(LiveSpikeError, match="CASEPROOF_LIVE_QAE_SPIKE"):
        spike_cli_main(["--live", "--authorize-billable-calls", "3", "--model", "eu/test", "--max-cost-usd", "0.02"])


def test_benchmark_scorecard_contains_required_metrics() -> None:
    scorecard = run_scripted_adversarial_benchmark()
    assert scorecard["billable_calls"] == 0
    assert scorecard["tier1_byte_identical_across_all_runs"] is True
    assert scorecard["summary"]["false_positives"] == 0
    assert scorecard["summary"]["missed_cases"] == 0
    assert scorecard["summary"]["review_burden_total_leads"] == 3
    assert all(scorecard["adversarial_traps"].values())
