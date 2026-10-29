"""Regression tests for conservative DOCX text coverage."""

from io import BytesIO
from zipfile import ZipFile

from infrastructure.parsers.docx_text_regions import extract_docx_text_regions


NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _docx(*, body: str, extra: dict[str, str] | None = None) -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", body)
        for name, data in (extra or {}).items():
            archive.writestr(name, data)
    return stream.getvalue()


def test_simple_main_story_is_extracted() -> None:
    payload = _docx(body=f'<w:document xmlns:w="{NS}"><w:body><w:p><w:r><w:t>Stuk 12</w:t></w:r></w:p></w:body></w:document>')
    result = extract_docx_text_regions(payload)
    assert result.coverage_complete
    assert result.regions[0].text == "Stuk 12"


def test_unrecognized_word_story_blocks_full_coverage() -> None:
    payload = _docx(body=f'<w:document xmlns:w="{NS}"><w:body/></w:document>', extra={"word/customStory.xml": "<root/>"})
    result = extract_docx_text_regions(payload)
    assert not result.coverage_complete
    assert "word/customStory.xml" in result.unscanned_parts


def test_textbox_blocks_full_coverage() -> None:
    payload = _docx(body=f'<w:document xmlns:w="{NS}"><w:body><w:txbxContent><w:p><w:r><w:t>Pièce 4</w:t></w:r></w:p></w:txbxContent></w:body></w:document>')
    result = extract_docx_text_regions(payload)
    assert not result.coverage_complete
    assert "word/document.xml#structured" in result.unscanned_parts


def test_revisions_are_not_silently_certified() -> None:
    payload = _docx(body=f'<w:document xmlns:w="{NS}"><w:body><w:ins><w:p><w:r><w:t>Stuk 2</w:t></w:r></w:p></w:ins></w:body></w:document>')
    result = extract_docx_text_regions(payload)
    assert not result.coverage_complete
    assert "word/document.xml" in result.unscanned_parts
