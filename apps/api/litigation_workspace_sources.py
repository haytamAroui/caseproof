"""Signed, brief-bound evidence inventory for the ClearBrief lawyer workbench.

Uses the *same* authorized source snapshot as the M2 checker, not a second
caller-selected source list. An indexed preview is only represented text; no
source authenticity, semantic claim support or legal conclusion is implied.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.litigation_check_service import AuthorizedLitigationChecker
from apps.api.litigation_evidence_app import _token
from apps.api.litigation_evidence_search import AuthorizedEvidenceSearch


class SignedBriefSources:
    def __init__(self, checker: AuthorizedLitigationChecker) -> None:
        self.checker = checker

    def _bundle(self, *, bearer: str, case_id: str, brief_version_id: str):
        if any(type(x) is not str or not 0 < len(x) <= 128
               for x in (case_id, brief_version_id)):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        subject = self.checker._verified(bearer)
        scope = self.checker._scope(subject, case_id)
        AuthorizedEvidenceSearch._require_evidence(scope)
        try:
            bundle = self.checker.store.load_bundle(
                case_id=case_id, brief_version_id=brief_version_id, access=scope,
            )
            if (bundle.representation.brief.case_id != case_id
                    or bundle.representation.brief.version_id != brief_version_id
                    or len(bundle.previews) > 32):
                raise ValueError("source/brief mismatch")
            declared = set(bundle.source_scope.declared_source_versions)
            excluded = set(bundle.source_scope.excluded_source_versions)
            present = {(p.row.source_id,p.row.version_id) for p in bundle.previews}
            if (len(present) != len(bundle.previews) or not present <= declared
                    or present & excluded):
                raise ValueError("incoherent source universe")
            current = self.checker._scope(self.checker._verified(bearer), case_id)
            AuthorizedEvidenceSearch._require_evidence(current)
            if current != scope or not self.checker.store.still_current(
                access=current, bundle=bundle,
            ):
                raise ValueError("stale source or grant")
            return bundle
        except AccessRejected:
            raise
        except Exception:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None

    def inventory(self, *, bearer: str, case_id: str, brief_version_id: str) -> dict[str, Any]:
        bundle = self._bundle(bearer=bearer, case_id=case_id, brief_version_id=brief_version_id)
        rows = tuple(x.row for x in bundle.previews)
        expected = set(bundle.source_scope.declared_source_versions)
        processed = {(x.row.source_id,x.row.version_id) for x in bundle.previews
                     if x.row.status=="ready" and not x.row.warnings and x.row.representation_id}
        missing = expected - processed
        incomplete = sum(x.row.status != "ready" or bool(x.row.warnings) for x in bundle.previews)
        excluded = bundle.source_scope.excluded_source_versions
        return {
            "schema": "caseproof-clearbrief-brief-sources-v1",
            "case_id": case_id,
            "brief_version_id": brief_version_id,
            "rows": [asdict(x) for x in rows],
            "complete": not missing and not excluded and len(rows)==len(expected),
            "failed_count": sum(x.status=="failed" for x in rows),
            "partial_count": incomplete+len(expected-{(x.source_id,x.version_id) for x in rows}),
            "declared": sorted(expected),
            "excluded": sorted(excluded),
        }

    def preview(
        self, *, bearer: str, case_id: str, brief_version_id: str, source_id: str,
    ) -> dict[str, Any]:
        bundle = self._bundle(bearer=bearer, case_id=case_id, brief_version_id=brief_version_id)
        matches = [x for x in bundle.previews if x.row.source_id==source_id]
        if len(matches)!=1:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        preview = matches[0]
        if len(preview.text) > 120_000 or len(preview.spans) > 4096:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return {
            "schema": "caseproof-clearbrief-brief-source-preview-v1",
            "case_id": case_id, "brief_version_id": brief_version_id,
            "row": asdict(preview.row),
            "text": preview.text,
            "spans": preview.spans,
            "claim_support": "not_assessed",
        }


def create_clearbrief_sources_router(checker: AuthorizedLitigationChecker | None = None) -> APIRouter:
    router = APIRouter()
    sources = SignedBriefSources(checker) if checker is not None else None
    base = "/v2/matters/{case_id}/briefs/{brief_version_id}/sources"

    @router.get(base)
    def inventory(
        case_id: str, brief_version_id: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        if sources is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return sources.inventory(
            bearer=_token(authorization), case_id=case_id, brief_version_id=brief_version_id,
        )

    @router.get(base + "/{source_id}")
    def preview(
        case_id: str, brief_version_id: str, source_id: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        if sources is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return sources.preview(
            bearer=_token(authorization), case_id=case_id,
            brief_version_id=brief_version_id, source_id=source_id,
        )
    return router
