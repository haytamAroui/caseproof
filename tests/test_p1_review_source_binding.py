"""P1 read-only frozen-source review provenance; never a signed legal receipt."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from application.litigation.report_projection import render_dossier_export
from application.litigation.review_source_binding import (
    SOURCE_BINDING_SCHEMA,
    project_review_source_bindings,
)
from apps.api.dossier_journey import create_dossier_router, read_dossier_report

SNAPSHOT = "a" * 64
ORIGINAL = "b" * 64
REGION = "c" * 64
QUOTE = "Le paiement est enregistré."


def frozen_report() -> dict[str, Any]:
    return {
        "schema": "caseproof-dossier-v1",
        "snapshot_hash": SNAPSHOT,
        "case_id": "case-synthetic",
        "brief_id": "brief-synthetic",
        "sources": [
            {
                "role": "exhibit",
                "version_id": "source-v1",
                "sha256": ORIGINAL,
                "page_count": 3,
            }
        ],
        "findings": [
            {
                "reference_id": "ref-1",
                "literal": "Pièce 7, p. 2",
                "version_id": "source-v1",
                "source_sha256": ORIGINAL,
                "pdf_page": 2,
                "quoted_text": QUOTE,
                "source_text_context": f"Avant. {QUOTE} Après.",
                "source_text_context_partial": False,
                "literal_assessment": {"state": "exact_match"},
                "fidelity": "exact_match",
                "visual_assessment": {"regions": [{"region_id": REGION}]},
                "identity": "resolved",
                "page_mapping": "mapped",
                "support": "not_assessed",
            }
        ],
        "coverage": {"references_not_assessed": 1},
        "abstentions": [],
    }


def ledger_row() -> dict[str, Any]:
    return {
        "request_id": "request-synthetic-1",
        "reference_id": "ref-1",
        "reviewer_id": "pseudonymous-actual-session",
        "decision": "CONFIRMED_QUALIFIED",
        "rationale": "Read preserved PDF pixels and the surrounding paragraph.",
        "reviewed_region_ids": [REGION],
        "timestamp": "2026-11-07T12:00:00Z",
    }


def test_matching_version_page_and_regions_produce_only_correspondence() -> None:
    result = project_review_source_bindings(frozen_report(), [ledger_row()])
    assert len(result) == 1
    binding = result[0]
    assert binding["schema"] == SOURCE_BINDING_SCHEMA
    assert binding["snapshot_hash"] == SNAPSHOT
    assert binding["reviewer_id"] == "pseudonymous-actual-session"
    assert binding["source_version_id"] == "source-v1"
    assert binding["original_pdf_sha256"] == ORIGINAL
    assert binding["physical_pdf_page"] == 2
    assert binding["reviewed_region_ids"] == [REGION]
    assert binding["binding_state"] == "SOURCE_VERSION_AND_REVIEW_REGIONS_CORRESPOND"
    assert binding["derived_quote_sha256"] == hashlib.sha256(QUOTE.encode()).hexdigest()
    assert binding["rationale_sha256"] == hashlib.sha256(ledger_row()["rationale"].encode()).hexdigest()
    assert binding["signed_as_one_record"] is False
    assert binding["original_pdf_pixels_verified_by_this_projection"] is False
    assert binding["semantic_support_verified_by_this_projection"] is False
    assert "not an independent signed receipt" in binding["notice"]


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("version_id", "source-other"),
        ("source_sha256", "d" * 64),
        ("pdf_page", 99),
    ],
)
def test_wrong_source_version_sha_or_page_never_generates_positive_binding(
    field: str,
    bad: object,
) -> None:
    report = frozen_report()
    report["findings"][0][field] = bad
    binding = project_review_source_bindings(report, [ledger_row()])[0]
    assert binding["binding_state"] == "NOT_SOURCE_BOUND"
    assert binding["original_pdf_sha256"] is None
    assert binding["physical_pdf_page"] is None
    assert binding["derived_quote_sha256"] is None


def test_unconfirmed_regions_and_missing_source_regions_abstain() -> None:
    row = ledger_row()
    row["reviewed_region_ids"] = []
    binding = project_review_source_bindings(frozen_report(), [row])[0]
    assert binding["binding_state"] == "NOT_SOURCE_BOUND"
    assert binding["reviewed_region_ids"] == []
    assert binding["derived_quote_sha256"] is None
    report = frozen_report()
    report["findings"][0]["visual_assessment"]["regions"] = []
    missing_regions = project_review_source_bindings(report, [ledger_row()])[0]
    assert missing_regions["binding_state"] == "NOT_SOURCE_BOUND"
    assert missing_regions["derived_quote_sha256"] is None


def test_duplicated_quotation_and_ocr_never_produce_unique_quote_hash() -> None:
    report = frozen_report()
    report["findings"][0]["source_text_context"] = QUOTE + "\n" + QUOTE
    assert project_review_source_bindings(report, [ledger_row()])[0]["derived_quote_sha256"] is None
    report = frozen_report()
    report["findings"][0]["fidelity"] = "ocr_unreliable"
    assert project_review_source_bindings(report, [ledger_row()])[0]["derived_quote_sha256"] is None
    report = frozen_report()
    report["findings"][0]["source_text_context_partial"] = True
    assert project_review_source_bindings(report, [ledger_row()])[0]["derived_quote_sha256"] is None


def test_orphan_replay_and_cross_snapshot_fails_closed() -> None:
    report = frozen_report()
    row = ledger_row()
    row["reference_id"] = "other-matter"
    with pytest.raises(ValueError, match="orphan"):
        project_review_source_bindings(report, [row])
    row = ledger_row()
    row["snapshot_hash"] = "f" * 64
    with pytest.raises(ValueError, match="different snapshot"):
        project_review_source_bindings(report, [row])
    with pytest.raises(ValueError, match="duplicate durable"):
        project_review_source_bindings(report, [ledger_row(), deepcopy(ledger_row())])
    report["sources"].append(deepcopy(report["sources"][0]))
    with pytest.raises(ValueError, match="duplicate source version"):
        project_review_source_bindings(report, [ledger_row()])


def test_optional_authenticated_source_projection_preserves_canonical_export_bytes() -> None:
    class AuthorizedMock:
        def __init__(self) -> None:
            self.report = frozen_report()
            self.original = b"synthetic-docx-bytes"
            self.rows = [ledger_row()]

        def reopen(self, bearer: str, case: str, brief: str, snapshot: str):
            assert (bearer, case, brief, snapshot) == (
                "synthetic-signed-bearer",
                "case-synthetic",
                "brief-synthetic",
                SNAPSHOT,
            )
            return self.report, self.original

        def rpc(self, bearer: str, case: str, action: str, data: dict[str, Any]):
            assert bearer == "synthetic-signed-bearer"
            assert case == "case-synthetic"
            assert action == "decisions"
            assert data["snapshot_hash"] == SNAPSHOT
            return {"decisions": self.rows}

    store = AuthorizedMock()
    report, original = read_dossier_report(
        store,
        "synthetic-signed-bearer",
        "case-synthetic",
        "brief-synthetic",
        SNAPSHOT,
        decisions=True,
    )
    assert original == b"synthetic-docx-bytes"
    assert "review_source_bindings" not in report
    assert "review_source_bindings" not in store.report
    markdown = render_dossier_export(report, "markdown")
    assert "Read-only reviewer-to-source bindings" not in markdown
    serialized = render_dossier_export(report, "json")
    assert '"review_source_bindings"' not in serialized

    app = FastAPI()
    app.include_router(create_dossier_router(store))
    with TestClient(app) as client:
        response = client.get(
            f"/v2/matters/case-synthetic/briefs/brief-synthetic/dossier/"
            f"snapshots/{SNAPSHOT}/review-source-bindings",
            headers={"Authorization": "Bearer synthetic-signed-bearer"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "caseproof-review-source-bindings-view-v1"
    assert payload["signed_as_one_record"] is False
    assert payload["bindings"][0]["binding_state"] == ("SOURCE_VERSION_AND_REVIEW_REGIONS_CORRESPOND")
    assert payload["bindings"][0]["original_pdf_sha256"] == ORIGINAL


def test_unknown_original_page_count_never_produces_positive_binding() -> None:
    report = frozen_report()
    del report["sources"][0]["page_count"]
    binding = project_review_source_bindings(report, [ledger_row()])[0]
    assert binding["binding_state"] == "NOT_SOURCE_BOUND"
