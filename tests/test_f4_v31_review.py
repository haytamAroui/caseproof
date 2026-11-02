"""F4 signed reviewer projections: no historical writes or guessed draft anchors."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from pydantic import ValidationError

from application.litigation.workspace_contract import DraftExcerptView, ReviewLedgerView
from apps.api.access_control import AccessRejected
from apps.api.dossier_journey import VisualDecisionBody, create_dossier_router
from tests.test_phase4_headless_api import docx

SNAP = "a" * 64
CASE = "case"
BRIEF = "brief"
REF = "ref-1"
DRAFT = docx("Before Stuk 1 after.")


class Stub:
    def __init__(self):
        self.revoked = False
        self.stale = False
        self.rows = []
        self.last_action = None
        self.report = {
            "snapshot_hash": SNAP,
            "findings": [{
                "reference_id": REF, "literal": "Stuk 1",
                "region": "word/document.xml", "offsets": {"start": 7, "end": 13},
                "technical_check": "checked",
                "visual_assessment": {"regions": [{"region_id": "region-one"}]},
            }],
        }

    def reopen(self, bearer, case, brief, snapshot):
        if self.revoked or (bearer, case, brief) != ("owner", CASE, BRIEF):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        if self.stale or snapshot != SNAP:
            from fastapi import HTTPException
            raise HTTPException(409, "stale scope")
        return self.report, DRAFT

    def rpc(self, bearer, case, action, data=None):
        self.last_action = action
        if self.revoked:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        if action == "decisions":
            return {"decisions": self.rows}
        if action == "review":
            request = data["request_id"]
            saved = next((x for x in self.rows if x["request_id"] == str(request)), None)
            if saved is None:
                self.rows.append({
                    "request_id": str(request), "reference_id": data["reference_id"],
                    "decision": data["decision"], "rationale": data["rationale"],
                    "reviewer_id": "owner",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "reviewed_region_ids": data["reviewed_region_ids"],
                })
            elif any(saved[k] != data[k] for k in ("reference_id", "decision", "rationale", "reviewed_region_ids")):
                from fastapi import HTTPException
                raise HTTPException(409, "different replay")
            return {"request_id": str(request), "reference_id": data["reference_id"],
                    "decision": data["decision"], "reviewer_id": "owner"}
        raise AssertionError(action)


def rig():
    store = Stub()
    app = FastAPI()
    app.include_router(create_dossier_router(store))

    @app.exception_handler(AccessRejected)
    def denied(request, error):
        return JSONResponse({"error": error.code.value}, status_code=error.http_status)
    return store, TestClient(app)


def route(suffix: str):
    return f"/v2/matters/{CASE}/briefs/{BRIEF}/dossier/{suffix}"


def auth():
    return {"Authorization": "Bearer owner"}


def test_review_ledger_and_preserved_draft_context_are_current_authorized():
    store, client = rig()
    ledger = client.get(route(f"reviews?snapshot_hash={SNAP}"), headers=auth())
    assert ledger.status_code == 200
    assert ledger.json()["schema"] == "caseproof-review-ledger-v1"
    assert ledger.json()["decisions"] == []
    excerpt = client.get(route(f"snapshots/{SNAP}/references/{REF}/draft-context"), headers=auth())
    assert excerpt.status_code == 200
    data = excerpt.json()
    assert data["available"] and data["excerpt"][data["selection_start"]:data["selection_end"]] == "Stuk 1"
    assert "Before" in data["excerpt"] and data["region"] == "word/document.xml"
    store.stale = True
    assert client.get(route(f"reviews?snapshot_hash={SNAP}"), headers=auth()).status_code == 409
    assert client.get(route(f"snapshots/{SNAP}/references/{REF}/draft-context"), headers=auth()).status_code == 409
    store.stale = False
    store.revoked = True
    assert client.get(route(f"reviews?snapshot_hash={SNAP}"), headers=auth()).status_code == 404
    assert client.get(route(f"snapshots/{SNAP}/references/{REF}/draft-context"), headers=auth()).status_code == 404


def test_unsupported_or_duplicate_docx_anchor_never_selects_first_occurrence():
    store, client = rig()
    store.report["findings"][0]["offsets"] = {"start": 0, "end": 6}
    result = client.get(route(f"snapshots/{SNAP}/references/{REF}/draft-context"), headers=auth()).json()
    assert result["available"] is False
    assert result["reason"] == "unsupported_or_ambiguous_anchor"
    assert result["excerpt"] == ""
    assert client.get(route(f"snapshots/{SNAP}/references/unknown/draft-context"), headers=auth()).status_code == 404


def test_review_replay_returns_one_persisted_receipt_and_rejects_changed_input():
    store, client = rig()
    command = {
        "snapshot_hash": SNAP, "reference_id": REF, "request_id": str(uuid4()),
        "decision": "CONFIRMED_SUPPORTED", "rationale": "Compared pixels and context",
        "reviewed_region_ids": ["region-one"],
    }
    first = client.post(route("reviews"), json=command, headers=auth())
    assert first.status_code == 200
    second = client.post(route("reviews"), json=command, headers=auth())
    assert second.status_code == 200
    ledger = client.get(route(f"reviews?snapshot_hash={SNAP}"), headers=auth()).json()
    assert len(ledger["decisions"]) == 1
    assert ledger["decisions"][0]["request_id"] == command["request_id"]
    assert client.post(route("reviews"), json={**command, "rationale": "Changed"}, headers=auth()).status_code == 409
    assert client.post(route("reviews"), json={**command, "reviewed_region_ids": []}, headers=auth()).status_code == 409
    store.revoked = True
    assert client.post(route("reviews"), json=command, headers=auth()).status_code == 404


def test_review_request_and_ledger_reject_invented_decisions_or_timestamps():
    command = {"snapshot_hash": SNAP, "reference_id": REF, "request_id": str(uuid4()),
               "decision": "CONFIRMED_SUPPORTED", "rationale": "Inspected"}
    assert VisualDecisionBody.model_validate(command).decision == "CONFIRMED_SUPPORTED"
    for bad in ({**command, "decision": "VERIFIED"}, {**command, "unexpected": "verified"},
                {**command, "rationale": ""}):
        with pytest.raises(ValidationError):
            VisualDecisionBody.model_validate(bad)
    row = {
        "schema": "caseproof-review-ledger-v1", "case_id": CASE,
        "brief_id": BRIEF, "snapshot_hash": SNAP,
        "decisions": [{"reference_id": REF, "decision": "CONFIRMED_SUPPORTED",
                       "rationale": "Inspected", "reviewer_id": "owner",
                       "timestamp": "2026-11-02T18:00:00Z", "request_id": str(uuid4()),
                       "reviewed_region_ids": []}],
    }
    assert ReviewLedgerView.model_validate(row).decisions
    for bad in [
        {**row, "decisions": row["decisions"] * 2},
        {**row, "decisions": [{**row["decisions"][0], "timestamp": "yesterday"}]},
        {**row, "decisions": [{**row["decisions"][0], "decision": "VERIFIED"}]},
    ]:
        with pytest.raises(ValidationError):
            ReviewLedgerView.model_validate(bad)
    with pytest.raises(ValidationError):
        DraftExcerptView.model_validate({
            "schema": "caseproof-draft-excerpt-v1", "case_id": CASE, "brief_id": BRIEF,
            "snapshot_hash": SNAP, "reference_id": REF, "original_sha256": "b"*64,
            "available": True, "excerpt": "text", "selection_start": 0, "selection_end": 9,
        })
