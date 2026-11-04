"""Synthetic negative cases through the actual resource-limited parser worker."""
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from application.extraction.contracts import ExtractionError
from infrastructure.parsers.limited import LimitedDocumentParser
from packages.evidence_kernel.domain.source_versions import SourceVersion

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
DOCUMENT = (b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            b'<w:body><w:p><w:r><w:t>Stuk 1</w:t></w:r></w:p></w:body></w:document>')


def _package(document: bytes = DOCUMENT, relationships: bytes = b'<Relationships/>') -> bytes:
    stream = BytesIO()
    with ZipFile(stream, 'w', compression=ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', b'<Types/>')
        archive.writestr('word/document.xml', document)
        archive.writestr('_rels/.rels', relationships)
    return stream.getvalue()


def _source(data: bytes) -> SourceVersion:
    return SourceVersion('synthetic', 'v1', sha256(data).hexdigest(), data,
                         datetime(2026, 11, 4, tzinfo=UTC), DOCX)


def test_ordinary_document_is_processed_in_worker() -> None:
    artifact = LimitedDocumentParser().parse(_source(_package()))
    assert artifact['text'] == 'Stuk 1'


@pytest.mark.parametrize('relationships', [
    b'<Relationships><Relationship TargetMode="External" Target="file:///etc/passwd"/></Relationships>',
    b'<!DOCTYPE x [<!ENTITY x SYSTEM "file:///etc/passwd">]><Relationships>&x;</Relationships>',
    b'<Relationships><Relationship',
])
def test_hostile_relationships_are_rejected_in_worker(relationships: bytes) -> None:
    with pytest.raises(ExtractionError, match='document_parse_rejected'):
        LimitedDocumentParser().parse(_source(_package(relationships=relationships)))


@pytest.mark.parametrize('document', [
    b'<!DOCTYPE x [<!ENTITY x "Stuk 99">]><x>&x;</x>',
    b'<w:document',
])
def test_hostile_document_xml_is_rejected_in_worker(document: bytes) -> None:
    with pytest.raises(ExtractionError, match='document_parse_rejected'):
        LimitedDocumentParser().parse(_source(_package(document=document)))
