"""Tests for BE-01: progressive inventory confirmation default vs strict firm policy
in FastAPI (apps/api/dossier_journey.py).
"""
from __future__ import annotations

import hashlib
import io
import zipfile
from typing import Any

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from apps.api.dossier_journey import DossierStore, VerificationOptions


def _minimal_docx(paragraph: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>",
        )
        zf.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/>'
            "</Relationships>",
        )
        zf.writestr(
            "word/document.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body><w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p></w:body>"
            "</w:document>",
        )
    return buf.getvalue()


class _FakeStore(DossierStore):
    def __init__(self, *, confirmed: bool) -> None:
        self._confirmed = confirmed
        self._draft = _minimal_docx("Voir Pièce 1, p. 2 pour le contrat.")
        self._inventory = b"Piece 1 - Contrat signe"
        self.client = None  # type: ignore[assignment]
        self.rights_gate = None
        self.receipt_key = b"test-hmac-key-32-bytes-minimum!!"

    def rpc(self, bearer: str, case: str, action: str, payload: dict[str, Any] | None = None) -> Any:
        if action == "context":
            return {
                "case_id": case,
                "bundle_signature": "b" * 64,
                "confirmation": (
                    {
                        "request_id": "conf-req-1",
                        "reviewer_id": "rev-1",
                        "timestamp": "2026-11-24T00:00:00Z",
                        "payload": {
                            "entries": [
                                {
                                    "label": "piece",
                                    "number": "1",
                                    "source_version_id": None,
                                    "pages": [],
                                }
                            ],
                            "inventory_complete": True,
                            "exceptions": [],
                        },
                    }
                    if self._confirmed
                    else None
                ),
                "reviews": [],
            }
        if action == "snapshot":
            return {"ok": True}
        raise AssertionError(f"Unexpected rpc action: {action}")

    def sources(self, bearer: str, case: str, *, inspect_pdf: bool = True) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
        draft_sha = hashlib.sha256(self._draft).hexdigest()
        inv_sha = hashlib.sha256(self._inventory).hexdigest()
        return (
            [
                {
                    "role": "draft",
                    "document_id": "doc-draft",
                    "version_id": "brief-1",
                    "filename": "conclusions.docx",
                    "media_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "sha256": draft_sha,
                    "byte_length": len(self._draft),
                },
                {
                    "role": "inventory",
                    "document_id": "doc-inv",
                    "version_id": "inv-1",
                    "filename": "bordereau.txt",
                    "media_type": "text/plain",
                    "sha256": inv_sha,
                    "byte_length": len(self._inventory),
                },
            ],
            {"brief-1": self._draft, "inv-1": self._inventory},
        )


def test_verification_options_defaults_to_progressive_mode() -> None:
    opts = VerificationOptions()
    assert opts.require_confirmed_inventory is False

    strict = VerificationOptions(require_confirmed_inventory=True)
    assert strict.require_confirmed_inventory is True

    with pytest.raises(ValidationError):
        VerificationOptions(require_confirmed_inventory="yes")  # type: ignore[arg-type]


def test_progressive_default_runs_immediately_with_inventory_unconfirmed() -> None:
    store = _FakeStore(confirmed=False)
    report, _ = store.load("tok", "case-1", "brief-1", require_confirmed_inventory=False)

    assert report["confirmation_id"] is None
    assert report["coverage"]["inventory_confirmation_mode"] == "progressive_unconfirmed"
    assert len(report["findings"]) == 1
    finding = report["findings"][0]
    assert finding["identity"] == "not_assessed"
    assert finding["identity_reason"] == "INVENTORY_UNCONFIRMED"


def test_strict_mode_fails_closed_when_inventory_unconfirmed() -> None:
    store = _FakeStore(confirmed=False)
    with pytest.raises(HTTPException) as exc_info:
        store.load("tok", "case-1", "brief-1", require_confirmed_inventory=True)
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "inventory_confirmation_required"


def test_strict_mode_succeeds_when_inventory_is_confirmed() -> None:
    store = _FakeStore(confirmed=True)
    report, _ = store.load("tok", "case-1", "brief-1", require_confirmed_inventory=True)

    assert report["confirmation_id"] == "conf-req-1"
    assert report["coverage"]["inventory_confirmation_mode"] == "confirmed"
