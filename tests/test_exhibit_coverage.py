"""Exhibit reference resolution and byte coverage: located is never PASS, content is never compared."""
from __future__ import annotations

import hashlib
import json
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from application.litigation.corpus import CorpusError
from application.litigation.exhibit_coverage import (
    R_ABSENT,
    R_LOCATED,
    R_MISSING,
    R_PAGE,
    R_UNREADABLE,
    exhibit_observations,
    find_references,
    load_exhibit_set,
)
from application.litigation.offline_legal_pack import verify_legal_pack
from apps.api.offline_docx_check import check_offline_docx
from apps.api.offline_review import recheck, record_decisions
from tests.signed_composed_rig import docx_without_custom_xml
from tests.test_legal_reference_adversarial import ARTICLE, pdf_corpus


def make_pdf(text: str) -> bytes:
    """Plain Helvetica PDF with a real text layer (pypdf-readable)."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (i, o)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % x for x in offsets)
    return out + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)


def pieces_dir(tmp_path: Path, *, declared: str | None = None, extra: str = "") -> Path:
    d = tmp_path / "pieces"
    d.mkdir(parents=True, exist_ok=True)
    (d / "p1.pdf").write_bytes(make_pdf("Contrat de bail signé le douze mars"))
    (d / "p2.txt").write_text("Courrier du 3 avril")
    (d / "p4.pdf").write_bytes(b"%PDF-1.4 not really a pdf")
    row = f'declared_sha256 = "{declared}"\n' if declared else ""
    (d / "bordereau.toml").write_text(
        'format = "caseproof-bordereau-v1"\n'
        f'[[piece]]\nnumber = "1"\nlabel = "Contrat de bail"\nfile = "p1.pdf"\n{row}'
        '[[piece]]\nnumber = "2"\nlabel = "Courrier"\nfile = "p2.txt"\n'
        '[[piece]]\nnumber = "3"\nlabel = "Photo"\nfile = "absent.pdf"\n'
        '[[piece]]\nnumber = "4"\nlabel = "Scan"\nfile = "p4.pdf"\n'
        '[[piece]]\nnumber = "9"\nlabel = "Jamais citée"\nfile = "p2.txt"\n' + extra)
    return d


def run(tmp_path: Path, paragraphs: list[str], **kw):
    p = tmp_path / "w.docx"
    p.write_bytes(docx_without_custom_xml(paragraphs))
    raw, cp = check_offline_docx(docx=p, corpus=pdf_corpus(tmp_path), exhibits=pieces_dir(tmp_path), **kw)
    return raw, cp, verify_legal_pack(raw, expected_sha256=cp)


def exhibit_rows(body):
    return [(r["raw_text"], r["status"], r["reason"]) for r in body["references"] if r["reason"].startswith("exhibit_")]


def test_references_resolve_by_number_with_bytes_read_and_never_pass(tmp_path):
    _, _, body = run(tmp_path, ["Le bail (pièce 1) et le courrier (Stuk nr. 2) le prouvent.",
                                "Voir pièce 3, pièce 4, pièce 7 et pièce 2, p. 3."])
    rows = exhibit_rows(body)
    by = {(a, c): s for a, s, c in rows}
    assert ("Pièce 1", R_LOCATED) in by and ("Stuk 2", R_LOCATED) in by
    assert by[("Pièce 3", R_MISSING)] == "UNDETERMINED" and by[("Pièce 4", R_UNREADABLE)] == "UNDETERMINED"
    assert by[("Pièce 7", R_ABSENT)] == "UNVERIFIED" and ("Pièce 2", R_PAGE) in by
    assert all(s != "PASS" for _, s, _ in rows)
    one = next(r for r in body["references"] if r["raw_text"] == "Pièce 1")
    assert hashlib.sha256((tmp_path / "pieces/p1.pdf").read_bytes()).hexdigest() in one["quote"]
    assert body["review"]["check_engine"].endswith("-v5") and "exhibits" in body


def test_lists_ranges_and_dates_are_not_confused():
    refs = find_references("pièces 3, 4 et 5, puis pièce 6, 12 mars 2024 ; stukken 2 t/m 4")
    assert [r["number"] for r in refs] == ["3", "4", "5", "6", "2", "3", "4"]


def test_declared_hash_is_checked_against_bytes_not_trusted(tmp_path):
    with pytest.raises(CorpusError, match="declared hash"):
        load_exhibit_set(pieces_dir(tmp_path, declared="0" * 64))
    good = hashlib.sha256(make_pdf("Contrat de bail signé le douze mars")).hexdigest()
    assert load_exhibit_set(pieces_dir(tmp_path / "ok", declared=good))["pieces"][0]["sha256"] == good


def test_duplicate_number_and_escaping_path_are_refused(tmp_path):
    with pytest.raises(CorpusError):
        load_exhibit_set(pieces_dir(tmp_path, extra='[[piece]]\nnumber = "1"\nlabel = "Doublon"\nfile = "p2.txt"\n'))
    d = pieces_dir(tmp_path / "e")
    (d / "bordereau.toml").write_text('format = "caseproof-bordereau-v1"\n[[piece]]\nnumber = "1"\nlabel = "x"\nfile = "../outside.txt"\n')
    with pytest.raises(CorpusError):
        load_exhibit_set(d)


def test_altered_manifest_is_refused_on_replay_computation(tmp_path):
    ex = load_exhibit_set(pieces_dir(tmp_path))
    ex["pieces"][0]["sha256"] = "f" * 64
    with pytest.raises(CorpusError, match="altered"):
        exhibit_observations("pièce 1", ex, 1)


def test_cold_replay_rejects_edited_review_and_report_scope_is_stated(tmp_path):
    raw, cp, _ = run(tmp_path, ["Voir pièce 1."])
    z = zipfile.ZipFile(BytesIO(raw))
    report = z.read("report.html").decode()
    assert "ne vérifie PAS que le contenu" in report and "Pièces jamais citées : 2, 3, 4, 9" in report
    body = json.loads(z.read("review.json"))
    body["exhibits"]["pieces"][0]["sha256"] = "a" * 64
    out = BytesIO()
    with zipfile.ZipFile(out, "w") as w:
        w.writestr("review.json", json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())
        w.writestr("report.html", z.read("report.html"))
    with pytest.raises(CorpusError):
        verify_legal_pack(out.getvalue(), expected_sha256=cp)


def test_decision_carries_when_piece_bytes_unchanged_and_lapses_when_the_file_changes(tmp_path):
    raw, cp, body = run(tmp_path, ["Le bail est signé (pièce 1)."])
    idx = next(i for i, r in enumerate(body["references"]) if r["reason"] == R_LOCATED)
    raw2, cp2 = record_decisions(pack=raw, checkpoint=cp, decisions=[
        {"reference_index": idx, "action": "confirm", "reason": "", "reviewer_label": "local"}])
    docx = tmp_path / "w.docx"
    corpus, pieces = pdf_corpus(tmp_path), tmp_path / "pieces"
    r3, c3 = recheck(docx=docx, corpus=corpus, prior_pack=raw2, prior_checkpoint=cp2, exhibits=pieces)
    assert verify_legal_pack(r3, expected_sha256=c3)["review"]["decisions"], "decision carried for the identical piece"
    (pieces / "p1.pdf").write_bytes(make_pdf("Contrat de bail NON signé"))
    r4, c4 = recheck(docx=docx, corpus=corpus, prior_pack=raw2, prior_checkpoint=cp2, exhibits=pieces)
    after = verify_legal_pack(r4, expected_sha256=c4)["review"]
    assert not after["decisions"] and after["superseded"]


def test_legal_findings_unchanged_by_exhibit_coverage(tmp_path):
    _, _, body = run(tmp_path, [f"Article 8.5 du Code civil : « {ARTICLE} » (pièce 1)."])
    legal = [r for r in body["references"] if not r["reason"].startswith("exhibit_")]
    assert any(r["status"] == "PASS" for r in legal)
