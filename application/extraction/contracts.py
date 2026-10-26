"""Versioned proposal contracts and strict untrusted-response decoding."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from hashlib import sha256
from typing import Any, Protocol
from uuid import UUID

from packages.evidence_kernel.domain.source_versions import DerivedRepresentation, SourceVersion

SCHEMA_VERSION = "caseproof-ei-v1"
PROMPT_VERSION = "caseproof-qae-v5"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class ExtractionError(ValueError):
    pass


class OutcomeUnknown(ExtractionError):
    """Possibly dispatched request: reconcile, never blindly purchase a retry."""


class ProviderRejected(ExtractionError):
    """Confirmed non-success HTTP response; never approve from it."""


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return sha256(canonical(value).encode("utf-8")).hexdigest()


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ExtractionError("duplicate JSON key")
        result[key] = value
    return result


def decode(raw: str) -> dict[str, Any]:
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_RESPONSE_BYTES:
        raise ExtractionError("response limit exceeded")
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ExtractionError("nonfinite JSON forbidden")),
        )
    except (ValueError, RecursionError) as exc:
        raise ExtractionError("invalid response JSON") from exc
    if type(value) is not dict:
        raise ExtractionError("response must be an object")
    return value


def text(value: Any, *, limit: int = 512) -> str:
    if type(value) is not str or not value.strip() or len(value) > limit:
        raise ExtractionError("bounded nonempty text required")
    return value


@dataclass(frozen=True)
class Scope:
    org_id: UUID
    case_id: UUID

    def __post_init__(self) -> None:
        if any(not isinstance(v, UUID) or v.int == 0 for v in (self.org_id, self.case_id)):
            raise ExtractionError("trusted UUID scope required")

    @property
    def namespace(self) -> str:
        return f"{self.org_id}:{self.case_id}"


@dataclass(frozen=True)
class ExtractionSource:
    source_id: str
    source: SourceVersion
    representation: DerivedRepresentation
    complete: bool = True

    def __post_init__(self) -> None:
        text(self.source_id, limit=128)
        s, r = self.source, self.representation
        if (
            (s.document_id, s.version_id, s.sha256_hex) != (r.document_id, r.version_id, r.source_sha256_hex)
            or r.media_type != "text/plain"
            or r.coordinate_convention != "unicode_codepoint_zero_based_half_open"
        ):
            raise ExtractionError("exact text representation lineage required")
        if type(self.complete) is not bool:
            raise ExtractionError("explicit completeness required")
        r.content.decode("utf-8", errors="strict")

    @property
    def content(self) -> str:
        return self.representation.content.decode("utf-8")


@dataclass(frozen=True)
class EntityScope:
    """Independently supplied boundary; model output cannot set confirmed."""

    entity_id: str
    kind: str
    source_id: str
    start: int
    end: int
    confirmed: bool = False

    def __post_init__(self) -> None:
        for v in (self.entity_id, self.kind, self.source_id):
            text(v, limit=128)
        if type(self.start) is not int or type(self.end) is not int or not 0 <= self.start < self.end:
            raise ExtractionError("explicit nonempty entity boundary required")
        if type(self.confirmed) is not bool:
            raise ExtractionError("typed boundary status required")


@dataclass(frozen=True)
class ClaimSlot:
    entity_id: str
    slot_id: str
    source_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        text(self.entity_id, limit=128)
        text(self.slot_id, limit=128)
        if (
            not isinstance(self.source_ids, tuple)
            or not self.source_ids
            or len(set(self.source_ids)) != len(self.source_ids)
        ):
            raise ExtractionError("unique required source inventory needed")


@dataclass(frozen=True)
class ExtractionConfig:
    topology: str = "global_first"
    max_calls: int = 16
    max_input_chars: int = 120_000
    max_output_tokens: int = 4096
    repair_passes: int = 1
    max_concurrency: int = 1

    def __post_init__(self) -> None:
        if self.topology not in {"global_first", "segmented", "four_pass"}:
            raise ExtractionError("unsupported topology")
        for value, upper in (
            (self.max_calls, 64),
            (self.max_input_chars, 250_000),
            (self.max_output_tokens, 8192),
            (self.max_concurrency, 4),
        ):
            if type(value) is not int or not 1 <= value <= upper:
                raise ExtractionError("bounded execution budget required")
        if type(self.repair_passes) is not int or not 0 <= self.repair_passes <= 2:
            raise ExtractionError("bounded repair budget required")


@dataclass(frozen=True)
class ExtractionRequest:
    scope: Scope
    run_id: str
    sources: tuple[ExtractionSource, ...]
    entities: tuple[EntityScope, ...]
    slots: tuple[ClaimSlot, ...]
    config: ExtractionConfig = field(default_factory=ExtractionConfig)

    def __post_init__(self) -> None:
        text(self.run_id, limit=128)
        if any(type(v) is not tuple for v in (self.sources, self.entities, self.slots)):
            raise ExtractionError("immutable request inventories required")
        if len(self.entities) > 128 or len(self.slots) > 256:
            raise ExtractionError("bounded entity and claim inventories required")
        if not self.sources or len(self.sources) > 32:
            raise ExtractionError("bounded nonempty source set required")
        ids = [s.source_id for s in self.sources]
        if len(set(ids)) != len(ids):
            raise ExtractionError("duplicate source IDs")
        if len({(s.source.document_id, s.source.version_id) for s in self.sources}) != len(ids):
            raise ExtractionError("duplicate source version aliases forbidden")
        if len({s.representation.representation_id for s in self.sources}) != len(ids):
            raise ExtractionError("duplicate representation aliases forbidden")
        sources = {s.source_id: s for s in self.sources}
        for e in self.entities:
            if e.source_id not in sources or e.end > len(sources[e.source_id].content):
                raise ExtractionError("entity boundary outside source")
        if len({(s.entity_id, s.slot_id) for s in self.slots}) != len(self.slots) or not self.slots:
            raise ExtractionError("unique required claim slots needed")
        for slot in self.slots:
            if any(s not in sources for s in slot.source_ids):
                raise ExtractionError("claim slot references absent source")
        if {sid for slot in self.slots for sid in slot.source_ids} != set(sources):
            raise ExtractionError("every source must be assigned to a claim slot")
        if len({(e.entity_id, e.source_id, e.start, e.end) for e in self.entities}) != len(self.entities):
            raise ExtractionError("duplicate entity boundaries")
        if sum(len(s.content) for s in self.sources) > self.config.max_input_chars:
            raise ExtractionError("input budget exceeded; no implicit truncation")


class Vocabulary(Protocol):
    namespace: str
    version: str
    signals: tuple[str, ...]

    def validate(self, signal: str, slot: str, quote: str, value: str, kind: str) -> tuple[str, str]: ...


@dataclass(frozen=True)
class ProviderReply:
    text: str = field(repr=False)
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost: str | None = None


class ExtractionProvider(Protocol):
    identity: str
    model: str

    def complete(self, system: str, payload: str, *, request_id: str, max_tokens: int) -> ProviderReply: ...


class StepState(StrEnum):
    PREPARED = "prepared"
    DISPATCHED = "dispatched"
    RECEIVED = "received"
    COMPLETED = "completed"
    UNKNOWN = "outcome_unknown"
    FAILED = "failed"


@dataclass(frozen=True)
class StepRecord:
    state: StepState
    input_digest: str
    created_at: str
    payload: str | None = field(default=None, repr=False)


class StepJournal(Protocol):
    def reserve(self, scope: Scope, run_id: str, step: str, fingerprint: str) -> StepRecord: ...
    def transition(
        self,
        scope: Scope,
        run_id: str,
        step: str,
        previous: StepState,
        target: StepState,
        payload: str | None = None,
    ) -> StepRecord: ...


def request_manifest(
    request: ExtractionRequest, provider: ExtractionProvider, policy: Vocabulary
) -> dict[str, Any]:
    return {
        "schema": SCHEMA_VERSION,
        "prompt": PROMPT_VERSION,
        "run_id": request.run_id,
        "provider": provider.identity,
        "model": provider.model,
        "vocabulary": policy.namespace,
        "vocabulary_version": policy.version,
        "signals": list(policy.signals),
        "config": asdict(request.config),
        "scope": request.scope.namespace,
        "entities": [asdict(e) for e in request.entities],
        "slots": [asdict(s) for s in request.slots],
        "sources": [
            {
                "id": s.source_id,
                "document": s.source.document_id,
                "version": s.source.version_id,
                "sha": s.source.sha256_hex,
                "representation": s.representation.representation_id,
                "representation_sha": s.representation.sha256_hex,
                "parser": s.representation.transform_name,
                "parser_version": s.representation.transform_version,
                "parser_config": s.representation.transform_config_sha256,
                "complete": s.complete,
            }
            for s in request.sources
        ],
    }
