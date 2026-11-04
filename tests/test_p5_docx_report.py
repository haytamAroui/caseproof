"""Synthetic output acceptance for readable append-only DOCX derivatives."""
from __future__ import annotations

import io
from zipfile import ZipFile

import pytest
from docx import Document

from infrastructure.parsers.dossier_docx_export import annotated_docx


def fixture() -> bytes:
    doc = Document()
    doc.add_heading('Preserved brief', 1)
    doc.add_paragraph('Pièce 1 - synthetic text')
    doc.add_table(rows=1, cols=2).cell(0, 0).text = 'Keep table'
    data = io.BytesIO()
    doc.save(data)
    return data.getvalue()


def report() -> dict:
    return {
        'snapshot_hash': 'a' * 64,
        'case_id': 'synthetic-case',
        'brief_id': 'synthetic-version',
        'coverage': {
            'checked': 1, 'unresolved': 1, 'reference_recall_measured': False,
            'dimension_counts': {'identity': {'resolved': 1, 'ambiguous': 1}},
            'source_pages': [{'version_id': 'source-1', 'method': 'NOT_PROCESSED'}],
        },
        'verification_contract': {'version': 'v1', 'language_context': {'nl': 'Nederlands'}},
        'abstentions': [{'reference_id': 'ref-2', 'reason': 'not assessed'}],
        'findings': [{
            'reference_id': 'ref-1', 'literal': 'Pièce 1', 'identity': 'resolved',
            'page_mapping': 'mapped', 'fidelity': 'ocr_unreliable',
            'version_id': 'source-1', 'source_text_context': 'café\tà Bruxelles\nligne 2',
            'visual_assessment': {'state': 'ocr_unreliable',
                                  'regions': [{'region_id': 'crop-1', 'bbox': {
                                      'x': 0, 'y': 10, 'width': 20, 'height': 30}}]},
        }],
        'human_decisions': [{
            'reference_id': 'ref-1', 'decision': 'CONFIRMED_QUALIFIED',
            'reviewer_id': 'synthetic-reviewer', 'timestamp': '2026-11-04T10:00:00Z',
            'rationale': 'Inspecté — contrôle humain',
        }],
    }


def test_appendix_is_readable_keeps_original_structure_and_zip_members():
    original = fixture()
    output = annotated_docx(original, report())
    text = '\n'.join(p.text for p in Document(io.BytesIO(output)).paragraphs)
    assert 'Preserved brief' in text
    assert 'CaseProof — scoped review appendix' in text
    assert 'Coverage / dekking / couverture' in text
    assert 'Checked: 1' in text
    assert 'ocr_unreliable' in text
    assert 'Review timestamp: 2026-11-04T10:00:00Z' in text
    assert 'café\tà Bruxelles\nligne 2' in text
    assert "{'checked':" not in text
    assert "{'region_id':" not in text
    assert 'Keep table' in Document(io.BytesIO(output)).tables[0].cell(0, 0).text
    with ZipFile(io.BytesIO(original)) as before, ZipFile(io.BytesIO(output)) as after:
        assert set(before.namelist()) == set(after.namelist())
        for part in before.namelist():
            if part != 'word/document.xml':
                assert before.read(part) == after.read(part)


def test_invalid_xml_character_rejects_annotation_without_substitution():
    data = report()
    data['human_decisions'][0]['rationale'] = 'unsafe\u0000text'
    with pytest.raises(ValueError, match='XML-invalid'):
        annotated_docx(fixture(), data)


def test_decisions_are_rendered_even_without_findings():
    data = report()
    data['findings'] = []
    text = '\n'.join(p.text for p in Document(io.BytesIO(
        annotated_docx(fixture(), data))).paragraphs)
    assert 'Number of detected references: 0' in text
    assert 'synthetic-reviewer' in text
