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
from application.litigation.legal_review_decisions import fingerprints
from application.litigation.local_corpus_library import LocalCorpusLibrary, encode_corpus_pack
from application.litigation.offline_legal_pack import _SCOPE, verify_legal_pack
from apps.api.offline_docx_check import check_offline_docx
from apps.api.offline_review import recheck, record_decisions

HTML = """<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CaseProof | Contrôle juridique local</title><style>body{overflow-wrap:anywhere;font:16px/1.6 system-ui;color:#193840;max-width:950px;margin:40px auto;padding:24px}h1{font-size:34px;line-height:1.15}button,input,select{font:inherit;padding:12px;margin:8px 0;max-width:100%;box-sizing:border-box}select{width:100%}button{background:#075c6b;color:white;border:0;border-radius:5px;cursor:pointer}.note{background:#f3efea;padding:20px}label{display:block;font-weight:600}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eef4f5;padding:20px}a{color:#075c6b}#result{margin-top:24px}small{display:block}code{overflow-wrap:anywhere}</style>
<p>CaseProof · contrôle juridique local · sans compte distant</p><h1>Votre Word. Le corpus choisi. Un contrôle hors ligne.</h1>
<p class="note">Périmètre : références explicites et intégrité des citations. Pas d'analyse de l'applicabilité, pas de conclusion juridique, pas de contrôle des pièces dans cet écran. Les contenus Word non pris en charge sont refusés. Les résultats locaux ne sont pas des décisions d'avocat authentifiées. PASS signifie seulement : extrait littéral présent dans le texte conservé. Contexte, réserves, portée et applicabilité restent à l'avocat. Une citation ou un alinéa non contrôlé apparaît comme non vérifié, jamais comme réussi.</p>
<p>Pack de départ : <code>PACK</code></p><p>SOURCES</p>
LIBRARY
<form id="form"><label for="docx">Conclusions Word (.docx)</label><input id="docx" type="file" accept=".docx" required>
<label for="version">Version demandée</label><select id="version"><option value="installed">Version déclarée du pack</option><option value="missing">Version historique volontairement absente (test)</option></select>
<small>Ce choix de test n'affirme pas qu'une version manque chez l'éditeur.</small><button id="check">Vérifier maintenant, en local</button></form>
<p id="status" role="status"></p><div id="result"></div>
<script>const token='TOKEN';
const H={'X-CaseProof-Local':token,'Accept':'application/json'};
let current=null;
const el=(t,txt,cls)=>{const e=document.createElement(t);if(txt!==undefined)e.textContent=txt;if(cls)e.className=cls;return e;};
const b64=async(file)=>{const buf=new Uint8Array(await file.arrayBuffer());let s='';for(let i=0;i<buf.length;i+=32768)s+=String.fromCharCode.apply(null,buf.subarray(i,i+32768));return btoa(s);};
const LABELS={confirm:'Confirmer',qualify:'Confirmer avec réserve',reject:'Rejeter',waive:'Écarter'};
async function post(path,body,type){const r=await fetch(path,{method:'POST',headers:{...H,'Content-Type':type},body});if(!r.ok)throw Error(await r.text());return r.json();}
function render(payload){current=payload;const result=document.getElementById('result');result.replaceChildren();
result.append(el('p','Corpus de cette revue : '+payload.corpus_pack_sha256));
result.append(el('p','Révision locale n° '+payload.revision+'. Les décisions ci-dessous portent une étiquette locale non authentifiée, ce ne sont pas des décisions d\u2019avocat et elles n\u2019autorisent aucun dépôt.'));
payload.references.forEach((finding,index)=>{const section=el('section'),brief=el('pre',finding.quote||'Aucune citation liée'),article=el('pre',finding.article_text||'Version ou article non sélectionné : aucun passage de substitution.');
section.append(el('h2',finding.status+' · '+finding.raw_text),el('p',finding.scope),brief,article);
const d=payload.decisions[index];
if(d){section.append(el('p','Décision locale : '+LABELS[d.action]+(d.reason?' · '+d.reason:'')+' · étiquette « '+d.reviewer_label+' » (non authentifiée) · '+(d.origin==='carried'?'reprise d\u2019une revue antérieure, finding identique':'enregistrée dans cette révision'),'note'));}
else{const f=el('form');f.dataset.index=index;const sel=el('select');sel.setAttribute('aria-label','Décision');for(const k of Object.keys(LABELS)){const o=el('option',LABELS[k]);o.value=k;sel.append(o);}
const reason=el('input');reason.placeholder='Motif (obligatoire sauf pour Confirmer)';reason.setAttribute('aria-label','Motif');
const label=el('input');label.placeholder='Votre étiquette locale (ex. Haytam)';label.setAttribute('aria-label','Étiquette locale');label.required=true;label.maxLength=80;
const btn=el('button','Enregistrer cette décision');btn.type='submit';f.append(sel,reason,label,btn);
f.onsubmit=async(e)=>{e.preventDefault();const status=document.getElementById('status');btn.disabled=true;try{const out=await post('/decide',JSON.stringify({archive_base64:current.archive_base64,checkpoint:current.checkpoint,decisions:[{reference_index:index,action:sel.value,reason:reason.value,reviewer_label:label.value}]}),'application/json');render(out);status.textContent='Décision enregistrée dans une nouvelle revue figée. L\u2019ancienne revue n\u2019est pas modifiée.';}catch(err){status.textContent='Décision refusée : '+err.message;btn.disabled=false;}};
section.append(f);}
result.append(section);});
if(payload.superseded.length){const box=el('section');box.append(el('h2','Décisions remplacées'),el('p','Ces décisions répondaient à un finding qui a changé. Elles restent visibles mais ne répondent à aucun finding de cette revue.'));for(const d of payload.superseded)box.append(el('p',LABELS[d.action]+(d.reason?' · '+d.reason:'')+' · étiquette « '+d.reviewer_label+' » (non authentifiée) · empreinte '+d.fingerprint.slice(0,12),'note'));result.append(box);}
const bytes=Uint8Array.from(atob(payload.archive_base64),c=>c.charCodeAt(0)),blob=new Blob([bytes],{type:'application/zip'}),url=URL.createObjectURL(blob);
const a=el('a','Télécharger la revue et ses passages figés');a.href=url;a.download='caseproof-offline-legal-review-r'+payload.revision+'.zip';result.append(a);
result.append(el('p','Empreinte de revue à conserver séparément : '+payload.checkpoint));
result.append(el('p','Décompressez le ZIP puis ouvrez report.html. Les passages sont conservés dans le pack exporté, sans accès Internet.'));
const rf=el('form');rf.id='recheckform';rf.append(el('h2','Revérifier un Word corrigé'),el('p','Une décision n\u2019est reprise que pour un finding strictement identique. Sinon elle reste visible comme remplacée et le nouveau finding attend une nouvelle décision.'));
const rin=el('input');rin.type='file';rin.accept='.docx';rin.id='recheckdocx';rin.required=true;const rb=el('button','Revérifier en local');rb.type='submit';rf.append(rin,rb);
rf.onsubmit=async(e)=>{e.preventDefault();const status=document.getElementById('status');rb.disabled=true;try{const file=rin.files[0];if(!file||file.size>8388608)throw Error('DOCX requis, maximum 8 Mo.');const out=await post('/recheck?pack='+(document.getElementById('pack')?.value||''),JSON.stringify({docx_base64:await b64(file),archive_base64:current.archive_base64,checkpoint:current.checkpoint}),'application/json');render(out);status.textContent='Revérification exécutée. '+out.summary+'.';}catch(err){status.textContent='Revérification impossible : '+err.message;rb.disabled=false;}};
result.append(rf);}
document.getElementById('form').onsubmit=async(e)=>{e.preventDefault();const button=document.getElementById('check'),status=document.getElementById('status'),result=document.getElementById('result');button.disabled=true;result.replaceChildren();status.textContent='Lecture du Word et contrôle du corpus local…';try{const file=document.getElementById('docx').files[0];if(!file||file.size>8388608)throw Error('DOCX requis, maximum 8 Mo.');const payload=await post('/check?version='+document.getElementById('version').value+'&pack='+(document.getElementById('pack')?.value||''),await file.arrayBuffer(),'application/octet-stream');render(payload);status.textContent='Contrôle exécuté depuis les octets Word et le corpus local. '+payload.summary+'. Export prêt.';}catch(error){status.textContent='Contrôle impossible : '+error.message;}finally{button.disabled=false;}};</script></html>"""


def _payload(data: bytes, checkpoint: str) -> dict[str, object]:
    body = verify_legal_pack(data, expected_sha256=checkpoint)
    counts = {status: sum(r["status"] == status for r in body["references"])
              for status in ("PASS", "FAIL", "UNDETERMINED", "UNVERIFIED")}
    summary = "; ".join(f"{status}: {count}" for status, count in counts.items() if count)
    by_key = {row["key"]: body["articles"][row["index"]]["derived_text"] for row in body["article_index"]}
    review = body["review"]
    by_print = {d["fingerprint"]: d for d in review.get("decisions", [])}
    prints = fingerprints(body["references"], body["articles"], body["article_index"], body["corpus_pack_sha256"])
    return {"checkpoint": checkpoint, "summary": summary, "revision": review.get("revision", 1),
            "corpus_pack_sha256": body["corpus_pack_sha256"],
            "archive_base64": base64.b64encode(data).decode(),
            "decisions": [by_print.get(fp) for fp in prints],
            "superseded": list(review.get("superseded", [])),
            "references": [{**row, "article_text": by_key.get(row["corpus_key"]),
                            "scope": _SCOPE.get(row["reason"], row["reason"])} for row in body["references"]]}


def serve(corpus: Path, port: int, *, open_browser: bool = True, library: Path | None = None) -> None:
    config = load_corpus_config(corpus)
    if config.failures or not config.records:
        raise CorpusError("complete chosen corpus required")
    store = LocalCorpusLibrary(library) if library is not None else None
    if store is not None:
        store.install(encode_corpus_pack(config))
    token = secrets.token_hex(24)
    sources = " · ".join(sorted({r.source_artifact_kind for r in config.records}))
    local_origin = f"http://127.0.0.1:{port}"
    def render_page() -> bytes:
        panel = ""
        if store is not None:
            options = "".join('<option value="' + str(row["digest"]) + ('" selected>' if row["digest"] == config.pack_sha256 else '">') + html.escape(
                str(row["versions"]) + " · " + str(row["languages"]) + " · sélection " + str(row["requested_versions"]) + " · " + str(row["digest"])) + '</option>'
                for row in store.inventory())
            panel = '<label for="pack">Corpus de cette nouvelle vérification</label><select id="pack">' + options + '</select><p id="packdetails"></p>'
            panel += '<p>Importer ajoute un pack. Les revues déjà exportées gardent leurs textes et leur identité.</p><input id="newpack" type="file" accept=".zip"><button type="button" id="importpack">Importer un pack local</button><p id="importstatus" role="status"></p>'
            panel += """<script>window.addEventListener('DOMContentLoaded',()=>{const select=document.getElementById('pack'),details=document.getElementById('packdetails');const show=()=>{details.textContent=select.options[select.selectedIndex].textContent;};select.onchange=show;show();document.getElementById('importpack').onclick=async()=>{const status=document.getElementById('importstatus');try{const f=document.getElementById('newpack').files[0];if(!f||f.size>41943040)throw Error('ZIP de corpus requis, maximum 40 Mo.');const r=await fetch('/packs',{method:'POST',headers:{'X-CaseProof-Local':'TOKEN','Content-Type':'application/zip'},body:await f.arrayBuffer()});if(!r.ok)throw Error(await r.text());const p=await r.json();status.textContent='Pack ajouté : '+p.digest+'. Rechargez la page pour le sélectionner.';}catch(e){status.textContent='Import refusé : '+e.message;}};});</script>"""
        return HTML.replace("LIBRARY", panel).replace("PACK", config.pack_sha256).replace("SOURCES", html.escape(sources)).replace("TOKEN", token).encode()

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
            self.wfile.write(render_page())

        def do_POST(self) -> None:
            parsed = urlsplit(self.path)
            origin = self.headers.get("Origin")
            if (self.headers.get("Host") != local_origin.removeprefix("http://")
                    or parsed.path not in ("/check", "/packs", "/decide", "/recheck") or self.headers.get("X-CaseProof-Local") != token
                    or origin not in (None, local_origin)):
                self.send_error(403)
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                limit = 40 * 1024 * 1024 if parsed.path == "/packs" else 24 * 1024 * 1024 if parsed.path in ("/decide", "/recheck") else 8 * 1024 * 1024
                if not 0 < size <= limit:
                    raise CorpusError("local input byte limit")
                raw = self.rfile.read(size)
                if len(raw) != size:
                    raise CorpusError("truncated DOCX")
                if parsed.path == "/packs":
                    if store is None:
                        raise CorpusError("local corpus library not enabled")
                    digest = store.install(raw)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"digest": digest}).encode())
                    return
                if parsed.path == "/decide":
                    req = json.loads(raw)
                    data, checkpoint = record_decisions(pack=base64.b64decode(req["archive_base64"], validate=True),
                                                        checkpoint=str(req["checkpoint"]), decisions=list(req["decisions"]))
                    out = json.dumps(_payload(data, checkpoint), ensure_ascii=False).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(out)
                    return
                selected = config
                if store is not None:
                    pack = parse_qs(parsed.query).get("pack", [""])
                    if len(pack) != 1:
                        raise CorpusError("one explicit corpus required")
                    selected = store.select(pack[0])
                elif load_corpus_config(corpus).pack_sha256 != config.pack_sha256:
                    raise CorpusError("chosen corpus changed; restart with the intended immutable pack")
                if parsed.path == "/recheck":
                    req = json.loads(raw)
                    with tempfile.TemporaryDirectory(prefix="caseproof-offline-") as temp:
                        source = Path(temp) / "brief.docx"
                        source.write_bytes(base64.b64decode(req["docx_base64"], validate=True))
                        data, checkpoint = recheck(docx=source, corpus=selected,
                                                   prior_pack=base64.b64decode(req["archive_base64"], validate=True),
                                                   prior_checkpoint=str(req["checkpoint"]))
                    out = json.dumps(_payload(data, checkpoint), ensure_ascii=False).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(out)
                    return
                choice = parse_qs(parsed.query).get("version", [""])
                if choice not in (["installed"], ["missing"]):
                    raise CorpusError("explicit version choice required")
                versions = ({r.act: "requested-historical-version-not-in-this-pack" for r in selected.records}
                            if choice == ["missing"] else None)
                with tempfile.TemporaryDirectory(prefix="caseproof-offline-") as temp:
                    source = Path(temp) / "brief.docx"
                    source.write_bytes(raw)
                    data, checkpoint = check_offline_docx(docx=source, corpus=selected, chosen_versions=versions)
            except Exception as exc:
                message = str(exc) if isinstance(exc, (CorpusError, ValueError)) else "Word input refused"
                self.send_response(422)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(message.encode())
                return
            if self.headers.get("Accept") == "application/json":
                encoded = json.dumps(_payload(data, checkpoint), ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(encoded)
                return
            summary = str(_payload(data, checkpoint)["summary"])
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
    parser.add_argument("--library", type=Path, help="Append-only local corpus pack directory")
    args = parser.parse_args()
    serve(args.corpus, args.port, open_browser=not args.no_browser, library=args.library)


if __name__ == "__main__":
    main()
