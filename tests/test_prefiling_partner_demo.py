"""BE-03 tests: synthetic Belgian FR/NL 5-trap FastAPI partner demo runner."""

from __future__ import annotations

from fastapi.testclient import TestClient

from scripts.run_prefiling_partner_demo import build_five_trap_audit, create_partner_demo_app


def test_five_trap_audit_exercises_real_engine_detectors() -> None:
    audit = build_five_trap_audit(confirmed_inventory=False, fact_confirmed=False)
    assert audit["synthetic_demo"] is True
    assert audit["not_legal_validation"] is True
    assert audit["identity_reason"] == "INVENTORY_UNCONFIRMED"

    traps = audit["traps"]
    assert traps["wrong_3_space_page"]["printed_page" if "printed_page" in traps["wrong_3_space_page"] else "cited_printed_page"] == 14
    assert traps["wrong_3_space_page"]["pdf_page"] == 16
    assert traps["wrong_3_space_page"]["bundle_page"] == 22

    assert traps["omitted_opening_reservation"] is not None
    assert traps["omitted_opening_reservation"]["kind"] == "omitted_opening_reservation"
    assert "Sous réserve" in traps["omitted_opening_reservation"]["omitted_source_prefix"]

    assert traps["absent_historical_legal_version"]["status"] == "UNVERIFIED"
    assert (
        traps["absent_historical_legal_version"]["reason"]
        == "requested_version_absent_from_chosen_corpus"
    )

    assert len(traps["status_cue_flags"]) >= 1
    assert any(
        "sign" in str(flag).casefold() for flag in traps["status_cue_flags"]
    )

    assert traps["fr_nl_amount_difference"]["state"] == "candidate_difference"
    assert traps["lawyer_condition"]["status"] == "UNDETERMINED"


def test_partner_demo_fastapi_routes_toggle_inventory_and_record_omission() -> None:
    client = TestClient(create_partner_demo_app())
    assert client.get("/v2/demo/health").json()["synthetic_demo"] is True

    initial = client.get("/v2/demo/five-trap-audit")
    assert initial.status_code == 200
    assert initial.json()["identity_reason"] == "INVENTORY_UNCONFIRMED"

    updated = client.post(
        "/v2/demo/five-trap-audit/state",
        json={"confirmed_inventory": True, "fact_confirmed": True},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["identity_reason"] is None
    assert body["traps"]["lawyer_condition"]["status"] == "PASS"

    omission = client.post(
        "/v2/demo/five-trap-audit/omissions",
        json={
            "passage": "Clause d'exclusion de garantie à l'art. 12",
            "rationale": "Passage pertinent omis dans l'analyse initiale",
        },
    )
    assert omission.status_code == 200
    assert omission.json()["count"] == 1


def test_partner_demo_cockpit_v2_routes_validate_against_canonical_schemas() -> None:
    from scripts.run_prefiling_partner_demo import DEMO_BRIEF_ID, DEMO_CASE_ID, DEMO_PDF_SOURCES

    client = TestClient(create_partner_demo_app())
    assert client.post("/v2/workspace/session").json()["synthetic_demo"] is True

    matters = client.get("/v2/workspace/matters")
    assert matters.status_code == 200
    assert matters.json()["matters"][0]["case_id"] == DEMO_CASE_ID

    reports = client.get(f"/v2/workspace/matters/{DEMO_CASE_ID}/reports")
    assert reports.status_code == 200
    assert reports.json()["reports"][0]["brief_id"] == DEMO_BRIEF_ID

    # Confirm inventory so exhibit-references surfaces both status & reservation cues.
    assert (
        client.post("/v2/demo/five-trap-audit/state", json={"confirmed_inventory": True}).status_code
        == 200
    )
    ex_refs = client.get(f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/exhibit-references")
    assert ex_refs.status_code == 200
    refs = ex_refs.json()["references"]
    assert any(r.get("status_cue_flag") is not None for r in refs)
    assert any(r.get("reservation_cue_flag") is not None for r in refs)

    legal_refs = client.get(f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/legal-references")
    assert legal_refs.status_code == 200
    assert legal_refs.json()["references"][0]["reason"] == "requested_version_absent_from_chosen_corpus"

    first_ver = next(iter(DEMO_PDF_SOURCES))
    pdf_resp = client.get(
        f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/dossier/sources/{first_ver}/original"
    )
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert pdf_resp.content.startswith(b"%PDF-1.4")
