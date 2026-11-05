"""Pilot metadata gates and paired practitioner measurements (synthetic only)."""
from __future__ import annotations

from copy import deepcopy

import pytest

from application.pilot_readiness import (
    REQUIRED_GATES,
    PilotEvidenceError,
    load_and_validate,
    validate_register,
)
from application.pilot_study import StudyEvidenceError, assess_study

REGISTER = "docs/pilot/PILOT_EXTERNAL_GATE_REGISTER.json"


def test_external_register_is_complete_but_not_approved():
    from pathlib import Path

    result = load_and_validate(Path(REGISTER))
    assert set(result["gates_requiring_external_review"]) == set(REQUIRED_GATES)
    assert result["ready_for_human_final_decision"] is False
    assert result["machine_approves_pilot"] is False
    assert result["machine_authorizes_client_data"] is False


def _register():
    import json
    from pathlib import Path

    return json.loads(Path(REGISTER).read_text())


def test_t70_t73_preliminary_mcp_evidence_cannot_approve_pilot():
    r = _register()
    for gate in ("T70", "T73"):
        assert r["gates"][gate]["status"] == "EVIDENCED"
        assert r["gates"][gate]["evidence_ref"]
    result = validate_register(r)
    assert {"T70", "T73"} <= set(result["gates_requiring_external_review"])
    assert result["ready_for_human_final_decision"] is False
    assert result["machine_approves_pilot"] is False
    assert result["machine_authorizes_client_data"] is False


def test_evidence_reference_does_not_approve_external_security_gate():
    r = _register()
    r["gates"]["T70"]["status"] = "EVIDENCED"
    r["gates"]["T70"]["evidence_ref"] = "public-readonly-catalog"
    result = validate_register(r)
    assert "T70" in result["gates_requiring_external_review"]
    assert not result["machine_approves_pilot"]


def test_fabricated_approval_without_independent_receipt_is_denied():
    r = _register()
    r["gates"]["T70"]["status"] = "APPROVED"
    with pytest.raises(PilotEvidenceError, match="external receipt"):
        validate_register(r)


def test_machine_never_authenticates_human_signatures():
    r = _register()
    for gate in REQUIRED_GATES:
        r["gates"][gate].update(
            status="APPROVED",
            reviewer="external-person-not-verified",
            reviewed_at="2026-11-05",
            evidence_ref="private/receipt",
            independent_receipt_sha256="f" * 64,
        )
    result = validate_register(r)
    assert result["ready_for_human_final_decision"] is True
    assert result["machine_approves_pilot"] is False
    assert result["machine_authorizes_client_data"] is False
    assert len(result["claimed_approvals_not_cryptographically_verified"]) == len(REQUIRED_GATES)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r["gates"].pop("T61"),
        lambda r: r["gates"]["T73"].update(status="CERTIFIED"),
        lambda r: r.update(data_class=""),
        lambda r: r["gates"]["T75"].update(owner_role=""),
        lambda r: r.update(client_data_authorized=True),
    ],
)
def test_register_denies_unknown_missing_and_fabricated_fields(mutate):
    r = _register()
    mutate(r)
    with pytest.raises(PilotEvidenceError):
        validate_register(r)


def study():
    dossiers = [
        {
            "code": f"synthetic-{i}",
            "input_sha256": hex(i)[2:].rjust(64, "0"),
            "rights_ref": "author-synthetic-fixture",
            "gold_receipt_ref": "two-independent-synthetic-labels",
            "gold_label_reviewer_codes": ["G1", "G2"],
            "gold_references": 12,
            "gold_errors": 2,
            "contains_scan": i == 2,
        }
        for i in range(1, 4)
    ]
    sessions = []
    for idx, d in enumerate(dossiers):
        first, second = ("A", "B") if idx != 1 else ("B", "A")
        sessions.extend(
            [
                {
                    "dossier_code": d["code"], "reviewer_code": first,
                    "mode": "manual", "seconds": 150 + idx * 10,
                    "caught_gold_errors": 1, "false_verified": 1,
                    "abstentions": 0, "wrong_source_or_page": 0,
                },
                {
                    "dossier_code": d["code"], "reviewer_code": second,
                    "mode": "caseproof", "seconds": 80 + idx * 10,
                    "caught_gold_errors": 2, "false_verified": 0,
                    "abstentions": 1, "wrong_source_or_page": 0,
                },
            ]
        )
    return {
        "schema": "caseproof-practitioner-study-v1",
        "data_class": "synthetic",
        "build_sha": "synthetic-test-only",
        "dossiers": dossiers,
        "sessions": sessions,
    }


def test_two_reviewer_study_is_scored_with_independent_denominators():
    result = assess_study(study())
    assert result["dossier_count"] == 3
    assert result["reviewer_count"] == 2
    assert result["conditions"]["manual"]["gold_error_denominator"] == 6
    assert result["conditions"]["manual"]["caught_gold_errors"] == 3
    assert result["conditions"]["manual"]["error_recall"] == 0.5
    assert result["conditions"]["caseproof"]["caught_gold_errors"] == 6
    assert result["conditions"]["caseproof"]["error_recall"] == 1.0
    assert result["conditions"]["caseproof"]["abstentions"] == 3
    assert result["external_practitioner_approval_verified"] is False
    assert result["pilot_approved"] is False


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r["dossiers"][0].update(rights_ref=""),
        lambda r: r["dossiers"][0].update(gold_label_reviewer_codes=["A", "B"]),
        lambda r: r["dossiers"][0].update(input_sha256="bad"),
        lambda r: r["dossiers"][0].update(gold_errors=13),
        lambda r: r["dossiers"][1].update(contains_scan="yes"),
        lambda r: r["sessions"][0].update(seconds=0),
        lambda r: r["sessions"][0].update(caught_gold_errors=3),
        lambda r: r["sessions"][0].update(reviewer_code="G1"),
        lambda r: r["sessions"][0].update(mode="caseproof"),
        lambda r: r["sessions"][0].update(false_verified=-1),
        lambda r: r["sessions"][1].update(reviewer_code="A"),
        lambda r: r["sessions"].pop(),
        lambda r: r.update(source_text="sensitive exhibit content"),
    ],
)
def test_study_refuses_unpermissioned_or_misleading_results(mutate):
    r = deepcopy(study())
    mutate(r)
    with pytest.raises(StudyEvidenceError):
        assess_study(r)


def test_zero_gold_errors_are_unknown_recall_not_perfect():
    r = study()
    for d in r["dossiers"]:
        d["gold_errors"] = 0
    for s in r["sessions"]:
        s["caught_gold_errors"] = 0
    result = assess_study(r)
    assert result["conditions"]["manual"]["error_recall"] is None
    assert result["conditions"]["caseproof"]["error_recall"] is None
