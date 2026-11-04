"""Real LibreOffice desktop-engine round-trip of CaseProof synthetic DOCX derivatives.

This is a host test, not Microsoft Word certification or practitioner acceptance.
Requires LibreOffice, python-docx and pypdf in a disposable CI environment.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZipFile

from docx import Document
from pypdf import PdfReader

from infrastructure.parsers.dossier_docx_export import annotated_docx, corrected_docx_preview


def _fixture() -> bytes:
    document = Document()
    document.add_heading("Preserved synthetic brief", level=1)
    document.add_paragraph("Zie Stuk 1, physical PDF page 6.")
    styled = document.add_paragraph()
    styled.add_run("Pièce 2").bold = True
    styled.add_run(" — café à Bruxelles").italic = True
    document.add_table(rows=1, cols=2).cell(0, 0).text = "Preserved synthetic table"
    document.add_paragraph("End of original evidence.")
    stream = io.BytesIO()
    document.save(stream)
    return stream.getvalue()


def _report() -> dict:
    return {
        "snapshot_hash": "a" * 64,
        "coverage": {
            "checked": 1, "unresolved": 1, "fully_checked": False,
            "docx_regions": {"regions_scanned": 4},
        },
        "verification_contract": {"version": "caseproof-v1", "semantic_support": "human_only"},
        "abstentions": [{"reference_id": "ref-0002", "reason": "OCR not assessed"}],
        "findings": [{
            "reference_id": "ref-0001", "literal": "Stuk 2",
            "identity": "resolved", "page_mapping": "unmapped",
            "fidelity": "not_assessed", "support": "not_assessed",
        }],
        "human_decisions": [{
            "reference_id": "ref-0001", "reviewer_id": "synthetic-reviewer",
            "timestamp": "2026-11-04T00:00:00Z",
            "decision": "CONFIRMED_QUALIFIED",
        }],
    }


def _converted(source: Path, output: Path, profile: Path, target: str) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    profile.mkdir(parents=True, exist_ok=True)
    command = [
        "libreoffice", "-env:UserInstallation=" + profile.as_uri(),
        "--headless", "--convert-to", target, "--outdir", str(output), str(source),
    ]
    try:
        run = subprocess.run(command, capture_output=True, text=True, timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("LibreOffice host invocation failed") from exc
    extension = target.split(":", 1)[0]
    result = output / (source.stem + "." + extension)
    if run.returncode != 0 or not result.exists() or result.stat().st_size == 0:
        raise RuntimeError("LibreOffice conversion or readback failed")
    return result


def main() -> None:
    if os.environ.get("CASEPROOF_SYNTHETIC_HOST_TEST") != "YES":
        raise RuntimeError("Explicit synthetic-only host guard required")
    if not shutil.which("libreoffice"):
        raise RuntimeError("LibreOffice is not installed")
    original = _fixture()
    corrected = corrected_docx_preview(
        original, expected_sha256=hashlib.sha256(original).hexdigest(),
        paragraph_index=1, before="Stuk 1", after="Stuk 2",
    )
    derivative = annotated_docx(corrected, _report())
    assert hashlib.sha256(original).hexdigest() != hashlib.sha256(corrected).hexdigest()
    assert hashlib.sha256(original).hexdigest() != hashlib.sha256(derivative).hexdigest()
    with ZipFile(io.BytesIO(original)) as old, ZipFile(io.BytesIO(derivative)) as new:
        assert old.testzip() is None and new.testzip() is None
        assert set(old.namelist()) == set(new.namelist())
        for name in old.namelist():
            if name not in {"word/document.xml"}:
                assert old.read(name) == new.read(name), name
    texts = [p.text for p in Document(io.BytesIO(derivative)).paragraphs]
    assert any("Stuk 2, physical" in line for line in texts)
    assert any("scoped review annotations" in line for line in texts)
    assert "Preserved synthetic table" in Document(io.BytesIO(derivative)).tables[0].cell(0, 0).text

    with tempfile.TemporaryDirectory(prefix="caseproof-synthetic-host-") as temp:
        root = Path(temp)
        docx_path = root / "annotated.docx"
        docx_path.write_bytes(derivative)
        # First pass through a real installed Writer engine and PDF importer.
        pdf = _converted(docx_path, root / "pdf", root / "profile-1", "pdf:writer_pdf_Export")
        reader = PdfReader(str(pdf), strict=True)
        rendered = "\n".join(page.extract_text() or "" for page in reader.pages)
        for token in ("Preserved synthetic brief", "Stuk 2", "Coverage", "scoped review annotations"):
            if token not in rendered:
                raise AssertionError("LibreOffice PDF lost expected visible text: " + token)
        # Read through Writer's ODF representation, then its DOCX writer.
        odt = _converted(docx_path, root / "odt", root / "profile-2", "odt:writer8")
        reopened_docx = _converted(odt, root / "docx", root / "profile-3", "docx:Office Open XML Text")
        reopened = Document(str(reopened_docx))
        lines = "\n".join(p.text for p in reopened.paragraphs)
        assert "Preserved synthetic brief" in lines
        assert "Stuk 2, physical PDF page 6." in lines
        assert "scoped review annotations" in lines
        assert "Preserved synthetic table" in reopened.tables[0].cell(0, 0).text
    # Only safe synthetic metadata, no document snippets/bodies or paths in job logs.
    result = subprocess.run(["libreoffice", "--version"], capture_output=True, text=True, check=True, timeout=10)
    print("P6_LIBREOFFICE_SYNTHETIC_HOST_ROUNDTRIP_PASSED")
    print(json.dumps({"host": result.stdout.strip(), "original_sha256": hashlib.sha256(original).hexdigest(),
                      "derivative_sha256": hashlib.sha256(derivative).hexdigest(),
                      "word_desktop_tested": False, "confidential_data_tested": False}, sort_keys=True))


if __name__ == "__main__":
    main()
