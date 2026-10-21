"""KRN-109: executable v2 external contracts (not registered HTTP routes)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from apps.api.contracts_v2 import (
    ApiError,
    AuthoritativeFactsForTest,
    BusinessExceptionRequest,
    CandidateRequest,
    CoverageResponse,
    EvidenceAnchorInput,
    EvidenceLinkRequest,
    LifecycleState,
    PreflightCode,
    PromotionRequest,
    ROUTE_MODELS,
    SCHEMA_VERSION,
    VerifiedPrincipalForTest,
    draft_openapi,
    promotion_preflight,
    request_fingerprint,
)
from apps.api.main import create_app

MATRIX = json.loads(
    (Path(__file__).parent.parent / "contracts" / "v2_operation_matrix.json")
    .read_text(encoding="utf-8")
)
HASH_A = "a" * 64
HASH_B = "b" * 64


def encode(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False)


def anchor(kind: str = "text_span") -> dict[str, object]:
    locator: dict[str, object]
    if kind == "text_span":
        locator = {
            "kind": "text_span", "start": 0, "end": 7,
            "basis": "unicode_codepoint_zero_based_half_open",
        }
    elif kind == "pdf_region":
        locator = {
            "kind": "pdf_region", "page_index": 0,
            "x0": 0.0, "y0": 0.0, "x1": 12.0, "y1": 9.0,
            "page_width": 100.0, "page_height": 200.0, "rotation": 0,
            "basis": "pdf_points_unrotated_bottom_left",
        }
    elif kind == "spreadsheet_range":
        locator = {
            "kind": "spreadsheet_range", "sheet_id": "sheet",
            "a1_range": "A1:B3", "basis": "spreadsheet_a1_sheet_id",
        }
    else:
        locator = {
            "kind": "structured_field", "schema_id": "json-v1",
            "path": ["items", 0, "amount"], "basis": "json_path_v1",
        }
    return {
        "anchor_id": "a1", "document_id": "doc", "version_id": "source-v1",
        "source_sha256_hex": HASH_A, "representation_id": "rep-v1",
        "representation_sha256_hex": HASH_B, "locator": locator,
    }


def candidate() -> dict[str, object]:
    return {
        "case_id": "case-1", "finding_id": "f1", "statement": 'Source says "paid".',
        "expected_case_revision": 1, "idempotency_key": "same-key",
    }


def evidence() -> dict[str, object]:
    return {
        "case_id": "case-1", "finding_id": "f1", "statement_revision": 1,
        "link_id": "link-1", "expected_assessment_revision": 1,
        "anchor": anchor(), "expected_content": {"kind": "quote", "text": "Payment"},
        "proposed_semantic_relation": "contradicts",
        "rationale": "Direct citation contradicts the statement.",
        "idempotency_key": "same-key",
    }


def promotion(target: str = "evidence_grounded") -> dict[str, object]:
    return {
        "case_id": "case-1", "target_state": target, "expected_case_revision": 2,
        "expected_manifest_revision": 3, "expected_policy_version": "policy-2026",
        "idempotency_key": "req-1", "decision_rationale": "Reviewed evidence snapshot.",
    }


def exception_request() -> dict[str, object]:
    return {
        "case_id": "case-1", "expected_case_revision": 2,
        "expected_manifest_revision": 3, "idempotency_key": "exception-1",
        "reason": "Operational acceptance is not legal approval.",
        "affected_issue_ids": ["i1"],
    }


def parsed(target: str = "evidence_grounded") -> PromotionRequest:
    return PromotionRequest.model_validate_json(encode(promotion(target)))


def facts(
    *,
    state: LifecycleState = LifecycleState.CANDIDATE,
) -> AuthoritativeFactsForTest:
    return AuthoritativeFactsForTest(
        owner_tenant_scope="tenant-A", current_case_revision=2,
        current_manifest_revision=3, effective_policy_version="policy-2026",
        current_state=state, grounding_eligible=True,
        review_packet_ready=True, ordinary_complete=True,
        no_material_conflicts=True, policy_sufficiency_met=True,
        audit_write_available=True,
    )


def principal(
    *,
    permissions: frozenset[str] = frozenset({"finding:promote", "conclusion:approve"}),
    human: bool = True,
    tenant: str = "tenant-A",
) -> VerifiedPrincipalForTest:
    return VerifiedPrincipalForTest(tenant, "trusted-actor-fixture", permissions, human)


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (CandidateRequest, candidate()),
        (EvidenceAnchorInput, anchor()),
        (EvidenceLinkRequest, evidence()),
        (PromotionRequest, promotion()),
        (BusinessExceptionRequest, exception_request()),
    ],
)
def test_valid_request_json_round_trip_and_schema(
    model: type, payload: dict[str, object]
) -> None:
    instance = model.model_validate_json(encode(payload))
    assert instance.model_dump(mode="json") == payload
    schema = model.model_json_schema()
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(payload)


@pytest.mark.parametrize("kind", [
    "text_span", "pdf_region", "spreadsheet_range", "structured_field",
])
def test_typed_anchors_have_exact_locator_discriminants(kind: str) -> None:
    value = EvidenceAnchorInput.model_validate_json(encode(anchor(kind)))
    assert value.locator.kind == kind


@pytest.mark.parametrize("forbidden", [
    "tenant_id", "actor_id", "role", "authorized", "approval_authority",
    "permissions", "effective_policy_version_from_header", "approved",
    "lifecycle_status",
])
def test_forged_authority_fields_fail_schema_validation(forbidden: str) -> None:
    for model, body in (
        (CandidateRequest, candidate()),
        (EvidenceLinkRequest, evidence()),
        (PromotionRequest, promotion()),
        (BusinessExceptionRequest, exception_request()),
        (EvidenceAnchorInput, anchor()),
    ):
        body[forbidden] = True
        with pytest.raises(ValidationError):
            model.model_validate_json(encode(body))


@pytest.mark.parametrize(
    ("mutation", "payload"),
    [
        ("negative_span", {"start": -1}),
        ("zero_span", {"end": 0}),
        ("reversed_span", {"start": 5, "end": 3}),
        ("invalid_basis", {"basis": "byte-offset"}),
        ("bool_position", {"start": True}),
        ("unknown_discriminator", {"kind": "figure"}),
        ("unsupported_coordinate", {"end": "100"}),
    ],
)
def test_malformed_text_locator_fails_closed(
    mutation: str, payload: dict[str, object]
) -> None:
    body = anchor()
    locator = body["locator"]
    assert isinstance(locator, dict)
    locator.update(payload)
    with pytest.raises(ValidationError):
        EvidenceAnchorInput.model_validate_json(encode(body))


@pytest.mark.parametrize("bad", [
    {"x1": 0.0},
    {"x1": 105.0},
    {"y1": 205.0},
    {"rotation": 45},
    {"page_index": -1},
    {"x1": float("nan")},
    {"page_height": -1.0},
])
def test_invalid_pdf_geometry_fails(bad: dict[str, object]) -> None:
    body = anchor("pdf_region")
    locator = body["locator"]
    assert isinstance(locator, dict)
    locator.update(bad)
    with pytest.raises(ValidationError):
        EvidenceAnchorInput.model_validate_json(encode(body))


@pytest.mark.parametrize("changed", [
    {"a1_range": "A0:B2"}, {"a1_range": "B1"}, {"sheet_id": ""},
])
def test_invalid_spreadsheet_locator_fails(changed: dict[str, object]) -> None:
    body = anchor("spreadsheet_range")
    assert isinstance(body["locator"], dict)
    body["locator"].update(changed)
    with pytest.raises(ValidationError):
        EvidenceAnchorInput.model_validate_json(encode(body))


@pytest.mark.parametrize("path", [[], [-1], [True], [""], [1.0]])
def test_invalid_structured_field_path_fails(path: list[object]) -> None:
    body = anchor("structured_field")
    assert isinstance(body["locator"], dict)
    body["locator"]["path"] = path
    with pytest.raises(ValidationError):
        EvidenceAnchorInput.model_validate_json(encode(body))


@pytest.mark.parametrize("invalid", [
    {"source_sha256_hex": "XYZ"},
    {"representation_sha256_hex": "0" * 63},
    {"document_id": ""},
    {"representation_id": ""},
])
def test_invalid_source_identity_fails(invalid: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        EvidenceAnchorInput.model_validate_json(encode(anchor() | invalid))


@pytest.mark.parametrize("value", [1.0, ["text"], {"k": "v"}])
def test_json_expected_content_excludes_float_or_compound_values(value: object) -> None:
    body = evidence()
    body["expected_content"] = {"kind": "json_scalar", "value": value}
    with pytest.raises(ValidationError):
        EvidenceLinkRequest.model_validate_json(encode(body))


@pytest.mark.parametrize("value", [True, 1, "1", None, False])
def test_exact_json_scalar_request_preserves_type(value: object) -> None:
    body = evidence()
    body["expected_content"] = {"kind": "json_scalar", "value": value}
    item = EvidenceLinkRequest.model_validate_json(encode(body))
    assert type(item.expected_content.value) is type(value)


@pytest.mark.parametrize("bad", [
    {"expected_case_revision": 0},
    {"expected_case_revision": True},
    {"target_state": "candidate"},
    {"target_state": "business_exception_accepted"},
    {"expected_policy_version": ""},
    {"decision_rationale": ""},
    {"idempotency_key": ""},
    {"expected_manifest_revision": -4},
])
def test_promotion_rejects_invalid_target_or_preconditions(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        PromotionRequest.model_validate_json(encode(promotion() | bad))


@pytest.mark.parametrize("bad", [
    {"affected_issue_ids": []},
    {"affected_issue_ids": ["i1", "i1"]},
    {"affected_issue_ids": [""]},
    {"reason": ""},
    {"expected_manifest_revision": 0},
])
def test_exception_payload_rejects_missing_or_duplicate_issues(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        BusinessExceptionRequest.model_validate_json(encode(exception_request() | bad))


def test_no_authentication_is_401_with_no_state_change() -> None:
    result = promotion_preflight(parsed(), principal=None, facts=facts())
    assert (result.code, result.http_status_if_denied) == (
        PreflightCode.AUTHENTICATION_REQUIRED, 401
    )


def test_cross_tenant_and_missing_case_are_masked_404() -> None:
    assert promotion_preflight(
        parsed(), principal=principal(tenant="other"), facts=facts()
    ).http_status_if_denied == 404
    assert promotion_preflight(
        parsed(), principal=principal(), facts=None
    ).http_status_if_denied == 404


def test_insufficient_permission_is_403_even_with_perfect_evidence() -> None:
    result = promotion_preflight(
        parsed(), principal=principal(permissions=frozenset()), facts=facts()
    )
    assert (result.code, result.http_status_if_denied) == (
        PreflightCode.PERMISSION_DENIED, 403
    )


@pytest.mark.parametrize("change", [
    {"current_case_revision": 3}, {"current_manifest_revision": 4},
    {"effective_policy_version": "stale-policy"},
])
def test_stale_revision_or_policy_fails_409(change: dict[str, object]) -> None:
    result = promotion_preflight(
        parsed(), principal=principal(), facts=replace(facts(), **change)
    )
    assert result.code is PreflightCode.STALE_REVISION
    assert result.http_status_if_denied == 409


@pytest.mark.parametrize("state", [
    LifecycleState.EVIDENCE_GROUNDED,
    LifecycleState.REVIEW_READY,
    LifecycleState.APPROVED_CONCLUSION,
])
def test_disallowed_or_reverse_transitions_fail_409(state: LifecycleState) -> None:
    result = promotion_preflight(
        parsed(), principal=principal(), facts=facts(state=state)
    )
    assert result.code is PreflightCode.INVALID_TRANSITION
    assert result.http_status_if_denied == 409


@pytest.mark.parametrize(
    ("target", "previous", "facts_change"),
    [
        ("evidence_grounded", LifecycleState.CANDIDATE, {"grounding_eligible": False}),
        ("review_ready", LifecycleState.EVIDENCE_GROUNDED, {"review_packet_ready": False}),
        ("approved_conclusion", LifecycleState.REVIEW_READY, {"ordinary_complete": False}),
        ("approved_conclusion", LifecycleState.REVIEW_READY, {"no_material_conflicts": False}),
        ("approved_conclusion", LifecycleState.REVIEW_READY, {"policy_sufficiency_met": False}),
        ("approved_conclusion", LifecycleState.REVIEW_READY, {"review_packet_ready": False}),
    ],
)
def test_missing_evidence_review_coverage_or_support_blocks_409(
    target: str, previous: LifecycleState, facts_change: dict[str, object]
) -> None:
    result = promotion_preflight(
        parsed(target), principal=principal(), facts=replace(facts(state=previous), **facts_change)
    )
    assert result.code is PreflightCode.GATE_BLOCKED
    assert result.http_status_if_denied == 409


def test_no_model_only_or_unverified_human_approval() -> None:
    result = promotion_preflight(
        parsed("approved_conclusion"),
        principal=principal(human=False), facts=facts(state=LifecycleState.REVIEW_READY)
    )
    assert result.code is PreflightCode.PERMISSION_DENIED
    assert result.http_status_if_denied == 403


@pytest.mark.parametrize("target,state", [
    ("evidence_grounded", LifecycleState.CANDIDATE),
    ("review_ready", LifecycleState.EVIDENCE_GROUNDED),
    ("approved_conclusion", LifecycleState.REVIEW_READY),
])
def test_even_admissible_request_is_not_approved_or_committed(
    target: str, state: LifecycleState
) -> None:
    result = promotion_preflight(parsed(target), principal=principal(), facts=facts(state=state))
    assert result.code is PreflightCode.APPLICATION_REVIEW_REQUIRED
    assert result.http_status_if_denied is None
    assert result.requires_application_commit
    assert not hasattr(result, "approved")
    assert not hasattr(result, "did_commit")


def test_audit_failure_prevents_any_admissible_transition() -> None:
    result = promotion_preflight(
        parsed(), principal=principal(), facts=replace(facts(), audit_write_available=False)
    )
    assert result.code is PreflightCode.AUDIT_UNAVAILABLE
    assert result.http_status_if_denied == 409


def test_duplicate_idempotency_fingerprint_replay_is_not_a_legal_success() -> None:
    payload = parsed()
    assert request_fingerprint(payload) == request_fingerprint(parsed())
    original = promotion_preflight(
        payload, principal=principal(), facts=facts(),
        prior_request_fingerprint=request_fingerprint(payload),
    )
    assert original.requires_application_commit  # durable result lookup required, not a new commit
    changed = PromotionRequest.model_validate_json(
        encode(promotion() | {"decision_rationale": "Different decision"})
    )
    collision = promotion_preflight(
        changed, principal=principal(), facts=facts(),
        prior_request_fingerprint=request_fingerprint(payload),
    )
    assert collision.code is PreflightCode.IDEMPOTENCY_CONFLICT
    assert collision.http_status_if_denied == 409


def test_operation_matrix_matches_exported_schema_routes_and_permissions() -> None:
    assert MATRIX["status"] == "typed_contract_only_no_v2_routes_enabled"
    assert MATRIX["schema_version"] == SCHEMA_VERSION
    assert {
        f"{op['method']} {op['path']}" for op in MATRIX["operations"]
    } == set(ROUTE_MODELS)
    for operation in MATRIX["operations"]:
        assert operation["permissions"]
        assert operation["errors"] == [401, 403, 404, 409, 422]
    proposal = draft_openapi()
    assert proposal["openapi"] == "3.1.0"
    paths = proposal["paths"]
    assert isinstance(paths, dict)
    assert set(paths) == {op["path"] for op in MATRIX["operations"]}
    assert "contract draft" in proposal["info"]["title"].lower()
    for op in MATRIX["operations"]:
        route = paths[op["path"]][op["method"].lower()]
        assert route["summary"].startswith("Contract proposal")
        assert set(route["responses"]) == {"200", "401", "403", "404", "409", "422"}
        if op["request"] is not None:
            assert "requestBody" in route
            assert route["requestBody"]["required"] is True


def test_generated_openapi_contains_strict_schemas_not_authority_claims() -> None:
    draft = draft_openapi()
    dump = encode(draft)
    assert '"openapi": "3.1.0"' in dump
    assert '"additionalProperties": false' in dump
    assert '"discriminator"' in dump
    assert "source_sha256_hex" in dump
    assert "authorization" not in PromotionRequest.model_fields
    assert "tenant_id" not in PromotionRequest.model_fields
    assert "actor_id" not in PromotionRequest.model_fields


def test_response_schema_is_typed_but_never_client_controlled() -> None:
    body = {
        "case_id": "case-1", "scope_version": 1, "manifest_revision": 2,
        "policy_version": "version-1", "ordinary_complete": False,
        "issues": [{"issue_id": "i1", "status": "contradicted",
                    "blocker_codes": ["contradiction_present"]}],
        "excluded_source_ids": [],
    }
    assert not CoverageResponse.model_validate_json(encode(body)).ordinary_complete
    assert ApiError.model_validate_json(encode({
        "code": "permission_denied", "message": "Access denied"
    })).code == "permission_denied"
    with pytest.raises(ValidationError):
        CoverageResponse.model_validate_json(encode(body | {"approved": True}))


def test_v1_routes_unmodified_and_no_v2_endpoints_exposed() -> None:
    client = TestClient(create_app())
    assert client.get("/health").status_code == 200
    assert "/v1/claims" in client.app.openapi()["paths"]
    assert not any(path.startswith("/v2/") for path in client.app.openapi()["paths"])
    assert client.post("/v2/cases/case-1/promotion", json=promotion()).status_code == 404
    assert client.get("/v2/cases/case-1/coverage").status_code == 404
