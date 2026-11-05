"""Hostile and representative OOXML editing tests; no authorization claim."""
import hashlib
import io
from zipfile import ZipFile

import pytest
from docx import Document
from docx.oxml import OxmlElement

from infrastructure.parsers.docx_structured_editing import (
    DocumentRevisionDecision,
    DocumentTextEdit,
    decide_document_revisions,
    edit_document_text,
    list_document_blocks,
    list_document_revisions,
)

STAMP = "2026-11-04T20:00:00+00:00"


def _draft():
    doc = Document()
    doc.add_paragraph("A plain paragraph")
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Table evidence"
    table.cell(0, 1).text = "Unchanged"
    outer = doc.add_paragraph("Drawing follows")
    drawing_run = outer.add_run()
    pict = OxmlElement("w:pict")
    box = OxmlElement("w:txbxContent")
    paragraph = OxmlElement("w:p")
    run = OxmlElement("w:r")
    text = OxmlElement("w:t")
    text.text = "Textbox evidence"
    run.append(text)
    paragraph.append(run)
    box.append(paragraph)
    pict.append(box)
    drawing_run._r.append(pict)
    value = io.BytesIO()
    doc.save(value)
    return value.getvalue()


def _edit(block, after, *, track=True):
    return DocumentTextEdit(block.part, block.paragraph_index, block.text_sha256,
                            block.text, after, track)


def _apply(original, edits):
    return edit_document_text(
        original, expected_sha256=hashlib.sha256(original).hexdigest(),
        edits=edits, author="Synthetic reviewer", timestamp=STAMP,
    )


def test_edits_plain_body_and_top_level_table_without_touching_original():
    source = _draft()
    blocks = list_document_blocks(source)
    body = next(b for b in blocks if b.text == "A plain paragraph")
    table = next(b for b in blocks if b.text == "Table evidence")
    assert body.kind == "body" and table.kind == "table"
    changed = _apply(source, [_edit(body, "A revised paragraph", track=False),
                              _edit(table, "Updated table evidence", track=False)])
    reopened = Document(io.BytesIO(changed))
    assert reopened.paragraphs[0].text == "A revised paragraph"
    assert reopened.tables[0].cell(0, 0).text == "Updated table evidence"
    assert reopened.tables[0].cell(0, 1).text == "Unchanged"
    assert Document(io.BytesIO(source)).paragraphs[0].text == "A plain paragraph"
    with ZipFile(io.BytesIO(source)) as old, ZipFile(io.BytesIO(changed)) as new:
        assert old.namelist() == new.namelist()
        for name in old.namelist():
            if name != "word/document.xml":
                assert old.read(name) == new.read(name)


def test_edit_textbox_paragraph_without_flattening_the_container():
    source = _draft()
    block = next(b for b in list_document_blocks(source) if b.text == "Textbox evidence")
    assert block.kind == "textbox"
    changed = _apply(source, [_edit(block, "New shape text", track=False)])
    with ZipFile(io.BytesIO(changed)) as archive:
        xml = archive.read("word/document.xml")
    assert b"w:txbxContent" in xml and b"New shape text" in xml
    assert b"Textbox evidence" not in xml


def test_native_word_tracking_creates_author_date_and_separate_revisions():
    source = _draft()
    block = next(b for b in list_document_blocks(source) if b.text == "Table evidence")
    proposed = _apply(source, [_edit(block, "New proposed text")])
    with ZipFile(io.BytesIO(proposed)) as archive:
        xml = archive.read("word/document.xml")
    assert b"w:ins" in xml and b"w:del" in xml
    assert b"w:delText" in xml and b"Table evidence" in xml
    assert b"New proposed text" in xml
    assert b"Synthetic reviewer" in xml and b"2026-11-04T20:00:00+00:00" in xml
    # A revision is not automatically included as verified paragraph text.
    assert not any(b.editable and b.text == "New proposed text"
                   for b in list_document_blocks(proposed))
    accepted = decide_document_revisions(
        proposed, expected_sha256=hashlib.sha256(proposed).hexdigest(),
        decisions=[DocumentRevisionDecision("word/document.xml", 1, "accept"),
                   DocumentRevisionDecision("word/document.xml", 2, "accept")],
    )
    assert Document(io.BytesIO(accepted)).tables[0].cell(0, 0).text == "New proposed text"
    rejected = decide_document_revisions(
        proposed, expected_sha256=hashlib.sha256(proposed).hexdigest(),
        decisions=[DocumentRevisionDecision("word/document.xml", 1, "reject"),
                   DocumentRevisionDecision("word/document.xml", 2, "reject")],
    )
    assert Document(io.BytesIO(rejected)).tables[0].cell(0, 0).text == "Table evidence"


def test_source_hash_target_hash_and_exact_text_abstain():
    source = _draft()
    block = next(b for b in list_document_blocks(source) if b.text == "A plain paragraph")
    edit = _edit(block, "New text")
    with pytest.raises(ValueError, match="source bytes changed"):
        edit_document_text(source, expected_sha256="0" * 64,
                           edits=[edit], author="Reviewer", timestamp=STAMP)
    for value in [
        DocumentTextEdit(edit.part, edit.paragraph_index, "0" * 64,
                         edit.before, edit.after),
        DocumentTextEdit(edit.part, edit.paragraph_index, edit.expected_text_sha256,
                         "Other", edit.after),
    ]:
        with pytest.raises(ValueError, match="stale"):
            _apply(source, [value])
    with pytest.raises(ValueError, match="duplicate"):
        _apply(source, [edit, edit])
    with pytest.raises(ValueError, match="unsupported DOCX story"):
        _apply(source, [DocumentTextEdit("../outside.xml", 0, edit.expected_text_sha256,
                                         edit.before, edit.after)])


def test_invalid_xml_characters_and_untrusted_metadata_refused():
    source = _draft()
    block = next(b for b in list_document_blocks(source) if b.text == "A plain paragraph")
    with pytest.raises(ValueError, match="invalid edit"):
        _apply(source, [_edit(block, "invalid\x00")])
    with pytest.raises(ValueError, match="invalid editing metadata"):
        edit_document_text(source, expected_sha256=hashlib.sha256(source).hexdigest(),
                           edits=[_edit(block, "New")], author="x\x00", timestamp=STAMP)
    with pytest.raises(ValueError, match="invalid editing metadata"):
        edit_document_text(source, expected_sha256=hashlib.sha256(source).hexdigest(),
                           edits=[_edit(block, "New")], author="X", timestamp="tomorrow")


def test_nested_revision_and_unknown_structure_are_not_silently_rewritten():
    doc = Document()
    p = doc.add_paragraph("Ordinary")
    p._p.append(OxmlElement("w:fldSimple"))
    file = io.BytesIO()
    doc.save(file)
    source = file.getvalue()
    block = list_document_blocks(source)[0]
    assert not block.editable
    with pytest.raises(ValueError, match="invalid edit payload|unsupported edit target"):
        _apply(source, [_edit(block, "A replacement")])


def test_revisions_must_have_exact_id_and_supported_markup():
    source = _draft()
    block = next(b for b in list_document_blocks(source) if b.text == "A plain paragraph")
    proposed = _apply(source, [_edit(block, "New")])
    with pytest.raises(ValueError, match="missing or ambiguous"):
        decide_document_revisions(
            proposed, expected_sha256=hashlib.sha256(proposed).hexdigest(),
            decisions=[DocumentRevisionDecision("word/document.xml", 42, "accept")],
        )
    with pytest.raises(ValueError, match="duplicate"):
        decide_document_revisions(
            proposed, expected_sha256=hashlib.sha256(proposed).hexdigest(),
            decisions=[DocumentRevisionDecision("word/document.xml", 1, "accept"),
                       DocumentRevisionDecision("word/document.xml", 1, "reject")],
        )


def test_revision_inventory_exposes_hash_without_raw_confidential_text():
    source = _draft()
    target = next(b for b in list_document_blocks(source) if b.text == "Textbox evidence")
    suggested = _apply(source, [_edit(target, "Confidential suggestion")])
    rows = list_document_revisions(suggested)
    assert len(rows) == 2
    assert {r.kind for r in rows} == {"deleted", "inserted"}
    assert [r.revision_id for r in rows] == [1, 2]
    assert all(r.author == "Synthetic reviewer" and r.timestamp == STAMP for r in rows)
    assert rows[1].text_sha256 == hashlib.sha256(b"Confidential suggestion").hexdigest()
    assert "Confidential" not in repr(rows)


def test_local_cli_never_overwrites_and_inspection_omits_text(tmp_path, capsys):
    import json
    import sys

    from scripts.docx_local_editor import main

    source = tmp_path / "original.docx"
    preserved = _draft()
    source.write_bytes(preserved)
    original_argv = sys.argv
    try:
        sys.argv = ["docx-editor", "inspect", "--input", str(source), "--list-targets"]
        assert main() == 0
        view = json.loads(capsys.readouterr().out)
        assert view["schema"] == "caseproof-docx-local-inspection-v1"
        assert view["targets"]
        assert all("before" not in block for block in view["targets"])
        block = next(b for b in view["targets"] if b["editable"] and b["kind"] == "body")
        plan = tmp_path / "plan.json"
        plan.write_text(json.dumps({
            "schema": "caseproof-docx-local-edit-plan-v1",
            "source_sha256": view["source_sha256"],
            "author": "Local reviewer",
            "timestamp": STAMP,
            "edits": [{
                "part": block["part"],
                "paragraph_index": block["paragraph_index"],
                "expected_text_sha256": block["expected_text_sha256"],
                "before": "A plain paragraph",
                "after": "A changed paragraph",
                "track_changes": False,
            }],
        }), encoding="utf-8")
        derivative = tmp_path / "derivative.docx"
        sys.argv = ["docx-editor", "edit", "--input", str(source),
                    "--output", str(derivative), "--plan", str(plan)]
        assert main() == 0
        receipt = json.loads(capsys.readouterr().out)
        assert receipt["activated"] is False
        assert Document(io.BytesIO(derivative.read_bytes())).paragraphs[0].text == "A changed paragraph"
        with pytest.raises(ValueError, match="never overwrite"):
            main()
        assert source.read_bytes() == preserved
    finally:
        sys.argv = original_argv
