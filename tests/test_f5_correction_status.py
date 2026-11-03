"""F5 durable reconciliation must be read-only and command-bound."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from apps.api.dossier_journey import CorrectionCommitBody, DossierStore
from apps.api.access_control import AccessRejected


class Revisions:
    def __init__(self, state: str):
        self.state = state
        self.calls = []

    def reserve(self, bearer, case, request, action, values):
        self.calls.append((bearer, case, request, action, values))
        assert action == "status"  # no reserve, upload or activation side effect
        if self.state == "absent":
            return {"state": "absent"}
        return {
            "state": self.state,
            "parent_snapshot_hash": "a" * 64,
            "reference_id": "reference-1",
            "parent_version_id": "draft-1",
            "version_id": "new-draft-2",
        }


def command() -> CorrectionCommitBody:
    return CorrectionCommitBody(
        snapshot_hash="a" * 64,
        original_sha256="b" * 64,
        reference_id="reference-1",
        paragraph_index=0,
        before="Piece 1",
        after="Piece 2",
        request_id=str(uuid4()),
    )


@pytest.mark.parametrize("state", ["absent", "reserved", "active"])
def test_status_never_writes(state: str) -> None:
    store = object.__new__(DossierStore)
    store.revisions = Revisions(state)
    result = store.correction_status("signed-user", "matter-1", "draft-1", command())
    assert result["state"] == state
    assert result["committed"] is (state == "active")
    assert len(store.revisions.calls) == 1
    assert store.revisions.calls[0][3] == "status"
    assert len(store.revisions.calls[0][4]["command_sha256"]) == 64


def test_status_rejects_mismatched_parent() -> None:
    store = object.__new__(DossierStore)
    store.revisions = Revisions("active")
    with pytest.raises(HTTPException) as exc:
        store.correction_status("signed-user", "matter-1", "wrong-draft", command())
    assert exc.value.status_code == 409


def test_status_rejects_unknown_state() -> None:
    store = object.__new__(DossierStore)
    store.revisions = Revisions("unknown")
    with pytest.raises(AccessRejected):
        store.correction_status("signed-user", "matter-1", "draft-1", command())
