"""F6 actual DOCX package fidelity: formatted originals never flattened."""
from __future__ import annotations

import hashlib
import io
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from docx import Document

from infrastructure.parsers.dossier_docx_export import annotated_docx


def fixture() -> bytes:
    document = Document()
    title = document.add_paragraph(style="Heading 2")
    title.add_run("Stuk 1").bold = True
    title.add_run(" — referentie, printed p. 4").italic = True
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Pièce 2"
    table.cell(0, 1).text = "7"
    table.cell(1, 0).text = "Behouden tabel"
    table.cell(1, 1).text = "1 250 EUR"
    document.add_paragraph("Unchanged concluding paragraph.")
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


def report() -> dict:
    return {
        "snapshot_hash": "a" * 64,
        "coverage": {"checked": 1, "unprocessed_regions": 2},
        "findings": [],
        "human_decisions": [],
        "verification_contract": {"version": "caseproof-v1"},
        "abstentions": [],
    }


def test_f6_annotated_docx_preserves_existing_styles_runs_tables_and_members():
    original = fixture()
    result = annotated_docx(original, report())
    before = Document(io.BytesIO(original))
    after = Document(io.BytesIO(result))
    assert before.paragraphs[0].text == after.paragraphs[0].text
    assert before.paragraphs[0].style.name == after.paragraphs[0].style.name
    assert [(r.text, r.bold, r.italic) for r in before.paragraphs[0].runs] == [
        (r.text, r.bold, r.italic) for r in after.paragraphs[0].runs
    ]
    assert len(after.tables) == 1
    assert [[c.text for c in row.cells] for row in after.tables[0].rows] == [
        ["Pièce 2", "7"], ["Behouden tabel", "1 250 EUR"]
    ]
    assert after.paragraphs[1].text == before.paragraphs[1].text
    assert any("scoped review annotations" in p.text for p in after.paragraphs)
    with ZipFile(io.BytesIO(original)) as src, ZipFile(io.BytesIO(result)) as derivative:
        assert derivative.testzip() is None
        assert set(src.namelist()) == set(derivative.namelist())
        for name in src.namelist():
            if name != "word/document.xml":
                assert src.read(name) == derivative.read(name), name
    assert hashlib.sha256(original).hexdigest() != hashlib.sha256(result).hexdigest()


def test_f6_docx_footnote_member_is_not_silently_rewritten():
    original = fixture()
    footnotes = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        b'<w:footnote w:id="5"><w:p><w:r><w:t>Source note</w:t></w:r></w:p></w:footnote>'
        b'</w:footnotes>'
    )
    target = io.BytesIO()
    with ZipFile(io.BytesIO(original)) as source, ZipFile(target, "w", ZIP_DEFLATED) as output:
        for item in source.infolist():
            output.writestr(item, source.read(item.filename))
        output.writestr("word/footnotes.xml", footnotes)
    amended = target.getvalue()
    result = annotated_docx(amended, report())
    with ZipFile(io.BytesIO(result)) as archive:
        assert archive.read("word/footnotes.xml") == footnotes


def test_f6_unsupported_external_docx_link_never_creates_export():
    original = fixture()
    replacement = io.BytesIO()
    with ZipFile(io.BytesIO(original)) as source, ZipFile(replacement, "w", ZIP_DEFLATED) as out:
        for entry in source.infolist():
            value = source.read(entry.filename)
            if entry.filename == "word/_rels/document.xml.rels":
                value = value.replace(
                    b"</Relationships>",
                    b'<Relationship Id="rId999" Type="http://schemas.openxmlformats.org/'
                    b'officeDocument/2006/relationships/hyperlink" Target="https://foreign.invalid" '
                    b'TargetMode="External"/></Relationships>',
                )
            out.writestr(entry, value)
    with pytest.raises(ValueError, match="cannot be exported"):
        annotated_docx(replacement.getvalue(), report())
