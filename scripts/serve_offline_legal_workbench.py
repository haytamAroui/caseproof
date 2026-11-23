"""Bounded local offline legal-reference workbench, loopback only.

No signed accounts or dossier mutations. Starts on 127.0.0.1 with an explicit
local corpus and opens a browser. POST accepts only a DOCX byte body, never a
filesystem path. The source/parser gate is the same as the CLI.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import secrets
import tempfile
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from application.litigation.corpus import CorpusError
from application.litigation.legal_references import load_corpus_config
from application.litigation.offline_legal_pack import verify_legal_pack
from apps.api.offline_docx_check import check_offline_docx

HTML = """<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CaseProof | Contrôle juridique local</title><style>body{font:16px/1.6 system-ui;color:#193840;max-width:950px;margin:40px auto;padding:24px}h1{font-size:34px;line-height:1.15}button,input,select{font:inherit;padding:12px;margin:8px 0}button{background:#075c6b;color:white;border:0;border-radius:5px;cursor:pointer}.note{background:#f3efea;padding:20px}label{display:block;font-weight:600}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eef4f5;padding:20px}a{color:#075c6b}#result{margin-top:24px}small{display:block}code{overflow-wrap:anywhere}</style>
<p>CaseProof · contrôle juridique local · sans compte distant</p><h1>Votre Word. Le corpus choisi. Un contrôle hors ligne.</h1>
<p class="note">Périmètre : références explicites et intégrité des citations. Pas d'analyse de l'applicabilité, pas de conclusion juridique, pas de contrôle des pièces dans cet écran. Les contenus Word non pris en charge sont refusés. Les résultats locaux ne sont pas des décisions d'avocat authentifiées.</p>
<p>Pack sélectionné : <code>PACK</code></p><p>SOURCES</p>
<form id="form"><label for="docx">Conclusions Word (.docx)</label><input id="docx" type="file" accept=".docx" required>
<label for="version">Version demandée</label><select id="version"><option value="installed">Version déclarée du pack</option><option value="missing">Version historique volontairement absente (test)</option></select>
<small>Ce choix de test n'affirme pas qu'une version manque chez l'éditeur.</small><button id="check">Vérifier maintenant, en local</button></form>
<p id="status" role="status"></p><div id="result"></div>
<script>const token='TOKEN';document.getElementById('form').onsubmit=async(e)=>{e.preventDefault();const button=document.getElementById('check'),status=document.getElementById('status'),result=document.getElementById('result');button.disabled=true;result.replaceChildren();status.textContent='Lecture du Word et contrôle du corpus local…';try{const file=document.getElementById('docx').files[0];if(!file||file.size>8388608)throw Error('DOCX requis, maximum 8 Mo.');const response=await fetch('/check?version='+document.getElementById('version').value,{method:'POST',headers:{'X-CaseProof-Local':token,'Content-Type':'application/octet-stream','Accept':'application/json'},body:await file.arrayBuffer()});if(!response.ok)throw Error(await response.text());const payload=await response.json(),checkpoint=payload.checkpoint;for(const finding of payload.references){const section=document.createElement('section'),heading=document.createElement('h2'),reason=document.createElement('p'),brief=document.createElement('pre'),article=document.createElement('pre');heading.textContent=finding.status+' · '+finding.raw_text;reason.textContent=finding.reason;brief.textContent=finding.quote||'Aucune citation liée';article.textContent=finding.article_text||'Version ou article non sélectionné : aucun passage de substitution.';section.append(heading,reason,brief,article);result.append(section);}const bytes=Uint8Array.from(atob(payload.archive_base64),c=>c.charCodeAt(0)),blob=new Blob([bytes],{type:'application/zip'}),url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='caseproof-offline-legal-review.zip';a.textContent='Télécharger la revue et ses passages figés';result.append(a);const p=document.createElement('p');p.textContent='Empreinte de revue à conserver séparément : '+checkpoint;result.append(p);const note=document.createElement('p');note.textContent='Décompressez le ZIP puis ouvrez report.html. Les passages sont conservés dans le pack exporté, sans accès Internet.';result.append(note);status.textContent='Contrôle exécuté depuis les octets Word et le corpus local. '+payload.summary+'. Export prêt.';}catch(error){status.textContent='Contrôle impossible : '+error.message;}finally{button.disabled=false;}};</script></html>"""


def serve(corpus: Path, port: int, *, open_browser: bool = True) -> None:
    config = load_corpus_config(corpus)
    if config.failures or not config.records:
        raise CorpusError("complete chosen corpus required")
    token = secrets.token_hex(24)
    sources = " · ".join(sorted({r.source_artifact_kind for r in config.records}))
    local_origin = f"http://127.0.0.1:{port}"
    page = HTML.replace("PACK", config.pack_sha256).replace("SOURCES", html.escape(sources)).replace("TOKEN", token).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != "/":
                self.send_error(404)
                return
            if self.headers.get("Host") != local_origin.removeprefix("http://"):
                self.send_error(403)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(page)

        def do_POST(self) -> None:
            parsed = urlsplit(self.path)
            origin = self.headers.get("Origin")
            if (self.headers.get("Host") != local_origin.removeprefix("http://")
                    or parsed.path != "/check" or self.headers.get("X-CaseProof-Local") != token
                    or origin not in (None, local_origin)):
                self.send_error(403)
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 8 * 1024 * 1024:
                    raise CorpusError("DOCX byte limit")
                if load_corpus_config(corpus).pack_sha256 != config.pack_sha256:
                    raise CorpusError("chosen corpus changed; restart with the intended immutable pack")
                raw = self.rfile.read(size)
                if len(raw) != size:
                    raise CorpusError("truncated DOCX")
                choice = parse_qs(parsed.query).get("version", [""])
                if choice not in (["installed"], ["missing"]):
                    raise CorpusError("explicit version choice required")
                versions = ({r.act: "requested-historical-version-not-in-this-pack" for r in config.records}
                            if choice == ["missing"] else None)
                with tempfile.TemporaryDirectory(prefix="caseproof-offline-") as temp:
                    source = Path(temp) / "brief.docx"
                    source.write_bytes(raw)
                    data, checkpoint = check_offline_docx(docx=source, corpus=corpus, chosen_versions=versions)
            except Exception as exc:
                message = str(exc) if isinstance(exc, (CorpusError, ValueError)) else "Word input refused"
                self.send_response(422)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(message.encode())
                return
            body = verify_legal_pack(data, expected_sha256=checkpoint)
            counts = {status: sum(r["status"] == status for r in body["references"])
                      for status in ("PASS", "FAIL", "UNDETERMINED", "UNVERIFIED")}
            summary = "; ".join(f"{status}: {count}" for status, count in counts.items() if count)
            if self.headers.get("Accept") == "application/json":
                by_key = {row["key"]: body["articles"][row["index"]]["derived_text"]
                          for row in body["article_index"]}
                payload = {"checkpoint": checkpoint, "summary": summary,
                           "archive_base64": base64.b64encode(data).decode(),
                           "references": [{**row, "article_text": by_key.get(row["corpus_key"])}
                                          for row in body["references"]]}
                encoded = json.dumps(payload, ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(encoded)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("X-CaseProof-Legal-Summary", summary)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-CaseProof-Legal-Review-SHA256", checkpoint)
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: object) -> None:
            return  # No Word text, file names or local credentials in logs.

    server = HTTPServer(("127.0.0.1", port), Handler)
    local_origin = f"http://127.0.0.1:{server.server_port}"
    url = local_origin + "/"
    print(json.dumps({"local_url": url, "corpus_pack_sha256": config.pack_sha256}), flush=True)
    if open_browser:
        webbrowser.open(url)
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    serve(args.corpus, args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
