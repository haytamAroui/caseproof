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


@pytest.mark.parametrize("filename", [
    "../evil.pdf", "..\\\\evil.pdf", "/tmp/evil.pdf", "C:\\\\evil.pdf",
    "sources/../evil.pdf", "evil.pdf\x00.txt", " evil.pdf ", "．．/evil.pdf",
])
def test_signed_registration_rejects_path_like_filename(filename: str) -> None:
    from pydantic import ValidationError

    from apps.api.litigation_live_journey import OriginalRegister

    with pytest.raises(ValidationError):
        OriginalRegister(filename=filename, sha256="a" * 64, byte_length=10,
                         media_type="application/pdf",
                         request_id="00000000-0000-4000-8000-000000000001")


def test_signed_registration_rejects_oversized_pdf_before_storage() -> None:
    from pydantic import ValidationError

    from apps.api.litigation_live_journey import MAX_ORIGINAL, OriginalRegister

    with pytest.raises(ValidationError):
        OriginalRegister(filename="large.pdf", sha256="a" * 64,
                         byte_length=MAX_ORIGINAL + 1, media_type="application/pdf",
                         request_id="00000000-0000-4000-8000-000000000001")


def test_signed_binary_ingest_rejects_zip_bomb_in_isolated_parser() -> None:
    """Exercise actual signed binary parse boundary, not only draft-pack verification."""
    from application.extraction.contracts import ExtractionError
    from apps.api.signed_document_parse import parse_verified_original

    compressed = _archive("word/document.xml", b"A" * (12 * 1024 * 1024), ZIP_DEFLATED)
    with pytest.raises(ExtractionError):
        parse_verified_original(document_id="doc", version_id="version", data=compressed,
                                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


def test_signed_binary_ingest_rejects_oversized_pdf_before_parser() -> None:
    from application.extraction.contracts import ExtractionError
    from apps.api.signed_document_parse import MAX_BINARY_BYTES, parse_verified_original

    with pytest.raises(ExtractionError, match="unsupported_bounded_binary_original"):
        parse_verified_original(document_id="doc", version_id="version",
                                data=b"%PDF-1.7\\n" + b"x" * MAX_BINARY_BYTES,
                                media_type="application/pdf")


@pytest.mark.parametrize("kind", ["bomb", "traversal", "duplicate", "malformed"])
def test_actual_signed_upload_rejects_hostile_docx_before_storage(kind):
    import base64
    from hashlib import sha256
    from types import SimpleNamespace
    from uuid import uuid4

    from application.documents.file_boundary import DOCX
    from apps.api.access_control import AccessRejected
    from apps.api.litigation_live_journey import JourneyClient

    out = io.BytesIO()
    if kind == "malformed":
        data = b"PK corrupt archive"
    else:
        with ZipFile(out, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", b"<Types/>")
            archive.writestr("word/document.xml", b"x" * (3 * 1024 * 1024) if kind == "bomb" else b"<doc/>")
            if kind == "traversal":
                archive.writestr("../../outside", b"forbidden")
            if kind == "duplicate":
                archive.writestr("word/document.xml", b"duplicate")
        data = out.getvalue()
    class Library:
        def source(self, **kwargs):
            return SimpleNamespace(sha256_hex=sha256(data).hexdigest(), content_type=DOCX), len(data)
        def put_once(self, **kwargs):
            pytest.fail("hostile archive reached private storage")
    client = JourneyClient("sb_publishable_synthetic")
    client.library = Library()
    with pytest.raises(AccessRejected):
        client.upload("signed-test-double", *(str(uuid4()) for _ in range(3)),
                      base64.b64encode(data).decode())
