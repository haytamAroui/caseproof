"""Local workbench: decide and recheck through the loopback HTTP surface."""
from __future__ import annotations

import base64
import json
import re
import socket
import threading
import time
import urllib.error
import urllib.request

from scripts.serve_offline_legal_workbench import serve
from tests.test_offline_legal_review_decisions import _corpus, _word


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _post(base: str, path: str, token: str, body: bytes, ctype: str) -> dict:
    req = urllib.request.Request(base + path, data=body, method="POST", headers={
        "X-CaseProof-Local": token, "Content-Type": ctype, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def test_decide_then_recheck_over_http(tmp_path):
    corpus = _corpus(tmp_path)
    port = _free_port()
    threading.Thread(target=serve, args=(corpus, port), kwargs={"open_browser": False}, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            page = urllib.request.urlopen(base + "/", timeout=2).read().decode()
            break
        except OSError:
            time.sleep(0.1)
    token = re.search(r"const token='([0-9a-f]+)'", page).group(1)
    first = _post(base, "/check?version=installed&pack=", token,
                  _word(tmp_path, "Article synthétique de contrôle uniquement.", "a.docx").read_bytes(),
                  "application/octet-stream")
    assert first["decisions"] == [None] and first["revision"] == 0 and first["superseded"] == []
    decided = _post(base, "/decide", token, json.dumps({
        "archive_base64": first["archive_base64"], "checkpoint": first["checkpoint"],
        "decisions": [{"reference_index": 0, "action": "confirm", "reason": "", "reviewer_label": "Haytam"}]}).encode(),
        "application/json")
    assert decided["revision"] == 1 and decided["decisions"][0]["attribution"] == "local_unauthenticated_label"
    assert decided["checkpoint"] != first["checkpoint"]
    # A bad decision is refused without a side effect.
    try:
        _post(base, "/decide", token, json.dumps({
            "archive_base64": first["archive_base64"], "checkpoint": first["checkpoint"],
            "decisions": [{"reference_index": 0, "action": "reject", "reason": "", "reviewer_label": "H"}]}).encode(),
            "application/json")
        raise AssertionError("must refuse")
    except urllib.error.HTTPError as exc:
        assert exc.code == 422
    # Identical Word: decision carried. Changed quote: decision superseded.
    def recheck(name: str, quote: str) -> dict:
        word = _word(tmp_path, quote, name).read_bytes()
        return _post(base, "/recheck?pack=", token, json.dumps({
            "docx_base64": base64.b64encode(word).decode(), "archive_base64": decided["archive_base64"],
            "checkpoint": decided["checkpoint"]}).encode(), "application/json")
    same = recheck("b.docx", "Article synthétique de contrôle uniquement.")
    assert same["decisions"][0]["origin"] == "carried" and same["superseded"] == []
    changed = recheck("c.docx", "Article synthétique")
    assert changed["decisions"] == [None] and len(changed["superseded"]) == 1
    # Wrong token is refused.
    try:
        _post(base, "/decide", "0" * 48, b"{}", "application/json")
        raise AssertionError("must refuse")
    except urllib.error.HTTPError as exc:
        assert exc.code == 403
