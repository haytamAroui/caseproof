"""Immutable catalogue source descriptor shared by evidence/application use cases."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from packages.evidence_kernel.domain.source_versions import SourceVersion


@dataclass(frozen=True)
class StoredDocument:
    source_id: str
    original: SourceVersion
    intent_id: UUID

    def __post_init__(self) -> None:
        if type(self.source_id) is not str or not self.source_id.strip() or len(self.source_id) > 128:
            raise ValueError("bounded source identity required")
        if not isinstance(self.original, SourceVersion) or not isinstance(self.intent_id, UUID):
            raise ValueError("typed immutable source and intent required")
        if self.intent_id.int == 0:
            raise ValueError("non-nil intent required")
