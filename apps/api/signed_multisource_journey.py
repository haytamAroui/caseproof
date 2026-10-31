"""Signed matter-scoped inventory + N exhibit Storage journey.

Each source must already have a server-registered immutable OriginalRef.
This adapter never issues grants, registers source rows or uses service keys.
"""

from dataclasses import dataclass
from hashlib import sha256

from apps.api.signed_supabase_originals import (
    MAX_BYTES,
    OriginalRef,
    PrivateStorageExists,
    PrivateStorageIntegrityError,
    PrivateStorageOutcomeUnknown,
    SignedOriginalsStorage,
)
from domains.disputes.multisource_manifest import MultiSourceManifest


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
        # Validate *every* payload before the first irreversible write. Without
        # this pass, a corrupt third exhibit leaves two already-written objects.
        # This does not claim network-failure atomicity (Storage has no batch
        # transaction); reconciliation is still needed after OUTCOME_UNKNOWN.
        orgs = {ref.org_id for ref in refs.values()}
        if len(orgs) != 1:
            raise ValueError("sources span multiple organizations")
        for item in manifest.all_sources:
            payload = payloads[item.document_version_id]
            if not isinstance(payload, bytes) or not 0 < len(payload) <= MAX_BYTES:
                raise PrivateStorageIntegrityError("invalid original byte bounds")
            if sha256(payload).hexdigest() != item.sha256:
                raise PrivateStorageIntegrityError("source bytes disagree with manifest")
        for item in manifest.all_sources:
            ref = refs[item.document_version_id]
            try:
                self.storage.put_once(ref, bearer, payloads[item.document_version_id])
            except (PrivateStorageExists, PrivateStorageOutcomeUnknown):
                # Interrupted prior requests or a 409 on retry must never
                # overwrite the original or be trusted as success. A fresh
                # signed read plus the immutable SHA proves this exact
                # source is already present. Denials and hash mismatches fail.
                self.storage.get_verified(ref, bearer)
            else:
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
