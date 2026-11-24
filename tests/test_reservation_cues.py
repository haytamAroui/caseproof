"""Literal reservation/negation cues: partial detection, never a status change or a reading of meaning."""
from types import SimpleNamespace

import pytest

from application.litigation.corpus import CorpusError
from application.litigation.reservation_cues import RULES, build_section, cues_for, validate_section

ART = "Art. 8.9. Le paiement est dû. Hormis les cas où la loi en dispose autrement, le débiteur ne peut refuser. Il n'y a pas d'exception."


def test_reservation_outside_quote_is_flagged():
    assert {"kind": "reservation", "cue": "hormis"} in cues_for("Le paiement est dû.", ART)


def test_negation_only_from_adjacent_sentence_and_never_inside_the_quote():
    quote = "le débiteur ne peut refuser."
    kinds = {(c["kind"], c["cue"]) for c in cues_for(quote, ART)}
    # "pas" is in the NEXT sentence, "ne" is inside the quote itself
    assert ("negation_adjacent", "pas") in kinds
    assert ("negation_adjacent", "ne") not in kinds


def test_no_cue_no_row_and_absent_quote_is_ignored():
    assert cues_for("Le paiement est dû.", "Le paiement est dû.") == []
    assert cues_for("absent", ART) == []


def _refs():
    rec = SimpleNamespace(derived_sha256="a" * 64, derived_text=ART)
    ref = {"reference_id": "r1", "status": "PASS", "quote": "Le paiement est dû.", "corpus_text_sha256": "a" * 64}
    return [ref, {**ref, "reference_id": "r2", "status": "FAIL"}], [rec]


def test_section_only_for_literally_found_quotes_and_replay_refuses_edits():
    refs, recs = _refs()
    sec = build_section(refs, recs)
    assert sec["rules"] == RULES and sec["quotations_checked"] == 1 and [r["reference_id"] for r in sec["flagged"]] == ["r1"]
    validate_section(sec, refs, recs)
    forged = {**sec, "flagged": []}
    with pytest.raises(CorpusError):
        validate_section(forged, refs, recs)


# --- through the signed offline pack (FAKE-backed auth/storage/DB; real build, report and cold replay) ---
def _pack_zip(raw, review):
    import io
    from zipfile import ZIP_STORED, ZipFile
    src = ZipFile(io.BytesIO(raw))
    out = io.BytesIO()
    with ZipFile(out, "w", compression=ZIP_STORED) as z:
        for n in src.namelist():
            z.writestr(n, review if n == "review.json" else src.read(n))
    return out.getvalue()


def test_pack_carries_the_cue_section_replays_and_tampering_is_refused(tmp_path, monkeypatch):
    import io
    import json
    from zipfile import ZipFile

    from application.litigation.offline_legal_pack import verify_legal_pack
    from tests.test_signed_conditions_pack import COND, build, pack
    c = build(tmp_path, monkeypatch, [COND], [])
    raw, cp = pack(c)
    body = verify_legal_pack(raw, expected_sha256=cp)
    sec = body["reservation_cues"]
    assert sec["rules"] == RULES and sec["quotations_checked"] >= 1
    html_ = ZipFile(io.BytesIO(raw)).read("report.html").decode()
    assert "détection partielle" in html_ and "ne change aucun statut" in html_
    assert all(r["status"] != "UNDETERMINED" or "reservation" not in r["reason"] for r in body["references"])
    # A forged "no cue" section cannot be certified even with a recomputed checkpoint of the whole body.
    forged = json.loads(ZipFile(io.BytesIO(raw)).read("review.json"))
    forged["reservation_cues"] = {**sec, "quotations_checked": sec["quotations_checked"] + 1}
    with pytest.raises(CorpusError):
        verify_legal_pack(_pack_zip(raw, json.dumps(forged).encode()), expected_sha256=cp)


def test_older_verifier_cannot_certify_a_pack_with_the_cue_section(tmp_path, monkeypatch):
    import subprocess
    import sys
    from pathlib import Path

    from tests.test_signed_conditions_pack import COND, build, pack
    raw, cp = pack(build(tmp_path, monkeypatch, [COND], []))
    root = Path(__file__).resolve().parents[1]
    old = subprocess.run(["git", "show", "7c92f8b0:application/litigation/offline_legal_pack.py"], cwd=root,
                         capture_output=True, text=True)
    if old.returncode != 0:
        pytest.skip("previous verifier not available in this checkout")
    (tmp_path / "pack.zip").write_bytes(raw)
    code = ("import sys, types\n"
            f"sys.path.insert(0, {str(root)!r})\n"
            f"src = {old.stdout!r}\n"
            "m = types.ModuleType('old_pack'); m.__dict__['__name__'] = 'old_pack'\n"
            "exec(compile(src, 'old', 'exec'), m.__dict__)\n"
            f"raw = open({str(tmp_path / 'pack.zip')!r}, 'rb').read()\n"
            "try:\n"
            f"    m.verify_legal_pack(raw, expected_sha256={cp!r})\n"
            "    print('CERTIFIED')\n"
            "except Exception as e:\n"
            "    print('REJECTED', type(e).__name__)\n")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=root)
    assert "REJECTED CorpusError" in out.stdout, out.stdout + out.stderr


def test_advisory_rows_carry_exact_article_context_and_the_route_never_changes_statuses(tmp_path, monkeypatch):
    from application.litigation.reservation_cues import advisory_rows
    from tests.test_signed_conditions_pack import build
    refs, recs = _refs()
    rows = advisory_rows(refs, recs)
    assert rows[0]["cues"][0]["cue"] == "hormis" and "Hormis les cas où la loi" in rows[0]["cues"][0]["article_context"]
    c = build(tmp_path, monkeypatch, None, [])
    h = {"Authorization": "Bearer synthetic"}
    before = c.get("/v2/matters/c/briefs/v/legal-references", headers=h).json()
    cue = c.get("/v2/matters/c/briefs/v/reservation-cues", headers=h)
    assert cue.status_code == 200
    body = cue.json()
    assert body["schema"] == "caseproof-reservation-cues-v1" and body["advisory"] is True and "status" not in body
    assert body["snapshot_hash"] == before["snapshot_hash"]
    assert c.get("/v2/matters/c/briefs/v/legal-references", headers=h).json()["references"] == before["references"]
