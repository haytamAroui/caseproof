"""OWASP ASVS 5 file boundary regressions for the existing draft-pack verifier."""
import io
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import pytest

from application.dossiers.pack import MAX_PACK_BYTES, verify_pack
from application.extraction.contracts import ExtractionError


def _archive(filename: str, payload: bytes, compression: int = ZIP_STORED) -> bytes:
    out = io.BytesIO()
    with ZipFile(out, "w", compression=compression) as archive:
        archive.writestr(filename, payload)
    return out.getvalue()


@pytest.mark.parametrize("filename", [
    "../case.json", "sources/000/../../case.json", "/tmp/case.json",
    "sources/000/../original.bin", "sources\\000\\original.bin",
])
def test_traversal_and_absolute_names_are_rejected(filename: str) -> None:
    with pytest.raises(ExtractionError):
        verify_pack(_archive(filename, b"{}"))


def test_compressed_zip_bomb_is_rejected_without_expansion() -> None:
    payload = b"0" * (12 * 1024 * 1024)
    archive = _archive("sources/000/original.bin", payload, ZIP_DEFLATED)
    assert len(archive) < 20_000
    with pytest.raises(ExtractionError):
        verify_pack(archive)


def test_oversized_pdf_original_is_rejected_before_read() -> None:
    payload = b"%PDF-1.7\\n" + b"x" * (11 * 1024 * 1024)
    with pytest.raises(ExtractionError):
        verify_pack(_archive("sources/000/original.bin", payload))


def test_oversized_raw_archive_is_rejected() -> None:
    with pytest.raises(ExtractionError):
        verify_pack(b"x" * (MAX_PACK_BYTES + 1))
