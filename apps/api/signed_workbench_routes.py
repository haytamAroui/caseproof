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

from collections.abc import Callable
from dataclasses import asdict
from typing import Annotated, Any, Protocol
from uuid import UUID

from fastapi import APIRouter, Header
from pydantic import BaseModel, ConfigDict, Field

from application.litigation.review_cycle import CorrectionProposal, preview_correction
from application.litigation.unified_review import ReviewDisposition
from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.litigation_check_service import AuthorizedLitigationChecker
from apps.api.litigation_evidence_app import _token
from apps.api.litigation_review_app import ReviewBody
from apps.api.litigation_review_workspace import ReviewCommand, SignedReviewWorkspace
from apps.api.litigation_workspace_sources import SignedBriefSources

__all__ = ["create_signed_workbench_router"]

_NOTE = (
    "Candidate differences compare typed values in one verified source passage. "
    "They are not legal conclusions, not approval and not a filing decision."
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


def _corpus_for(wb: Any, case_id: str) -> Any:
    provider = getattr(wb.checker, "legal_corpus_for", None)
    return provider(case_id) if callable(provider) else None


def create_signed_workbench_router(
    factory: Callable[[str], _Workbench] | None,
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
            "corpus_articles": len(config.records) if config is not None else 0,
            "corpus_failures": list(config.failures) if config is not None else [],
            "references": [
                {**asdict(x), "observation_id": f"legal:{x.reference_id}",
                 "claim_support": "not_assessed"} for x in run.legal_observations
            ],
        }

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
        return {
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


