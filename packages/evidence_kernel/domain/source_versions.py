"""KRN-101: immutable source bytes and versioned derived representations.

This is a pure-Python, in-memory reference implementation. A trusted application
boundary must authenticate and authorize the tenant scope; these primitives
provide namespace isolation, NOT production authorization or durable storage.

Hashes establish consistency with captured bytes, not authenticity or truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from hashlib import sha256
from threading import RLock


class SourceVersionError(ValueError):
    """A source or its provenance violates the immutable version contract."""


class SourceRecordConflict(SourceVersionError):
    """An immutable source or representation identity is already occupied."""


class SourceRecordNotFound(KeyError):
    """No record is available in the authorized tenant namespace."""


def _identity(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise SourceVersionError(f"{name} must be nonempty")


def _digest(value: str, content: bytes, name: str) -> None:
    if not isinstance(content, bytes):
        raise SourceVersionError("source or representation content must be bytes")
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
        or sha256(content).hexdigest() != value
    ):
        raise SourceVersionError(f"{name} digest does not match immutable bytes")


def _digest_format(value: str, name: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise SourceVersionError(f"{name} digest must be lowercase SHA-256 hex")


def _utc_instant(value: datetime, name: str) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() != timedelta(0)
    ):
        raise SourceVersionError(f"{name} must be a timezone-aware UTC datetime")


@dataclass(frozen=True, slots=True)
class SourceVersion:
    """One immutable capture of exact source bytes; not an authenticity claim."""

    document_id: str
    version_id: str
    sha256_hex: str
    content: bytes = field(repr=False)
    ingested_at: datetime
    media_type: str

    def __post_init__(self) -> None:
        _identity(self.document_id, "document_id")
        _identity(self.version_id, "version_id")
        _identity(self.media_type, "media_type")
        _digest(self.sha256_hex, self.content, "source")
        _utc_instant(self.ingested_at, "ingested_at")


@dataclass(frozen=True, slots=True)
class DerivedRepresentation:
    """Exact bytes and transformation lineage of a parser/OCR output.

    Any new parser/OCR output requires a fresh representation_id. Existing
    representation IDs never implicitly track new versions or transform output.
    Coordinate conventions describe the locator basis for future typed anchors.
    """

    representation_id: str
    document_id: str
    version_id: str
    source_sha256_hex: str
    sha256_hex: str
    content: bytes = field(repr=False)
    media_type: str
    transform_name: str
    transform_version: str
    transform_config_sha256: str
    coordinate_convention: str
    created_at: datetime

    def __post_init__(self) -> None:
        for name in (
            "representation_id",
            "document_id",
            "version_id",
            "media_type",
            "transform_name",
            "transform_version",
            "coordinate_convention",
        ):
            _identity(getattr(self, name), name)
        _digest_format(self.source_sha256_hex, "parent source")
        _digest_format(self.transform_config_sha256, "transform configuration")
        _digest(self.sha256_hex, self.content, "representation")
        _utc_instant(self.created_at, "created_at")


@dataclass
class InMemorySourceRegistry:
    """Thread-safe, tenant-keyed prototype; NOT authentication or durable audit.

    tenant_scope MUST be supplied by a trusted application boundary, never from
    client-controlled headers or form fields. Duplicate IDs are rejected even
    when the new record is byte-for-byte identical.
    """

    _sources: dict[tuple[str, str, str], SourceVersion] = field(default_factory=dict)
    _representations: dict[tuple[str, str], DerivedRepresentation] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    @staticmethod
    def _scope(tenant_scope: str) -> str:
        _identity(tenant_scope, "tenant scope")
        return tenant_scope

    def register_source(self, tenant_scope: str, source: SourceVersion) -> SourceVersion:
        tenant = self._scope(tenant_scope)
        key = (tenant, source.document_id, source.version_id)
        with self._lock:
            if key in self._sources:
                raise SourceRecordConflict("source version already exists")
            self._sources[key] = source
        return source

    def get_source(self, tenant_scope: str, document_id: str, version_id: str) -> SourceVersion:
        tenant = self._scope(tenant_scope)
        with self._lock:
            source = self._sources.get((tenant, document_id, version_id))
            if source is None:
                raise SourceRecordNotFound("source version unavailable")
            return source

    def register_representation(
        self, tenant_scope: str, representation: DerivedRepresentation
    ) -> DerivedRepresentation:
        tenant = self._scope(tenant_scope)
        rep_key = (tenant, representation.representation_id)
        source_key = (tenant, representation.document_id, representation.version_id)
        with self._lock:
            parent = self._sources.get(source_key)
            if parent is None:
                raise SourceRecordNotFound("parent source version unavailable")
            if parent.sha256_hex != representation.source_sha256_hex:
                raise SourceVersionError("parent source digest mismatch")
            if rep_key in self._representations:
                raise SourceRecordConflict("representation identity already exists")
            self._representations[rep_key] = representation
        return representation

    def get_representation(
        self, tenant_scope: str, representation_id: str
    ) -> DerivedRepresentation:
        tenant = self._scope(tenant_scope)
        with self._lock:
            representation = self._representations.get((tenant, representation_id))
            if representation is None:
                raise SourceRecordNotFound("representation unavailable")
            return representation

    def get_representation_for_source(
        self, tenant_scope: str, document_id: str, version_id: str, representation_id: str
    ) -> DerivedRepresentation:
        """Fail closed if any part of an anchor's source identity differs."""
        representation = self.get_representation(tenant_scope, representation_id)
        if (
            representation.document_id != document_id
            or representation.version_id != version_id
        ):
            raise SourceRecordNotFound("representation unavailable for source version")
        return representation
