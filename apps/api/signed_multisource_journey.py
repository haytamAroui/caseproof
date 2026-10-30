"""Signed matter-scoped inventory + N exhibit Storage journey.

Each source must already have a server-registered immutable OriginalRef.
This adapter never issues grants, registers source rows or uses service keys.
"""

from dataclasses import dataclass

from apps.api.signed_supabase_originals import OriginalRef, SignedOriginalsStorage
from domains.disputes.multisource_manifest import MultiSourceManifest, SourceRole


@dataclass(frozen=True, slots=True)
class SignedMultiSourceJourney:
    storage: SignedOriginalsStorage

    def upload_and_verify(
        self,
        *,
        manifest: MultiSourceManifest,
        refs: dict[str, OriginalRef],
        payloads: dict[str, bytes],
        bearer: str,
    ) -> None:
        """Fail closed before writes on any missing or cross-matter reference.

        Registration and permission checks remain server-side. The signed
        Storage policy enforces live matter permissions on each operation.
        """
        versions = {item.document_version_id for item in manifest.all_sources}
        if set(refs) != versions or set(payloads) != versions:
            raise ValueError("exact inventory and exhibit source set required")
        for item in manifest.all_sources:
            ref = refs[item.document_version_id]
            if str(ref.case_id) != manifest.matter_id or str(ref.version_id) != item.document_version_id:
                raise ValueError("source not bound to requested matter/version")
            if ref.sha256_hex != item.sha256:
                raise ValueError("source manifest and registered digest disagree")
        for item in manifest.all_sources:
            ref = refs[item.document_version_id]
            self.storage.put_once(ref, bearer, payloads[item.document_version_id])
            self.storage.get_verified(ref, bearer)

    def reopen_verified(
        self, *, manifest: MultiSourceManifest,
        refs: dict[str, OriginalRef], bearer: str,
    ) -> tuple[bytes, ...]:
        """Reopen all immutable originals with fresh signed read authorization."""
        versions = {item.document_version_id for item in manifest.all_sources}
        if set(refs) != versions:
            raise ValueError("exact inventory and exhibit source set required")
        for item in manifest.all_sources:
            ref = refs[item.document_version_id]
            if str(ref.case_id) != manifest.matter_id or str(ref.version_id) != item.document_version_id or ref.sha256_hex != item.sha256:
                raise ValueError("cross-matter, cross-version or stale digest")
        return tuple(self.storage.get_verified(refs[item.document_version_id], bearer) for item in manifest.all_sources)
