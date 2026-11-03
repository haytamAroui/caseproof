"""Reference anchors must select the exact supported paragraph and occurrence."""
import io

import pytest
from docx import Document

from infrastructure.parsers.docx_correction_anchor import correction_anchor


def docx(*paragraphs):
    doc = Document()
    for value in paragraphs:
        doc.add_paragraph(value)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def finding(start, end, literal='Stuk 1'):
    return {'region': 'word/document.xml', 'literal': literal, 'offsets': {'start': start, 'end': end}}


def test_anchor_tracks_exact_occurrence_across_paragraphs():
    original = docx('First Stuk 1', 'Second Stuk 1')
    assert correction_anchor(original, finding(6, 12)) == 0
    assert correction_anchor(original, finding(20, 26)) == 1


def test_repeated_reference_in_one_paragraph_is_ambiguous():
    with pytest.raises(ValueError):
        correction_anchor(docx('Stuk 1 and Stuk 1'), finding(0, 6))


@pytest.mark.parametrize('selection', [finding(0, 6), finding(6, 11), finding(6, 12, 'Stuk 2')])
def test_stale_or_wrong_reference_rejected(selection):
    with pytest.raises(ValueError):
        correction_anchor(docx('First Stuk 1'), selection)


def test_table_content_is_not_guessed():
    document = Document()
    document.add_paragraph('Stuk 1')
    document.add_table(rows=1, cols=1).cell(0, 0).text = 'Other'
    output = io.BytesIO()
    document.save(output)
    with pytest.raises(ValueError):
        correction_anchor(output.getvalue(), finding(0, 6))


def test_tracked_format_change_abstains():
    from docx.oxml import OxmlElement

    document = Document()
    paragraph = document.add_paragraph('Stuk 1')
    paragraph._p.get_or_add_pPr().append(OxmlElement('w:pPrChange'))
    output = io.BytesIO()
    document.save(output)
    with pytest.raises(ValueError, match='tracked changes'):
        correction_anchor(output.getvalue(), finding(0, 6))
