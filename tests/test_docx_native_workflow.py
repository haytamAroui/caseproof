"""Hostile native-Word DOCX upload + durable review integration tests.

These fixtures simulate a signed database/storage adapter. The disposable
PostgreSQL SQL script separately checks actual RLS/RPC and audit atomicity.
"""
from __future__ import annotations

import hashlib
import io
from zipfile import ZIP_DEFLATED, ZipFile

from docx import Document
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.docx_editor_api import create_document_editor_router
from apps.api.docx_native_workflow import DOCX_MEDIA, MAX_DOCX
from infrastructure.parsers.docx_structured_editing import (
    DocumentTextEdit,
    edit_document_text,
    list_document_blocks,
)

CASE = "synthetic-matter"
BRIEF = "synthetic-brief"
SNAP = "a" * 64
ROOT = f"/v2/matters/{CASE}/briefs/{BRIEF}/dossier/editor/native"
REVIEW = "40eadc66-e2be-40ea-8e0b-646590688660"
COMMIT = "78956ac1-e5c8-497f-9490-1bfc22155d98"


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class Verifier:
    def verify_bearer(self, token: str):
        assert token == "signed"
        return type("User", (), {"subject_id": "user"})()


class Library:
    def __init__(self, store):
        self.store = store
        self.files = {}
        self.writes = 0

    def put_once(self, *, data, bearer, case_id, document_id, version_id):
        assert bearer == "signed" and case_id == CASE
        assert document_id == "document" and version_id == "new-version"
        assert version_id not in self.files
        self.files[version_id] = data
        self.writes += 1

    def read(self, *, bearer, case_id, document_id, version_id):
        assert bearer == "signed" and case_id == CASE
        assert document_id == "document"
        return self.store.original if version_id == BRIEF else self.files[version_id]


class Ledger:
    verifier = Verifier()

    def __init__(self, store):
        self.store = store
        self.reviewed = None
        self.reserved = None
        self.active = False

    def authorized(self, bearer, case):
        if self.store.revoked or bearer != "signed" or case != CASE:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)

    def editor_review(self, bearer, case, parent, snapshot, request, values):
        self.authorized(bearer, case)
        assert parent == BRIEF and snapshot == SNAP and request == REVIEW
        if self.reviewed is None:
            self.reviewed = dict(values)
        elif self.reviewed != values:
            raise HTTPException(409, "review replay changed")
        return {
            "state": "reviewed", "review_request_id": request,
            "command_sha256": values["command_sha256"],
            "candidate_sha256": values["candidate_sha256"],
        }

    def editor_status(self, bearer, case, request, review, fingerprint):
        self.authorized(bearer, case)
        if self.reviewed is None or self.reviewed["command_sha256"] != fingerprint or review != REVIEW:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        if self.reserved is None:
            return {"state": "absent"}
        if request != COMMIT or self.reserved["command_sha256"] != fingerprint:
            raise HTTPException(409, "replay changed")
        return {**self.reserved, "state": "active" if self.active else "reserved"}

    def editor_reserve(self, bearer, case, parent, snapshot, request, review, values):
        self.authorized(bearer, case)
        assert parent == BRIEF and snapshot == SNAP
        if self.reviewed is None or review != REVIEW or request != COMMIT:
            raise HTTPException(409, "prior whole-document approval required")
        if values["command_sha256"] != self.reviewed["command_sha256"] or (
            values["candidate_sha256"] != self.reviewed["candidate_sha256"]
        ):
            raise HTTPException(409, "review fingerprint mismatch")
        if self.reserved is None:
            self.reserved = {
                "parent_version_id": BRIEF, "parent_snapshot_hash": SNAP,
                "reference_id": "doc-edit:" + review,
                "command_sha256": values["command_sha256"],
                "original_sha256": values["candidate_sha256"],
                "byte_length": values["byte_length"],
                "document_id": "document", "version_id": "new-version",
            }
        return dict(self.reserved)

    def editor_activate(self, bearer, case, request, review, candidate_digest, size):
        self.authorized(bearer, case)
        if self.reserved is None or review != REVIEW:
            raise HTTPException(409, "no reviewed reservation")
        assert digest(self.store.client.library.files["new-version"]) == candidate_digest
        assert len(self.store.client.library.files["new-version"]) == size
        self.active = True
        self.store.active_version = "new-version"
        return {"state": "active", "version_id": "new-version"}


class Store:
    def __init__(self):
        doc = Document()
        doc.add_paragraph("Original passage")
        doc.add_table(rows=1, cols=1).cell(0, 0).text = "Table passage"
        src = io.BytesIO()
        doc.save(src)
        self.original = src.getvalue()
        self.revoked = False
        self.active_version = BRIEF
        self.revisions = Ledger(self)
        self.client = type("Client", (), {})()
        self.client.library = Library(self)

    def current_draft_version(self, bearer, case):
        self.revisions.authorized(bearer, case)
        return self.active_version

    def reopen(self, bearer, case, brief, snapshot):
        self.revisions.authorized(bearer, case)
        assert brief == BRIEF and snapshot == SNAP
        return {"brief_id": BRIEF, "snapshot_hash": SNAP}, self.original


def harness():
    store = Store()
    app = FastAPI()
    app.include_router(create_document_editor_router(store))
    app.add_exception_handler(
        AccessRejected,
        lambda _req, _exc: JSONResponse(status_code=404, content={"detail": "unavailable"}),
    )
    return TestClient(app), store


def candidate_bytes(source: bytes) -> bytes:
    doc = Document(io.BytesIO(source))
    doc.paragraphs[0].text = "Edited in Microsoft Word"
    doc.tables[0].cell(0, 0).text = "Changed Word table"
    stream = io.BytesIO()
    doc.save(stream)
    return stream.getvalue()


def metadata(source: bytes, candidate: bytes) -> dict:
    return {
        "snapshot_hash": SNAP, "original_sha256": digest(source),
        "candidate_sha256": digest(candidate), "byte_length": len(candidate),
    }


def upload(api, method: str, candidate: bytes, binding: dict, **headers):
    return api.post(
        f"{ROOT}/{method}",
        content=candidate,
        headers={
            "Authorization": "Bearer signed",
            "Content-Type": DOCX_MEDIA,
            "If-Match": "snapshot_id:" + binding["snapshot_hash"],
            "X-CaseProof-Snapshot-Hash": binding["snapshot_hash"],
            "X-CaseProof-Original-SHA256": binding["original_sha256"],
            "X-CaseProof-Candidate-SHA256": binding["candidate_sha256"],
            "X-CaseProof-Byte-Length": str(binding["byte_length"]),
            **headers,
        },
    )


def test_word_native_preview_preserves_word_tables_and_source():
    api, store = harness()
    candidate = candidate_bytes(store.original)
    binding = metadata(store.original, candidate)
    result = upload(api, "preview", candidate, binding)
    assert result.status_code == 200, result.text
    receipt = result.json()
    assert receipt["schema"] == "caseproof-native-docx-preview-v1"
    assert receipt["candidate_sha256"] == digest(candidate)
    assert receipt["original_sha256"] == digest(store.original)
    assert receipt["changed_package_parts"] >= 1
    assert receipt["evidence_status"] == "unverified"
    assert receipt["activated"] is False
    assert store.client.library.writes == 0
    assert Document(io.BytesIO(store.original)).paragraphs[0].text == "Original passage"


def test_true_word_tracked_changes_are_preserved_not_flattened():
    api, store = harness()
    block = next(b for b in list_document_blocks(store.original) if b.text == "Original passage")
    candidate = edit_document_text(
        store.original, expected_sha256=digest(store.original),
        edits=[DocumentTextEdit(
            block.part, block.paragraph_index,
            block.text_sha256, block.text, "Tracked Word insert", True,
        )], author="Native Word user", timestamp="2026-11-05T06:00:00+00:00",
    )
    response = upload(api, "preview", candidate, metadata(store.original, candidate))
    assert response.status_code == 200, response.text
    with ZipFile(io.BytesIO(candidate)) as z:
        xml = z.read("word/document.xml")
    assert b"w:delText" in xml and b"w:ins" in xml


def test_native_preflight_refuses_dangerous_or_unbound_docx():
    api, store = harness()
    candidate = candidate_bytes(store.original)
    binding = metadata(store.original, candidate)
    assert upload(api, "preview", candidate, {**binding, "original_sha256": "b" * 64}).status_code == 412
    assert upload(api, "preview", candidate, {**binding, "candidate_sha256": "c" * 64}).status_code == 422
    assert upload(api, "preview", candidate[:-1], binding).status_code == 422
    assert upload(api, "preview", store.original,
                  {**binding, "candidate_sha256": digest(store.original), "byte_length": len(store.original)}).status_code == 422
    assert upload(api, "preview", candidate, {
        **binding, "byte_length": MAX_DOCX + 1
    }).status_code == 422
    with io.BytesIO() as bad:
        with ZipFile(bad, "w", ZIP_DEFLATED) as output, ZipFile(io.BytesIO(candidate)) as source:
            for entry in source.infolist():
                output.writestr(entry, source.read(entry))
            output.writestr("word/vbaProject.bin", b"not permitted")
        hostile = bad.getvalue()
    assert upload(api, "preview", hostile, metadata(store.original, hostile)).status_code == 422
    assert store.client.library.writes == 0
    store.revoked = True
    denied = upload(api, "preview", candidate, binding)
    assert denied.status_code == 404
    assert b"Original passage" not in denied.content


def test_native_review_reserved_commit_recovery_and_revocation():
    api, store = harness()
    candidate = candidate_bytes(store.original)
    binding = metadata(store.original, candidate)
    assert upload(api, "preview", candidate, binding).status_code == 200
    headers = {"Authorization": "Bearer signed", "If-Match": "snapshot_id:" + SNAP}
    review = {**binding, "review_request_id": REVIEW,
              "rationale": "I reviewed the entire Word document and tracked all changes."}
    commit = {**binding, "review_request_id": REVIEW, "request_id": COMMIT}
    denied = upload(api, "commit", candidate, binding,
                    **{"Idempotency-Key": COMMIT, "X-CaseProof-Review-Request-ID": REVIEW})
    assert denied.status_code in (403, 404)
    assert store.client.library.writes == 0
    assert api.post(f"{ROOT}/review", json=review, headers={
        **headers, "Idempotency-Key": COMMIT,
    }).status_code == 422
    saved = api.post(f"{ROOT}/review", json=review, headers={
        **headers, "Idempotency-Key": REVIEW,
    })
    assert saved.status_code == 200, saved.text
    assert saved.json()["saved"] is True
    assert store.client.library.writes == 0
    status = api.post(f"{ROOT}/status", json=commit, headers=headers)
    assert status.status_code == 200 and status.json()["state"] == "absent"
    committed = upload(api, "commit", candidate, binding,
                       **{"Idempotency-Key": COMMIT, "X-CaseProof-Review-Request-ID": REVIEW})
    assert committed.status_code == 200, committed.text
    assert committed.json()["requires_recheck"] is True
    assert store.client.library.writes == 1
    exported = store.client.library.files["new-version"]
    assert digest(exported) == digest(candidate)
    assert Document(io.BytesIO(exported)).tables[0].cell(0, 0).text == "Changed Word table"
    assert Document(io.BytesIO(store.original)).tables[0].cell(0, 0).text == "Table passage"
    replay = upload(api, "commit", candidate, binding,
                    **{"Idempotency-Key": COMMIT, "X-CaseProof-Review-Request-ID": REVIEW})
    assert replay.status_code == 200
    assert replay.json()["reconciled"] is True
    assert store.client.library.writes == 1
    store.revoked = True
    assert api.post(f"{ROOT}/status", json=commit, headers=headers).status_code == 404
    assert upload(api, "commit", candidate, binding,
                  **{"Idempotency-Key": COMMIT, "X-CaseProof-Review-Request-ID": REVIEW}).status_code == 404
