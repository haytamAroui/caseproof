"""KRN-101: immutable source/derivative identity and tenant-scoped reference semantics."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from hashlib import sha256

import pytest

from packages.evidence_kernel.domain.source_versions import (
    DerivedRepresentation,
    InMemorySourceRegistry,
    SourceRecordConflict,
    SourceRecordNotFound,
    SourceVersion,
    SourceVersionError,
)

STAMP = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
BYTES = b"Signed by Alice on Tuesday."


def digest(content: bytes) -> str:
    return sha256(content).hexdigest()


def source(*, document_id: str = "d1", version_id: str = "v1", content: bytes = BYTES) -> SourceVersion:
    return SourceVersion(
        document_id=document_id,
        version_id=version_id,
        sha256_hex=digest(content),
        content=content,
        ingested_at=STAMP,
        media_type="application/pdf",
    )


def rep(
    *,
    representation_id: str = "ocr-1",
    document_id: str = "d1",
    version_id: str = "v1",
    source_sha256_hex: str = digest(BYTES),
    content: bytes = b"Signed by Alice on Tuesday.\n",
    transform_version: str = "2026.1",
    transform_config_sha256: str = digest(b"config-1"),
) -> DerivedRepresentation:
    return DerivedRepresentation(
        representation_id=representation_id,
        document_id=document_id,
        version_id=version_id,
        source_sha256_hex=source_sha256_hex,
        sha256_hex=digest(content),
        content=content,
        media_type="text/plain",
        transform_name="pdf-ocr",
        transform_version=transform_version,
        transform_config_sha256=transform_config_sha256,
        coordinate_convention="unicode_codepoint_zero_based_half_open",
        created_at=STAMP,
    )


def test_preserves_exact_source_bytes_and_digest() -> None:
    registry = InMemorySourceRegistry()
    original = source()
    assert registry.register_source("tenant-a", original) is original
    assert registry.get_source("tenant-a", "d1", "v1").content == BYTES
    assert registry.get_source("tenant-a", "d1", "v1").sha256_hex == digest(BYTES)


@pytest.mark.parametrize("content", [b"", b"\x00\xff\x80", b"e\xcc\x81", "é".encode()])
def test_source_integrity_covers_exact_bytes(content: bytes) -> None:
    assert source(content=content).sha256_hex == digest(content)


def test_changed_bytes_with_reused_digest_fail_closed() -> None:
    with pytest.raises(SourceVersionError, match="digest"):
        replace(source(), content=b"silently modified")
    with pytest.raises(SourceVersionError, match="digest"):
        replace(rep(), content=b"altered parser output")


def test_record_types_reject_mutation_and_do_not_expose_content_in_repr() -> None:
    original = source(content=b"private-customer-evidence")
    representation = rep(content=b"private-extracted-text")
    with pytest.raises(FrozenInstanceError):
        original.version_id = "v2"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        representation.transform_version = "new"  # type: ignore[misc]
    assert "private-customer-evidence" not in repr(original)
    assert "private-extracted-text" not in repr(representation)


def test_duplicate_version_cannot_overwrite_even_with_identical_bytes() -> None:
    registry = InMemorySourceRegistry()
    registry.register_source("tenant-a", source())
    with pytest.raises(SourceRecordConflict):
        registry.register_source("tenant-a", source())
    assert registry.get_source("tenant-a", "d1", "v1").content == BYTES


def test_document_revisions_are_distinct() -> None:
    registry = InMemorySourceRegistry()
    registry.register_source("tenant-a", source())
    registry.register_source("tenant-a", source(version_id="v2", content=b"Revised"))
    assert registry.get_source("tenant-a", "d1", "v1").content == BYTES
    assert registry.get_source("tenant-a", "d1", "v2").content == b"Revised"


def test_same_document_keys_allowed_across_scopes_without_data_leak() -> None:
    registry = InMemorySourceRegistry()
    registry.register_source("tenant-a", source())
    registry.register_source("tenant-b", source(content=b"tenant-b secret"))
    assert registry.get_source("tenant-a", "d1", "v1").content == BYTES
    assert registry.get_source("tenant-b", "d1", "v1").content == b"tenant-b secret"
    with pytest.raises(SourceRecordNotFound):
        registry.get_source("tenant-c", "d1", "v1")


def test_missing_scope_fails_closed_on_every_operation() -> None:
    registry = InMemorySourceRegistry()
    with pytest.raises(SourceVersionError, match="tenant"):
        registry.register_source("", source())
    with pytest.raises(SourceVersionError, match="tenant"):
        registry.get_source(" ", "d1", "v1")
    with pytest.raises(SourceVersionError, match="tenant"):
        registry.register_representation("", rep())
    with pytest.raises(SourceVersionError, match="tenant"):
        registry.get_representation("", "ocr-1")


def test_representation_requires_existing_exact_parent_source() -> None:
    registry = InMemorySourceRegistry()
    with pytest.raises(SourceRecordNotFound):
        registry.register_representation("tenant-a", rep())
    registry.register_source("tenant-a", source())
    with pytest.raises(SourceRecordNotFound):
        registry.register_representation("tenant-b", rep())
    with pytest.raises(SourceRecordNotFound):
        registry.register_representation("tenant-a", rep(version_id="v2"))


def test_representation_parent_hash_mismatch_rejected() -> None:
    registry = InMemorySourceRegistry()
    registry.register_source("tenant-a", source())
    with pytest.raises(SourceVersionError, match="parent"):
        registry.register_representation("tenant-a", rep(source_sha256_hex="a" * 64))
    with pytest.raises(SourceRecordNotFound):
        registry.get_representation("tenant-a", "ocr-1")


def test_reocr_requires_new_identity_and_preserves_earlier_representation() -> None:
    registry = InMemorySourceRegistry()
    registry.register_source("tenant-a", source())
    first = rep()
    second = rep(
        representation_id="ocr-2", content=b"Signed by Alice; Tuesday.",
        transform_version="2026.2",
    )
    registry.register_representation("tenant-a", first)
    registry.register_representation("tenant-a", second)
    assert registry.get_representation_for_source("tenant-a", "d1", "v1", "ocr-1") == first
    assert registry.get_representation_for_source("tenant-a", "d1", "v1", "ocr-2") == second
    assert registry.get_representation("tenant-a", "ocr-1").content == first.content
    with pytest.raises(SourceRecordConflict):
        registry.register_representation("tenant-a", replace(first, content=first.content))
    with pytest.raises(SourceRecordNotFound):
        registry.get_representation_for_source("tenant-a", "d1", "v2", "ocr-1")


def test_representation_id_cannot_be_reused_for_another_document() -> None:
    registry = InMemorySourceRegistry()
    registry.register_source("tenant-a", source())
    registry.register_source("tenant-a", source(document_id="d2"))
    registry.register_representation("tenant-a", rep())
    with pytest.raises(SourceRecordConflict):
        registry.register_representation("tenant-a", rep(document_id="d2"))


def test_same_representation_id_can_exist_under_other_tenant_but_not_leak() -> None:
    registry = InMemorySourceRegistry()
    registry.register_source("tenant-a", source())
    registry.register_source("tenant-b", source())
    registry.register_representation("tenant-a", rep())
    registry.register_representation("tenant-b", rep(content=b"other-tenant bytes"))
    assert registry.get_representation("tenant-b", "ocr-1").content == b"other-tenant bytes"
    assert registry.get_representation("tenant-a", "ocr-1").content != b"other-tenant bytes"
    with pytest.raises(SourceRecordNotFound):
        registry.get_representation("tenant-c", "ocr-1")


@pytest.mark.parametrize("field_name", ["document_id", "version_id", "media_type"])
def test_source_rejects_missing_identity_fields(field_name: str) -> None:
    with pytest.raises(SourceVersionError):
        replace(source(), **{field_name: "  "})


@pytest.mark.parametrize(
    "field_name",
    [
        "representation_id", "document_id", "version_id", "media_type",
        "transform_name", "transform_version", "coordinate_convention",
    ],
)
def test_derivative_rejects_missing_provenance_fields(field_name: str) -> None:
    with pytest.raises(SourceVersionError):
        replace(rep(), **{field_name: ""})


def test_invalid_hash_and_nonutc_time_fail_closed() -> None:
    with pytest.raises(SourceVersionError, match="digest"):
        replace(source(), sha256_hex="not-a-digest")
    with pytest.raises(SourceVersionError, match="digest"):
        replace(rep(), transform_config_sha256="bad")
    with pytest.raises(SourceVersionError, match="UTC"):
        replace(source(), ingested_at=datetime(2026, 10, 21))
    with pytest.raises(SourceVersionError, match="UTC"):
        replace(rep(), created_at=datetime(2026, 10, 21))


def test_invalid_blob_types_fail_closed() -> None:
    with pytest.raises(SourceVersionError, match="bytes"):
        replace(source(), content="text")  # type: ignore[arg-type]
    with pytest.raises(SourceVersionError, match="bytes"):
        replace(rep(), content=bytearray(b"text"))  # type: ignore[arg-type]


def test_old_v1_evidence_reference_contract_is_unchanged() -> None:
    from packages.evidence_kernel.domain.evidence import SourceReference
    from packages.evidence_kernel.domain.workflow import DocumentVersion

    assert SourceReference("d1", digest(BYTES), "quote").document_id == "d1"
    assert DocumentVersion("d1", "v1", digest(b"old"), "old").version_id == "v1"
