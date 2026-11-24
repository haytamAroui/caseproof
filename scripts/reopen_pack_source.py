"""Reopen the original source bytes retained in a signed offline pack, offline (run with sockets denied).
usage: reopen_pack_source.py PACK.zip OUTDIR
Replays the whole pack first (any failure stops here), then writes each retained source with its digest-checked bytes
and renders PDF pages with pdftoppm when available. Omitted sources are listed with their reason, never invented.
The bytes are what the signed service returned and digested at export; this does not prove they are the lawyer's real exhibit."""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

from application.litigation.offline_legal_pack import verify_legal_pack
from application.litigation.signed_sources_pack import decode_entry

pack, out = sys.argv[1], Path(sys.argv[2])
raw = Path(pack).read_bytes()
body = verify_legal_pack(raw, expected_sha256=hashlib.sha256(ZipFile(pack).read("review.json")).hexdigest())
section = body.get("signed_sources")
if section is None:
    sys.exit("no retained sources in this pack")
out.mkdir(parents=True, exist_ok=True)
report = []
for e in section["entries"]:
    item = {"piece": e["piece"], "state": e["state"], "media_type": e["media_type"], "sha256": e["original_sha256"]}
    if e["state"] == "retained":
        data = decode_entry(e)
        stem = re.sub(r"[^A-Za-z0-9]+", "-", e["piece"]).strip("-") + "-" + e["original_sha256"][:8]
        path = out / (stem + (".pdf" if e["media_type"] == "application/pdf" else ".txt"))
        path.write_bytes(data)
        item["file"] = str(path)
        if e["media_type"] == "application/pdf":
            r = subprocess.run(["pdftoppm", "-png", "-r", "60", str(path), str(out / stem)], capture_output=True)
            item["pages_rendered"] = sorted(p.name for p in out.glob(stem + "-*.png")) if r.returncode == 0 else "pdftoppm unavailable"
    else:
        item["reason"] = e["reason"]
    report.append(item)
print(json.dumps(report, ensure_ascii=False, indent=1))
