"""Versioned extraction job inputs. Persist references, never credentials or originals."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

from application.documents.intake import EntityAssignment
from application.extraction.contracts import (
    ClaimSlot,
    ExtractionConfig,
    ExtractionError,
    Scope,
    canonical,
    decode,
    digest,
    text,
)


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRY = "retry_wait"
    SUCCEEDED = "succeeded"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "outcome_unknown"


class LeaseLost(ExtractionError):
    pass


class RetryLater(ExtractionError):
    """Only for a known pre-dispatch transient failure; checkpoints veto unsafe retry."""


@dataclass(frozen=True)
class SourceRef:
    source_id: str
    document_id: UUID
    version_id: UUID
    intent_id: UUID
    sha256: str
    media_type: str

    def __post_init__(self) -> None:
        text(self.source_id, limit=128)
        text(self.media_type, limit=128)
        if any(
            not isinstance(v, UUID) or not v.int for v in (self.document_id, self.version_id, self.intent_id)
        ):
            raise ExtractionError("physical scoped source references required")
        if type(self.sha256) is not str or re.fullmatch(r"[0-9a-f]{64}", self.sha256) is None:
            raise ExtractionError("source digest required")

    def payload(self) -> dict[str, str]:
        return {k: str(v) for k, v in asdict(self).items()}


@dataclass(frozen=True)
class JobSpec:
    scope: Scope
    request_id: UUID
    actor_id: UUID
    case_revision: int
    policy_version: str
    sources: tuple[SourceRef, ...]
    plan_json: str
    max_attempts: int = 3
    max_runtime_seconds: int = 1800

    def __post_init__(self) -> None:
        if not isinstance(self.scope, Scope):
            raise ExtractionError("trusted job scope required")
        if any(not isinstance(v, UUID) or not v.int for v in (self.request_id, self.actor_id)):
            raise ExtractionError("server actor and stable request UUID required")
        if type(self.case_revision) is not int or self.case_revision < 0:
            raise ExtractionError("case revision required")
        text(self.policy_version, limit=128)
        if type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 5:
            raise ExtractionError("bounded attempts required")
        if type(self.max_runtime_seconds) is not int or not 30 <= self.max_runtime_seconds <= 3600:
            raise ExtractionError("bounded total job deadline required")
        if type(self.sources) is not tuple or not 1 <= len(self.sources) <= 32:
            raise ExtractionError("bounded immutable source references required")
        if any(not isinstance(s, SourceRef) for s in self.sources):
            raise ExtractionError("typed source references required")
        if len({s.source_id for s in self.sources}) != len(self.sources) or len(
            {s.version_id for s in self.sources}
        ) != len(self.sources):
            raise ExtractionError("duplicate source identity")
        if type(self.plan_json) is not str or len(self.plan_json.encode()) > 65536:
            raise ExtractionError("bounded job plan required")
        plan = decode(self.plan_json)
        if set(plan) != {"assignments", "slots", "config", "engine"} or canonical(plan) != self.plan_json:
            raise ExtractionError("canonical known job plan required")
        assignments, slots, _ = self.inputs()
        ids = {s.source_id for s in self.sources}
        if not 1 <= len(assignments) <= 128 or {a.source_id for a in assignments} != ids:
            raise ExtractionError("assignment inventory mismatch")
        if not 1 <= len(slots) <= 128 or {s for slot in slots for s in slot.source_ids} != ids:
            raise ExtractionError("slot inventory mismatch")
        engine = plan["engine"]
        if type(engine) is not dict or set(engine) != {
            "schema",
            "prompt",
            "parser",
            "provider",
            "model",
            "vocabulary",
            "validator",
        }:
            raise ExtractionError("frozen engine versions required")
        for value in engine.values():
            text(value, limit=256)

    def inputs(self) -> tuple[tuple[EntityAssignment, ...], tuple[ClaimSlot, ...], ExtractionConfig]:
        p = decode(self.plan_json)
        try:
            assignments = tuple(
                EntityAssignment(**{**a, "block_ids": tuple(a["block_ids"])}) for a in p["assignments"]
            )
            slots = tuple(ClaimSlot(**{**s, "source_ids": tuple(s["source_ids"])}) for s in p["slots"])
            return assignments, slots, ExtractionConfig(**p["config"])
        except (KeyError, TypeError, ValueError):
            raise ExtractionError("invalid typed job plan") from None

    @property
    def run_id(self) -> str:
        return "job:" + str(self.request_id)

    def payload(self) -> dict[str, Any]:
        return {
            "schema": "document-job-v1",
            "org_id": str(self.scope.org_id),
            "case_id": str(self.scope.case_id),
            "request_id": str(self.request_id),
            "actor_id": str(self.actor_id),
            "case_revision": self.case_revision,
            "policy_version": self.policy_version,
            "sources": [s.payload() for s in self.sources],
            "plan": decode(self.plan_json),
            "max_attempts": self.max_attempts,
            "max_runtime_seconds": self.max_runtime_seconds,
        }

    @property
    def fingerprint(self) -> str:
        return digest(self.payload())

    @classmethod
    def restore(cls, raw: str) -> JobSpec:
        p = decode(raw)
        if (
            set(p)
            != {
                "schema",
                "org_id",
                "case_id",
                "request_id",
                "actor_id",
                "case_revision",
                "policy_version",
                "sources",
                "plan",
                "max_attempts",
                "max_runtime_seconds",
            }
            or p["schema"] != "document-job-v1"
        ):
            raise ExtractionError("unsupported job schema")
        try:
            sources = tuple(
                SourceRef(**{**s, **{k: UUID(s[k]) for k in ("document_id", "version_id", "intent_id")}})
                for s in p["sources"]
            )
            return cls(
                Scope(UUID(p["org_id"]), UUID(p["case_id"])),
                UUID(p["request_id"]),
                UUID(p["actor_id"]),
                p["case_revision"],
                p["policy_version"],
                sources,
                canonical(p["plan"]),
                p["max_attempts"],
                p["max_runtime_seconds"],
            )
        except (KeyError, TypeError, ValueError):
            raise ExtractionError("invalid persisted job") from None


@dataclass(frozen=True)
class Lease:
    spec: JobSpec
    token: UUID
    attempt: int
    worker_id: UUID


@dataclass(frozen=True)
class JobResult:
    state: JobState
    reason: str
    payload_json: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, JobState) or self.state not in {
            JobState.SUCCEEDED,
            JobState.BLOCKED,
            JobState.UNKNOWN,
            JobState.FAILED,
            JobState.RETRY,
        }:
            raise ExtractionError("invalid worker outcome")
        if self.reason not in {
            "review_ready",
            "incomplete_evidence",
            "provider_outcome_unknown",
            "execution_unknown",
            "preflight_retry",
            "attempts_exhausted",
            "input_changed",
            "job_rejected",
        }:
            raise ExtractionError("safe reason code required")
        if self.payload_json is not None:
            if len(self.payload_json.encode()) > 2 * 1024 * 1024:
                raise ExtractionError("job result limit")
            p = decode(self.payload_json)
            if p.get("approved") is not False:
                raise ExtractionError("job cannot approve")
        if self.state is JobState.SUCCEEDED and self.payload_json is None:
            raise ExtractionError("durable result required")


class JobQueue(Protocol):
    def enqueue(self, spec: JobSpec) -> dict[str, Any]: ...
    def claim(self, scope: Scope, worker_id: UUID, lease_seconds: int) -> Lease | None: ...
    def heartbeat(self, lease: Lease, lease_seconds: int) -> None: ...
    def finish(self, lease: Lease, result: JobResult) -> dict[str, Any]: ...
    def read(self, scope: Scope, request_id: UUID, actor_id: UUID) -> dict[str, Any]: ...
    def cancel(self, scope: Scope, request_id: UUID, actor_id: UUID) -> dict[str, Any]: ...
