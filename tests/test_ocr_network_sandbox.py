"""Command construction regression; real egress denial runs in Docker CI."""
import pytest

from infrastructure.parsers.pdf_ocr import OCRUnavailable, _isolated_command


def test_namespace_is_required_and_never_falls_back_to_direct_execution(monkeypatch):
    monkeypatch.delenv("CASEPROOF_OCR_SANDBOX", raising=False)
    monkeypatch.setattr("infrastructure.parsers.pdf_ocr.sys.platform", "linux")
    monkeypatch.setattr("infrastructure.parsers.pdf_ocr.shutil.which", lambda _: "/usr/bin/unshare")
    assert _isolated_command(["/usr/bin/pdftoppm", "input.pdf"]) == [
        "/usr/bin/unshare", "--user", "--map-root-user", "--net", "--",
        "/usr/bin/pdftoppm", "input.pdf",
    ]
    monkeypatch.setattr("infrastructure.parsers.pdf_ocr.shutil.which", lambda _: None)
    with pytest.raises(OCRUnavailable, match="ocr_network_sandbox_unavailable"):
        _isolated_command(["/usr/bin/pdftoppm", "input.pdf"])
