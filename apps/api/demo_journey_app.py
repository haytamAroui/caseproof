"""Loopback-only interactive demo of the CaseProof lawyer journey; never mounted by main.py.

Serves a small static page and a JSON API that execute the REAL merged engine
in-process (M2 unified brief check, review cycle, correction + recheck,
task-4 corpus, task-5 rules, task-3 decisions, task-6 Word measurement and
the bounded DOCX text-region reader) over a local demo dossier. Uploaded
DOCX files are actually read by the product reader: a clean document is
read, a document with unresolved revisions is refused (fail-closed), and
the UI shows the measured result. The dossier's references/facts are
labelled simulated extraction and are validated against the text actually
read; the reviewer is simulated. No auth, no persistence, no network, no
LLM. This app exists so the user can technically test the complete path
before any lawyer sees it.
"""

from __future__ import annotations

import hashlib
import secrets
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from application.litigation.brief_checks import VersionedBrief
from application.litigation.corpus import load_corpus
from application.litigation.lawyer_decisions import (
    Disposition,
    LawyerDecisionError,
    record_decision,
    validate_decision,
)
from application.litigation.review_cycle import (
    CorrectionProposal,
    ReviewPacket,
    decision_summary,
    preview_correction,
    ready_for_release,
    revise_review,
)
from application.litigation.suitability_rules import ConfirmedFact, evaluate_rule
from application.litigation.unified_review import (
    BriefRepresentation,
    ObservationReview,
    ReviewDisposition,
    VerificationError,
)
from infrastructure.parsers.docx_text_regions import extract_docx_text_regions
from scripts.demo_belgian_dossier import (
    DEMO_RUNNER_VERSION,
    SIMULATED_ACTOR,
    DemoDossierError,
    M2Journey,
    _load_decision_specs,
    _load_facts,
    _load_m2,
    _load_meta,
    _load_rules,
    _locate,
    _references_with_quote_updates,
    _run_check,
    render_html,
)
from scripts.measure_docx_coverage import measure_file

ASSETS = Path(__file__).resolve().parents[1] / "web/demo"
MAX_UPLOAD = 5_000_000
MAX_BODY = 50_000


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    observation_id: str = Field(min_length=1, max_length=200)
    disposition: str = Field(min_length=1, max_length=40)
    rationale: str = Field(min_length=1, max_length=2000)


class RuleDecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    rule_id: str = Field(min_length=1, max_length=128)
    disposition: str = Field(min_length=1, max_length=40)
    rationale: str = Field(min_length=1, max_length=600)
    scope: str = Field(min_length=1, max_length=400)


class FactInput(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    confirmed: bool


class CorrectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    passage_id: str = Field(min_length=1, max_length=160)
    after: str = Field(min_length=1, max_length=4000)
    rationale: str = Field(min_length=1, max_length=2000)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class DocumentState:
    """The currently loaded DOCX: measured + actually read by the product reader."""

    def __init__(self, name: str, payload: bytes) -> None:
        self.name = name
        self.payload = payload
        self.sha256 = hashlib.sha256(payload).hexdigest()
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as handle:
            handle.write(payload)
            tmp = Path(handle.name)
        try:
            self.coverage = measure_file(tmp)
        finally:
            tmp.unlink()
        extraction = extract_docx_text_regions(payload)
        self.text = "\n".join(region.text for region in extraction.regions)
        self.body_read = any(region.part == "word/document.xml" for region in extraction.regions)
        self.text_coverage_complete = extraction.coverage_complete
        self.unscanned_parts = list(extraction.unscanned_parts)

    def payload_view(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "sha256": self.sha256,
            "body_read": self.body_read,
            "text_coverage_complete": self.text_coverage_complete,
            "unscanned_parts": self.unscanned_parts,
            "regions": self.coverage["regions"],
        }


class DemoState:
    """In-memory demo session; rebuilt on /run, lost on restart. By design."""

    def __init__(self, dossier: Path) -> None:
        self.meta = _load_meta(dossier)
        self.corpus = load_corpus(dossier / "corpus")
        self.facts = _load_facts(dossier)
        self.rules = _load_rules(dossier)
        self.m2 = _load_m2(dossier)
        self.decided_at, _ = _load_decision_specs(dossier)
        default_name = self.meta.brief
        self.document = DocumentState(default_name, (dossier / default_name).read_bytes())
        self.reset_run()

    def reset_run(self) -> None:
        self.active_text = self.document.text if self.document.body_read else ""
        self.active_version = self.m2.brief_version_id
        self.versions: list[dict[str, Any]] = []
        self.run = None
        self.packet: ReviewPacket | None = None
        self.rule_results: list[Any] = []
        self.lawyer_decisions: dict[str, Any] = {}
        self.started = False
        self.run_document_sha256: str | None = None
        self.align_uploaded_version()

    def align_uploaded_version(self) -> None:
        """An uploaded document whose content matches the DECLARED corrected
        passage (original gone, declared correction present) IS that corrected
        version: register it, so the measured findings follow the actual
        uploaded content. The correction stays declared/synthetic-labeled."""
        correction = self.m2.correction
        if not self.document.body_read or correction is None:
            return
        passage_id = correction["passage_id"]
        passage = next((p for p in self.m2.passages if p["passage_id"] == passage_id), None)
        if passage is None:
            return
        if passage["text"] in self.active_text or correction["after"] not in self.active_text:
            return
        self.versions.append(
            {
                "passage_id": passage_id,
                "observation_id": passage["observation_id"],
                "before": passage["text"],
                "after": correction["after"],
                "rationale": correction["rationale"] + " (version corrigée téléversée)",
                "version": self.m2.brief_version_id,
            }
        )
        self.active_version = f"{self.m2.brief_version_id}-corrige-1"

    def active_references(self) -> Any:
        quote_updates = {
            entry["passage_id"]: entry["after"]
            for entry in self.versions
            if entry["observation_id"].startswith("citation:")
        }
        return _references_with_quote_updates(self.m2, quote_updates)

    def representation(self, text: str, version: str) -> BriefRepresentation:
        references = self.active_references()
        brief = VersionedBrief(self.m2.case_id, version, _sha(f"original:{version}"), references)
        return BriefRepresentation(brief, text, _sha(text), DEMO_RUNNER_VERSION, ())

    def validate_extraction(self) -> list[str]:
        """Locate every declared demo input (reference quotes, correction
        passages) in the ACTUALLY READ text; missing items are reported, never
        silently skipped."""
        missing: list[str] = []
        if not self.document.body_read:
            return ["document body not read (fail-closed)"]
        text = self.document.text
        for reference in self.active_references():
            if reference.exact_quote is not None and reference.exact_quote not in text:
                missing.append(f"quote of {reference.reference_id}")
        corrected = {entry["passage_id"] for entry in self.versions}
        for passage in self.m2.passages:
            if passage["passage_id"] in corrected:
                continue
            if passage["text"] not in text:
                missing.append(f"passage {passage['passage_id']}")
        return missing


def _excerpt(text: str, start: int | None, end: int | None, radius: int = 140) -> dict[str, Any] | None:
    if start is None or end is None:
        return None
    lo = max(0, start - radius)
    hi = min(len(text), end + radius)
    return {
        "before": text[lo:start],
        "match": text[start:end],
        "after": text[end:hi],
        "truncated_start": lo > 0,
        "truncated_end": hi < len(text),
    }


def _finding_payloads(state: DemoState, run: Any) -> dict[str, Any]:
    previews = {s.source_id: s for s in state.m2.sources}
    citations = []
    for obs in run.citation_observations:
        source = previews.get(obs.source_id or "")
        quote = next(
            (r.exact_quote for r in state.active_references() if r.reference_id == obs.reference_id),
            None,
        )
        citations.append(
            {
                "observation_id": f"citation:{obs.reference_id}",
                "reference_id": obs.reference_id,
                "state": obs.state.value,
                "scope_note": obs.scope_note,
                "quote": quote,
                "source_id": obs.source_id,
                "source_label": source.label if source else None,
                "source_excerpt": _excerpt(source.text, obs.text_start, obs.text_end) if source else None,
            }
        )
    facts = []
    claims = {c["claim_id"]: c for c in state.m2.claim_specs}
    for obs in run.factual_observations:
        source = previews.get(obs.source_id or "")
        claim = claims.get(obs.claim_id, {})
        facts.append(
            {
                "observation_id": f"fact:{obs.claim_id}",
                "claim_id": obs.claim_id,
                "kind": obs.kind.value,
                "role": obs.role.value,
                "state": obs.state.value,
                "explanation": obs.explanation,
                "brief_passage": claim.get("text"),
                "brief_token": obs.brief_token,
                "source_token": obs.source_token,
                "source_id": obs.source_id,
                "source_label": source.label if source else None,
                "source_locator": obs.source_locator,
                "source_pdf_page": obs.source_pdf_page,
                "source_excerpt": _excerpt(source.text, obs.source_start, obs.source_end) if source else None,
            }
        )
    return {"citations": citations, "facts": facts}


def _rule_payload(result: Any, decision: Any, validity: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "rule_id": result.rule_id,
        "rule_version": result.rule_version,
        "status": result.status.value,
        "reference": result.reference,
        "scope": result.scope,
        "reason": result.reason,
        "preconditions": [{"name": p.name, "met": p.met, "detail": p.detail} for p in result.preconditions],
        "subresults": [[k, v] for k, v in result.subresults],
    }
    if decision is not None:
        payload["decision"] = {
            "disposition": decision.disposition.value,
            "rationale": decision.rationale,
            "scope": decision.scope,
            "validity": validity[0].value if validity else None,
            "validity_detail": validity[1] if validity else None,
        }
    return payload


def create_demo_app(dossier: Path) -> FastAPI:
    state = DemoState(dossier)
    app = FastAPI(title="CaseProof demo journey (loopback)", docs_url=None, redoc_url=None, openapi_url=None)
    session = secrets.token_urlsafe(32)

    @app.middleware("http")
    async def guard(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if request.url.hostname not in {"127.0.0.1", "localhost", "::1", "testserver"}:
            return JSONResponse({"error": "loopback_demo_only"}, status_code=403)
        if request.method not in {"GET", "HEAD", "POST"}:
            return JSONResponse({"error": "method_not_allowed"}, status_code=405)
        if request.method == "POST":
            origin = request.headers.get("origin", "")
            try:
                parsed = urlsplit(origin)
            except ValueError:
                return JSONResponse({"error": "origin_rejected"}, status_code=403)
            if parsed.scheme != request.url.scheme or parsed.netloc != request.headers.get("host"):
                return JSONResponse({"error": "origin_rejected"}, status_code=403)
            if not secrets.compare_digest(request.headers.get("x-demo-session", ""), session):
                return JSONResponse({"error": "session_rejected"}, status_code=403)
            content_type = request.headers.get("content-type", "").split(";", 1)[0]
            limit = MAX_UPLOAD if request.url.path == "/demo/api/document" else MAX_BODY
            if content_type not in {"application/json", "application/octet-stream"}:
                return JSONResponse({"error": "content_type_rejected"}, status_code=415)
            raw = await request.body()
            if len(raw) > limit:
                return JSONResponse({"error": "request_limit"}, status_code=413)
        response = await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": "default-src 'none'; script-src 'self'; "
                "style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
            }
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse({"error": "invalid_demo_input"}, status_code=422)

    @app.exception_handler(DemoDossierError)
    async def dossier_rejected(request: Request, exc: DemoDossierError) -> JSONResponse:
        return JSONResponse({"error": "demo_input_rejected", "message": str(exc)}, status_code=422)

    @app.exception_handler(LawyerDecisionError)
    async def decision_rejected(request: Request, exc: LawyerDecisionError) -> JSONResponse:
        return JSONResponse({"error": "decision_rejected", "message": str(exc)}, status_code=422)

    @app.exception_handler(VerificationError)
    async def verification_rejected(request: Request, exc: VerificationError) -> JSONResponse:
        return JSONResponse({"error": "verification_rejected", "message": str(exc)}, status_code=409)

    @app.exception_handler(Exception)
    async def unknown(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse({"error": "demo_outcome_unknown"}, status_code=503)

    @app.get("/demo")
    def index() -> FileResponse:
        return FileResponse(ASSETS / "index.html", media_type="text/html")

    @app.get("/demo/assets/{name}")
    def asset(name: str) -> Response:
        if name not in {"demo.css", "demo.js"}:
            return Response(status_code=404)
        return FileResponse(
            ASSETS / name, media_type="text/css" if name.endswith("css") else "text/javascript"
        )

    @app.get("/demo/api/state")
    def overview() -> dict[str, Any]:
        corpus = state.corpus
        return {
            "session": session,
            "runner": DEMO_RUNNER_VERSION,
            "title": state.meta.title,
            "audience_note": state.meta.audience_note,
            "document": {
                **state.document.payload_view(),
                "extraction_validated_against_read_text": state.validate_extraction() == [],
                "extraction_missing": state.validate_extraction(),
                "simulated_extraction": True,
                "active_version": state.active_version,
            },
            "corpus": {
                "articles": [
                    {
                        "act": r.act,
                        "article": r.article,
                        "language": r.language,
                        "version": r.version,
                        "source_uri": r.source_uri,
                        "sha256": r.original_sha256,
                    }
                    for r in corpus.records
                ],
                "failures": list(corpus.failures),
                "ambiguous_versions": list(corpus.ambiguous_versions),
            },
            "sources": [
                {
                    "source_id": s.source_id,
                    "version_id": s.version_id,
                    "label": s.label,
                    "synthetic": s.synthetic,
                    "sha256": hashlib.sha256(s.text.encode()).hexdigest(),
                }
                for s in state.m2.sources
            ],
            "facts": [
                {"name": f.name, "value": f.value, "confirmed": f.confirmed} for f in state.facts.values()
            ],
            "rules": [{"rule_id": rule.rule_id, "version": rule.rule_version} for _n, rule in state.rules],
            "started": state.started,
        }

    @app.post("/demo/api/document")
    async def upload_document(request: Request) -> Any:
        payload = await request.body()
        if not payload.startswith(b"PK\x03\x04"):
            return JSONResponse(
                {"error": "not_a_docx", "message": "Le fichier n'est pas un document Word (.docx) lisible."},
                status_code=422,
            )
        name = request.headers.get("x-demo-filename", "document-televerse.docx")[:128]
        try:
            state.document = DocumentState(name, payload)
        except Exception:
            return JSONResponse(
                {"error": "docx_unreadable", "message": "Le lecteur Word n'a pas pu lire ce fichier."},
                status_code=422,
            )
        state.reset_run()
        missing = state.validate_extraction()
        aligned = state.active_version != state.m2.brief_version_id
        return {
            "document": state.document.payload_view(),
            "body_read": state.document.body_read,
            "extraction_missing": missing,
            "active_version": state.active_version,
            "note": (
                "Corps du document lu par le lecteur produit"
                + (
                    " ; contenu identique à la version corrigée déclarée "
                    f"({state.active_version}) — la vérification porte sur cette version."
                    if aligned
                    else "."
                )
                if state.document.body_read
                else "Le lecteur produit refuse le corps de ce document (fail-closed) : voir les régions mesurées."
            ),
        }

    @app.post("/demo/api/run")
    def run_checks() -> Any:
        if not state.document.body_read:
            return JSONResponse(
                {
                    "error": "document_not_readable",
                    "message": "Le lecteur produit n'a pas lu le corps du document : vérification impossible.",
                },
                status_code=409,
            )
        missing = state.validate_extraction()
        if missing:
            return JSONResponse(
                {
                    "error": "extraction_mismatch",
                    "message": "L'extraction simulée ne correspond pas au texte réellement lu.",
                    "missing": missing,
                },
                status_code=422,
            )
        state.reset_run()
        representation = state.representation(state.active_text, state.active_version)
        run = _run_check(state.m2, representation)
        state.run = run
        state.packet = ReviewPacket(run.snapshot_hash, 0, ())
        state.rule_results = [
            evaluate_rule(rule, state.facts, state.corpus.article_keys) for _n, rule in state.rules
        ]
        state.started = True
        state.run_document_sha256 = state.document.sha256
        return {
            "snapshot": run.snapshot_hash,
            "brief_version": state.active_version,
            "findings": _finding_payloads(state, run),
            "rule_results": [_rule_payload(r, None, None) for r in state.rule_results],
            "processed": [list(p) for p in run.processed],
            "incomplete": [list(p) for p in run.incomplete],
        }

    def _require_run() -> JSONResponse | None:
        if not state.started or state.run is None or state.packet is None:
            return JSONResponse({"error": "run_first"}, status_code=409)
        if state.run_document_sha256 != state.document.sha256:
            # Le résultat courant appartient à un autre document : jamais
            # d'export ni de décision sur un instantané caduc.
            return JSONResponse(
                {"error": "stale_result", "message": "Document changé : relancez les vérifications."},
                status_code=409,
            )
        return None

    @app.post("/demo/api/facts")
    def confirm_fact(payload: FactInput) -> Any:
        """Confirm or unconfirm one case fact (simulated reviewer act, labeled
        as such in the UI): deterministic rules are re-evaluated live on the
        updated facts, and recorded rule decisions are re-validated."""
        fact = state.facts.get(payload.name)
        if fact is None:
            return JSONResponse({"error": "unknown_fact"}, status_code=422)
        state.facts[payload.name] = ConfirmedFact(fact.name, fact.value, payload.confirmed)
        if state.started and state.run is not None and state.run_document_sha256 == state.document.sha256:
            state.rule_results = [
                evaluate_rule(rule, state.facts, state.corpus.article_keys) for _n, rule in state.rules
            ]
        validity_by_rule = {}
        for rule_id, decision in state.lawyer_decisions.items():
            result = next(r for r in state.rule_results if r.rule_id == rule_id)
            validity_by_rule[rule_id] = validate_decision(decision, result)
        return {
            "facts": [
                {"name": f.name, "value": f.value, "confirmed": f.confirmed} for f in state.facts.values()
            ],
            "rule_results": [
                _rule_payload(r, state.lawyer_decisions.get(r.rule_id), validity_by_rule.get(r.rule_id))
                for r in state.rule_results
            ],
        }

    @app.post("/demo/api/review")
    def review(payload: ReviewInput) -> Any:
        early = _require_run()
        if early is not None:
            return early
        assert state.run is not None
        try:
            disposition = ReviewDisposition(payload.disposition)
        except ValueError:
            return JSONResponse({"error": "unknown_disposition"}, status_code=422)
        assert state.packet is not None and state.run is not None
        state.packet = revise_review(
            run=state.run,
            packet=state.packet,
            expected_revision=state.packet.revision,
            decision=ObservationReview(
                payload.observation_id,
                SIMULATED_ACTOR,
                disposition,
                payload.rationale,
            ),
        )
        return {
            "revision": state.packet.revision,
            "summary": decision_summary(state.packet),
            "release_ready": ready_for_release(state.run, state.packet),
        }

    @app.post("/demo/api/rule-decision")
    def rule_decision(payload: RuleDecisionInput) -> Any:
        early = _require_run()
        if early is not None:
            return early
        assert state.run is not None
        result = next((r for r in state.rule_results if r.rule_id == payload.rule_id), None)
        if result is None:
            return JSONResponse({"error": "unknown_rule"}, status_code=422)
        try:
            disposition = Disposition(payload.disposition)
        except ValueError:
            return JSONResponse({"error": "unknown_disposition"}, status_code=422)
        decision = record_decision(
            result,
            actor_id=SIMULATED_ACTOR,
            disposition=disposition,
            rationale=payload.rationale,
            scope=payload.scope,
            decided_at=state.decided_at or "2026-11-22T20:00:00+01:00",
        )
        state.lawyer_decisions[payload.rule_id] = decision
        validity, detail = validate_decision(decision, result)
        return {
            "decision_id": decision.decision_id,
            "disposition": disposition.value,
            "validity": validity.value,
            "validity_detail": detail,
            "machine_status": result.status.value,
        }

    @app.post("/demo/api/correction")
    def correction(payload: CorrectionInput) -> Any:
        early = _require_run()
        if early is not None:
            return early
        assert state.run is not None
        assert state.run is not None
        passage_spec: dict[str, Any] | None = None
        for passage in state.m2.passages:
            if passage["passage_id"] == payload.passage_id:
                passage_spec = passage
        if passage_spec is None:
            return JSONResponse({"error": "unknown_passage"}, status_code=422)
        current_text = passage_spec["text"]
        for version in state.versions:
            if version["passage_id"] == payload.passage_id:
                current_text = version["after"]
        try:
            start, end = _locate(state.active_text, current_text, "passage")
        except DemoDossierError as exc:
            return JSONResponse({"error": "passage_not_in_text", "message": str(exc)}, status_code=422)
        representation = state.representation(state.active_text, state.active_version)
        proposal = CorrectionProposal(
            observation_id=passage_spec["observation_id"],
            actor_id=SIMULATED_ACTOR,
            expected_run_hash=state.run.snapshot_hash,
            expected_brief_version=state.active_version,
            expected_text_sha256=representation.text_sha256,
            start=start,
            end=end,
            before=current_text,
            after=payload.after,
            rationale=payload.rationale,
        )
        preview = preview_correction(run=state.run, text=state.active_text, proposal=proposal)
        state.versions.append(
            {
                "passage_id": payload.passage_id,
                "observation_id": passage_spec["observation_id"],
                "before": current_text,
                "after": payload.after,
                "rationale": payload.rationale,
                "version": state.active_version,
            }
        )
        state.active_text = preview.proposed_text
        state.active_version = f"{state.m2.brief_version_id}-corrige-{len(state.versions)}"
        before_citations = {o.reference_id: o.state.value for o in state.run.citation_observations}
        representation2 = state.representation(state.active_text, state.active_version)
        state.run = _run_check(state.m2, representation2)
        state.packet = ReviewPacket(state.run.snapshot_hash, 0, ())
        after_citations = {o.reference_id: o.state.value for o in state.run.citation_observations}
        flips = {
            ref: {"before": before_citations.get(ref), "after": after_citations.get(ref)}
            for ref in after_citations
            if before_citations.get(ref) != after_citations.get(ref)
        }
        return {
            "brief_version": state.active_version,
            "snapshot": state.run.snapshot_hash,
            "correction": state.versions[-1],
            "flips": flips,
            "findings": _finding_payloads(state, state.run),
            "note": "La relecture est liée à la version : les dispositions sont réinitialisées après correction.",
        }

    @app.get("/demo/api/export.json")
    def export_json() -> Any:
        early = _require_run()
        if early is not None:
            return early
        assert state.run is not None
        assert state.run is not None and state.packet is not None
        decisions = []
        for rule_id, decision in state.lawyer_decisions.items():
            result = next((r for r in state.rule_results if r.rule_id == rule_id), None)
            validity = validate_decision(decision, result)
            decisions.append(_rule_payload(result, decision, validity))
        return {
            "export_contract": "caseproof-demo-export-v1",
            "demonstration": True,
            "not_legal_validation": True,
            "title": state.meta.title,
            "document": {"name": state.document.name, "sha256": state.document.sha256},
            "brief_version": state.active_version,
            "snapshot": state.run.snapshot_hash,
            "versions": state.versions,
            "findings": _finding_payloads(state, state.run),
            "review": {
                "simulated": True,
                "summary": decision_summary(state.packet),
                "decisions": [
                    {
                        "observation_id": d.observation_id,
                        "disposition": d.disposition.value,
                        "rationale": d.rationale,
                    }
                    for d in state.packet.decisions
                ],
            },
            "rule_results": [
                _rule_payload(r, state.lawyer_decisions.get(r.rule_id), None) for r in state.rule_results
            ],
            "rule_decisions": decisions,
            "release_ready": ready_for_release(state.run, state.packet),
            "limits": [
                "Démonstration : faits, pièces, règles et relecture simulés, non approuvés par un avocat.",
                "Pas de conseil juridique, pas de pilote (tâche 7), pas de couverture exhaustive du droit belge.",
                "La conséquence d'une dérogation (export / prêt avec exceptions) reste une décision ouverte (tâche 2).",
                "Aucune donnée persistée ni envoyée ; session locale éphémère.",
            ],
        }

    @app.get("/demo/api/export.html")
    def export_html() -> Response:
        early = _require_run()
        if early is not None:
            return early
        assert state.run is not None
        assert state.run is not None and state.packet is not None
        journey = M2Journey(
            run1=state.run,
            packet=state.packet,
            correction_preview=None,
            corrected_claim_id=state.versions[-1]["passage_id"] if state.versions else None,
            corrected_text=state.active_text,
            run2=state.run if state.versions else None,
            release_ready=ready_for_release(state.run, state.packet),
            summary=decision_summary(state.packet),
        )
        validity_map = {}
        for rule_id, decision in state.lawyer_decisions.items():
            result = next(r for r in state.rule_results if r.rule_id == rule_id)
            validity_map[decision.decision_id] = validate_decision(decision, result)
        html_report = render_html(
            {
                "meta": state.meta,
                "corpus": state.corpus,
                "coverage": state.document.coverage,
                "reader": {
                    "body_read": state.document.body_read,
                    "unscanned_parts": list(state.document.unscanned_parts),
                    "coverage_complete": state.document.text_coverage_complete,
                    "text_matches_brief": state.document.body_read
                    and state.document.text == state.m2.brief_text,
                },
                "facts": state.facts,
                "results": state.rule_results,
                "decisions": list(state.lawyer_decisions.values()),
                "validity": validity_map,
                "m2": state.m2,
                "journey": journey,
            },
            generated_at="session de démonstration interactive",
        )
        return Response(
            content=html_report,
            media_type="text/html",
            headers={"Content-Disposition": 'attachment; filename="caseproof-demo-rapport.html"'},
        )

    return app
