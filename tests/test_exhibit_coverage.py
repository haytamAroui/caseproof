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
    data, sha = reseal(body, z.read("report.html"))  # recomputed checkpoint: only the replay can refuse it
    with pytest.raises(CorpusError, match="rejected"):
        verify_legal_pack(data, expected_sha256=sha)


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


def _decided(tmp_path, paragraphs, index_of):
    raw, cp, body = run(tmp_path, paragraphs)
    idx = index_of(body)
    raw2, cp2 = record_decisions(pack=raw, checkpoint=cp, decisions=[
        {"reference_index": idx, "action": "confirm", "reason": "", "reviewer_label": "local"}])
    return raw2, cp2


def _recheck_decisions(tmp_path, paragraphs, prior):
    docx = tmp_path / "w.docx"
    docx.write_bytes(docx_without_custom_xml(paragraphs))
    raw, cp = recheck(docx=docx, corpus=pdf_corpus(tmp_path), prior_pack=prior[0], prior_checkpoint=prior[1],
                      exhibits=tmp_path / "pieces")
    return verify_legal_pack(raw, expected_sha256=cp)["review"]


def test_same_piece_cited_in_two_assertions_gets_its_own_decision(tmp_path):
    paragraphs = ["Le bail est signé (pièce 1).", "Le loyer est de 800 euros (pièce 1)."]
    first = lambda body: next(i for i, r in enumerate(body["references"]) if r["reason"] == R_LOCATED)  # noqa: E731
    prior = _decided(tmp_path, paragraphs, first)
    review = _recheck_decisions(tmp_path, paragraphs, prior)
    assert len(review["decisions"]) == 1, "only the first occurrence is covered, not the identical reference elsewhere"


def test_changed_surrounding_assertion_withdraws_the_piece_decision_although_bytes_are_identical(tmp_path):
    paragraphs = ["Le bail est signé (pièce 1)."]
    first = lambda body: next(i for i, r in enumerate(body["references"]) if r["reason"] == R_LOCATED)  # noqa: E731
    prior = _decided(tmp_path, paragraphs, first)
    review = _recheck_decisions(tmp_path, ["Le bail est résilié (pièce 1)."], prior)
    assert not review["decisions"] and review["superseded"]


def reseal(doc: dict, report: bytes) -> tuple[bytes, str]:
    """Rebuild an export from an edited review.json WITH a recomputed checkpoint (what an attacker or a legacy writer would do)."""
    payload = json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    out = BytesIO()
    with zipfile.ZipFile(out, "w") as w:
        w.writestr("review.json", payload)
        w.writestr("report.html", report)
    return out.getvalue(), hashlib.sha256(payload).hexdigest()


def passage_run(tmp_path: Path, paragraphs: list[str]):
    d = tmp_path / "pieces"
    d.mkdir(parents=True)
    (d / "p1.pdf").write_bytes(make_pdf("Le contrat a ete envoye pour signature le 15/03/2024 pour 1.250,00 EUR."))
    (d / "bordereau.toml").write_text('format = "caseproof-bordereau-v1"\n[[piece]]\nnumber = "1"\nlabel = "Bail"\nfile = "p1.pdf"\n')
    p = tmp_path / "w.docx"
    p.write_bytes(docx_without_custom_xml(paragraphs))
    raw, cp = check_offline_docx(docx=p, corpus=pdf_corpus(tmp_path), exhibits=d)
    return raw, cp, verify_legal_pack(raw, expected_sha256=cp)


def test_passages_show_same_values_and_flag_absent_ones_without_a_verdict(tmp_path):
    _, _, body = passage_run(tmp_path, ["Le bail a été signé le 15/03/2024 pour 1.250,00 EUR (pièce 1).",
                                        "Le loyer de 9.999,00 EUR est dû (pièce 1)."])
    first, second = body["passages"]
    assert [f["page"] for f in first["found"]] == [1, 1] and first["missing_values"] == []
    assert "envoye pour signature" in first["found"][0]["excerpt"]  # same date: wording is the lawyer's to read
    assert second["missing_values"] and not second["found"]
    assert all(r["status"] != "PASS" for r in body["references"] if r["reason"].startswith("exhibit_"))


def test_altered_passage_excerpt_or_claim_is_refused_even_with_a_recomputed_checkpoint(tmp_path):
    raw, cp, _ = passage_run(tmp_path, ["Signé le 15/03/2024 (pièce 1)."])
    z = zipfile.ZipFile(BytesIO(raw))
    control, control_sha = reseal(json.loads(z.read("review.json")), z.read("report.html"))
    verify_legal_pack(control, expected_sha256=control_sha)  # an untouched resealed export is accepted: the refusals below come from the edits
    for edit in ("claim", "missing", "excerpt_without_hash", "added_cue_without_marker"):
        body = json.loads(z.read("review.json"))
        entry = body["passages"][0]
        if edit == "claim":
            entry["claim"] = "Signé le 16/03/2024 (pièce 1)."
        elif edit == "missing":
            entry["missing_values"] = [entry["found"][0]["key"]]
        elif edit == "excerpt_without_hash":
            entry["found"][0]["excerpt"] = "signe definitivement"
        else:
            body.pop("passages_rules")
            for _f in body["passages"][0]["found"]:
                _f.pop("page_ref", None)
        data, sha = reseal(body, z.read("report.html"))
        with pytest.raises(CorpusError, match="rejected") as caught:
            verify_legal_pack(data, expected_sha256=sha)
        assert any(k in str(caught.value.__cause__) for k in ("passage", "replay", "found and missing", "status cue")), (edit, caught.value.__cause__)


def test_thousands_dot_does_not_cut_a_fact_sentence():
    from application.litigation.fact_extraction import extract_fact_assertions
    text = "Le paiement du 20/01/2024 de 1.250,00 EUR a été fait le 15/03/2024 (réf)."
    found = extract_fact_assertions(text, (("r1", 0),))
    assert all(len(a.text) > 40 for a in found)  # no assertion truncated at "1."
    assert not [a for a in found if a.kind.value == "date"]  # two dates in one sentence: abstain


def test_workbench_page_scripts_are_valid_javascript(tmp_path):
    """A syntax error silently kills the whole panel in a browser: parse every inline script with node."""
    import re
    import shutil
    import subprocess

    from scripts import serve_offline_legal_workbench as w

    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    scripts = re.findall(r"<script>(.*?)</script>", w.HTML.replace("TOKEN", "t"), re.S)
    assert scripts and "function render" in scripts[0]
    for i, js in enumerate(scripts):
        f = tmp_path / f"s{i}.js"
        f.write_text(js)
        done = subprocess.run([node, "--check", str(f)], capture_output=True, text=True, timeout=30)
        assert done.returncode == 0, done.stderr


@pytest.mark.parametrize(("claim", "excerpt", "expected"), [
    ("Le contrat a été signé le 15/03/2024 (pièce 1).", "Le contrat a ete envoye pour signature le 15/03/2024.", True),
    ("Het contract werd ondertekend op 15/03/2024.", "Contract ter ondertekening verstuurd op 15/03/2024.", True),
    ("Le contrat a été signé le 15/03/2024.", "Contrat non signé au 15/03/2024.", True),
    ("Le contrat a été signé le 15/03/2024.", "Le contrat signé le 15/03/2024 (envoyé pour signature le 1er mars).", False),
    ("Le contrat est envoyé pour signature le 15/03/2024.", "Le contrat a ete envoye pour signature le 15/03/2024.", False),
    ("Le contrat n'est pas signé.", "Contrat non signé.", False),
])
def test_status_cue_mismatch_is_a_partial_flag(claim, excerpt, expected):
    from application.litigation.exhibit_passages import status_mismatch
    assert (status_mismatch(claim, excerpt) is not None) is expected


def test_passage_flags_signed_vs_sent_for_signature_and_replay_refuses_edits(tmp_path):
    raw, _, body = passage_run(tmp_path, ["Le contrat a été signé le 15/03/2024 (pièce 1)."])
    row = body["passages"][0]["found"][0]
    assert row["status_cue_mismatch"] == {"claim_cue": "signé", "passage_cue": "pour signature"}
    assert all(r["status"] != "PASS" for r in body["references"])
    z = zipfile.ZipFile(BytesIO(raw))
    doc = json.loads(z.read("review.json"))
    del doc["passages"][0]["found"][0]["status_cue_mismatch"]
    data, sha = reseal(doc, z.read("report.html"))
    with pytest.raises(CorpusError, match="rejected"):
        verify_legal_pack(data, expected_sha256=sha)


def test_export_without_status_cue_rules_still_replays_and_decisions_keep_it(tmp_path):
    """A delivered v5 export has passages but no status-cue field or rules marker: it must replay unchanged."""
    raw, cp, body = passage_run(tmp_path, ["Le contrat a été signé le 15/03/2024 (pièce 1)."])
    from application.litigation.offline_legal_pack import _report
    z = zipfile.ZipFile(BytesIO(raw))
    doc = json.loads(z.read("review.json"))
    del doc["passages_rules"]
    for f in doc["passages"][0]["found"]:
        f.pop("status_cue_mismatch", None)
        f.pop("page_ref", None)
    legacy, legacy_sha = reseal(doc, _report(doc))
    assert "passages_rules" not in verify_legal_pack(legacy, expected_sha256=legacy_sha)
    # a status cue smuggled in without the marker is refused
    doc["passages"][0]["found"][0]["status_cue_mismatch"] = {"claim_cue": "signé", "passage_cue": "pour signature"}
    bad, bad_sha = reseal(doc, _report(doc))
    with pytest.raises(CorpusError, match="rejected"):
        verify_legal_pack(bad, expected_sha256=bad_sha)


@pytest.mark.parametrize(("claim", "excerpt", "flagged", "why"), [
    ("Le contrat n'a pas été signé le 15/03/2024.", "Contrat envoyé pour signature le 15/03/2024.", False, "claim itself negated"),
    ("Le contrat a été signé le 15/03/2024.", "Contrat signé le 15/03/2024 par les deux parties.", False, "completed signature"),
    ("Het contract is ondertekend op 15/03/2024.", "Contract getekend op 15/03/2024.", False, "completed signature (NL)"),
    ("Le contrat a été signé le 15/03/2024.", "Le contrat signé le 15/03/2024 reste à signer par le garant.", False, "also says signed: no mismatch claimed"),
    ("Le contrat a été signé le 15/03/2024.", "Le bailleur a envoyé pour signature au garant le 15/03/2024.", True, "KNOWN LIMIT: other party/other act is still flagged"),
    ("Le locataire a signé le 15/03/2024.", "Contrat non signé par le bailleur le 15/03/2024.", True, "KNOWN LIMIT: the flag does not know WHO signs"),
])
def test_status_cue_contrast_cases_do_not_become_a_verdict(claim, excerpt, flagged, why):
    from application.litigation.exhibit_passages import status_mismatch
    assert (status_mismatch(claim, excerpt) is not None) is flagged, why


def test_legacy_passage_scope_text_is_frozen():
    """Exports without a rules marker replay their reading view byte for byte: this text must never change."""
    from application.litigation.exhibit_passages import SCOPE_LEGACY
    assert hashlib.sha256(SCOPE_LEGACY.encode()).hexdigest() == "a26681ee9128291599cac01a4304387c84d71a5a7a56145d36f40f4a6aa8e1a0"


def test_delivered_v5_exports_replay_unchanged():
    """Real exports from the delivered v5 pack (commit 2321e3dd) must keep replaying under every later code version."""
    fixtures = Path(__file__).parent / "fixtures" / "offline_legal_v5"
    checkpoints = json.loads((fixtures / "checkpoints.json").read_text())
    assert len(checkpoints) == 2
    for case, checkpoint in checkpoints.items():
        body = verify_legal_pack((fixtures / f"{case}.zip").read_bytes(), expected_sha256=checkpoint)
        assert "passages_rules" not in body and "exhibits" in body


def test_status_cue_rules_marker_names_immutable_behaviour():
    """The marker identifies this exact cue list and negation rule. Change either and you must add a new marker."""
    from application.litigation import exhibit_passages as e
    assert e.RULES == "status-cue-v3" and e.RULES_V2 == "status-cue-v2"
    pinned = hashlib.sha256(repr((e._SIGNED, e._PENDING, e._NEGATION.pattern, e._NEGATION.flags)).encode()).hexdigest()
    assert pinned == "0837b4fb2312319b33a9f0bd6349d85181ff60360b3469741af449c117f3549c"


def _pdf_stream(body: str) -> bytes:
    stream = body.encode("latin-1")
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


def test_printed_number_is_a_literal_footer_match_only():
    from application.litigation.exhibit_passages import printed_number
    assert printed_number("Texte\nPage 7 / 12") == "7" and printed_number("Texte\n7") == "7"
    assert printed_number("Texte sans pied de page") is None
    assert printed_number("Le loyer est de 1250\nsuite du texte") is None  # a number inside a sentence is not a page number


def page_ref_run(tmp_path: Path):
    d = tmp_path / "pieces"
    d.mkdir(parents=True)
    (d / "p1.pdf").write_bytes(_pdf_stream("BT /F1 12 Tf 72 720 Td 14 TL (Signe le 15/03/2024.) Tj T* (Page 7) Tj ET"))
    (d / "bordereau.toml").write_text('format = "caseproof-bordereau-v1"\n[[piece]]\nnumber = "1"\nlabel = "Bail"\nfile = "p1.pdf"\n')
    p = tmp_path / "w.docx"
    p.write_bytes(docx_without_custom_xml(["Le bail a été signé le 15/03/2024 (pièce 1)."]))
    raw, cp = check_offline_docx(docx=p, corpus=pdf_corpus(tmp_path), exhibits=d)
    return raw, cp, verify_legal_pack(raw, expected_sha256=cp)


def test_page_ref_shows_file_position_pdf_label_and_printed_number_separately(tmp_path):
    raw, _, body = page_ref_run(tmp_path)
    ref = body["passages"][0]["found"][0]["page_ref"]
    assert ref == {"index": 1, "label": None, "printed": "7"} and body["passages_rules"] == "status-cue-v3"
    html = zipfile.ZipFile(BytesIO(raw)).read("report.html").decode()
    assert "position dans le fichier 1" in html and "numéro imprimé lu" in html and "pas d&#x27;étiquette" in html or "pas d'étiquette" in html


def test_page_ref_tampering_is_refused_after_reseal_with_control(tmp_path):
    raw, _, _ = page_ref_run(tmp_path)
    z = zipfile.ZipFile(BytesIO(raw))
    control, control_sha = reseal(json.loads(z.read("review.json")), z.read("report.html"))
    verify_legal_pack(control, expected_sha256=control_sha)
    for edit in ("old_marker", "bad_index", "bad_printed", "extra_key"):
        body = json.loads(z.read("review.json"))
        ref = body["passages"][0]["found"][0]["page_ref"]
        if edit == "old_marker":
            body["passages_rules"] = "status-cue-v2"
        elif edit == "bad_index":
            ref["index"] = 4
        elif edit == "bad_printed":
            ref["printed"] = "<b>7</b>"
        else:
            ref["extra"] = "x"
        data, sha = reseal(body, z.read("report.html"))
        with pytest.raises(CorpusError, match="rejected"):
            verify_legal_pack(data, expected_sha256=sha)


def test_export_with_the_v2_marker_and_no_page_refs_still_replays(tmp_path):
    from application.litigation.offline_legal_pack import _report
    raw, _, _ = passage_run(tmp_path, ["Le contrat a été signé le 15/03/2024 (pièce 1)."])
    doc = json.loads(zipfile.ZipFile(BytesIO(raw)).read("review.json"))
    doc["passages_rules"] = "status-cue-v2"
    for f in doc["passages"][0]["found"]:
        f.pop("page_ref", None)
    data, sha = reseal(doc, _report(doc))
    assert verify_legal_pack(data, expected_sha256=sha)["passages_rules"] == "status-cue-v2"


def test_pdf_defined_page_label_is_recorded_as_the_pdf_label_not_as_a_printed_number(tmp_path):
    from application.litigation.exhibit_passages import page_meta
    raw = _pdf_stream("BT /F1 12 Tf 72 720 Td (Texte sans pied de page) Tj ET")
    raw = raw.replace(b"/Type /Catalog /Pages 2 0 R", b"/Type /Catalog /Pages 2 0 R /PageLabels << /Nums [0 << /S /r >>] >>", 1)
    (tmp_path / "p1.pdf").write_bytes(raw)
    meta = page_meta(tmp_path, {"pieces": [{"number": "1", "file": "p1.pdf", "present": True, "readable": True}]})
    assert meta["1"] == [{"index": 1, "label": "i", "printed": None}]
