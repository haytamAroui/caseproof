"""Development-only SIGNED routes for check, review and correction preview.

These routes reach the signed adapters (LiveMatterCheckStore, the signed review
ledger) through a per-request workbench factory bound to ONE verified bearer
(assemble_request_workbench in production composition; a labeled fake auth and
transport rig in tests). Nothing here is mounted in production, writes live
data on its own, or accepts a client actor, org, checked payload or source text.

Vocabulary: a "candidate difference" is a deterministic comparison of typed
values inside one verified source passage. It is never a legal conclusion,
never proof that the brief is wrong, and never an approval.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import asdict
from typing import Annotated, Any, Protocol
from uuid import UUID

from fastapi import APIRouter, Body, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from application.litigation.review_cycle import CorrectionProposal, preview_correction
from application.litigation.unified_review import ReviewDisposition
from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.litigation_check_service import AuthorizedLitigationChecker
from apps.api.litigation_evidence_app import _token
from apps.api.litigation_review_app import ReviewBody
from apps.api.litigation_review_workspace import ReviewCommand, SignedReviewWorkspace
from apps.api.litigation_workspace_sources import SignedBriefSources
from apps.api.signed_supabase_facts import FactRefused
from apps.api.signed_supabase_originals import PrivateStorageDenied
from infrastructure.parsers.pdf_ocr import OCRUnavailable
from infrastructure.parsers.pdf_source_crop import render_pdf_page

__all__ = ["ConflictError", "create_signed_workbench_router"]

_NOTE = (
    "Candidate differences compare typed values in one verified source passage. "
    "They are not legal conclusions, not approval and not a filing decision."
)


_PACK_NOTE = (
    "The digest proves the downloaded bytes equal what the server built for this check. "
    "It does not prove who built them, that the corpus is current or applicable, or that any claim is supported."
)
_LEGAL_NOTE = (
    "PASS means the article is in the chosen corpus and any bound quotation is "
    "literally in its stored text. It never means the article is applicable, "
    "correctly read or supports the claim. UNVERIFIED means only: article absent "
    "from the chosen corpus."
)


class _Workbench(Protocol):
    checker: AuthorizedLitigationChecker
    workspace: SignedReviewWorkspace
    store: Any


class CorrectionPreviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    observation_id: str = Field(min_length=1, max_length=160)
    # Optional: when omitted the exact text must occur exactly once in the
    # current verified representation, otherwise the preview abstains (409).
    start: int | None = Field(default=None, ge=0, le=120_000)
    end: int | None = Field(default=None, ge=1, le=120_000)
    before: str = Field(min_length=1, max_length=4000)
    after: str = Field(min_length=1, max_length=4000)
    rationale: str = Field(min_length=1, max_length=2000)


_FACT_NOTE = (
    "Records that the signed session user entered this value against this source "
    "version. It is not proof the fact is true and not a legal conclusion.")


class FactConfirmBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    request_id: str
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    value: bool | int | float | str
    confirmed: bool
    source_document_id: str
    source_version_id: str
    brief_version_id: str
    passage: str = Field(min_length=1, max_length=120)
    passage_start: int | None = Field(default=None, ge=0)


def _verified_passage(wb: Any, bearer: str, case_id: str, body: FactConfirmBody) -> str:
    """The actor selects an exact passage of the source's represented text.

    The passage must occur verbatim in the verified representation of the
    named source version (a repeated passage needs an explicit start offset).
    The locator stored is the page (when mapped), the offsets and the passage.
    """
    sources = SignedBriefSources(wb.checker)
    inventory = sources.inventory(
        bearer=bearer, case_id=case_id, brief_version_id=body.brief_version_id)
    rows = [r for r in inventory["rows"]
            if r["document_id"] == body.source_document_id
            and r["version_id"] == body.source_version_id]
    if len(rows) != 1:
        raise AccessRejected(AccessFailure.RESOURCE_MASKED)
    preview = sources.preview(
        bearer=bearer, case_id=case_id, brief_version_id=body.brief_version_id,
        source_id=rows[0]["source_id"])
    text: str = preview["text"]
    starts = [m.start() for m in re.finditer(re.escape(body.passage), text)]
    if body.passage_start is not None:
        starts = [s for s in starts if s == body.passage_start]
    if len(starts) != 1:
        raise AccessRejected(AccessFailure.RESOURCE_MASKED)
    start = starts[0]
    end = start + len(body.passage)
    page = next((s[3] for s in preview["spans"] if s[0] <= start < s[1] and s[3] is not None), None)
    where = f"p.{page} " if page is not None else "page not mapped "
    return f"{where}offsets {start}-{end}: \u00ab{body.passage}\u00bb"[:200]


def _fact_ledger(wb: Any, bearer: str) -> Any:
    provider = getattr(wb.checker, "fact_ledger_for", None)
    if not callable(provider):
        raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
    return provider(bearer)


def _corpus_for(wb: Any, case_id: str) -> Any:
    provider = getattr(wb.checker, "legal_corpus_for", None)
    return provider(case_id) if callable(provider) else None


class PassageFlagBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    request_id: str
    brief_version_id: str
    source_document_id: str
    source_version_id: str
    draft_passage: str = Field(min_length=1, max_length=1200)
    source_passage: str = Field(min_length=1, max_length=1200)
    source_start: int = Field(ge=0)
    rationale: str = Field(min_length=1, max_length=2000)


class SearchBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str = Field(min_length=2, max_length=120)


_EXHIBIT_NOTE = (
    "Located means the number exists in the inventory a person confirmed, with its recorded "
    "source file. The exhibit's content is not compared to the brief. Unconfirmed, unbound, "
    "ambiguous or unnamed page-space references stay undetermined.")


_CONDITIONS_NOTE = (
    "Conditions are defined by the lawyer: literal words, no synonyms, no reading of meaning. "
    "Nothing here is a verdict and no condition is ever marked as met.")


class ConflictError(Exception):
    """The stored revision moved since the caller read it."""


def create_signed_workbench_router(
    factory: Callable[[str], _Workbench] | None,
    intake_context: Callable[[str, str], Any] | None = None,
    conditions_store: Any | None = None,
) -> APIRouter:
    router = APIRouter()
    base = "/dev/signed/matters/{case_id}/briefs/{brief_version_id}"

    def bench(authorization: str | None) -> tuple[str, _Workbench]:
        if factory is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        bearer = _token(authorization)
        try:
            return bearer, factory(bearer)
        except ValueError:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None

    @router.get(base + "/check")
    @router.post(base + "/check")
    def signed_check(
        case_id: str, brief_version_id: str,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        bearer, wb = bench(authorization)
        run = wb.checker.check(bearer=bearer, case_id=case_id, brief_version_id=brief_version_id)
        return {"schema": "caseproof-signed-check-v1", "note": _NOTE, **asdict(run)}

    def pack_for(case_id: str, brief_version_id: str, authorization: str | None) -> tuple[bytes, str, str]:
        """Authorized legal slice with locally preserved corpus, no online fallback."""
        from application.litigation.corpus import CorpusError
        from application.litigation.legal_references import ENGINE_STRICT4
        from application.litigation.offline_legal_pack import build_legal_pack
        bearer, wb = bench(authorization)
        run = wb.checker.check(bearer=bearer, case_id=case_id, brief_version_id=brief_version_id)
        config = _corpus_for(wb, case_id)
        if config is None:
            raise HTTPException(status_code=409, detail="chosen_corpus_unavailable")
        subject = wb.checker._verified(bearer)
        access = wb.checker._scope(subject, case_id)
        from apps.api.litigation_evidence_search import AuthorizedEvidenceSearch
        AuthorizedEvidenceSearch._require_evidence(access)
        bundle = wb.store.load_bundle(case_id=case_id, brief_version_id=brief_version_id, access=access)
        review = wb.workspace.state(bearer=bearer, case_id=case_id, brief_version_id=brief_version_id)
        section = None
        if conditions_store is not None:
            from application.litigation.signed_conditions import match_conditions
            from application.litigation.signed_conditions_pack import build_section
            from apps.api.litigation_workspace_sources import _labels
            revision, spec = stored_spec(bearer, case_id)
            if spec is not None:
                head = conditions_store.read(bearer, case_id)
                if head is None or int(head["revision"]) != revision:
                    raise AccessRejected(AccessFailure.STALE_SNAPSHOT)
                from application.litigation.signed_conditions import _readable
                labels = _labels(bundle)
                matched = (match_conditions(bundle.representation.text, spec, bundle.previews, labels)
                           if spec["conditions"] else {"anchors": []})
                section = build_section(head["spec_text"], head["spec_sha256"], revision, matched, spec,
                                        bundle.previews, labels, _readable)
        try:
            data, checkpoint = build_legal_pack(config=config, run=run,
                                                brief_text=bundle.representation.text,
                                                review={**review, "check_engine": ENGINE_STRICT4},
                                                signed_conditions=section)
        except CorpusError:
            raise HTTPException(status_code=409, detail="offline_corpus_bytes_unavailable_or_changed") from None
        if (wb.checker._scope(wb.checker._verified(bearer), case_id) != access
                or not wb.store.still_current(access=access, bundle=bundle)):
            raise AccessRejected(AccessFailure.STALE_SNAPSHOT)
        return data, checkpoint, run.snapshot_hash

    @router.get(base + "/offline-legal-pack")
    def signed_offline_legal_pack(
        case_id: str, brief_version_id: str,
        authorization: Annotated[str | None, Header()] = None,
    ) -> Response:
        data, checkpoint, _snap = pack_for(case_id, brief_version_id, authorization)
        return Response(data, media_type="application/zip", headers={
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Content-Disposition": 'attachment; filename="caseproof-offline-legal-review.zip"',
            "X-CaseProof-Legal-Review-SHA256": checkpoint,
        })

    pack_v2 = "/v2/matters/{case_id}/briefs/{brief_version_id}/offline-pack"

    @router.get(pack_v2 + "/manifest")
    def v2_offline_pack_manifest(
        case_id: str, brief_version_id: str,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        """Digest and size of the pack as it would be served now. Download must match it exactly."""
        from application.litigation.workspace_contract import OfflinePackManifest
        data, checkpoint, snap = pack_for(case_id, brief_version_id, authorization)
        view = OfflinePackManifest.model_validate({
            "schema": "caseproof-offline-pack-manifest-v1", "brief_version_id": brief_version_id,
            "snapshot_hash": snap, "sha256": hashlib.sha256(data).hexdigest(),
            "byte_length": len(data), "checkpoint_sha256": checkpoint, "media": "application/zip",
            "note": _PACK_NOTE})
        return view.model_dump(by_alias=True)

    @router.get(pack_v2)
    def v2_offline_pack(
        case_id: str, brief_version_id: str,
        authorization: Annotated[str | None, Header()] = None,
    ) -> Response:
        data, checkpoint, snap = pack_for(case_id, brief_version_id, authorization)
        return Response(data, media_type="application/zip", headers={
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Content-Disposition": 'attachment; filename="caseproof-offline-legal-review.zip"',
            "X-CaseProof-Snapshot": snap,
            "X-CaseProof-Pack-SHA256": hashlib.sha256(data).hexdigest(),
            "X-CaseProof-Pack-Size": str(len(data)),
            "X-CaseProof-Legal-Review-SHA256": checkpoint,
        })

    @router.get(base + "/legal-references")
    def signed_legal_references(
        case_id: str, brief_version_id: str,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        """Cited articles of THIS run, version-bound (same snapshot as the check).

        The results are observations of the frozen run, so they are reviewable
        and exported with it. Without a corpus chosen for the matter the route
        says so and returns no verdicts: no default corpus, no network lookup.
        """
        bearer, wb = bench(authorization)
        run = wb.checker.check(
            bearer=bearer, case_id=case_id, brief_version_id=brief_version_id)
        config = _corpus_for(wb, case_id)
        return {
            "schema": "caseproof-signed-legal-references-v1",
            "brief_version_id": brief_version_id,
            "snapshot_hash": run.snapshot_hash,
            "note": _LEGAL_NOTE,
            "corpus": "configured" if config is not None else "not_configured",
            "corpus_pack_sha256": run.corpus_pack_sha256,
            "corpus_articles": len(config.records) if config is not None else 0,
            "corpus_failures": list(config.failures) if config is not None else [],
            "references": [
                {**asdict(x), "observation_id": f"legal:{x.reference_id}",
                 "claim_support": "not_assessed"} for x in run.legal_observations
            ],
            "coverage": {
                "detected": len(run.legal_observations),
                "by_status": {s: sum(1 for x in run.legal_observations if str(x.status) == s)
                              for s in ("PASS", "FAIL", "UNVERIFIED", "UNDETERMINED")},
                "analysed": "explicit 'article N' mentions naming a code or act only",
                "not_analysed": ["case law and court decisions", "provisions cited without an article number",
                                 "assertions without an explicit citation",
                                 "whether a cited article supports the claim"],
            },
            "suitability": [
                {**asdict(x), "observation_id": f"suitability:{x.rule_id}"}
                for x in run.suitability_observations
            ],
        }

    @router.get("/dev/signed/matters/{case_id}/facts")
    def signed_facts(
        case_id: str, authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        bearer, wb = bench(authorization)
        ledger = _fact_ledger(wb, bearer)
        try:
            rows = ledger.list(case_id=case_id)
        except FactRefused:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        return {"schema": "caseproof-signed-facts-v1", "note": _FACT_NOTE, "facts": list(rows)}

    @router.post("/dev/signed/matters/{case_id}/facts")
    def signed_fact_confirm(
        case_id: str, body: FactConfirmBody,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        bearer, wb = bench(authorization)
        ledger = _fact_ledger(wb, bearer)
        locator = _verified_passage(wb, bearer, case_id, body)
        try:
            recorded = ledger.confirm(
                case_id=case_id, request_id=body.request_id, name=body.name,
                value=body.value, confirmed=body.confirmed,
                source_document_id=body.source_document_id,
                source_version_id=body.source_version_id, locator=locator)
        except FactRefused:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
        return {"schema": "caseproof-signed-fact-recorded-v1", "recorded": recorded,
                "note": _FACT_NOTE}

    @router.post("/dev/signed/matters/{case_id}/passage-flags")
    def signed_passage_flag(
        case_id: str, body: PassageFlagBody,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        bearer, wb = bench(authorization)
        provider = getattr(wb.checker, "passage_flags_for", None)
        if not callable(provider):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        subject = wb.checker._verified(bearer)
        access = wb.checker._scope(subject, case_id)
        bundle = wb.checker.store.load_bundle(case_id=case_id, brief_version_id=body.brief_version_id, access=access)
        from apps.api.litigation_evidence_search import AuthorizedEvidenceSearch
        AuthorizedEvidenceSearch._require_evidence(access)
        p = next((p for p in bundle.previews if p.row.document_id == body.source_document_id
                  and p.row.version_id == body.source_version_id), None)
        if (p is None or p.row.status != "ready" or p.row.warnings
                or p.text[body.source_start:body.source_start + len(body.source_passage)] != body.source_passage
                or body.draft_passage not in bundle.representation.text
                or not wb.checker.store.still_current(access=access, bundle=bundle)):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        try:
            recorded = provider(bearer).record(case_id=case_id, request_id=body.request_id,
                                               flag=body.model_dump(exclude={"request_id"}))
        except FactRefused:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        return {"schema": "caseproof-human-passage-flag-v1", "recorded": recorded,
                "note": "Human-reported passage; exact text existence checked, not semantic support. Recheck required."}

    @router.get(base + "/legal-references/{reference_id}/passage")
    def signed_legal_passage(
        case_id: str, brief_version_id: str, reference_id: str,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        """Side by side: the lawyer's sentence and the exact corpus article text.

        The article text is served only when its hash equals the hash frozen
        in the run; otherwise the corpus changed and the run must be redone.
        """
        bearer, wb = bench(authorization)
        run = wb.checker.check(
            bearer=bearer, case_id=case_id, brief_version_id=brief_version_id)
        obs = next((x for x in run.legal_observations if x.reference_id == reference_id), None)
        if obs is None:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        subject = wb.checker._verified(bearer)
        scope = wb.checker._scope(subject, case_id)
        try:
            bundle = wb.store.load_bundle(
                case_id=case_id, brief_version_id=brief_version_id, access=scope)
        except Exception:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        text = bundle.representation.text
        lo, hi = max(0, obs.start - 160), min(len(text), obs.end + 240)
        article_text = None
        config = _corpus_for(wb, case_id)
        if config is not None and obs.corpus_key is not None:
            rec = next((r for r in config.records if r.key == obs.corpus_key), None)
            if rec is not None and rec.derived_sha256 == obs.corpus_text_sha256:
                article_text = rec.derived_text
            else:
                raise AccessRejected(AccessFailure.STALE_SNAPSHOT)
        def rel(a: int, b: int) -> list[int] | None:
            return [a - lo, b - lo] if lo <= a and b <= hi else None

        def quote_at(o: Any) -> list[int] | None:
            if not o.quote:
                return None
            i = text.find(o.quote, o.end)
            return rel(i, i + len(o.quote)) if i >= 0 else None

        others = []
        for x in run.legal_observations:
            span = rel(x.start, x.end)
            if x.reference_id != obs.reference_id and span is not None:
                others.append({"reference_id": x.reference_id, "status": x.status,
                               "span": span, "quote_span": quote_at(x)})
        return {
            "quote": obs.quote,
            "quote_span": quote_at(obs),
            "other_findings": others,
            "schema": "caseproof-signed-legal-passage-v1",
            "observation_id": f"legal:{obs.reference_id}",
            "snapshot_hash": run.snapshot_hash,
            "brief_excerpt": text[lo:hi],
            "citation_span": [obs.start - lo, obs.end - lo],
            "article_text": article_text,
            "corpus_key": obs.corpus_key, "corpus_version": obs.corpus_version,
            "corpus_text_sha256": obs.corpus_text_sha256,
            "corpus_source_uri": obs.corpus_source_uri,
            "status": obs.status, "reason": obs.reason,
            "note": _LEGAL_NOTE,
        }

    v2 = "/v2/matters/{case_id}/briefs/{brief_version_id}/legal-references"

    @router.get(v2)
    def v2_legal_references(
        case_id: str, brief_version_id: str,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        """Same signed run and checks as the /dev route, under the product contract.

        The body is validated by LegalReferencesView before it leaves: counts
        must add up and a PASS cannot exist without a chosen corpus.
        """
        from application.litigation.workspace_contract import LegalReferencesView
        raw = signed_legal_references(case_id, brief_version_id, authorization)
        raw["schema"] = "caseproof-legal-references-v1"
        raw["corpus_failures"] = [str(x) for x in raw["corpus_failures"]]
        raw["suitability"] = [
            {**row, "cited_by": list(row["cited_by"]), "missing": list(row["missing"]),
             "facts": [list(f) for f in row["facts"]], "input_hashes": [list(h) for h in row["input_hashes"]],
             "subresults": [list(x) for x in row["subresults"]]}
            for row in raw["suitability"]]
        try:
            view = LegalReferencesView.model_validate(raw)
        except ValueError:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        return view.model_dump(by_alias=True)

    @router.get("/v2/matters/{case_id}/briefs/{brief_version_id}/exhibit-references")
    def v2_exhibit_references(
        case_id: str, brief_version_id: str,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        """Exhibit mentions mapped to the CONFIRMED inventory of the matter.

        Identities, source versions and page mappings are passed through as
        confirmed by a person; nothing is numbered here. Located means the
        number exists in the confirmed inventory, never that content matches.
        """
        from application.litigation.inventory_mapping import map_exhibit_references
        from application.litigation.workspace_contract import ExhibitReferencesView
        if intake_context is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        bearer, wb = bench(authorization)
        run = wb.checker.check(bearer=bearer, case_id=case_id, brief_version_id=brief_version_id)
        subject = wb.checker._verified(bearer)
        scope = wb.checker._scope(subject, case_id)
        try:
            bundle = wb.store.load_bundle(
                case_id=case_id, brief_version_id=brief_version_id, access=scope)
            intake = intake_context(bearer, case_id)
        except AccessRejected:
            raise
        except Exception:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        raw = intake.model_dump(by_alias=True) if hasattr(intake, "model_dump") else dict(intake)
        mapped = map_exhibit_references(
            bundle.representation.text, brief_version_id=brief_version_id, intake=raw)
        try:
            view = ExhibitReferencesView.model_validate({
                "schema": "caseproof-exhibit-references-v1",
                "brief_version_id": brief_version_id,
                "snapshot_hash": run.snapshot_hash,
                "note": _EXHIBIT_NOTE,
                **mapped,
            })
        except ValueError:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        return view.model_dump(by_alias=True)

    def cond_store() -> Any:
        if conditions_store is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return conditions_store

    def stored_spec(bearer: str, case_id: str) -> tuple[int, dict[str, Any] | None]:
        from application.litigation.corpus import CorpusError
        from application.litigation.signed_conditions import load_stored
        try:
            head = cond_store().read(bearer, case_id)
            if head is None:
                return 0, None
            return int(head["revision"]), load_stored(head["spec_text"], head["spec_sha256"])
        except AccessRejected:
            raise
        except PrivateStorageDenied:
            # A denied caller is told "not found", never an empty conditions list.
            raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
        except (CorpusError, KeyError, ValueError, TypeError):
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        except Exception:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None

    @router.get("/v2/matters/{case_id}/conditions")
    def v2_conditions_state(
        case_id: str, authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        """Lawyer-defined conditions of this matter: the stored revision, re-hashed on read."""
        from application.litigation.workspace_contract import ConditionsStateView
        bearer = _token(authorization)
        revision, spec = stored_spec(bearer, case_id)
        view = ConditionsStateView.model_validate({
            "schema": "caseproof-conditions-state-v1", "revision": revision,
            "spec_sha256": None if spec is None else spec["spec_sha256"],
            "conditions": [] if spec is None else spec["conditions"], "note": _CONDITIONS_NOTE})
        return view.model_dump(by_alias=True)

    @router.post("/v2/matters/{case_id}/conditions")
    def v2_conditions_save(
        case_id: str, body: Annotated[Any, Body()],
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        from pydantic import ValidationError

        from application.litigation.corpus import CorpusError
        from application.litigation.signed_conditions import canonical_text, normalise_input
        from application.litigation.workspace_contract import ConditionsSaveBody, ConditionsStateView
        bearer = _token(authorization)
        try:
            parsed = ConditionsSaveBody.model_validate(body)
            spec = normalise_input([c.model_dump() for c in parsed.conditions])
            text, digest = canonical_text(spec)
        except (ValidationError, CorpusError) as exc:
            raise HTTPException(422, "conditions refused: " + (str(exc) if isinstance(exc, CorpusError) else "invalid shape")) from None
        store = cond_store()
        try:
            revision = int(store.append(bearer, case_id, parsed.expected_revision, text, digest))
        except AccessRejected:
            raise
        except PrivateStorageDenied:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
        except ConflictError:
            raise HTTPException(409, "conditions changed since you loaded them; reload") from None
        except Exception:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        # Read back: only report what the store now holds.
        got, stored = stored_spec(bearer, case_id)
        if got != revision or stored is None or stored["spec_sha256"] != digest:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return ConditionsStateView.model_validate({
            "schema": "caseproof-conditions-state-v1", "revision": got, "spec_sha256": digest,
            "conditions": stored["conditions"], "note": _CONDITIONS_NOTE}).model_dump(by_alias=True)

    @router.get("/v2/matters/{case_id}/briefs/{brief_version_id}/conditions")
    def v2_condition_matches(
        case_id: str, brief_version_id: str,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        """Where the brief hits a lawyer trigger, and the literal passages found in readable sources."""
        from application.litigation.corpus import CorpusError
        from application.litigation.signed_conditions import match_conditions
        from application.litigation.workspace_contract import ConditionMatchesView
        bearer, wb = bench(authorization)
        revision, spec = stored_spec(bearer, case_id)
        sources = SignedBriefSources(wb.checker)
        bundle = sources._bundle(bearer=bearer, case_id=case_id, brief_version_id=brief_version_id)
        if spec is None or not spec["conditions"]:
            matched: dict[str, Any] = {"spec_sha256": None, "scope": _CONDITIONS_NOTE, "anchors": [],
                                       "coverage": {"conditions": 0, "anchors": 0, "sources_read": 0,
                                                    "sources_not_read": 0,
                                                    "by_status": {s: 0 for s in ("PASS", "FAIL", "UNVERIFIED", "UNDETERMINED")}}}
        else:
            from apps.api.litigation_workspace_sources import _labels
            try:
                matched = match_conditions(bundle.representation.text, spec, bundle.previews, _labels(bundle))
            except CorpusError:
                raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        try:
            view = ConditionMatchesView.model_validate({
                "schema": "caseproof-condition-matches-v1", "brief_version_id": brief_version_id,
                "revision": revision, **matched})
        except ValueError:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        return view.model_dump(by_alias=True)

    @router.get(v2 + "/{reference_id}/passage")
    def v2_legal_passage(
        case_id: str, brief_version_id: str, reference_id: str,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        from application.litigation.workspace_contract import LegalPassageView
        raw = signed_legal_passage(case_id, brief_version_id, reference_id, authorization)
        raw["schema"] = "caseproof-legal-passage-v1"
        try:
            view = LegalPassageView.model_validate(raw)
        except ValueError:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        return view.model_dump(by_alias=True)

    @router.get(base + "/sources")
    def signed_sources(
        case_id: str, brief_version_id: str,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        bearer, wb = bench(authorization)
        return SignedBriefSources(wb.checker).inventory(
            bearer=bearer, case_id=case_id, brief_version_id=brief_version_id)

    @router.get(base + "/sources/{source_id}")
    def signed_source_preview(
        case_id: str, brief_version_id: str, source_id: str,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        bearer, wb = bench(authorization)
        return SignedBriefSources(wb.checker).preview(
            bearer=bearer, case_id=case_id, brief_version_id=brief_version_id,
            source_id=source_id)

    @router.post(base + "/evidence/search")
    def signed_search(
        case_id: str, brief_version_id: str, body: SearchBody,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        """Literal text search over the brief's declared, verified source versions.
        A hit is where the words occur. It is never support for an assertion."""
        from apps.api.litigation_evidence_search import AuthorizedEvidenceSearch
        bearer, wb = bench(authorization)
        try:
            result = AuthorizedEvidenceSearch(wb.checker).search(
                bearer=bearer, case_id=case_id, brief_version_id=brief_version_id,
                query=body.query)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid search query") from None
        return {"schema": "caseproof-evidence-search-v1", **asdict(result)}

    def _original(wb: Any, bearer: str, case_id: str, brief_version_id: str,
                  source_id: str, version_id: str) -> Any:
        reader = getattr(wb, "originals", None)
        if reader is None or getattr(reader, "checker", None) is not wb.checker:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return reader.read(
            bearer=bearer, case_id=case_id, brief_version_id=brief_version_id,
            source_id=source_id, version_id=version_id)

    @router.get(base + "/sources/{source_id}/versions/{version_id}/original")
    def signed_original(
        case_id: str, brief_version_id: str, source_id: str, version_id: str,
        authorization: Annotated[str | None, Header()] = None,
    ) -> Response:
        """Verified original bytes: authorized, digest-bound, never inline."""
        bearer, wb = bench(authorization)
        item = _original(wb, bearer, case_id, brief_version_id, source_id, version_id)
        return Response(
            item.data, media_type="application/octet-stream",
            headers={
                "Content-Disposition": "attachment; filename=caseproof-original",
                "X-Content-Type-Options": "nosniff",
                "X-CaseProof-Original-SHA256": item.sha256_hex,
                "X-CaseProof-Original-Media-Type": item.media_type,
            })

    @router.get(base + "/sources/{source_id}/versions/{version_id}/pages/{pdf_page}")
    def signed_original_page(
        case_id: str, brief_version_id: str, source_id: str, version_id: str,
        pdf_page: int, authorization: Annotated[str | None, Header()] = None,
    ) -> Response:
        """Physical-page PNG of the verified original: a rendering, not a verdict."""
        bearer, wb = bench(authorization)
        item = _original(wb, bearer, case_id, brief_version_id, source_id, version_id)
        if item.media_type != "application/pdf":
            raise HTTPException(status_code=404, detail="physical_page_unavailable")
        try:
            png = render_pdf_page(item.data, page_number=pdf_page)
        except OCRUnavailable as exc:
            if str(exc) in {"crop_rasterizer_unavailable", "crop_pillow_unavailable"}:
                raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
            raise HTTPException(status_code=404, detail="physical_page_unavailable") from None
        return Response(png, media_type="image/png", headers={
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "X-CaseProof-Original-SHA256": item.sha256_hex,
            "X-CaseProof-Physical-Page": str(pdf_page)})

    @router.get(base + "/review")
    def signed_review_state(
        case_id: str, brief_version_id: str,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        bearer, wb = bench(authorization)
        return wb.workspace.state(
            bearer=bearer, case_id=case_id, brief_version_id=brief_version_id)

    @router.post(base + "/review")
    def signed_review_record(
        case_id: str, brief_version_id: str, body: ReviewBody,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        bearer, wb = bench(authorization)
        if not body.rationale.strip():
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        return wb.workspace.record(
            bearer=bearer, case_id=case_id, brief_version_id=brief_version_id,
            command=ReviewCommand(
                snapshot_hash=body.snapshot_hash, observation_id=body.observation_id,
                request_id=UUID(body.request_id), expected_revision=body.expected_revision,
                disposition=ReviewDisposition(body.disposition), rationale=body.rationale,
            ),
        )

    @router.post(base + "/correction-preview")
    def signed_correction_preview(
        case_id: str, brief_version_id: str, body: CorrectionPreviewBody,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        """Pure bounded preview against the CURRENT verified representation.

        Persisting is a separate, explicit step: upload the corrected file
        through the signed upload route, publish it as a new brief version,
        then re-check that new version. This route writes nothing.
        """
        bearer, wb = bench(authorization)
        subject = wb.checker._verified(bearer)
        scope = wb.checker._scope(subject, case_id)
        try:
            bundle = wb.store.load_bundle(
                case_id=case_id, brief_version_id=brief_version_id, access=scope)
        except Exception:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        run = wb.checker.check(
            bearer=bearer, case_id=case_id, brief_version_id=brief_version_id)
        if run.snapshot_hash != body.snapshot_hash:
            raise AccessRejected(AccessFailure.STALE_SNAPSHOT)
        text = bundle.representation.text
        start, end = body.start, body.end
        if start is None or end is None:
            if text.count(body.before) != 1:
                raise AccessRejected(AccessFailure.STALE_SNAPSHOT)
            start = text.index(body.before)
            end = start + len(body.before)
        try:
            proposal = CorrectionProposal(
                body.observation_id, subject.subject_id, run.snapshot_hash,
                brief_version_id, run.representation_sha256, start, end,
                body.before, body.after, body.rationale)
            preview = preview_correction(
                run=run, text=text, proposal=proposal)
        except Exception:
            # Changed range, unknown observation or stale text: never guess.
            raise AccessRejected(AccessFailure.STALE_SNAPSHOT) from None
        return {
            "schema": "caseproof-signed-correction-preview-v1",
            "brief_version_id": brief_version_id,
            "invalidates_check_hash": preview.invalidates_check_hash,
            "old_text_sha256": preview.old_text_sha256,
            "proposed_text_sha256": preview.proposed_text_sha256,
            "proposed_text": preview.proposed_text,
            "requires_new_brief_version": True,
            "persisted": False,
            "note": _NOTE,
        }

    return router


