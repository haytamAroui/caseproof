"""Retained original source bytes in the signed offline pack. FAKE-backed: auth, storage, DB, conditions store and
the original reader are stand-ins; section build, validation, recomputation and cold replay are real code."""
from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
from types import SimpleNamespace as NS
from zipfile import ZipFile

import pytest

from application.litigation import signed_sources_pack as ssp
from application.litigation.corpus import CorpusError
from application.litigation.offline_legal_pack import verify_legal_pack
from application.litigation.signed_conditions import load_stored
from tests.test_signed_conditions_pack import COND, V, build, pack

TEXT = "Le courrier est bien reçu le 3 mars."
PDF = b"%PDF-1.4 synthetic bytes, not a real exhibit"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def rows():
    def row(sid, media, data, status="ready", warnings=(), rep="r"):
        return NS(source_id=sid, version_id=V, original_sha256=sha(data), status=status, warnings=warnings,
                  representation_id=rep, media_type=media)
    return [NS(row=row("s1", "text/plain", TEXT.encode()), text=TEXT, spans=((0, len(TEXT), "identity_utf8", None),)),
            NS(row=row("s2", "application/pdf", PDF, "partial", ("parser_lineage_not_integrated",), None), text="", spans=())]


def reader(overrides=None):
    blobs = {"s1": (TEXT.encode(), "text/plain"), "s2": (PDF, "application/pdf"), **(overrides or {})}

    def read(source_id, version_id):
        b, m = blobs[source_id]
        return NS(data=b, sha256_hex=sha(b), media_type=m)
    return read


def export(tmp_path, monkeypatch, overrides=None, cond=None):
    c = build(tmp_path, monkeypatch, [cond or COND], rows(), originals=reader(overrides))
    raw, cp = pack(c)
    return raw, cp, verify_legal_pack(raw, expected_sha256=cp)


def test_retained_bytes_replay_and_conditions_are_recomputed_from_them(tmp_path, monkeypatch):
    raw, _cp, body = export(tmp_path, monkeypatch)
    sec = body["signed_sources"]
    by = {e["piece"]: e for e in sec["entries"]}
    assert by["Pièce 1"]["state"] == "retained" and ssp.decode_entry(by["Pièce 1"]) == TEXT.encode()
    assert by["Pièce 2"]["state"] == "retained" and ssp.decode_entry(by["Pièce 2"]) == PDF
    assert body["signed_conditions"]["anchors"][0]["found"]
    html_ = ZipFile(io.BytesIO(raw)).read("report.html").decode()
    assert "Sources d'origine conservées" in html_ and "recalculés au rejeu" in html_ and "pas la pièce d'origine" not in html_


def test_forged_bytes_with_consistent_hashes_do_not_replay(tmp_path, monkeypatch):
    _raw, _cp, body = export(tmp_path, monkeypatch)
    forged = copy.deepcopy(body)
    new = b"Rien ici."
    for e in forged["signed_sources"]["entries"]:
        if e["piece"] == "Pièce 1":
            e.update(data_base64=base64.b64encode(new).decode(), byte_length=len(new), original_sha256=sha(new))
    for r in forged["signed_conditions"]["inventory"]:
        if r["piece"] == "Pièce 1":
            r["original_sha256"] = sha(new)
    for a in forged["signed_conditions"]["anchors"]:
        for f in a["found"]:
            f["original_sha256"] = sha(new)
    sc = forged["signed_conditions"]
    ssp.validate_section(forged["signed_sources"], sc)  # hashes are consistent, so the shape check passes
    with pytest.raises(CorpusError):
        ssp.replay_conditions(forged["brief_text"], forged["signed_sources"], sc, load_stored(sc["spec_text"], sc["spec_sha256"]))
    sc0 = body["signed_conditions"]  # untouched control
    assert ssp.replay_conditions(body["brief_text"], body["signed_sources"], sc0, load_stored(sc0["spec_text"], sc0["spec_sha256"])) == "recomputed"


@pytest.mark.parametrize("mutate", [
    lambda s: s["entries"][0].update(data_base64=base64.b64encode(b"other").decode()),
    lambda s: s["entries"][0].update(byte_length=1),
    lambda s: s["entries"][0].update(state="omitted", reason="read_failed"),
    lambda s: s["entries"][0].update(state="omitted", reason="because"),
    lambda s: s["entries"].append(copy.deepcopy(s["entries"][0])),
    lambda s: s["entries"].pop(),
    lambda s: s["entries"].reverse(),
    lambda s: s["entries"][0].update(media_type="application/zip"),
])
def test_forged_or_inconsistent_source_sections_are_refused(tmp_path, monkeypatch, mutate):
    _raw, _cp, body = export(tmp_path, monkeypatch)
    forged = copy.deepcopy(body["signed_sources"])
    mutate(forged)
    with pytest.raises(CorpusError):
        ssp.validate_section(forged, body["signed_conditions"])
    ssp.validate_section(body["signed_sources"], body["signed_conditions"])  # control


def test_unretrievable_and_unserved_sources_are_explicit_omissions(tmp_path, monkeypatch):
    def failing(sid, vid):
        raise RuntimeError("storage down")
    c = build(tmp_path, monkeypatch, [COND], rows(), originals=lambda sid, vid: failing(sid, vid) if sid == "s2" else reader()(sid, vid))
    raw, cp = pack(c)
    sec = verify_legal_pack(raw, expected_sha256=cp)["signed_sources"]
    by = {e["piece"]: e for e in sec["entries"]}
    assert by["Pièce 2"]["state"] == "omitted" and by["Pièce 2"]["reason"] == "read_failed" and by["Pièce 2"]["data_base64"] is None
    assert by["Pièce 1"]["state"] == "retained"
    assert "omise (read_failed)" in ZipFile(io.BytesIO(raw)).read("report.html").decode()


def test_text_that_differs_from_the_stored_representation_is_omitted_not_certified(tmp_path, monkeypatch):
    _raw, _cp, body = export(tmp_path, monkeypatch, {"s1": (b"Autre texte.", "text/plain")})
    # the reader's own digest check fails first (hash differs from the preview row): explicit omission, never retained
    e = next(e for e in body["signed_sources"]["entries"] if e["piece"] == "Pièce 1")
    assert e["state"] == "omitted" and e["reason"] == "read_failed"


def test_budget_overflow_is_an_explicit_omission(tmp_path, monkeypatch):
    monkeypatch.setattr(ssp, "MAX_TOTAL_BYTES", len(TEXT.encode()) + 5)
    _raw, _cp, body = export(tmp_path, monkeypatch)
    by = {e["piece"]: e for e in body["signed_sources"]["entries"]}
    assert by["Pièce 1"]["state"] == "retained" and by["Pièce 2"]["reason"] == "over_pack_budget"


def test_older_verifier_cannot_certify_a_pack_with_retained_sources(tmp_path, monkeypatch):
    import subprocess
    import sys
    from pathlib import Path
    raw, cp, _ = export(tmp_path, monkeypatch)
    root = Path(__file__).resolve().parents[1]
    old = subprocess.run(["git", "show", "2cf0d94d:application/litigation/offline_legal_pack.py"], cwd=root,
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
    assert json.loads(ZipFile(io.BytesIO(raw)).read("review.json"))["signed_sources"]
