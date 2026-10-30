"""Immutable multi-source intake contract for one inventory and N exhibit originals.

The manifest does not grant access or perform uploads. The signed transport must
independently authorize each source and verify its original-byte SHA-256.
"""

import re
from dataclasses import dataclass
from enum import StrEnum

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class SourceRole(StrEnum):
    INVENTORY = "inventory"
    EXHIBIT = "exhibit"


@dataclass(frozen=True, slots=True)
class SourceItem:
    document_version_id: str
    role: SourceRole
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.role, SourceRole):
            raise ValueError("source role required")
        if not isinstance(self.document_version_id, str) or not (1 <= len(self.document_version_id.strip()) <= 160):
            raise ValueError("bounded document version id required")
        if not isinstance(self.sha256, str) or _SHA256.fullmatch(self.sha256) is None:
            raise ValueError("lowercase SHA-256 required")


@dataclass(frozen=True, slots=True)
class MultiSourceManifest:
    matter_id: str
    inventory: SourceItem
    exhibits: tuple[SourceItem, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.matter_id, str) or not (1 <= len(self.matter_id.strip()) <= 160):
            raise ValueError("matter id required")
        if self.inventory.role is not SourceRole.INVENTORY:
            raise ValueError("inventory role required")
        if not isinstance(self.exhibits, tuple) or not (1 <= len(self.exhibits) <= 512):
            raise ValueError("between 1 and 512 exhibits required")
        if any(item.role is not SourceRole.EXHIBIT for item in self.exhibits):
            raise ValueError("all exhibit roles must be explicit")
        versions = [self.inventory.document_version_id, *(item.document_version_id for item in self.exhibits)]
        if len(set(versions)) != len(versions):
            raise ValueError("source version cannot appear twice")

    @property
    def all_sources(self) -> tuple[SourceItem, ...]:
        return (self.inventory, *self.exhibits)

    def assert_authorized(self, authorized_version_ids: frozenset[str]) -> None:
        """Fail closed if even one inventory/exhibit source is inaccessible."""
        if not all(item.document_version_id in authorized_version_ids for item in self.all_sources):
            raise PermissionError("one or more matter sources are not authorized")
