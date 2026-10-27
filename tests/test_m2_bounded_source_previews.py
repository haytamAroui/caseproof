"""Opt-in real-format previews remain source-bound and conservative."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from uuid import UUID
from zipfile import ZIP_STORED, ZipFile

import pytest

from application.litigation.library import EvidenceIndexer
from apps.api.postgres_litigation_check_store import (
    CustodySource,
    PostgresPrivateMatterCheckStore,
    PrivateCheckStoreError,
)
from infrastructure.parsers.limited import LimitedDocumentParser


class Access:
    org_id = "11111111-1111-4111-8111-111111111111"
    case_id = "22222222-2222-4222-8222-222222222222"


def make(raw, *, media="application/pdf", enabled=True):
    source = CustodySource(
        UUID("33333333-3333-4333-8333-333333333333"),
        UUID("44444444-4444-4444-8444-444444444444"),
        UUID("55555555-5555-4555-8555-555555555555"), sha256(raw).hexdigest(), media,
    )
    store = PostgresPrivateMatterCheckStore(
        lambda: None, None, lambda *_: raw,  # type: ignore[arg-type]
        indexer=EvidenceIndexer(LimitedDocumentParser()) if enabled else None,
    )
    return store, source


def test_real_pdf_preview_uses_verified_bytes_and_page_lineage():
    raw = Path("tests/fixtures/documents/synthetic_invoice.pdf").read_bytes()
    store, source = make(raw)
    first = store._preview(access=Access(), source=source, require_page_lineage=True)  # type: ignore[arg-type]
    second = store._preview(access=Access(), source=source, require_page_lineage=True)  # type: ignore[arg-type]
    assert first == second
    assert first.row.original_sha256 == sha256(raw).hexdigest()
    assert first.row.representation_id and first.row.parser_id
    assert first.spans and all(span[3] is not None for span in first.spans)


def test_parser_remains_opt_in_and_bad_bytes_fail_closed():
    raw = Path("tests/fixtures/documents/synthetic_invoice.pdf").read_bytes()
    store, source = make(raw, enabled=False)
    result = store._preview(access=Access(), source=source, require_page_lineage=True)  # type: ignore[arg-type]
    assert result.row.status == "partial" and not result.text
    store, _ = make(b"changed")
    with pytest.raises(PrivateCheckStoreError):
        store._preview(access=Access(), source=source)  # type: ignore[arg-type]


def test_docx_page_requests_remain_partial():
    buf = BytesIO()
    with ZipFile(buf, "w", compression=ZIP_STORED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:r><w:t>Texte fictif</w:t></w:r></w:p></w:body></w:document>',
        )
    store, source = make(
        buf.getvalue(), media="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    result = store._preview(access=Access(), source=source, require_page_lineage=True)  # type: ignore[arg-type]
    assert result.row.status == "partial"
    assert "page_lineage_unverified" in result.row.warnings
    assert "Texte fictif" in result.text
