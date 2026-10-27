"""Unreleased source-bound original retrieval; not a production storage adapter."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.litigation_check_service import AuthorizedLitigationChecker, PrivateMatterAccess
from apps.api.litigation_evidence_search import AuthorizedEvidenceSearch
from apps.api.signed_supabase_originals import OriginalRef, SignedOriginalsStorage


@dataclass(frozen=True, slots=True)
class Original:
    data: bytes = field(repr=False)
    sha256_hex: str
    media_type: str


class OriginalPort(Protocol):
    def read(self, *, access: PrivateMatterAccess, source_id: str, version_id: str) -> Original: ...


class AuthorizedOriginalReader:
    """Read originals only from the server-owned, confirmed source snapshot."""

    def __init__(
        self, checker: AuthorizedLitigationChecker,
        originals: OriginalPort | SignedOriginalsStorage,
    ) -> None:
        self.checker = checker
        self.originals = originals

    def read(self, *, bearer: str, case_id: str, brief_version_id: str,
             source_id: str, version_id: str) -> Original:
        ids = (case_id, brief_version_id, source_id, version_id)
        if any(type(value) is not str or not 0 < len(value) <= 128 for value in ids):
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        subject = self.checker._verified(bearer)
        scope = self.checker._scope(subject, case_id)
        AuthorizedEvidenceSearch._require_evidence(scope)
        try:
            bundle = self.checker.store.load_bundle(
                case_id=case_id, brief_version_id=brief_version_id, access=scope,
            )
            key = (source_id, version_id)
            if (bundle.representation.brief.case_id != case_id
                    or bundle.representation.brief.version_id != brief_version_id
                    or key not in bundle.source_scope.declared_source_versions
                    or key in bundle.source_scope.excluded_source_versions):
                raise AccessRejected(AccessFailure.RESOURCE_MASKED)
            matches = [p for p in bundle.previews if (p.row.source_id, p.row.version_id) == key]
            if len(matches) != 1:
                raise AccessRejected(AccessFailure.RESOURCE_MASKED)
            # For the live Supabase backend, reuse the verified caller's JWT
            # against Storage RLS and derive the path ONLY from the trusted,
            # already source-bound evidence preview and current scope.
            if isinstance(self.originals, SignedOriginalsStorage):
                row = matches[0].row
                original_ref = OriginalRef(
                    UUID(scope.org_id), UUID(scope.case_id), UUID(row.document_id),
                    UUID(row.version_id), row.original_sha256, row.media_type,
                )
                payload = self.originals.get_verified(original_ref, bearer)
                original = Original(payload, row.original_sha256, row.media_type)
            else:
                original = self.originals.read(
                    access=scope, source_id=source_id, version_id=version_id,
                )
            if (not isinstance(original, Original) or type(original.data) is not bytes
                    or not 0 < len(original.data) <= 5_242_880
                    or original.media_type not in {"application/pdf", "text/plain"}
                    or original.sha256_hex != matches[0].row.original_sha256
                    or hashlib.sha256(original.data).hexdigest() != original.sha256_hex):
                raise ValueError("original is unavailable or inconsistent")
            current = self.checker._scope(self.checker._verified(bearer), case_id)
            AuthorizedEvidenceSearch._require_evidence(current)
            if current != scope or not self.checker.store.still_current(access=current, bundle=bundle):
                raise ValueError("source or permission snapshot changed")
            return original
        except AccessRejected:
            raise
        except Exception:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
