"""Reproducible *local* OCR/intake/export measurement; not a pilot approval.

Run with CASEPROOF_OCR_SANDBOX=docker and the pinned isolated OCR image.
Only synthetic, raster-only Dutch/French exhibits; never print document text.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import platform
import resource
from datetime import UTC, datetime
from time import monotonic
from uuid import uuid4

from docx import Document
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas

from application.capacity_envelope import CAPACITY_POLICY
from apps.api.dossier_export_release import LIMITS, _checked_artifacts
from apps.api.signed_document_parse import parse_verified_original
from apps.api.workspace_intake import IntakeCommand, preflight
from infrastructure.parsers.pdf_ocr import LocalPDFOCR
from packages.evidence_kernel.domain.source_versions import SourceVersion
from tests.test_f6_reviewed_exports import SignedReleaseStore

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def make_scan(label: str) -> bytes:
    image = Image.new("RGB", (1500, 550), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(FONT, 58)
    draw.text((55, 90), label, fill="black", font=font)
    draw.text((55, 210), "FACTUUR FACTURE 1250 EUR", fill="black", font=font)
    draw.text((55, 340), "PAGINA PAGE 1", fill="black", font=font)
    data = io.BytesIO()
    pdf = canvas.Canvas(data, pagesize=(750, 275), invariant=1)
    pdf.drawInlineImage(image, 0, 0, width=750, height=275)
    pdf.showPage()
    pdf.save()
    return data.getvalue()


def main() -> None:
    started = monotonic()
    doc = Document()
    doc.add_paragraph("Zie Stuk 1, p. 1. Voir Pièce 2, p. 1.")
    b = io.BytesIO()
    doc.save(b)
    originals = [
        (
            "draft",
            "draft.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            b.getvalue(),
        ),
        ("inventory", "inventory.txt", "text/plain", b"Stuk 1 factuur\nPiece 2 facture\n"),
        ("exhibit", "nl-scan.pdf", "application/pdf", make_scan("STUK 1 NEDERLANDS")),
        ("exhibit", "fr-scan.pdf", "application/pdf", make_scan("PIECE 2 FRANCAIS")),
    ]
    command = IntakeCommand(
        request_id=str(uuid4()),
        files=[
            {
                "role": role,
                "filename": filename,
                "media_type": media,
                "byte_length": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "content_base64": base64.b64encode(raw).decode("ascii"),
            }
            for role, filename, media, raw in originals
        ],
    )
    assert len(command.files) == CAPACITY_POLICY["source_count"]
    preflight(command)  # Whole-bundle check; no storage write.
    intake_time = monotonic()
    ocr = LocalPDFOCR()
    counts: dict[str, int] = {}
    for language, row in zip(("nl", "fr"), originals[2:], strict=True):
        raw = row[3]
        geometry: list[bytes] = []
        source = SourceVersion(
            f"synthetic-{language}",
            f"version-{language}",
            hashlib.sha256(raw).hexdigest(),
            raw,
            datetime.now(UTC),
            "application/pdf",
        )
        _, manifest = parse_verified_original(
            document_id=source.document_id,
            version_id=source.version_id,
            data=raw,
            media_type="application/pdf",
            ocr=ocr,
            ocr_languages=(language,),
            persist_geometry=lambda ref, payload, destination=geometry: destination.append(payload),
        )
        candidate = manifest.get("ocr_candidates", [])
        assert len(candidate) == 1 and candidate[0]["status"] == "OCR_UNRELIABLE", candidate
        assert candidate[0]["word_count"] >= 3 and len(geometry) == 1
        assert not manifest["complete"] and manifest["coverage"] == "partial"
        counts[language] = int(candidate[0]["word_count"])
    ocr_time = monotonic()
    store = SignedReleaseStore()
    store.report["human_decisions"] = store.decisions
    artifacts = _checked_artifacts(store.report, store.original)
    assert all(0 < len(data) <= LIMITS[name] for name, data in artifacts.items())
    reopened = Document(io.BytesIO(artifacts["docx"]))
    assert reopened.paragraphs
    end = monotonic()
    print(
        "CAPACITY_LOCAL_MEASUREMENT "
        + json.dumps(
            {
                "schema": "caseproof-local-capacity-measurement-v1",
                "policy_version": CAPACITY_POLICY["schema"],
                "approval": CAPACITY_POLICY["approval"],
                "input_sources": len(originals),
                "input_bytes": sum(len(item[3]) for item in originals),
                "raster_only_pdf_pages": 2,
                "ocr_languages": sorted(counts),
                "ocr_word_counts": counts,
                "output_bytes": {name: len(value) for name, value in artifacts.items()},
                "intake_validation_seconds": round(intake_time - started, 3),
                "isolated_ocr_seconds": round(ocr_time - intake_time, 3),
                "scoped_artifact_seconds": round(end - ocr_time, 3),
                "total_seconds": round(end - started, 3),
                "parent_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "child_max_rss_kib": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                "python": platform.python_version(),
                "signed_live": False,
                "full_envelope_measured": False,
                "accuracy_established": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
