"""Fail-closed multi-source readback verification over a signed transport.

The caller supplies a matter-scoped, signed-user read function. Never use service
credentials here. This adapter checks every original before allowing processing.
"""

from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256

from domains.disputes.multisource_manifest import MultiSourceManifest, SourceItem


@dataclass(frozen=True, slots=True)
class VerifiedSource:
    item: SourceItem
    original: bytes


def verify_multisource_originals(
    manifest: MultiSourceManifest,
    *,
    authorized_version_ids: frozenset[str],
    signed_read_original: Callable[[str, str], bytes],
) -> tuple[VerifiedSource, ...]:
    """Verify all sources; never return a partial success on a failed member.

    The signed reader must enforce matter grants and revocation at read time.
    Manifest membership alone is not authorization.
    """
    manifest.assert_authorized(authorized_version_ids)
    verified: list[VerifiedSource] = []
    for item in manifest.all_sources:
        original = signed_read_original(manifest.matter_id, item.document_version_id)
        if not isinstance(original, bytes):
            raise ValueError("signed source read must return immutable bytes")
        if sha256(original).hexdigest() != item.sha256:
            raise ValueError("source SHA-256 mismatch")
        verified.append(VerifiedSource(item, original))
    return tuple(verified)
