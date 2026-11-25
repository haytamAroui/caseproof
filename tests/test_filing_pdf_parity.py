"""Tests for Final Filing PDF vs. verified DOCX parity check (Farhat v. Cutera guard)."""

from __future__ import annotations

import hashlib
import io
from uuid import uuid4

from docx import Document
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from application.litigation.filing_pdf_parity import (
    PARITY_SCHEMA,
    compare_verified_docx_and_filing_pdf,
    normalize_filing_text,
)
from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.dossier_export_release import create_release_router
from infrastructure.parsers.filing_pdf_parity_adapter import check_filing_pdf_parity
from scripts.run_prefiling_partner_demo import (
    DEMO_BRIEF_ID,
    DEMO_CASE_ID,
    create_partner_demo_app,
)

CASE_ID = str(uuid4())
BRIEF_ID = str(uuid4())
SNAPSHOT = "a" * 64


def _docx_bytes(*paragraphs: str, add_header: str | None = None) -> bytes:
    doc = Document()
    for para in paragraphs:
        doc.add_paragraph(para)
    if add_header:
        doc.sections[0].header.paragraphs[0].text = add_header
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _pdf_bytes(*page_lines: list[str]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for lines in page_lines:
        y = 760
        for line in lines:
            c.drawString(72, y, line)
            y -= 18
        c.showPage()
    c.save()
    return buf.getvalue()


class _ParityStore:
    def __init__(self, docx_raw: bytes) -> None:
        self.original = docx_raw
        self.active_brief = BRIEF_ID
        self.decisions = [
            {
                "reference_id": "ref-1",
                "decision": "CONFIRMED_SUPPORTED",
                "rationale": "Checked source page.",
                "reviewer_id": str(uuid4()),
                "request_id": str(uuid4()),
                "timestamp": "2026-11-25T10:00:00+00:00",
            }
        ]
        self.report = {
            "schema": "caseproof-dossier-v1",
            "case_id": CASE_ID,
            "brief_id": BRIEF_ID,
            "snapshot_hash": SNAPSHOT,
            "bundle_signature": "b" * 64,
            "confirmation_id": str(uuid4()),
            "sources": [
                {
                    "role": "draft",
                    "version_id": BRIEF_ID,
                    "sha256": hashlib.sha256(docx_raw).hexdigest(),
                }
            ],
            "coverage": {
                "checked": 1,
                "unresolved": 0,
                "text_coverage_complete": True,
                "reference_recall_measured": False,
            },
            "findings": [{"reference_id": "ref-1", "visual_assessment": {"regions": []}}],
        }

    def release_actor(self, bearer: str) -> dict[str, str]:
        assert bearer == "signed"
        return {
            "actor_id": str(uuid4()),
            "actor_label": "avocat@example.be",
            "actor_label_type": "confirmed_email",
        }

    def current_draft_version(self, bearer: str, case_id: str) -> str:
        assert bearer == "signed" and case_id == CASE_ID
        return self.active_brief

    def reopen(self, bearer: str, case_id: str, brief_id: str, snapshot_hash: str) -> tuple[dict, bytes]:
        assert bearer == "signed" and case_id == CASE_ID and brief_id == BRIEF_ID
        if snapshot_hash != SNAPSHOT:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        return self.report, self.original

    def rpc(self, bearer: str, case_id: str, action: str, _data=None) -> dict:
        assert bearer == "signed" and case_id == CASE_ID and action == "decisions"
        return {"decisions": self.decisions}

    def export_rpc(self, *_args, **_kwargs) -> dict:
        return {"state": "absent"}


def _make_client(store: _ParityStore) -> TestClient:
    app = FastAPI()

    @app.exception_handler(AccessRejected)
    def _denied(_request, error):
        return JSONResponse({"error": error.code.value}, status_code=error.http_status)

    app.include_router(create_release_router(store))
    return TestClient(app)


def test_normalize_benign_unicode_and_soft_hyphen() -> None:
    raw = "Sous\u00a0r\u00e9serve\u00ad de l\u2019article \u201c1134\u201d\n  du Code."
    assert normalize_filing_text(raw) == 'Sous réserve de l\'article "1134" du Code.'


def test_exact_match_across_line_wraps_and_punctuation() -> None:
    docx_raw = _docx_bytes(
        "Conclusions additionnelles pour Jana HealthCare.",
        "Le contrat a été envoyé pour signature le 12 mars 2026 (Pièce 1, p. 16).",
    )
    # Line breaks differ cleanly from DOCX paragraphs when exported to PDF.
    pdf_raw = _pdf_bytes(
        ["Conclusions additionnelles pour", "Jana HealthCare."],
        ["Le contrat a été envoyé pour signature le 12 mars 2026", "(Pièce 1, p. 16)."],
    )
    res = check_filing_pdf_parity(
        original_docx=docx_raw,
        filing_pdf=pdf_raw,
        case_id=CASE_ID,
        brief_id=BRIEF_ID,
        snapshot_hash=SNAPSHOT,
    )
    assert res["schema"] == PARITY_SCHEMA
    assert res["status"] == "MATCH_OBSERVED"
    assert "TEXT_PARITY_MATCH" in res["reason_codes"]
    assert res["filing_pdf_page_count"] == 2
    assert res["diff_count"] == 0
    assert res["diffs"] == []
    assert any("text-layer comparison only" in note for note in res["limitations"])


def test_farhat_wrong_draft_pdf_drift_detected_with_diff_hunks() -> None:
    verified_docx = _docx_bytes(
        "Conformément à la Pièce 1 (p. 16), le projet d'avenant n°2 a été envoyé pour signature le 12 mars 2026."
    )
    stale_pdf = _pdf_bytes(
        ["Conformément à la Pièce 1 (p. 14), le contrat a été signé le 12 mars 2026."]
    )
    res = check_filing_pdf_parity(
        original_docx=verified_docx,
        filing_pdf=stale_pdf,
        case_id=CASE_ID,
        brief_id=BRIEF_ID,
        snapshot_hash=SNAPSHOT,
    )
    assert res["status"] == "MISMATCH_DETECTED"
    assert "TEXT_MISMATCH_DETECTED" in res["reason_codes"]
    assert res["diff_count"] >= 1
    assert any("16" in h["docx_excerpt"] or "envoyé" in h["docx_excerpt"] for h in res["diffs"])
    assert any("14" in h["pdf_excerpt"] or "signé" in h["pdf_excerpt"] for h in res["diffs"])


def test_blank_or_image_only_pdf_page_fails_closed_ocr_unreliable() -> None:
    docx_raw = _docx_bytes("Conclusions complètes.")
    # Page 0 has text, page 1 is blank / image-only (no extractable text).
    pdf_with_blank = _pdf_bytes(["Conclusions complètes."], [])
    res = check_filing_pdf_parity(
        original_docx=docx_raw,
        filing_pdf=pdf_with_blank,
        case_id=CASE_ID,
        brief_id=BRIEF_ID,
        snapshot_hash=SNAPSHOT,
    )
    assert res["status"] == "CANNOT_VERIFY"
    assert "OCR_UNRELIABLE" in res["reason_codes"]
    assert "PDF_TEXT_LAYER_EMPTY_OR_IMAGE_ONLY" in res["reason_codes"]
    assert res["pdf_pages_without_text"] == [1]
    assert res["diffs"] == []


def test_partial_docx_coverage_surfaces_explicit_code() -> None:
    res = compare_verified_docx_and_filing_pdf(
        case_id=CASE_ID,
        brief_id=BRIEF_ID,
        snapshot_hash=SNAPSHOT,
        verified_docx_sha256="c" * 64,
        filing_pdf_sha256="d" * 64,
        filing_pdf_byte_length=1234,
        docx_text="Article 1134 C. civ.",
        docx_coverage_complete=False,
        docx_unscanned_parts=["word/header1.xml"],
        pdf_pages=["Article 1134 C. civ."],
        pdf_warnings=[],
    )
    assert res["status"] == "MATCH_OBSERVED"
    assert "DOCX_COVERAGE_PARTIAL" in res["reason_codes"]
    assert res["docx_coverage_complete"] is False
    assert res["docx_unscanned_parts"] == ["word/header1.xml"]


def test_api_filing_pdf_parity_endpoint_guards_and_outcomes() -> None:
    docx_raw = _docx_bytes("Paiement constaté de 12.500,00 EUR selon Pièce 2.")
    good_pdf = _pdf_bytes(["Paiement constaté de 12.500,00 EUR selon Pièce 2."])
    bad_pdf = _pdf_bytes(["Paiement constaté de 10.000,00 EUR selon Pièce 2."])
    store = _ParityStore(docx_raw)
    client = _make_client(store)
    url = f"/v2/matters/{CASE_ID}/briefs/{BRIEF_ID}/dossier/releases/filing-pdf-parity"

    def post_pdf(pdf_raw: bytes, *, sha_override: str | None = None, content_type: str = "application/pdf"):
        sha = sha_override or hashlib.sha256(pdf_raw).hexdigest()
        return client.post(
            url,
            content=pdf_raw,
            headers={
                "Authorization": "Bearer signed",
                "Content-Type": content_type,
                "X-CaseProof-Snapshot-Hash": SNAPSHOT,
                "X-CaseProof-Filing-PDF-SHA256": sha,
                "X-CaseProof-Byte-Length": str(len(pdf_raw)),
            },
        )

    ok_resp = post_pdf(good_pdf)
    assert ok_resp.status_code == 200
    assert ok_resp.headers["cache-control"] == "no-store"
    assert ok_resp.json()["status"] == "MATCH_OBSERVED"

    drift_resp = post_pdf(bad_pdf)
    assert drift_resp.status_code == 200
    assert drift_resp.json()["status"] == "MISMATCH_DETECTED"

    # Tampered digest or invalid PDF rejected cleanly with 422.
    assert post_pdf(good_pdf, sha_override="0" * 64).status_code == 422
    assert post_pdf(good_pdf, content_type="text/plain").status_code == 422
    assert post_pdf(b"not a pdf at all").status_code == 422

    # Unauthorized request fails closed with 401.
    unauth = client.post(
        url,
        content=good_pdf,
        headers={
            "Content-Type": "application/pdf",
            "X-CaseProof-Snapshot-Hash": SNAPSHOT,
            "X-CaseProof-Filing-PDF-SHA256": hashlib.sha256(good_pdf).hexdigest(),
            "X-CaseProof-Byte-Length": str(len(good_pdf)),
        },
    )
    assert unauth.status_code == 401

    # Superseded draft fails closed with 409 Conflict.
    store.active_brief = str(uuid4())
    assert post_pdf(good_pdf).status_code == 409


def test_partner_demo_filing_pdf_parity_endpoint() -> None:
    app = create_partner_demo_app()
    client = TestClient(app)
    dossier = client.get(f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/dossier").json()
    snap = dossier["snapshot_hash"]
    doc = Document()
    source_text = client.get(f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/dossier/editor/blocks").json()
    full_lines = [b["text"] for b in source_text["blocks"] if b.get("text")]
    doc.add_paragraph("\n".join(full_lines))
    matching_pdf = _pdf_bytes(full_lines)
    stale_pdf = _pdf_bytes(["Ancienne version non corrigée des conclusions."])

    url = f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/dossier/releases/filing-pdf-parity"
    r1 = client.post(
        url,
        content=matching_pdf,
        headers={
            "Authorization": "Bearer demo-token",
            "Content-Type": "application/pdf",
            "X-CaseProof-Snapshot-Hash": snap,
            "X-CaseProof-Filing-PDF-SHA256": hashlib.sha256(matching_pdf).hexdigest(),
            "X-CaseProof-Byte-Length": str(len(matching_pdf)),
        },
    )
    assert r1.status_code == 200
    assert r1.json()["status"] == "MATCH_OBSERVED"

    r2 = client.post(
        url,
        content=stale_pdf,
        headers={
            "Authorization": "Bearer demo-token",
            "Content-Type": "application/pdf",
            "X-CaseProof-Snapshot-Hash": snap,
            "X-CaseProof-Filing-PDF-SHA256": hashlib.sha256(stale_pdf).hexdigest(),
            "X-CaseProof-Byte-Length": str(len(stale_pdf)),
        },
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "MISMATCH_DETECTED"
