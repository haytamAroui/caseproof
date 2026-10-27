"""Unreleased private-matter lexical search over a versioned M2 source snapshot.

The caller supplies no sources or authorization decisions. This adapter requires
both draft:check and evidence:read and revalidates identity, grants and snapshot
before returning text. It is not mounted by the production/dev API.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from application.litigation.matter_policy import MatterPermission, authorize_matter
from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.litigation_check_service import AuthorizedLitigationChecker, PrivateMatterAccess
from domains.disputes.exhibits import ExhibitRegister, MappingState


@dataclass(frozen=True, slots=True)
class CitationCandidate:
    exhibit_id: str
    label: str
    pdf_page: int


def citation_candidate(register: ExhibitRegister, source_id: str, version_id: str,
                       physical_page: int | None) -> CitationCandidate | None:
    """Require a unique, confirmed label and exact physical page mapping."""
    if physical_page is None:
        return None
    candidates = []
    for entry in register.entries:
        if not entry.confirmed:
            continue
        resolution = register.resolve(entry.display_label, pdf_page=physical_page)
        if (resolution.state == MappingState.CONFIRMED and resolution.page is not None
                and resolution.page.source_id == source_id
                and resolution.page.version_id == version_id):
            candidates.append(CitationCandidate(entry.exhibit_id, entry.display_label, physical_page))
    return candidates[0] if len(candidates) == 1 else None


@dataclass(frozen=True, slots=True)
class SearchHit:
    source_id: str
    source_version_id: str
    representation_id: str
    source_sha256: str
    locator: str
    page: int | None
    text: str
    start: int
    end: int
    citation: CitationCandidate | None


@dataclass(frozen=True, slots=True)
class SearchResult:
    case_id: str
    brief_version_id: str
    exhibit_revision: int
    coverage: str
    omitted_sources: int
    hits: tuple[SearchHit, ...]


class AuthorizedEvidenceSearch:
    def __init__(self, checker: AuthorizedLitigationChecker) -> None:
        self.checker = checker

    @staticmethod
    def _require_evidence(scope: PrivateMatterAccess) -> None:
        try:
            verdict = authorize_matter(
                actor_id=scope.member.actor_id, org_id=scope.org_id, case_id=scope.case_id,
                action=MatterPermission.EVIDENCE_READ, membership=scope.member, grant=scope.grant,
            )
        except ValueError:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        if not verdict.allowed:
            raise AccessRejected(AccessFailure.PERMISSION_DENIED)

    def search(self, *, bearer: str, case_id: str, brief_version_id: str, query: str) -> SearchResult:
        if (type(query) is not str or not 2 <= len(query.strip()) <= 120
                or len(query.split()) > 16):
            raise ValueError("bounded search query required")
        if (type(case_id) is not str or not 0 < len(case_id) <= 128
                or type(brief_version_id) is not str or not 0 < len(brief_version_id) <= 128):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        subject = self.checker._verified(bearer)
        scope = self.checker._scope(subject, case_id)
        self._require_evidence(scope)
        try:
            bundle = self.checker.store.load_bundle(
                case_id=case_id, brief_version_id=brief_version_id, access=scope,
            )
            if (bundle.representation.brief.case_id != case_id
                    or bundle.representation.brief.version_id != brief_version_id):
                raise ValueError("invalid brief snapshot")
            declared = set(bundle.source_scope.declared_source_versions)
            excluded = set(bundle.source_scope.excluded_source_versions)
            seen: set[tuple[str, str]] = set()
            hits: list[SearchHit] = []
            query_folded = query.strip().casefold()
            omitted = 0
            for preview in bundle.previews:
                row = preview.row
                key = (row.source_id, row.version_id)
                if key in seen or key not in declared or key in excluded:
                    raise ValueError("invalid source scope")
                seen.add(key)
                if (row.status != "ready" or row.warnings or not row.representation_id
                        or not preview.spans):
                    omitted += 1
                    continue
                for start, end, locator, page_index in preview.spans:
                    if (type(start) is not int or type(end) is not int or start < 0
                            or end <= start or end > len(preview.text) or not locator
                            or (page_index is not None and
                                (type(page_index) is not int or page_index < 0))):
                        raise ValueError("invalid representation span")
                    passage = preview.text[start:end]
                    # Return an exact, bounded slice with its representation offsets.
                    # Search by literal text, never a semantic support assertion.
                    pos = passage.casefold().find(query_folded)
                    if pos < 0:
                        continue
                    # Casefold may change character count: locate using a direct
                    # case-insensitive regex that preserves original offsets.
                    match = re.search(re.escape(query.strip()), passage, re.IGNORECASE)
                    if match is None:
                        continue
                    left = max(0, match.start() - 160)
                    right = min(len(passage), match.end() + 160)
                    hits.append(SearchHit(
                        row.source_id, row.version_id, row.representation_id,
                        row.original_sha256, locator, None if page_index is None else page_index + 1,
                        passage[left:right], start + left, start + right,
                        citation_candidate(bundle.register, row.source_id, row.version_id,
                                           None if page_index is None else page_index + 1),
                    ))
                    if len(hits) >= 20:
                        break
                if len(hits) >= 20:
                    break
            # Missing/omitted sources and output truncation cannot be called complete.
            missing = len(declared - seen)
            omitted += missing
            complete = seen == declared and not excluded and not omitted and len(hits) < 20
            current = self.checker._scope(self.checker._verified(bearer), case_id)
            self._require_evidence(current)
            if current != scope or not self.checker.store.still_current(access=current, bundle=bundle):
                raise ValueError("source or permission snapshot changed")
            return SearchResult(case_id, brief_version_id, bundle.register.revision,
                                "complete" if complete else "partial", omitted, tuple(hits))
        except AccessRejected:
            raise
        except Exception:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
