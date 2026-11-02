"""Contract strictness and compatibility regression tests for actual API models."""
import pytest
from pydantic import ValidationError

from application.litigation.frontend_contract import DossierView, FindingView
from application.litigation.viewer_contract import ViewerContext
from apps.api.dossier_journey import InventoryConfirmation
from apps.api.workspace_auth import LoginBody
from apps.api.workspace_intake import IntakeCommand, IntakeFile


def finding():
    return dict(reference_id="r1", literal="Stuk 1", identity="resolved",
                page_mapping="mapped", fidelity="exact_match", support="supported")


def dossier():
    return dict(schema="caseproof-dossier-v1", case_id="case", brief_id="brief",
                snapshot_hash="a" * 64, findings=[finding()], coverage={})


def test_versioned_dossier_and_findings_allow_future_fields():
    data = dossier()
    data["future_extension"] = {"source": "v2"}
    data["findings"][0]["future_detail"] = "supported"
    view = DossierView.model_validate(data)
    assert view.model_dump(by_alias=True)["future_extension"] == {"source": "v2"}
    assert view.findings[0].model_dump()["future_detail"] == "supported"


@pytest.mark.parametrize("field,value", [
    ("identity", "verified"), ("page_mapping", "invented"),
    ("fidelity", "verified"), ("support", "guaranteed"),
])
def test_finding_rejects_invalid_states(field, value):
    data = finding()
    data[field] = value
    with pytest.raises(ValidationError):
        FindingView.model_validate(data)


def test_dossier_required_fields_and_invalid_evidence_reference():
    data = dossier()
    del data["snapshot_hash"]
    with pytest.raises(ValidationError):
        DossierView.model_validate(data)
    data = dossier()
    data["findings"][0]["reference_id"] = ""
    with pytest.raises(ValidationError):
        DossierView.model_validate(data)


def test_viewer_rejects_unknown_fields_and_invalid_page():
    assert ViewerContext.model_json_schema()["additionalProperties"] is False
    data = dict(schema="caseproof-viewer-v1", case_id="case", brief_id="brief",
                snapshot_hash="a" * 64, reference_id="r1", version_id="v1",
                original_sha256="b" * 64, byte_length=100, page_mapping="mapped",
                pdf_page=1, legacy_region_count=0,
                geometry_policy="derived_pdf_text_only_legacy_raster_not_projected")
    assert ViewerContext.model_validate(data).pdf_page == 1
    for patch in ({"unknown": True}, {"pdf_page": 0}, {"page_mapping": "invented"}):
        with pytest.raises(ValidationError):
            ViewerContext.model_validate({**data, **patch})


def test_inventory_confirmation_is_strict():
    assert InventoryConfirmation.model_json_schema()["additionalProperties"] is False
    with pytest.raises(ValidationError):
        InventoryConfirmation.model_validate({"bundle_signature": "a" * 64, "unknown": True})


@pytest.mark.parametrize("model", [LoginBody, IntakeCommand, IntakeFile])
def test_request_models_reject_extra_fields(model):
    assert model.model_json_schema()["additionalProperties"] is False


def test_login_body_rejects_unexpected_property():
    assert LoginBody.model_validate({"email": "a@example.org", "password": "test"}).email == "a@example.org"
    with pytest.raises(ValidationError):
        LoginBody.model_validate({"email": "a@example.org", "password": "test", "role": "admin"})
