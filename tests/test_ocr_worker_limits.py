"""Fail-closed input, timeout and process resource-limit contracts."""
import subprocess
from datetime import UTC, datetime
from hashlib import sha256

import pytest

from infrastructure.parsers import pdf_ocr
from packages.evidence_kernel.domain.source_versions import SourceVersion


def test_oversized_pdf_never_launches_worker(monkeypatch):
    content = b"%PDF-" + b"x" * pdf_ocr.OCR_LIMIT
    source = SourceVersion("synthetic", "v1", sha256(content).hexdigest(),
                           content, datetime.now(UTC), "application/pdf")
    monkeypatch.setattr(pdf_ocr, "_run", lambda *a, **k: pytest.fail("worker launched"))
    with pytest.raises(pdf_ocr.OCRUnavailable, match="ocr_input_budget"):
        pdf_ocr.LocalPDFOCR().recognize(source, page_number=1, languages=("en",))


def test_timeout_does_not_expose_child_output(monkeypatch):
    monkeypatch.setattr(pdf_ocr, "_isolated_command", lambda command: command)

    def timeout(*args, **kwargs):
        assert kwargs["timeout"] == 12
        assert kwargs["preexec_fn"] is pdf_ocr._worker_limits
        raise subprocess.TimeoutExpired("ocr", 12, output=b"confidential source bytes")

    monkeypatch.setattr(pdf_ocr.subprocess, "run", timeout)
    with pytest.raises(pdf_ocr.OCRUnavailable) as error:
        pdf_ocr._run(["pdftoppm"], timeout=12)
    assert str(error.value) == "ocr_binary_unavailable_or_timeout"


def test_worker_resource_limits(monkeypatch):
    limits = {}
    monkeypatch.setattr(pdf_ocr.resource, "setrlimit", lambda key, value: limits.update({key: value}))
    pdf_ocr._worker_limits()
    assert limits[pdf_ocr.resource.RLIMIT_AS] == (768 * 1024 * 1024,) * 2
    assert limits[pdf_ocr.resource.RLIMIT_CPU] == (30, 30)
    assert limits[pdf_ocr.resource.RLIMIT_FSIZE] == (16 * 1024 * 1024,) * 2
