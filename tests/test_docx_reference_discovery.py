"""End-to-end synthetic DOCX reference-discovery fixtures."""

from io import BytesIO
from zipfile import ZipFile

from infrastructure.parsers.docx_reference_discovery import discover_docx_references


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _payload(main: str, *, unknown: bool = False) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", f'<w:document xmlns:w="{WORD_NS}"><w:body><w:p><w:r><w:t>{main}</w:t></w:r></w:p></w:body></w:document>')
        if unknown:
            archive.writestr("word/customStory.xml", "<root/>")
    return output.getvalue()


def test_docx_regions_feed_reference_discovery() -> None:
    result = discover_docx_references(_payload("Zie stuk 12 en pièce 4."))
    assert [ref.number for ref in result.references] == ["12", "4"]
    assert result.coverage_complete
    assert all(ref.region == "word/document.xml" for ref in result.references)


def test_partial_docx_still_returns_candidates_but_not_complete() -> None:
    result = discover_docx_references(_payload("Stuk 7", unknown=True))
    assert [ref.number for ref in result.references] == ["7"]
    assert not result.coverage_complete
    assert "word/customStory.xml" in result.unscanned_parts
