import io
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from docx import Document

from infrastructure.parsers.dossier_docx_export import annotated_docx


def package(extra_name=None, extra_bytes=b'', instruction=None):
    doc = Document()
    doc.add_paragraph('Synthetic private draft')
    out = io.BytesIO()
    doc.save(out)
    result = io.BytesIO()
    with ZipFile(io.BytesIO(out.getvalue())) as source, ZipFile(result, 'w', ZIP_DEFLATED) as target:
        for entry in source.infolist():
            content = source.read(entry)
            if instruction and entry.filename == 'word/document.xml':
                content = content.replace(b'</w:body>', instruction + b'</w:body>')
            target.writestr(entry, content)
        if extra_name:
            target.writestr(extra_name, extra_bytes)
    return result.getvalue()


@pytest.mark.parametrize('name,payload', [
    ('word/_rels/evil.rels', b'<Relationships><Relationship TargetMode="External" Target="https://evil.invalid/private"/></Relationships>'),
    ('word/vbaProject.bin', b'active'),
    ('word/embeddings/object.dat', b'active'),
])
def test_derivative_refuses_external_relationships_macros_and_embedded_objects(name, payload):
    original = package(name, payload)
    with pytest.raises(ValueError):
        annotated_docx(original, {})


def test_split_active_field_is_refused_before_derivative_is_emitted():
    instruction = b'<w:p><w:r><w:instrText>INCLU</w:instrText></w:r><w:r><w:instrText>DEPICTURE "https://evil.invalid/private"</w:instrText></w:r></w:p>'
    with pytest.raises(ValueError, match='active draft field'):
        annotated_docx(package(instruction=instruction), {})


def test_link_field_with_xml_tab_cannot_bypass_active_field_gate():
    instruction = b'<w:p><w:fldSimple w:instr="LINK&#9;Excel.Sheet.12 secret.xlsx"/></w:p>'
    with pytest.raises(ValueError, match='active draft field'):
        annotated_docx(package(instruction=instruction), {})


@pytest.mark.parametrize('relation', ['vbaProject', 'oleObject', 'control', 'aFChunk', 'attachedTemplate'])
def test_active_relationship_is_denied_even_with_innocent_part_name(relation):
    payload = ('<Relationships><Relationship Type="http://schemas.microsoft.com/office/2006/relationships/'
               + relation + '" Target="arbitrary.dat"/></Relationships>').encode()
    with pytest.raises(ValueError, match='active draft relationship'):
        annotated_docx(package('word/_rels/active.rels', payload), {})


def test_malformed_optional_xml_is_a_safe_export_rejection():
    with pytest.raises(ValueError, match='unsafe draft archive'):
        annotated_docx(package('word/unknown.xml', b'<broken'), {})


def test_adjacent_benign_field_cannot_hide_active_command():
    instruction = b'<w:p><w:fldSimple w:instr="PAGE"/><w:fldSimple w:instr="LINK&#9;Excel.Sheet.12 secret.xlsx"/></w:p>'
    with pytest.raises(ValueError, match='active draft field'):
        annotated_docx(package(instruction=instruction), {})
