"""S2-008a3: read-only *disposable-proposal* evidence graph metadata adapter.

Not wired to FastAPI, Supabase, user sessions, or production PostgreSQL.
The caller MUST independently obtain and authorize ExpectedEvidenceParent
from a trusted server-side context. Supplying one from client JSON, or
constructing it from the retrieved anchor, defeats the scope boundary.

The join proves consistent persisted IDs and types. It does NOT verify
original bytes, storage availability, evidence authenticity, source fidelity,
semantic support, human reviewer identity, or promote an assessment.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from apps.api.evidence_locator_codec import (
    ExpectedEvidenceParent,
    StoredLocatorError,
    decode_anchor_projection,
)
from packages.evidence_kernel.domain.anchors import (
    JSON_BASIS,
    PDF_BASIS,
    SHEET_BASIS,
    TEXT_BASIS,
    EvidenceAnchor,
)

# Explicit composite joins even where FK constraints already exist. A
# same-organization/different-case document must NEVER be accepted.
# Named DB-API parameters; no string substitution for runtime identifiers.
SQL_SELECT_EXACT_ANCHOR = """
select
    a.org_id::text as org_id,
    a.case_id::text as case_id,
    a.kernel_anchor_id,
    d.kernel_document_id,
    v.kernel_version_id,
    r.kernel_representation_id,
    a.source_sha256_hex,
    a.representation_sha256_hex,
    a.locator_kind,
    a.locator_schema_version,
    a.locator,
    r.coordinate_convention as coordinate_basis,
    l.layout_kind
from caseproof.s2_008a_anchors as a
join caseproof.s2_008a_representations as r
  on r.org_id = a.org_id and r.case_id = a.case_id
 and r.document_pk = a.document_pk and r.version_pk = a.version_pk
 and r.representation_pk = a.representation_pk
 and r.source_sha256_hex = a.source_sha256_hex
 and r.representation_sha256_hex = a.representation_sha256_hex
join caseproof.s2_008a_layouts as l
  on l.org_id = a.org_id and l.case_id = a.case_id
 and l.representation_pk = a.representation_pk
join caseproof.s2_008a_version_logical_ids as v
  on v.org_id = a.org_id and v.case_id = a.case_id
 and v.document_pk = a.document_pk and v.version_pk = a.version_pk
 and v.kernel_version_id = r.kernel_version_id
 and v.source_sha256_hex = a.source_sha256_hex
join caseproof.s2_008a_source_logical_ids as d
  on d.org_id = a.org_id and d.case_id = a.case_id
 and d.document_pk = a.document_pk
join caseproof.documents as physical_doc
  on physical_doc.org_id = a.org_id
 and physical_doc.case_id = a.case_id
 and physical_doc.id = a.document_pk
join caseproof.document_versions as physical_version
  on physical_version.org_id = a.org_id
 and physical_version.document_id = a.document_pk
 and physical_version.id = a.version_pk
 and physical_version.original_sha256_hex = a.source_sha256_hex
where
 a.org_id = %(org_id)s::uuid
 and a.case_id = %(case_id)s::uuid
 and a.kernel_anchor_id = %(anchor_id)s
 and d.kernel_document_id = %(document_id)s
 and v.kernel_version_id = %(version_id)s
 and r.kernel_representation_id = %(representation_id)s
 and a.source_sha256_hex = %(source_sha256_hex)s
 and a.representation_sha256_hex = %(representation_sha256_hex)s
limit 2
"""

_KINDS = {
    "text_span": ("text", TEXT_BASIS),
    "pdf_region": ("pdf", PDF_BASIS),
    "sheet_range": ("spreadsheet", SHEET_BASIS),
    "structured_field": ("structured", JSON_BASIS),
}

_PROJECTION_KEYS = frozenset({
    "org_id", "case_id", "kernel_anchor_id", "kernel_document_id",
    "kernel_version_id", "kernel_representation_id",
    "source_sha256_hex", "representation_sha256_hex",
    "locator_kind", "locator_schema_version", "locator",
})
_ROW_KEYS = _PROJECTION_KEYS | {"coordinate_basis", "layout_kind"}


class EvidenceRowNotFound(LookupError):
    """Masked missing, foreign, or stale evidence identity."""


class EvidenceCursor(Protocol):
    """Dict-row DB-API cursor; app composition must choose a trusted DB role."""

    def execute(self, query: str, params: Mapping[str, str]) -> object: ...
    def fetchone(self) -> Mapping[str, object] | None: ...


@dataclass(frozen=True, slots=True)
class UnverifiedEvidenceMetadata:
    """Reconstructed locator metadata, explicitly NOT citation resolution."""

    anchor: EvidenceAnchor
    coordinate_basis: str
    layout_kind: str

    @property
    def eligibility_established(self) -> bool:
        """Always false: source bytes, authorizations, and reviews are absent."""
        return False


def get_exact_anchor_metadata(
    cursor: EvidenceCursor, *,
    expected: ExpectedEvidenceParent,
    anchor_id: str,
) -> UnverifiedEvidenceMetadata:
    """Query exact server-chosen parent; fail closed on foreign/stale revisions.

    A caller-constructed ExpectedEvidenceParent is not authentication. Never
    register this function in an HTTP route or use a privileged pooled
    connection without independently reviewed identity and tenancy gates.
    """
    if not isinstance(expected, ExpectedEvidenceParent):
        raise StoredLocatorError("independently authorized parent required")
    if type(anchor_id) is not str or not 1 <= len(anchor_id) <= 256 or not anchor_id.strip():
        raise StoredLocatorError("bounded anchor identity required")
    cursor.execute(SQL_SELECT_EXACT_ANCHOR, {
        "org_id": str(expected.org_id),
        "case_id": str(expected.case_id),
        "anchor_id": anchor_id,
        "document_id": expected.document_id,
        "version_id": expected.version_id,
        "representation_id": expected.representation_id,
        "source_sha256_hex": expected.source_sha256_hex,
        "representation_sha256_hex": expected.representation_sha256_hex,
    })
    row = cursor.fetchone()
    if row is None:
        raise EvidenceRowNotFound("evidence unavailable")
    if not isinstance(row, Mapping) or set(row) != _ROW_KEYS:
        raise StoredLocatorError("unexpected stored evidence projection")
    if row["kernel_anchor_id"] != anchor_id:
        raise StoredLocatorError("queried anchor identity mismatch")
    kind = row["locator_kind"]
    if kind not in _KINDS:
        raise StoredLocatorError("unsupported stored locator kind")
    layout_kind, basis = _KINDS[kind]
    if row["layout_kind"] != layout_kind or row["coordinate_basis"] != basis:
        raise StoredLocatorError("layout/coordinate convention mismatch")
    return UnverifiedEvidenceMetadata(
        anchor=decode_anchor_projection(
            {key: row[key] for key in _PROJECTION_KEYS}, expected
        ),
        coordinate_basis=basis,
        layout_kind=layout_kind,
    )
