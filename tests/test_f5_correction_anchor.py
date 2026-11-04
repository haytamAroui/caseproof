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
    assert correction_anchor(output.getvalue(), finding(0, 6)) == 0
    with pytest.raises(ValueError, match='direct body'):
        correction_anchor(output.getvalue(), finding(7, 12, 'Other'))


def test_tracked_format_change_abstains():
    from docx.oxml import OxmlElement

    document = Document()
    paragraph = document.add_paragraph('Stuk 1')
    paragraph._p.get_or_add_pPr().append(OxmlElement('w:pPrChange'))
    output = io.BytesIO()
    document.save(output)
    with pytest.raises(ValueError, match='tracked changes'):
        correction_anchor(output.getvalue(), finding(0, 6))


def test_anchor_handles_unrelated_table_and_multiple_formatted_runs():
    from hashlib import sha256

    from infrastructure.parsers.dossier_docx_export import corrected_docx_preview

    document = Document()
    document.add_table(rows=1, cols=1).cell(0, 0).text = 'Table evidence'
    unrelated = document.add_paragraph('Unrelated ')
    unrelated.add_run('formatted').bold = True
    document.add_paragraph('See Stuk 1 here')
    output = io.BytesIO()
    document.save(output)
    raw = output.getvalue()
    body = 'Table evidence\nUnrelated formatted\nSee Stuk 1 here'
    start = body.index('Stuk 1')
    index = correction_anchor(raw, finding(start, start + 6))
    assert index == 1  # table paragraphs are not direct body paragraphs
    corrected = corrected_docx_preview(raw, expected_sha256=sha256(raw).hexdigest(),
                                      paragraph_index=index, before='Stuk 1', after='Stuk 2')
    reopened = Document(io.BytesIO(corrected))
    assert reopened.tables[0].cell(0, 0).text == 'Table evidence'
    assert reopened.paragraphs[0].runs[1].bold is True
    assert reopened.paragraphs[1].text == 'See Stuk 2 here'
    assert Document(io.BytesIO(raw)).paragraphs[1].text == 'See Stuk 1 here'
    from zipfile import ZipFile

    with ZipFile(io.BytesIO(raw)) as source, ZipFile(io.BytesIO(corrected)) as derivative:
        assert source.namelist() == derivative.namelist()
        for member in source.namelist():
            if member != 'word/document.xml':
                assert source.read(member) == derivative.read(member)


def test_table_target_is_not_confused_with_identical_direct_paragraph():
    document = Document()
    document.add_table(rows=1, cols=1).cell(0, 0).text = 'Stuk 1'
    document.add_paragraph('Stuk 1')
    output = io.BytesIO()
    document.save(output)
    original = output.getvalue()
    with pytest.raises(ValueError, match='direct body'):
        correction_anchor(original, finding(0, 6))
    assert correction_anchor(original, finding(7, 13)) == 0


def test_complex_target_stays_blocked_even_when_unrelated_content_is_supported():
    document = Document()
    document.add_table(rows=1, cols=1).cell(0, 0).text = 'Table'
    target = document.add_paragraph('Stuk ')
    target.add_run('1').bold = True
    from docx.oxml import OxmlElement

    target._p.append(OxmlElement('w:bookmarkStart'))
    output = io.BytesIO()
    document.save(output)
    with pytest.raises(ValueError, match='unsupported target'):
        correction_anchor(output.getvalue(), finding(6, 12))


def test_anchor_accepts_reference_split_across_plain_formatted_runs():
    document = Document()
    paragraph = document.add_paragraph('See Stu')
    paragraph.add_run('k 1').italic = True
    output = io.BytesIO()
    document.save(output)
    assert correction_anchor(output.getvalue(), finding(4, 10)) == 0


def test_locator_identity_accepts_exact_paragraph_context():
    from hashlib import sha256

    original = docx('Before Stuk 1 after')
    target = finding(7, 13)
    target['locator_identity'] = {
        'content_hash': sha256('Before Stuk 1 after'.encode()).hexdigest(),
        'paragraph_id': None,
        'prefix': 'Before ',
        'suffix': ' after',
        'occurrence_index': 0,
    }
    assert correction_anchor(original, target) == 0


@pytest.mark.parametrize('change', [
    {'content_hash': '0' * 64},
    {'paragraph_id': 'DEADBEEF'},
    {'prefix': 'Wrong '},
    {'suffix': ' wrong'},
    {'occurrence_index': 1},
])
def test_locator_identity_fails_closed_when_stale(change):
    from hashlib import sha256

    original = docx('Before Stuk 1 after')
    target = finding(7, 13)
    target['locator_identity'] = {
        'content_hash': sha256('Before Stuk 1 after'.encode()).hexdigest(),
        'paragraph_id': None,
        'prefix': 'Before ',
        'suffix': ' after',
        'occurrence_index': 0,
        **change,
    }
    with pytest.raises(ValueError):
        correction_anchor(original, target)


@pytest.mark.parametrize('override', [
    {'exact_text': 'Stuk 2'},
    {'exact_text': 123},
    {'content_hash': 'z' * 64},
    {'content_hash': 'A' * 64},
])
def test_locator_rejects_mismatched_exact_text_and_invalid_digest(override):
    from hashlib import sha256

    original = docx('Before Stuk 1 after')
    target = finding(7, 13)
    target['locator_identity'] = {
        'exact_text': 'Stuk 1',
        'content_hash': sha256('Before Stuk 1 after'.encode()).hexdigest(),
        'paragraph_id': None,
        'prefix': 'Before ',
        'suffix': ' after',
        'occurrence_index': 0,
        **override,
    }
    with pytest.raises(ValueError):
        correction_anchor(original, target)


def test_locator_exact_text_matches_before_in_contract():
    from apps.api.dossier_journey import CorrectionPreviewBody
    from hashlib import sha256

    base = dict(snapshot_hash='a' * 64, original_sha256='b' * 64,
                reference_id='ref-1', paragraph_index=0, before='Stuk 1', after='Stuk 2')
    identity = dict(exact_text='Stuk 1', prefix='Before ', suffix=' after',
                    occurrence_index=0, content_hash=sha256(b'Before Stuk 1 after').hexdigest(),
                    paragraph_id=None, source_version_id='version-1')
    assert CorrectionPreviewBody.model_validate({**base, 'locator_identity': identity}).locator_identity is not None
    with pytest.raises(ValueError):
        CorrectionPreviewBody.model_validate({**base, 'locator_identity': {**identity, 'exact_text': 'Stuk 9'}})
    with pytest.raises(ValueError):
        CorrectionPreviewBody.model_validate({**base, 'locator_identity': {**identity, 'content_hash': 'z' * 64}})
