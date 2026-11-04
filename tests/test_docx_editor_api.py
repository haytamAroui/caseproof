"""Real FastAPI transport tests for the signed current-DOCX candidate editor."""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from zipfile import ZipFile

from docx import Document
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from apps.api.access_control import AccessRejected
from apps.api.docx_editor_api import create_document_editor_router

SNAPSHOT = "a" * 64
DATE = "2026-11-04T20:00:00+00:00"
BASE = "/v2/matters/matter/briefs/current/dossier/editor"
HEADERS = {"Authorization": "Bearer signed", "If-Match": "snapshot_id:" + SNAPSHOT}


@dataclass(frozen=True)
class Actor:
    subject_id: str = "7bf0fd99-0801-4db8-86e4-32b60ac6a740"


class Verifier:
    def verify_bearer(self, token: str) -> Actor:
        if token != "signed":
            raise ValueError("unknown actor")
        return Actor()


class Revisions:
    verifier = Verifier()


class Store:
    revisions = Revisions()
    revoked = False
    active_version = "current"

    def __init__(self) -> None:
        document = Document()
        document.add_paragraph("Original paragraph")
        cells = document.add_table(rows=1, cols=2).rows[0].cells
        cells[0].text = "Original table cell"
        cells[1].text = "Unrelated second cell"
        stream = io.BytesIO()
        document.save(stream)
        self.original = stream.getvalue()
        self.reads: list[tuple[str, str, str, str]] = []

    def current_draft_version(self, bearer: str, case: str) -> str:
        assert bearer == "signed" and case == "matter"
        return self.active_version

    def reopen(self, bearer: str, case: str, brief: str, snapshot: str):
        self.reads.append((bearer, case, brief, snapshot))
        if self.revoked or bearer != "signed" or case != "matter":
            from apps.api.access_control import AccessFailure, AccessRejected
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        if snapshot != SNAPSHOT or brief != "current":
            raise ValueError("not a bound snapshot")
        return {"brief_id": brief, "snapshot_hash": SNAPSHOT}, self.original


def client() -> tuple[TestClient, Store]:
    store = Store()
    app = FastAPI()
    app.include_router(create_document_editor_router(store))
    app.add_exception_handler(
        AccessRejected,
        lambda _request, _error: JSONResponse(
            status_code=404, content={"detail": "unavailable"}
        ),
    )
    return TestClient(app), store


def command(original: bytes, block: dict, *, after: str, track: bool = False) -> dict:
    return {
        "snapshot_hash": SNAPSHOT,
        "original_sha256": hashlib.sha256(original).hexdigest(),
        "timestamp": DATE,
        "edits": [{
            "part": block["part"],
            "paragraph_index": block["paragraph_index"],
            "expected_text_sha256": block["text_sha256"],
            "before": block["text"],
            "after": after,
            "track_changes": track,
        }],
    }


def test_current_snapshot_editor_pages_and_exact_binary_derivative():
    api, store = client()
    route = f"{BASE}/blocks?snapshot_hash={SNAPSHOT}&offset=0&limit=20"
    response = api.get(route, headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["schema"] == "caseproof-docx-editor-blocks-v1"
    assert data["original_sha256"] == hashlib.sha256(store.original).hexdigest()
    assert data["committed"] is False
    assert data["editable_count"] >= 3
    table = next(row for row in data["blocks"] if row["text"] == "Original table cell")
    assert table["kind"] == "table" and table["editable"]
    requested = command(store.original, table, after="Edited table cell")
    preview = api.post(f"{BASE}/preview", json=requested, headers=HEADERS)
    assert preview.status_code == 200
    proof = preview.json()
    assert proof["committed"] is False
    assert proof["activated"] is False
    assert proof["requires_document_scoped_review_and_import"] is True
    assert "content_base64" not in proof
    received = api.post(f"{BASE}/candidate", json=requested, headers=HEADERS)
    assert received.status_code == 200
    assert received.headers["cache-control"] == "no-store"
    assert received.headers["x-content-type-options"] == "nosniff"
    assert received.headers["x-caseproof-snapshot"] == SNAPSHOT
    assert hashlib.sha256(received.content).hexdigest() == proof["derivative_sha256"]
    assert len(received.content) == proof["derivative_byte_length"]
    assert Document(io.BytesIO(received.content)).tables[0].cell(0, 0).text == "Edited table cell"
    assert Document(io.BytesIO(store.original)).tables[0].cell(0, 0).text == "Original table cell"
    assert store.reads


def test_tracking_preview_and_explicit_revision_decisions():
    api, store = client()
    blocks = api.get(f"{BASE}/blocks?snapshot_hash={SNAPSHOT}", headers=HEADERS).json()["blocks"]
    paragraph = next(b for b in blocks if b["text"] == "Original paragraph")
    proposed = command(store.original, paragraph, after="Proposed paragraph", track=True)
    response = api.post(f"{BASE}/candidate", json=proposed, headers=HEADERS)
    assert response.status_code == 200
    with ZipFile(io.BytesIO(response.content)) as package:
        xml = package.read("word/document.xml")
    assert b"w:delText" in xml
    assert b"w:ins" in xml
    # Fake storage swap just for a synthetic already-versioned draft.
    store.original = response.content
    revisions = api.get(f"{BASE}/revisions?snapshot_hash={SNAPSHOT}", headers=HEADERS)
    assert revisions.status_code == 200
    rows = revisions.json()["revisions"]
    assert len(rows) == 2
    assert {r["kind"] for r in rows} == {"inserted", "deleted"}
    decisions = {
        "snapshot_hash": SNAPSHOT,
        "original_sha256": hashlib.sha256(store.original).hexdigest(),
        "timestamp": DATE,
        "decisions": [{
            "part": row["part"], "revision_id": row["revision_id"], "action": "accept",
        } for row in rows],
    }
    accepted = api.post(f"{BASE}/candidate", json=decisions, headers=HEADERS)
    assert accepted.status_code == 200
    assert Document(io.BytesIO(accepted.content)).paragraphs[0].text == "Proposed paragraph"


def test_stale_snapshot_wrong_source_and_forged_target_fail_closed():
    api, store = client()
    response = api.get(f"{BASE}/blocks?snapshot_hash={SNAPSHOT}", headers=HEADERS)
    paragraph = response.json()["blocks"][0]
    requested = command(store.original, paragraph, after="Proposed")
    assert api.post(
        f"{BASE}/preview", json=requested, headers={
            "Authorization": "Bearer signed", "If-Match": "snapshot_id:" + "f" * 64,
        }
    ).status_code == 412
    assert api.post(f"{BASE}/preview", json={
        **requested, "original_sha256": "e" * 64,
    }, headers=HEADERS).status_code == 412
    assert api.post(f"{BASE}/candidate", json={
        **requested, "edits": [{
            **requested["edits"][0], "expected_text_sha256": "e" * 64,
        }],
    }, headers=HEADERS).status_code == 422
    assert api.post(f"{BASE}/candidate", json={
        **requested, "edits": requested["edits"] * 2,
    }, headers=HEADERS).status_code == 422
    assert api.post(f"{BASE}/candidate", json={
        **requested, "decisions": [{
            "part": "word/document.xml", "revision_id": 5, "action": "accept",
        }],
    }, headers=HEADERS).status_code == 422
    assert api.get(f"{BASE}/blocks?snapshot_hash={SNAPSHOT}&limit=21", headers=HEADERS).status_code == 422
    store.active_version = "superseding-draft"
    assert api.get(f"{BASE}/blocks?snapshot_hash={SNAPSHOT}", headers=HEADERS).status_code == 409
    assert api.post(f"{BASE}/candidate", json=requested, headers=HEADERS).status_code == 409


def test_revocation_denies_read_and_preview_without_leaking_bytes():
    api, store = client()
    store.revoked = True
    metadata = api.get(f"{BASE}/blocks?snapshot_hash={SNAPSHOT}", headers=HEADERS)
    assert metadata.status_code in (403, 404)
    candidate = api.post(f"{BASE}/candidate", json={
        "snapshot_hash": SNAPSHOT,
        "original_sha256": hashlib.sha256(store.original).hexdigest(),
        "timestamp": DATE,
        "edits": [{
            "part": "word/document.xml", "paragraph_index": 0,
            "expected_text_sha256": "0" * 64,
            "before": "Original paragraph", "after": "Other",
            "track_changes": False,
        }],
    }, headers=HEADERS)
    assert candidate.status_code in (403, 404)
    assert b"Original paragraph" not in candidate.content


REVIEW_ID = "11223344-1122-4122-8122-112233445566"
COMMIT_ID = "55667788-5566-4566-8566-556677889900"


def test_document_wide_review_commit_replay_and_integrity_with_disposable_adapter():
    """Synthetic API integration, not genuine Supabase signed SQL acceptance."""
    from fastapi import HTTPException

    from apps.api.docx_editor_api import editor_command_sha256

    api, store = client()
    blocks = api.get(
        f"{BASE}/blocks?snapshot_hash={SNAPSHOT}", headers=HEADERS
    ).json()["blocks"]
    original = store.original
    selected = next(row for row in blocks if row["text"] == "Original table cell")
    draft = command(original, selected, after="Reviewed table revision", track=False)
    digest = editor_command_sha256(
        "matter", "current",
        __import__("apps.api.docx_editor_api", fromlist=["EditorCandidateBody"]).EditorCandidateBody(
            **draft
        ),
    )

    class Library:
        files = {}
        writes = 0

        def put_once(self, *, data, bearer, case_id, document_id, version_id):
            assert bearer == "signed" and case_id == "matter"
            assert document_id == "document"
            assert version_id == "derived"
            assert version_id not in self.files
            self.files[version_id] = data
            self.writes += 1

        def read(self, *, bearer, case_id, document_id, version_id):
            assert bearer == "signed" and case_id == "matter"
            assert document_id == "document"
            if version_id == "current":
                return original
            return self.files[version_id]

    class Client:
        library = Library()

    class Ledger:
        verifier = Verifier()
        approved = None
        reserved = None
        active = False

        def editor_review(self, bearer, case, parent, snapshot, request, values):
            assert bearer == "signed" and case == "matter" and parent == "current"
            assert snapshot == SNAPSHOT and request == REVIEW_ID
            assert values["command_sha256"] == digest
            if self.approved is None:
                self.approved = dict(values)
            elif self.approved != values:
                raise HTTPException(409, "review replay conflict")
            return {
                "state": "reviewed", "review_request_id": request,
                "command_sha256": digest,
                "candidate_sha256": values["candidate_sha256"],
            }

        def reserve(self, bearer, case, request, action, values):
            assert bearer == "signed" and case == "matter"
            assert action == "status" and request == COMMIT_ID
            if values["command_sha256"] != digest:
                raise HTTPException(409, "durable request ID used with different edit")
            if self.reserved is None:
                return {"state": "absent"}
            return {
                **self.reserved,
                "state": "active" if self.active else "reserved",
            }

        def editor_reserve(self, bearer, case, parent, snapshot, request, review, values):
            assert bearer == "signed" and case == "matter"
            assert parent == "current" and snapshot == SNAPSHOT
            assert request == COMMIT_ID and review == REVIEW_ID
            if self.approved is None:
                raise HTTPException(409, "explicit document review required")
            if values["command_sha256"] != digest:
                raise HTTPException(409, "document command differs")
            if values["candidate_sha256"] != self.approved["candidate_sha256"]:
                raise HTTPException(409, "candidate content differs")
            if self.reserved is None:
                self.reserved = {
                    "parent_version_id": "current",
                    "parent_snapshot_hash": SNAPSHOT,
                    "reference_id": "doc-edit:" + REVIEW_ID,
                    "command_sha256": digest,
                    "original_sha256": values["candidate_sha256"],
                    "byte_length": values["byte_length"],
                    "document_id": "document",
                    "version_id": "derived",
                }
            return dict(self.reserved)

        def editor_activate(self, bearer, case, request, review, digest_value, size):
            assert review == REVIEW_ID
            assert self.reserved is not None
            assert digest_value == self.reserved["original_sha256"]
            assert size == self.reserved["byte_length"]
            self.active = True
            store.active_version = "derived"
            return {"state": "active", "version_id": "derived"}

    store.revisions = Ledger()
    store.client = Client()
    review = {**draft, "review_request_id": REVIEW_ID,
              "rationale": "I reviewed the whole synthetic draft change."}
    commit = {**draft, "review_request_id": REVIEW_ID,
              "request_id": COMMIT_ID}
    missing = api.post(
        f"{BASE}/commit", json=commit,
        headers={**HEADERS, "Idempotency-Key": COMMIT_ID},
    )
    assert missing.status_code == 409
    assert store.client.library.writes == 0
    bad_review = api.post(
        f"{BASE}/review", json=review,
        headers={**HEADERS, "Idempotency-Key": COMMIT_ID},
    )
    assert bad_review.status_code == 422
    saved = api.post(
        f"{BASE}/review", json=review,
        headers={**HEADERS, "Idempotency-Key": REVIEW_ID},
    )
    assert saved.status_code == 200
    assert saved.json()["persisted"] is True
    assert saved.json()["activated"] is False
    assert saved.json()["command_sha256"] == digest
    assert store.client.library.writes == 0
    again = api.post(
        f"{BASE}/review", json=review,
        headers={**HEADERS, "Idempotency-Key": REVIEW_ID},
    )
    assert again.status_code == 200
    status = api.post(f"{BASE}/status", json=commit, headers=HEADERS)
    assert status.status_code == 200 and status.json()["state"] == "absent"
    committed = api.post(
        f"{BASE}/commit", json=commit,
        headers={**HEADERS, "Idempotency-Key": COMMIT_ID},
    )
    assert committed.status_code == 200
    assert committed.json()["version_id"] == "derived"
    assert committed.json()["requires_recheck"] is True
    assert store.client.library.writes == 1
    rewritten = Document(io.BytesIO(store.client.library.files["derived"]))
    assert rewritten.tables[0].cell(0, 0).text == "Reviewed table revision"
    assert Document(io.BytesIO(original)).tables[0].cell(0, 0).text == "Original table cell"
    replay = api.post(
        f"{BASE}/commit", json=commit,
        headers={**HEADERS, "Idempotency-Key": COMMIT_ID},
    )
    assert replay.status_code == 200
    assert replay.json()["reconciled"] is True
    assert store.client.library.writes == 1
    changed_command = {
        **commit,
        "edits": [{**commit["edits"][0], "after": "Unapproved variation"}],
    }
    conflict = api.post(
        f"{BASE}/commit", json=changed_command,
        headers={**HEADERS, "Idempotency-Key": COMMIT_ID},
    )
    assert conflict.status_code == 409
    assert store.client.library.writes == 1
