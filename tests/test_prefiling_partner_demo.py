"""BE-03 tests: synthetic Belgian FR/NL 5-trap FastAPI partner demo runner."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from scripts.run_prefiling_partner_demo import (
    DEMO_BRIEF_ID,
    DEMO_BUNDLE_SIGNATURE,
    DEMO_CASE_ID,
    DEMO_PDF_SOURCES,
    VER_PIECE_1,
    build_five_trap_audit,
    create_partner_demo_app,
)

SCHEMAS_DIR = Path(__file__).resolve().parents[1] / "frontend" / "src" / "shared" / "api"


def _validate_node(value: Any, schema: dict[str, Any], root: dict[str, Any], path: str = "$") -> None:
    """Zero-dependency Draft 2020-12 subset validator for checked-in frontend JSON schemas."""
    if "$ref" in schema:
        ref = schema["$ref"]
        assert ref.startswith("#/$defs/"), f"unsupported $ref {ref}"
        target = root["$defs"][ref.split("/", 2)[2]]
        _validate_node(value, target, root, path)
        return
    if "anyOf" in schema:
        for branch in schema["anyOf"]:
            try:
                _validate_node(value, branch, root, path)
                return
            except AssertionError:
                continue
        raise AssertionError(f"{path}: {value!r} failed all anyOf branches")
    if "const" in schema:
        assert value == schema["const"], f"{path}: expected const {schema['const']!r}, got {value!r}"
    if "enum" in schema:
        assert value in schema["enum"], f"{path}: {value!r} not in {schema['enum']!r}"
    expected_type = schema.get("type")
    if expected_type == "null":
        assert value is None, f"{path}: expected null, got {value!r}"
        return
    if expected_type == "boolean":
        assert isinstance(value, bool), f"{path}: expected bool, got {value!r}"
    elif expected_type == "integer":
        assert isinstance(value, int) and not isinstance(value, bool), f"{path}: expected int, got {value!r}"
        if "minimum" in schema:
            assert value >= schema["minimum"], f"{path}: {value} < {schema['minimum']}"
        if "maximum" in schema:
            assert value <= schema["maximum"], f"{path}: {value} > {schema['maximum']}"
    elif expected_type == "string":
        assert isinstance(value, str), f"{path}: expected str, got {value!r}"
        if "minLength" in schema:
            assert len(value) >= schema["minLength"], f"{path}: len < {schema['minLength']}"
        if "maxLength" in schema:
            assert len(value) <= schema["maxLength"], f"{path}: len > {schema['maxLength']}"
        if "pattern" in schema:
            assert re.search(schema["pattern"], value) is not None, f"{path}: {value!r} failed {schema['pattern']}"
    elif expected_type == "array":
        assert isinstance(value, list), f"{path}: expected list, got {value!r}"
        if "minItems" in schema:
            assert len(value) >= schema["minItems"], f"{path}: len < {schema['minItems']}"
        if "maxItems" in schema:
            assert len(value) <= schema["maxItems"], f"{path}: len > {schema['maxItems']}"
        if "items" in schema:
            for idx, item in enumerate(value):
                _validate_node(item, schema["items"], root, f"{path}[{idx}]")
    elif expected_type == "object":
        assert isinstance(value, dict), f"{path}: expected object, got {value!r}"
        props = schema.get("properties", {})
        for req in schema.get("required", ()):
            assert req in value, f"{path}: missing required key {req!r}"
        if schema.get("additionalProperties") is False:
            extra = set(value) - set(props)
            assert not extra, f"{path}: forbidden extra keys {sorted(extra)}"
        for key, item in value.items():
            if key in props:
                _validate_node(item, props[key], root, f"{path}.{key}")
            elif isinstance(schema.get("additionalProperties"), dict):
                _validate_node(item, schema["additionalProperties"], root, f"{path}.{key}")


def _assert_matches_frontend_schema(schema_name: str, payload: dict[str, Any]) -> None:
    """Validate payload directly against the checked-in frontend JSON schema (no external deps)."""
    schema = json.loads((SCHEMAS_DIR / schema_name).read_text(encoding="utf-8"))
    _validate_node(payload, schema, schema)


def test_five_trap_audit_exercises_real_engine_detectors() -> None:
    audit = build_five_trap_audit(confirmed_inventory=False, fact_confirmed=False)
    assert audit["synthetic_demo"] is True
    assert audit["not_legal_validation"] is True
    assert audit["identity_reason"] == "INVENTORY_UNCONFIRMED"

    traps = audit["traps"]
    assert traps["wrong_3_space_page"]["cited_printed_page"] == 14
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
    assert any("sign" in str(flag).casefold() for flag in traps["status_cue_flags"])

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


def test_partner_demo_cockpit_v2_routes_validate_against_frontend_schemas() -> None:
    client = TestClient(create_partner_demo_app())

    # 1. Session sign-in strictly matches frontend/src/shared/api/session.schema.json (no extra keys).
    session_resp = client.post(
        "/v2/workspace/session", json={"email": "demo@example.test", "password": "demo"}
    )
    assert session_resp.status_code == 200
    session_body = session_resp.json()
    assert set(session_body.keys()) == {"access_token", "expires_at"}
    _assert_matches_frontend_schema("session.schema.json", session_body)
    assert client.post("/v2/workspace/session/end").status_code == 204

    # 2. Matters, organizations, reports.
    orgs = client.get("/v2/workspace/intake/organizations")
    assert orgs.status_code == 200
    _assert_matches_frontend_schema("organizations.schema.json", orgs.json())

    matters = client.get("/v2/workspace/matters")
    assert matters.status_code == 200
    _assert_matches_frontend_schema("matters.schema.json", matters.json())
    assert matters.json()["matters"][0]["case_id"] == DEMO_CASE_ID

    reports = client.get(f"/v2/workspace/matters/{DEMO_CASE_ID}/reports")
    assert reports.status_code == 200
    _assert_matches_frontend_schema("reports.schema.json", reports.json())
    snapshot = reports.json()["reports"][0]["snapshot_hash"]
    assert reports.json()["reports"][0]["brief_id"] == DEMO_BRIEF_ID

    # 3. Main cockpit: dossier, reviews, viewer, original PDF headers, regions, draft-context, recovery.
    dossier_resp = client.get(
        f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/dossier?snapshot_hash={snapshot}"
    )
    assert dossier_resp.status_code == 200
    dossier = dossier_resp.json()
    _assert_matches_frontend_schema("dossier.schema.json", dossier)
    assert len(dossier["findings"]) == 3
    ref_id = dossier["findings"][0]["reference_id"]
    assert ref_id == "ref-piece-1"

    reviews_resp = client.get(
        f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/dossier/reviews?snapshot_hash={snapshot}"
    )
    assert reviews_resp.status_code == 200
    _assert_matches_frontend_schema("review-ledger.schema.json", reviews_resp.json())

    req_id = str(uuid.uuid4())
    write_review = client.post(
        f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/dossier/reviews",
        json={
            "snapshot_hash": snapshot,
            "reference_id": ref_id,
            "decision": "CONFIRMED_QUALIFIED",
            "rationale": "Opening reservation clause omitted in draft quotation.",
            "request_id": req_id,
            "reviewed_region_ids": [],
        },
    )
    assert write_review.status_code == 200
    assert write_review.json()["request_id"] == req_id
    reviews_after = client.get(
        f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/dossier/reviews?snapshot_hash={snapshot}"
    )
    assert len(reviews_after.json()["decisions"]) == 1

    viewer_base = (
        f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/dossier"
        f"/snapshots/{snapshot}/references/{ref_id}"
    )
    viewer = client.get(f"{viewer_base}/viewer")
    assert viewer.status_code == 200
    viewer_json = viewer.json()
    _assert_matches_frontend_schema("viewer.schema.json", viewer_json)
    assert viewer_json["pdf_page"] == 16

    pdf_resp = client.get(f"{viewer_base}/viewer/original")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert pdf_resp.headers["x-caseproof-snapshot"] == snapshot
    assert pdf_resp.headers["x-caseproof-original-sha256"] == viewer_json["original_sha256"]
    assert hashlib.sha256(pdf_resp.content).hexdigest() == viewer_json["original_sha256"]
    assert b"/Count 16" in pdf_resp.content

    regions = client.get(f"{viewer_base}/viewer/regions")
    assert regions.status_code == 200
    assert regions.json()["schema"] == "caseproof-raster-overlays-v1"
    assert regions.json()["original_sha256"] == viewer_json["original_sha256"]

    draft_ctx = client.get(f"{viewer_base}/draft-context")
    assert draft_ctx.status_code == 200
    _assert_matches_frontend_schema("draft-excerpt.schema.json", draft_ctx.json())
    assert draft_ctx.json()["available"] is True

    corr_ops = client.get(f"{viewer_base}/correction-operations")
    assert corr_ops.status_code == 200
    assert corr_ops.json()["current_draft_version_id"] == DEMO_BRIEF_ID

    corr_anchor = client.get(f"{viewer_base}/correction-anchor")
    assert corr_anchor.status_code == 200
    _assert_matches_frontend_schema(
        "docx-locator-v1.schema.json", corr_anchor.json()["locator_identity"]
    )

    corr_receipt = client.get(
        f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/dossier/corrections/review-receipt"
        f"?snapshot_hash={snapshot}&reference_id={ref_id}"
    )
    assert corr_receipt.status_code == 200
    assert corr_receipt.json()["review_request_id"] == req_id

    # Unreviewed reference returns 409 (never 404, which would clear the session).
    unreviewed_receipt = client.get(
        f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/dossier/corrections/review-receipt"
        f"?snapshot_hash={snapshot}&reference_id=ref-piece-3"
    )
    assert unreviewed_receipt.status_code == 409

    # 4. Intake & live inventory confirmation flow.
    intake_resp = client.get(f"/v2/workspace/intake/matters/{DEMO_CASE_ID}")
    assert intake_resp.status_code == 200
    intake_json = intake_resp.json()
    _assert_matches_frontend_schema("intake.schema.json", intake_json)
    assert intake_json["confirmation_id"] is None

    confirm_id = str(uuid.uuid4())
    confirm_resp = client.post(
        f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/dossier/confirmation",
        json={
            "request_id": confirm_id,
            "bundle_signature": DEMO_BUNDLE_SIGNATURE,
            "inventory_complete": True,
            "entries": intake_json["entries"],
            "exceptions": [],
        },
    )
    assert confirm_resp.status_code == 200
    intake_after = client.get(f"/v2/workspace/intake/matters/{DEMO_CASE_ID}").json()
    _assert_matches_frontend_schema("intake.schema.json", intake_after)
    assert intake_after["confirmation_id"] == confirm_id
    assert intake_after["inventory_complete"] is True

    # Historical read-only fallback works for the pre-confirmation snapshot.
    stale_check = client.get(
        f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/dossier?snapshot_hash={snapshot}"
    )
    assert stale_check.status_code == 409
    hist_resp = client.get(
        f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/dossier/history/{snapshot}"
    )
    assert hist_resp.status_code == 200
    assert hist_resp.json()["mode"] == "historical_read_only"

    # 5. Exhibits, legal references, legal passage, reservation cues, conditions, clearbrief review.
    ex_refs = client.get(f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/exhibit-references")
    assert ex_refs.status_code == 200
    _assert_matches_frontend_schema("exhibit-references.schema.json", ex_refs.json())
    refs = ex_refs.json()["references"]
    assert any(r.get("status_cue_flag") is not None for r in refs)
    assert any(r.get("reservation_cue_flag") is not None for r in refs)

    legal_refs = client.get(f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/legal-references")
    assert legal_refs.status_code == 200
    _assert_matches_frontend_schema("legal-references.schema.json", legal_refs.json())
    assert (
        legal_refs.json()["references"][0]["reason"]
        == "requested_version_absent_from_chosen_corpus"
    )
    new_snapshot = legal_refs.json()["snapshot_hash"]

    passage = client.get(
        f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/legal-references/legal-ref-01/passage"
    )
    assert passage.status_code == 200
    _assert_matches_frontend_schema("legal-passage.schema.json", passage.json())

    res_cues = client.get(f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/reservation-cues")
    assert res_cues.status_code == 200
    assert res_cues.json()["schema"] == "caseproof-reservation-cues-v1"
    assert res_cues.json()["advisory"] is True

    cond_state = client.get(f"/v2/matters/{DEMO_CASE_ID}/conditions")
    assert cond_state.status_code == 200
    _assert_matches_frontend_schema("conditions-state.schema.json", cond_state.json())

    cond_matches = client.get(f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/conditions")
    assert cond_matches.status_code == 200
    _assert_matches_frontend_schema("condition-matches.schema.json", cond_matches.json())

    cb_review = client.get(f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/review")
    assert cb_review.status_code == 200
    _assert_matches_frontend_schema("clearbrief-review.schema.json", cb_review.json())

    cb_post = client.post(
        f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/review",
        json={
            "snapshot_hash": new_snapshot,
            "observation_id": "omission:demo-1",
            "request_id": str(uuid.uuid4()),
            "expected_revision": 0,
            "disposition": "omission",
            "rationale": "Missing limitation clause in annex.",
        },
    )
    assert cb_post.status_code == 200
    _assert_matches_frontend_schema("clearbrief-receipt.schema.json", cb_post.json())

    # 6. Exports & DOCX editor read routes & original source download.
    rel_list = client.get(f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/dossier/releases")
    assert rel_list.status_code == 200
    assert rel_list.json() == {"releases": []}

    rel_preview = client.get(
        f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/dossier/releases/preview"
        f"?snapshot_hash={new_snapshot}"
    )
    assert rel_preview.status_code == 200
    assert rel_preview.json()["schema"] == "caseproof-release-preview-v1"
    assert "immutable CaseProof review record" in rel_preview.json()["acknowledgement_notice"]

    blocks = client.get(
        f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/dossier/editor/blocks"
        f"?snapshot_hash={new_snapshot}&offset=0&limit=20"
    )
    assert blocks.status_code == 200
    assert blocks.json()["schema"] == "caseproof-docx-editor-blocks-v1"

    revs = client.get(
        f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/dossier/editor/revisions"
        f"?snapshot_hash={new_snapshot}"
    )
    assert revs.status_code == 200
    assert revs.json()["schema"] == "caseproof-docx-editor-revisions-v1"

    src_pdf = client.get(
        f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/dossier/sources/{VER_PIECE_1}/original"
    )
    assert src_pdf.status_code == 200
    assert src_pdf.headers["content-type"] == "application/pdf"
    assert src_pdf.content == DEMO_PDF_SOURCES[VER_PIECE_1][1]

    draft_docx = client.get(
        f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/dossier/sources/{DEMO_BRIEF_ID}/original"
        f"?snapshot_hash={new_snapshot}"
    )
    assert draft_docx.status_code == 200
    assert "wordprocessingml.document" in draft_docx.headers["content-type"]
    assert draft_docx.headers["x-caseproof-snapshot"] == new_snapshot


def test_partner_demo_mounts_built_frontend_under_workspace_base(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        '<!doctype html><script src="/workspace/assets/app.js"></script>',
        encoding="utf-8",
    )
    (dist / "assets" / "app.js").write_text("console.log('caseproof');", encoding="utf-8")

    client = TestClient(create_partner_demo_app(frontend_dist=dist))

    root = client.get("/", follow_redirects=False)
    assert root.status_code == 307
    assert root.headers["location"] == "/workspace/"

    ws = client.get("/workspace/")
    assert ws.status_code == 200
    assert "/workspace/assets/app.js" in ws.text

    asset = client.get("/workspace/assets/app.js")
    assert asset.status_code == 200
    assert "caseproof" in asset.text

    deep_link = client.get(
        f"/workspace/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}?snapshot={'a' * 64}"
    )
    assert deep_link.status_code == 200
    assert "/workspace/assets/app.js" in deep_link.text
