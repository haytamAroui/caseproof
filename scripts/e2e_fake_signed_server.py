# ruff: noqa: E402,E701,E702,E731
"""FAKE-BACKED browser harness server (test only, loopback). NOT real identity or persistence.
Real: route, matching, corpus and contract code, and the built React app. FAKE: bearer auth, storage, Postgres,
review ledger, intake record, conditions store and the two source previews (s1 readable, s2 partial).
Run: see frontend/tests/e2e-conditions.mjs."""
import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace

import uvicorn

from application.litigation.legal_references import check_legal_references, load_corpus_config
from apps.api.litigation_development_app import create_litigation_development_app
from apps.api.offline_docx_check import parse_docx

docx, corpus, port = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
config = load_corpus_config(corpus)
text = parse_docx(docx.read_bytes())["text"]
legal = check_legal_references(text, config.records, config.act_aliases, chosen_versions=config.chosen_versions, strict=True, v3=True)
run = SimpleNamespace(snapshot_hash="a"*64, representation_sha256=hashlib.sha256(text.encode()).hexdigest(), corpus_pack_sha256=config.pack_sha256, legal_observations=tuple(legal), suitability_observations=())
checker = SimpleNamespace(check=lambda **_: run, legal_corpus_for=lambda _c: config, _verified=lambda _b: None, _scope=lambda _s,_c: SimpleNamespace(case_id="c"))
wb = SimpleNamespace(checker=checker, workspace=None, store=SimpleNamespace(load_bundle=lambda **_: SimpleNamespace(representation=SimpleNamespace(text=text)), still_current=lambda **_: True))
checker.store=wb.store
wb.workspace=SimpleNamespace(state=lambda **_: {'snapshot_hash':'a'*64,'decisions':[]})
from apps.api import litigation_evidence_search as les

les.AuthorizedEvidenceSearch._require_evidence=staticmethod(lambda _a: None)
run.corpus_pack_sha256=config.pack_sha256
app = create_litigation_development_app(signed_workbench_factory=lambda b: wb, workspace_directory=Path("frontend/dist"))
# LABELLED FAKE: in-memory review ledger (real route code and real blocker builder, no signed identity/DB).
from fastapi import HTTPException

from application.litigation.review_blockers import review_blockers
from apps.api.litigation_review_app import create_clearbrief_review_router

run.citation_observations=(); run.factual_observations=(); run.event_observations=(); run.passage_flags=(); run.incomplete=(); run.excluded=()
class FakeLedgerService:
    def __init__(self): self.rows=[]
    def state(self, *, bearer, case_id, brief_version_id):
        decs=tuple(SimpleNamespace(observation_id=o,disposition=SimpleNamespace(value=d),rationale=r) for o,d,r in self.rows)
        return {"schema":"caseproof-clearbrief-review-v1","case_id":case_id,"brief_version_id":brief_version_id,"snapshot_hash":run.snapshot_hash,"revision":len(self.rows),
                "decisions":[{"observation_id":o,"actor_id":"fake-actor","disposition":d,"rationale":r} for o,d,r in self.rows],
                "blocker_inventory":review_blockers(run,decs),"release_authorized":False}
    def record(self, *, bearer, case_id, brief_version_id, command):
        if command.snapshot_hash!=run.snapshot_hash or command.expected_revision!=len(self.rows): raise HTTPException(409,"stale")
        self.rows.append((command.observation_id,command.disposition.value,command.rationale))
        return {"schema":"caseproof-clearbrief-review-receipt-v1","snapshot_hash":run.snapshot_hash,"revision":len(self.rows),"replayed":False,"release_authorized":False}
from fastapi import FastAPI

outer = FastAPI()
from fastapi.responses import JSONResponse

from apps.api.access_control import AccessRejected


@outer.exception_handler(AccessRejected)
async def _d(request, exc): return JSONResponse({"error": exc.code.value}, status_code=exc.http_status)
outer.include_router(create_clearbrief_review_router(FakeLedgerService()))
# LABELLED FAKE: intake record (confirmed inventory) is synthetic; route and mapping code are real.
from apps.api.signed_workbench_routes import create_signed_workbench_router

H1="33333333-3333-4333-8333-333333333333"; H2="44444444-4444-4444-8444-444444444444"
INTAKE={"entries":[{"label":"piece","number":"1","source_version_id":H1,"pages":[{"space":"printed","label":"iv","pdf_page":2,"rationale":"fixture"}]},
  {"label":"piece","number":"2","source_version_id":None,"pages":[]},{"label":"piece","number":"5","source_version_id":H2,"pages":[]}],
 "sources":[{"version_id":H1,"filename":"piece-1.pdf","sha256":"c"*64,"readback":"verified","page_count":4},{"version_id":H2,"filename":"piece-5.pdf","sha256":"d"*64,"readback":"verified","page_count":2}],
 "confirmation_id":"fixture-confirmation-1","brief_id":"22222222-2222-4222-8222-222222222222","inventory_complete":True}
# LABELLED FAKE: in-memory conditions store (CAS + hash check) and synthetic readable source previews.
import hashlib as _h

from apps.api.signed_workbench_routes import ConflictError


class FakeCondStore:
    def __init__(self): self.rows=[]
    def read(self,b,c):
        if not self.rows: return None
        t,s=self.rows[-1]; return {"revision":len(self.rows),"spec_text":t,"spec_sha256":s}
    def append(self,b,c,e,t,s):
        assert _h.sha256(t.encode()).hexdigest()==s
        if e!=len(self.rows): raise ConflictError
        self.rows.append((t,s)); return len(self.rows)
_row=lambda sid,**k: SimpleNamespace(source_id=sid,version_id=H1,original_sha256="c"*64,status=k.get("status","ready"),warnings=k.get("warnings",()),representation_id="r")
_prev=[SimpleNamespace(row=_row("s1"),text="Accuse de reception. Le paiement a bien ete recu par la banque le 3 mars. Fin.",spans=((0,90,"para",1),)),
       SimpleNamespace(row=_row("s2",status="partial",warnings=("scan",)),text="x",spans=())]
_orig=wb.store.load_bundle
def _lb(**k):
    b=_orig(**k)
    return SimpleNamespace(representation=SimpleNamespace(text=b.representation.text,brief=SimpleNamespace(case_id=k["case_id"],version_id=k["brief_version_id"],references=())),
        register=SimpleNamespace(entries=[SimpleNamespace(confirmed=True,display_label="Pièce 1",pages=[SimpleNamespace(source_id="s1")]),SimpleNamespace(confirmed=True,display_label="Pièce 2",pages=[SimpleNamespace(source_id="s2")])]),
        previews=tuple(_prev),source_scope=SimpleNamespace(declared_source_versions=(("s1",H1),("s2",H1)),excluded_source_versions=()))
wb.store.load_bundle=_lb
outer.include_router(create_signed_workbench_router(lambda b: wb, lambda b,c: INTAKE, FakeCondStore()))
outer.mount("/", app)
app = outer
uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
