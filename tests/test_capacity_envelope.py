"""Capacity T20–T29: no unsafe promotion of a worker benchmark to pilot."""
from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from reportlab.pdfgen import canvas

from application.capacity_envelope import (
    CAPACITY_POLICY,
    MAX_INTAKE_BYTES,
    MAX_INVENTORY_BYTES,
    MAX_PDF_PAGES,
    MAX_SOURCE_BYTES,
    SOURCE_COUNT,
    refusal_reason,
)
from apps.api.dossier_export_release import LIMITS, _checked_artifacts
from apps.api.workspace_intake import IntakeCommand, WorkspaceIntake, preflight
from tests.fixtures.dossier_journey import dossier_bundle
from tests.test_f6_reviewed_exports import SignedReleaseStore


def request():
    return IntakeCommand(
        request_id=str(uuid4()),
        files=[
            {
                "role": s.role,
                "filename": s.filename,
                "media_type": s.media_type,
                "byte_length": len(s.content),
                "sha256": hashlib.sha256(s.content).hexdigest(),
                "content_base64": base64.b64encode(s.content).decode("ascii"),
            }
            for s in dossier_bundle()
        ],
    )


def test_capacity_generated_frontend_contract_is_exact_and_not_pilot_approved():
    path = Path("frontend/src/shared/api/capacity-policy.json")
    assert json.loads(path.read_text()) == CAPACITY_POLICY
    assert CAPACITY_POLICY["approval"] == "development_only_not_pilot_approved"
    assert CAPACITY_POLICY["source_count"] == SOURCE_COUNT == 4
    assert CAPACITY_POLICY["max_source_bytes"] == MAX_SOURCE_BYTES
    assert CAPACITY_POLICY["max_intake_bytes"] == MAX_INTAKE_BYTES
    assert CAPACITY_POLICY["max_inventory_bytes"] == MAX_INVENTORY_BYTES
    assert CAPACITY_POLICY["max_pdf_pages_per_source"] == MAX_PDF_PAGES
    assert LIMITS == {
        "json": CAPACITY_POLICY["max_export_json_bytes"],
        "markdown": CAPACITY_POLICY["max_export_markdown_bytes"],
        "docx": CAPACITY_POLICY["max_export_docx_bytes"],
    }


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"source_count": 3}, "CAPACITY_SOURCE_COUNT"),
        ({"byte_lengths": [1, 1, 1, 0]}, "CAPACITY_SOURCE_BYTES"),
        ({"byte_lengths": [1, 1, 1, MAX_SOURCE_BYTES + 1]}, "CAPACITY_SOURCE_BYTES"),
        ({"byte_lengths": [3_000_001] * 4}, "CAPACITY_INTAKE_BYTES"),
        ({"inventory_bytes": MAX_INVENTORY_BYTES + 1}, "CAPACITY_INVENTORY_BYTES"),
        ({"pdf_page_counts": [0]}, "CAPACITY_PDF_PAGES"),
        ({"pdf_page_counts": [MAX_PDF_PAGES + 1]}, "CAPACITY_PDF_PAGES"),
        ({"pdf_page_counts": [True]}, "CAPACITY_PDF_PAGES"),
    ],
)
def test_stable_refusal_reason(kwargs, reason):
    values = {
        "source_count": SOURCE_COUNT,
        "byte_lengths": [MAX_SOURCE_BYTES, 1, 1, 1],
        "inventory_bytes": MAX_INVENTORY_BYTES,
        "pdf_page_counts": [MAX_PDF_PAGES],
    }
    values.update(kwargs)
    assert refusal_reason(**values) == reason


def test_exact_capacity_boundary_is_admissible_before_format_validation():
    assert refusal_reason(
        source_count=4,
        byte_lengths=[MAX_SOURCE_BYTES, 1, 1, 1],
        inventory_bytes=MAX_INVENTORY_BYTES,
        pdf_page_counts=[MAX_PDF_PAGES],
    ) is None


def test_inventory_over_limit_rejected_before_register_or_any_write():
    cmd = request()
    raw = b"Stuk 1 " + b"A" * MAX_INVENTORY_BYTES
    inventory = cmd.files[1]
    inventory.byte_length = len(raw)
    inventory.sha256 = hashlib.sha256(raw).hexdigest()
    inventory.content_base64 = base64.b64encode(raw).decode("ascii")
    client = Mock()
    service = WorkspaceIntake(client, Mock())
    service.register = Mock()
    with pytest.raises(HTTPException) as failure:
        service.upload("synthetic", str(uuid4()), cmd)
    assert failure.value.status_code == 422
    assert "CAPACITY_INVENTORY_BYTES" in failure.value.detail
    service.register.assert_not_called()
    client.library.put_once.assert_not_called()


def test_over_pdf_page_limit_refuses_before_original_registration():
    raw = io.BytesIO()
    pdf = canvas.Canvas(raw, invariant=1)
    for number in range(MAX_PDF_PAGES + 1):
        pdf.drawString(40, 750, f"Synthetic printed page {number}")
        pdf.showPage()
    pdf.save()
    cmd = request()
    last = cmd.files[-1]
    last.byte_length = len(raw.getvalue())
    last.sha256 = hashlib.sha256(raw.getvalue()).hexdigest()
    last.content_base64 = base64.b64encode(raw.getvalue()).decode("ascii")
    service = WorkspaceIntake(Mock(), Mock())
    service.register = Mock()
    with pytest.raises(HTTPException) as failure:
        service.upload("synthetic", str(uuid4()), cmd)
    assert failure.value.status_code == 422
    service.register.assert_not_called()
    service.client.library.put_once.assert_not_called()


def test_declared_byte_overrun_is_rejected_at_request_schema():
    value = request().model_dump()
    value["files"][-1]["byte_length"] = MAX_SOURCE_BYTES + 1
    with pytest.raises(ValidationError):
        IntakeCommand.model_validate(value)


def test_release_json_overrun_fails_before_docx_computation(monkeypatch):
    import apps.api.dossier_export_release as module

    store = SignedReleaseStore()
    store.report["human_decisions"] = store.decisions
    called = Mock()
    monkeypatch.setattr(module, "annotated_docx", called)
    monkeypatch.setattr(
        module,
        "render_dossier_export",
        lambda report, format: "X" * (LIMITS["json"] + 1) if format == "json" else "short",
    )
    with pytest.raises(HTTPException) as failure:
        _checked_artifacts(store.report, store.original)
    assert failure.value.status_code == 422
    called.assert_not_called()


def test_release_docx_overrun_fails_before_persist(monkeypatch):
    import apps.api.dossier_export_release as module

    store = SignedReleaseStore()
    store.report["human_decisions"] = store.decisions
    monkeypatch.setattr(module, "annotated_docx", lambda *args: b"D" * (LIMITS["docx"] + 1))
    with pytest.raises(HTTPException) as failure:
        _checked_artifacts(store.report, store.original)
    assert failure.value.status_code == 422


def test_existing_small_release_roundtrips_under_current_cap():
    from docx import Document

    store = SignedReleaseStore()
    store.report["human_decisions"] = store.decisions
    artifacts = _checked_artifacts(store.report, store.original)
    assert set(artifacts) == set(LIMITS)
    assert all(0 < len(v) <= LIMITS[k] for k, v in artifacts.items())
    assert Document(io.BytesIO(artifacts["docx"])).paragraphs
