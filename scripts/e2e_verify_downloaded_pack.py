"""Cold replay of a pack downloaded by the browser test (run with sockets denied, e.g. under unshare -rn).
usage: e2e_verify_downloaded_pack.py PACK.zip [expected_state]. FAKE-backed provenance: see e2e-conditions.mjs."""
import hashlib
import json
import sys
from zipfile import ZipFile

from application.litigation.offline_legal_pack import verify_legal_pack

raw = open(sys.argv[1], "rb").read()
checkpoint = hashlib.sha256(ZipFile(sys.argv[1]).read("review.json")).hexdigest()
body = verify_legal_pack(raw, expected_sha256=checkpoint)
sec = body.get("signed_conditions")
print(json.dumps({"replay": "ok", "checkpoint": checkpoint[:16], "section": None if sec is None else {
    "state": sec["state"], "revision": sec["revision"], "anchors": len(sec["anchors"]),
    "statuses": sorted({a["status"] for a in sec["anchors"]}), "inventory": [(r["piece"], r["read"]) for r in sec["inventory"]],
    "events": sec["events"]}, "sources": None if body.get("signed_sources") is None else [(e["piece"], e["state"], e["media_type"]) for e in body["signed_sources"]["entries"]]}))
if len(sys.argv) > 2:
    assert sec is not None and sec["state"] == sys.argv[2], sec and sec["state"]
