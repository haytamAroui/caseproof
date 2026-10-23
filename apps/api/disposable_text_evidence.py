"""Resolve one persisted text anchor against actual private original bytes.

Internal disposable composition ONLY: the caller must authorize the parent,
source intent and cursor independently. No HTTP route, user authentication,
approved finding, semantic support or production writer is implemented here.
The first parser is deliberately identity UTF-8: representation bytes equal
the preserved original, so the existing Vault stores them once. Other parser
outputs require a separately reviewed immutable representation-byte binding.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from apps.api.evidence_locator_codec import (
    ExpectedEvidenceParent,
    StoredLocatorError,
    validate_against_verified_bytes,
)
from apps.api.evidence_vault_protocol import MAX_REFERENCE_BYTES, VaultCoordinator, VaultScope
from apps.api.postgres_evidence_reader import (
    EvidenceCursor,
    EvidenceRowNotFound,
    get_exact_anchor_metadata,
)
from packages.evidence_kernel.domain.anchors import TEXT_BASIS, AnchorResolver, TextSpan
from packages.evidence_kernel.domain.fidelity import (
    ExactQuote,
    FidelityAssessment,
    FidelityEvaluator,
    FindingRevision,
)
from packages.evidence_kernel.domain.source_versions import (
    DerivedRepresentation,
    InMemorySourceRegistry,
    SourceVersion,
)

TRANSFORM_NAME = "identity_utf8"
TRANSFORM_VERSION = "1"
CONFIG_BYTES = b'{"encoding":"utf-8","normalization":"none"}'
CONFIG_SHA256 = sha256(CONFIG_BYTES).hexdigest()

# Bind parser metadata to the SAME physical source version as the exact scoped
# Vault intent. A matching hash alone cannot substitute another source/version.
SQL_TEXT_LINEAGE = """
select v.ingested_at, v.media_type as source_media_type, v.byte_length,
       r.created_at, r.media_type, r.transform_name, r.transform_version,
       r.transform_config_sha256, r.coordinate_convention,
       l.layout_manifest, l.layout_sha256_hex
from caseproof.s2_008a_representations r
join caseproof.s2_008a_source_logical_ids d
  on d.org_id=r.org_id and d.case_id=r.case_id and d.document_pk=r.document_pk
join caseproof.s2_008a_version_logical_ids k
  on k.org_id=r.org_id and k.case_id=r.case_id and k.document_pk=r.document_pk
 and k.version_pk=r.version_pk and k.kernel_version_id=r.kernel_version_id
 and k.source_sha256_hex=r.source_sha256_hex
join caseproof.document_versions v
  on v.org_id=r.org_id and v.document_id=r.document_pk and v.id=r.version_pk
 and v.original_sha256_hex=r.source_sha256_hex
join caseproof.s2_008a_layouts l
  on l.org_id=r.org_id and l.case_id=r.case_id and l.representation_pk=r.representation_pk
join caseproof._s2_009b_vault_intents i
  on i.org_id=r.org_id and i.case_id=r.case_id and i.document_id=r.document_pk
 and i.document_version_id=r.version_pk and i.sha256_hex=r.source_sha256_hex
 and i.byte_length=v.byte_length and i.media_type=v.media_type
where r.org_id=%(org_id)s::uuid and r.case_id=%(case_id)s::uuid
  and d.kernel_document_id=%(document_id)s and k.kernel_version_id=%(version_id)s
  and r.kernel_representation_id=%(representation_id)s
  and r.source_sha256_hex=%(source_sha256_hex)s
  and r.representation_sha256_hex=%(representation_sha256_hex)s
  and i.intent_id=%(intent_id)s::uuid and i.state='verified'
limit 2
"""


def identity_text_layout(data: bytes) -> dict[str, object]:
    """Preserve Unicode, whitespace and line endings; never fabricate offsets."""
    if type(data) is not bytes or not 0 < len(data) <= MAX_REFERENCE_BYTES:
        raise StoredLocatorError("bounded nonempty UTF-8 source required")
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise StoredLocatorError("source is not UTF-8") from exc
    return {"normalization": "none", "codepoints": len(text)}


def layout_digest(layout: Mapping[str, object]) -> str:
    canonical = json.dumps(layout, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(canonical.encode("utf-8")).hexdigest()


def _timestamp(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise StoredLocatorError("persisted timezone-aware timestamp required")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class TextEvidenceRead:
    """Fidelity to exact captured bytes; no support or approval authority."""

    source: SourceVersion
    representation: DerivedRepresentation
    fidelity: FidelityAssessment

    @property
    def eligibility_established(self) -> bool:
        return False


def read_disposable_text_evidence(
    cursor: EvidenceCursor, *, vault: VaultCoordinator,
    expected: ExpectedEvidenceParent, source_intent_id: UUID,
    anchor_id: str, finding: FindingRevision, quote: ExactQuote,
) -> TextEvidenceRead:
    """Rehydrate immutable records per read; never treat a warm cache as proof.

    Current availability is checked through Vault before and after resolution.
    This best-effort read is not an atomic approval/export snapshot or a real
    user authorization boundary. The inherited disposable metadata reader has
    no actor verification. Never construct expected from the retrieved row.
    """
    if not isinstance(expected, ExpectedEvidenceParent):
        raise StoredLocatorError("independently selected parent required")
    if not isinstance(source_intent_id, UUID) or source_intent_id.int == 0:
        raise StoredLocatorError("independently selected source intent required")
    metadata = get_exact_anchor_metadata(cursor, expected=expected, anchor_id=anchor_id)
    anchor = metadata.anchor
    if not isinstance(anchor.locator, TextSpan) or anchor.locator.normalization != "none":
        raise StoredLocatorError("identity UTF-8 text-span contract required")
    scope = VaultScope(expected.org_id, expected.case_id)
    source_bytes = vault.read(scope=scope, intent_id=source_intent_id)
    layout = identity_text_layout(source_bytes)
    cursor.execute(SQL_TEXT_LINEAGE, {
        "org_id": str(expected.org_id), "case_id": str(expected.case_id),
        "document_id": expected.document_id, "version_id": expected.version_id,
        "representation_id": expected.representation_id,
        "source_sha256_hex": expected.source_sha256_hex,
        "representation_sha256_hex": expected.representation_sha256_hex,
        "intent_id": str(source_intent_id),
    })
    row = cursor.fetchone()
    if row is None:
        raise EvidenceRowNotFound("evidence unavailable")
    keys = {
        "ingested_at", "source_media_type", "byte_length", "created_at", "media_type",
        "transform_name", "transform_version", "transform_config_sha256",
        "coordinate_convention", "layout_manifest", "layout_sha256_hex",
    }
    if not isinstance(row, Mapping) or set(row) != keys or cursor.fetchone() is not None:
        raise StoredLocatorError("ambiguous or unsupported text lineage")
    stored_layout = row["layout_manifest"]
    if (type(stored_layout) is not dict or set(stored_layout) != {"normalization", "codepoints"}
            or type(stored_layout["codepoints"]) is not int):
        raise StoredLocatorError("invalid persisted text layout types")
    if (
        row["source_media_type"] != "text/plain" or row["media_type"] != "text/plain"
        or type(row["byte_length"]) is not int or row["byte_length"] != len(source_bytes)
        or row["transform_name"] != TRANSFORM_NAME
        or row["transform_version"] != TRANSFORM_VERSION
        or row["transform_config_sha256"] != CONFIG_SHA256
        or row["coordinate_convention"] != TEXT_BASIS
        or row["layout_manifest"] != layout
        or row["layout_sha256_hex"] != layout_digest(layout)
        or expected.representation_sha256_hex != expected.source_sha256_hex
    ):
        raise StoredLocatorError("unsupported or inconsistent identity parser lineage")
    validate_against_verified_bytes(
        anchor, source_bytes=source_bytes, representation_bytes=source_bytes,
        coordinate_basis=TEXT_BASIS,
    )
    source = SourceVersion(
        document_id=expected.document_id, version_id=expected.version_id,
        sha256_hex=expected.source_sha256_hex, content=source_bytes,
        ingested_at=_timestamp(row["ingested_at"]), media_type="text/plain",
    )
    representation = DerivedRepresentation(
        representation_id=expected.representation_id, document_id=expected.document_id,
        version_id=expected.version_id, source_sha256_hex=expected.source_sha256_hex,
        sha256_hex=expected.representation_sha256_hex, content=source_bytes,
        media_type="text/plain", transform_name=TRANSFORM_NAME,
        transform_version=TRANSFORM_VERSION, transform_config_sha256=CONFIG_SHA256,
        coordinate_convention=TEXT_BASIS, created_at=_timestamp(row["created_at"]),
    )
    # Transient Kernel objects hydrate the persisted graph. They are not a
    # parallel authoritative source registry or a persisted approval state.
    namespace = f"{scope.org_id}:{scope.case_id}"
    registry = InMemorySourceRegistry()
    registry.register_source(namespace, source)
    registry.register_representation(namespace, representation)
    fidelity = FidelityEvaluator(AnchorResolver(registry)).evaluate(namespace, finding, anchor, quote)
    if vault.read(scope=scope, intent_id=source_intent_id) != source_bytes:
        raise StoredLocatorError("source changed during evidence read")
    return TextEvidenceRead(source, representation, fidelity)
