"""Frozen architecture/contract compatibility gates, not production authorization."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from apps.api.access_control import CaseAction
from apps.api.contracts_v2 import EvidenceAnchorInput, to_kernel_locator
from apps.api.evidence_locator_codec import decode_locator, encode_locator
from packages.evidence_kernel.domain.anchors import (
    PdfRegion, SheetRange, StructuredField, TextSpan,
)

ROOT = Path(__file__).resolve().parents[1]
BASELINE = json.loads((ROOT / "contracts/architecture_baseline_v1.json").read_text())
CATALOG = json.loads((ROOT / "contracts/action_catalog.v1.json").read_text())
OPERATIONS = json.loads((ROOT / "contracts/v2_operation_matrix.json").read_text())
FOUNDATION = (ROOT / "supabase/migrations/20261022001009_caseproof_tenant_foundation.sql").read_text()


def _anchor(locator: dict[str, object]) -> dict[str, object]:
    return {
        "anchor_id": "anchor", "document_id": "doc",
        "version_id": "v1", "source_sha256_hex": "a" * 64,
        "representation_id": "rep1", "representation_sha256_hex": "b" * 64,
        "locator": locator,
    }


@pytest.mark.parametrize(("locator", "expected"), [
    ({"kind":"text_span","start":0,"end":7,"encoding":"utf-8",
      "normalization":"NFC","basis":"unicode_codepoint_zero_based_half_open"},
     TextSpan(0,7,"utf-8","NFC")),
    ({"kind":"pdf_region","page_index":0,"x0":"0.00000000000000000001",
      "y0":"1.2500","x1":"12.00000000000000000001",
      "y1":"9.7500","page_width":"100.000","page_height":"200",
      "rotation":0,"basis":"pdf_points_unrotated_bottom_left"},
     PdfRegion(0,Decimal("0.00000000000000000001"),Decimal("1.2500"),
               Decimal("12.00000000000000000001"),Decimal("9.7500"),
               Decimal("100.000"),Decimal("200"),0)),
    ({"kind":"sheet_range","sheet_id":"sheet","a1_range":"A1:B3",
      "table_id":"table-7","basis":"spreadsheet_a1_sheet_id"},
     SheetRange("sheet","A1:B3","table-7")),
    ({"kind":"structured_field","schema_id":"UBL-v1",
      "path":["Invoice","TaxTotal",0,"TaxAmount"],"basis":"json_path_v1"},
     StructuredField("UBL-v1",("Invoice","TaxTotal",0,"TaxAmount"))),
])
def test_exact_v2_to_domain_to_storage_roundtrip(
    locator: dict[str, object],
    expected: TextSpan | PdfRegion | SheetRange | StructuredField,
) -> None:
    external = EvidenceAnchorInput.model_validate(_anchor(locator))
    model = to_kernel_locator(external.locator)
    assert model == expected
    kind, version, saved = encode_locator(model)
    assert kind == locator["kind"]
    assert decode_locator(kind, version, saved) == expected
    assert external.model_dump(mode="json")["locator"] == locator


@pytest.mark.parametrize("value", [
    0.1, 1, None, -0.1, float("inf"), float("nan"), "1e-2", "-1", ".5",
    "0001", "0.", "9" * 65, "1." + "0" * 65,
])
def test_pdf_coordinate_json_number_or_noncanonical_string_rejected(value: object) -> None:
    locator: dict[str, object] = {
        "kind":"pdf_region","page_index":0,"x0":"0","y0":"0",
        "x1":value,"y1":"9","page_width":"100","page_height":"200",
        "rotation":0,"basis":"pdf_points_unrotated_bottom_left",
    }
    with pytest.raises(ValidationError):
        EvidenceAnchorInput.model_validate(_anchor(locator))


@pytest.mark.parametrize("locator", [
    {"kind":"spreadsheet_range","sheet_id":"sheet","a1_range":"A1:B3",
     "table_id":None,"basis":"spreadsheet_a1_sheet_id"},
    {"kind":"sheet_range","sheet_id":"sheet","a1_range":"B4:A1",
     "table_id":None,"basis":"spreadsheet_a1_sheet_id"},
    {"kind":"sheet_range","sheet_id":"sheet","a1_range":"A0",
     "table_id":None,"basis":"spreadsheet_a1_sheet_id"},
    {"kind":"text_span","start":0,"end":3,"basis":"unicode_codepoint_zero_based_half_open"},
    {"kind":"text_span","start":0,"end":3,"encoding":"utf-8",
     "normalization":"unsupported","basis":"unicode_codepoint_zero_based_half_open"},
])
def test_legacy_or_lossy_locators_are_not_silently_upgraded(
    locator: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        EvidenceAnchorInput.model_validate(_anchor(locator))


def test_permission_catalog_equals_installed_typed_and_sql_grants() -> None:
    installed = set(CATALOG["installed_actions"])
    proposed = set(CATALOG["future_actions_not_installed"])
    assert installed == {a.value for a in CaseAction}
    assert not installed.intersection(proposed)
    for action in installed:
        assert f"'{action}'" in FOUNDATION
    for action in proposed:
        assert f"'{action}'" not in FOUNDATION
    assert "to authenticated;" in FOUNDATION
    assert BASELINE["release_gates"]["client_reviewer_id_never_authority"]
    assert BASELINE["mvp_access_scope"] == "org_membership_with_action_grants_no_per_case_assignment"


def test_uninstalled_permissions_are_blocked_and_no_v2_routing_exists() -> None:
    assert OPERATIONS["action_catalog"] == "contracts/action_catalog.v1.json"
    assert OPERATIONS["status"] == "typed_contract_only_all_v2_routes_disabled"
    for op in OPERATIONS["operations"]:
        required = set(op["permissions"])
        not_installed = required - set(CATALOG["installed_actions"])
        assert op["runtime_route_enabled"] is False
        assert set(op["uninstalled_actions"]) == not_installed
        if not_installed:
            assert op["permission_installation"] == "blocked_new_scopes_not_installed"
            assert not_installed <= set(CATALOG["future_actions_not_installed"])
        else:
            assert op["permission_installation"] == "installed_scopes_only_no_v2_route"
    assert '"/v2/' not in (ROOT / "apps/api/main.py").read_text()
    assert BASELINE["release_gates"]["explicit_human_attestation_for_approval"]


def test_kernel_sectors_and_workflow_are_distinct_concerns() -> None:
    assert BASELINE["architecture"] == "hexagonal_modular_monolith"
    assert BASELINE["deployment"]["microservices"] is False
    assert BASELINE["product"]["first_application"] == "ExceptionDesk"
    assert BASELINE["source_model"].startswith("KRN-101 SourceVersion")
    assert BASELINE["locator_kind_names"] == [
        "text_span", "pdf_region", "sheet_range", "structured_field"
    ]
    assert "DomainPack_framework" in BASELINE["defer"]
    assert "universal_EvidenceState_enum" in BASELINE["defer"]
    assert "candidate_extraction" in BASELINE["ownership"]["application"]
    assert "money_and_currency_rules" in BASELINE["ownership"]["finance"]
    assert "worker_execution" in BASELINE["state_dimensions"]
    assert "real_auth_db_isolation" in BASELINE["delivery_tracks"]["foundation"]
    assert "UBL_parser" in BASELINE["delivery_tracks"]["synthetic_product"]
