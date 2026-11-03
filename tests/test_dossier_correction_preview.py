import io
from hashlib import sha256
from zipfile import ZipFile

import pytest
from docx import Document

from infrastructure.parsers.dossier_docx_export import corrected_docx_preview


def draft(split=False):
    document = Document()
    paragraph = document.add_paragraph('See Stuk 1, p. 2.')
    if split:
        paragraph.add_run(' More text.').bold = True
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


def test_correction_preserves_original_and_other_package_parts():
    original = draft()
    result = corrected_docx_preview(original, expected_sha256=sha256(original).hexdigest(),
                                    paragraph_index=0, before='p. 2', after='p. 3')
    assert Document(io.BytesIO(original)).paragraphs[0].text == 'See Stuk 1, p. 2.'
    assert Document(io.BytesIO(result)).paragraphs[0].text == 'See Stuk 1, p. 3.'
    with ZipFile(io.BytesIO(original)) as old, ZipFile(io.BytesIO(result)) as new:
        assert old.namelist() == new.namelist()
        assert b'xmlns:w14=' in new.read('word/document.xml')
        for name in old.namelist():
            if name != 'word/document.xml':
                assert old.read(name) == new.read(name)


@pytest.mark.parametrize('split,before,digest', [(False, 'missing', None),
                                               (False, 'p. 2', '0' * 64)])
def test_complex_stale_and_missing_ranges_abstain(split, before, digest):
    original = draft(split)
    with pytest.raises(ValueError):
        corrected_docx_preview(original, expected_sha256=digest or sha256(original).hexdigest(),
                               paragraph_index=0, before=before, after='p. 3')


@pytest.mark.parametrize('replacement', ['bad\x00', 'bad\ufffe', 'bad\ud800', 'line\nbreak', 'tab\there', 'return\rhere'])
def test_correction_refuses_xml_invalid_characters(replacement):
    original = draft()
    with pytest.raises(ValueError):
        corrected_docx_preview(original, expected_sha256=sha256(original).hexdigest(),
                               paragraph_index=0, before='p. 2', after=replacement)


def test_replacement_across_formatted_runs_preserves_unaffected_text_and_styles():
    document = Document()
    paragraph = document.add_paragraph()
    paragraph.add_run('Avant Stu').bold = True
    paragraph.add_run('k 1 après').italic = True
    out = io.BytesIO()
    document.save(out)
    original = out.getvalue()
    result = corrected_docx_preview(original, expected_sha256=sha256(original).hexdigest(),
                                    paragraph_index=0, before='Stuk 1', after='Pièce 2')
    paragraph = Document(io.BytesIO(result)).paragraphs[0]
    assert paragraph.text == 'Avant Pièce 2 après'
    assert paragraph.runs[0].text == 'Avant Pièce 2'
    assert paragraph.runs[0].bold is True
    assert paragraph.runs[1].text == ' après'
    assert paragraph.runs[1].italic is True
    assert Document(io.BytesIO(original)).paragraphs[0].text == 'Avant Stuk 1 après'


def test_writer_rejects_tracked_changes_even_outside_target():
    from docx.oxml import OxmlElement

    document = Document()
    document.add_paragraph('See Stuk 1')
    document.add_paragraph('Other')._p.get_or_add_pPr().append(OxmlElement('w:pPrChange'))
    out = io.BytesIO()
    document.save(out)
    raw = out.getvalue()
    with pytest.raises(ValueError, match='tracked changes'):
        corrected_docx_preview(raw, expected_sha256=sha256(raw).hexdigest(),
                               paragraph_index=0, before='Stuk 1', after='Stuk 2')


def test_writer_refuses_bookmark_in_target_paragraph():
    from docx.oxml import OxmlElement

    document = Document()
    paragraph = document.add_paragraph('See Stuk 1')
    paragraph._p.append(OxmlElement('w:bookmarkStart'))
    out = io.BytesIO()
    document.save(out)
    raw = out.getvalue()
    with pytest.raises(ValueError, match='complex paragraph'):
        corrected_docx_preview(raw, expected_sha256=sha256(raw).hexdigest(),
                               paragraph_index=0, before='Stuk 1', after='Stuk 2')


def test_writer_refuses_repeated_reference_even_across_runs():
    document = Document()
    paragraph = document.add_paragraph('Stuk 1 then Stu')
    paragraph.add_run('k 1')
    out = io.BytesIO()
    document.save(out)
    raw = out.getvalue()
    with pytest.raises(ValueError, match='ambiguous'):
        corrected_docx_preview(raw, expected_sha256=sha256(raw).hexdigest(),
                               paragraph_index=0, before='Stuk 1', after='Stuk 2')
