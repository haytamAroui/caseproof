from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

from application.documents.intake import IntakeResult
from application.extraction.contracts import ExtractionError, Scope, canonical, decode, digest, text

REVIEW_SCHEMA = "caseproof-review-proposals-v1"
ZERO_HASH = "0" * 64


def sha(value: str) -> str:
    if type(value) is not str or re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise ExtractionError("SHA-256 required")
    return value


class ReviewConflict(ExtractionError):
    pass


class ReviewKind(StrEnum):
    RETAIN = "retain"
    REJECT = "reject"
    CORRECT = "correct"
    QUALIFY = "qualify"
    REQUEST_EVIDENCE = "request_evidence"


@dataclass(frozen=True)
class ReviewCommand:
    request_id: UUID
    snapshot_hash: str
    expected_revision: int
    item_id: str
    kind: ReviewKind
    note: str = field(repr=False)
    correction: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, UUID) or not self.request_id.int:
            raise ExtractionError("stable request UUID required")
        sha(self.snapshot_hash)
        if type(self.expected_revision) is not int or self.expected_revision < 0:
            raise ExtractionError("nonnegative review revision required")
        text(self.item_id, limit=128)
        if not isinstance(self.kind, ReviewKind):
            raise ExtractionError("typed review recommendation required")
        text(self.note, limit=4000)
        if self.kind in {ReviewKind.CORRECT, ReviewKind.QUALIFY}:
            text(self.correction, limit=8192)
        elif self.correction is not None:
            raise ExtractionError("correction not valid for this action")

    def payload(self) -> dict[str, Any]:
        return {**asdict(self), "request_id": str(self.request_id), "kind": self.kind.value}


@dataclass(frozen=True)
class ReviewSnapshot:
    scope: Scope
    snapshot_hash: str
    payload_json: str = field(repr=False)

    def __post_init__(self) -> None:
        payload = decode(self.payload_json)
        if payload.get("schema") != REVIEW_SCHEMA or payload.get("scope") != self.scope.namespace:
            raise ExtractionError("review snapshot scope/schema mismatch")
        if (
            payload.get("approved") is not False
            or payload.get("review_authority") != "recommendations_only"
            or payload.get("extraction", {}).get("approved") is not False
        ):
            raise ExtractionError("review approval authority is disabled")
        if digest(payload) != sha(self.snapshot_hash):
            raise ExtractionError("review snapshot integrity mismatch")

    @property
    def data(self) -> dict[str, Any]:
        return decode(self.payload_json)


def freeze_review(
    result: IntakeResult,
    *,
    scope: Scope,
    title: str,
    case_revision: int,
    policy_version: str,
    source_intents: dict[str, UUID] | None = None,
) -> ReviewSnapshot:
    text(title, limit=256)
    text(policy_version, limit=128)
    if type(case_revision) is not int or case_revision < 1 or result.extraction is None:
        raise ExtractionError("current case revision and extraction required")
    report = result.extraction
    if report.manifest.get("scope") != scope.namespace or digest(report.manifest) != report.manifest_hash:
        raise ExtractionError("extraction snapshot scope/integrity mismatch")
    expected = {s["id"]: s for s in report.manifest["sources"]}
    if set(expected) != {p.evidence.source_id for p in result.documents}:
        raise ExtractionError("extraction source inventory changed")
    descriptors = []
    for parsed in result.documents:
        source, rep = parsed.evidence.source, parsed.evidence.representation
        pinned = expected[parsed.evidence.source_id]
        if (
            pinned["document"],
            pinned["version"],
            pinned["sha"],
            pinned["representation"],
            pinned["representation_sha"],
        ) != (
            source.document_id,
            source.version_id,
            source.sha256_hex,
            rep.representation_id,
            rep.sha256_hex,
        ):
            raise ExtractionError("stale source or representation")
        descriptors.append(
            {
                "source_id": parsed.evidence.source_id,
                "document_id": source.document_id,
                "version_id": source.version_id,
                "sha256": source.sha256_hex,
                "media_type": source.media_type,
                "ingested_at": source.ingested_at.isoformat(),
                "representation_id": rep.representation_id,
                "representation_sha256": rep.sha256_hex,
                "representation_created_at": rep.created_at.isoformat(),
                "artifact_sha256": digest(parsed.artifact()),
                "parser_id": parsed.parser_id,
                "complete": parsed.evidence.complete,
                "intent_id": str(source_intents[parsed.evidence.source_id]) if source_intents else None,
            }
        )
    locations = {}
    for atom in report.atoms:
        if atom.start is not None and atom.end is not None and atom.state != "rejected":
            parsed = next(p for p in result.documents if p.evidence.source_id == atom.source_id)
            if parsed.evidence.content[atom.start : atom.end] != atom.quote:
                raise ExtractionError("review quote no longer exact")
            locations[atom.candidate_id] = [asdict(b) for b in parsed.locations(atom.start, atom.end)]
    data = {
        "schema": REVIEW_SCHEMA,
        "scope": scope.namespace,
        "title": title,
        "case_revision": case_revision,
        "policy_version": policy_version,
        "sources": descriptors,
        "extraction": asdict(report),
        "locations": locations,
        "approved": False,
        "review_authority": "recommendations_only",
    }
    return ReviewSnapshot(scope, digest(data), canonical(data))


def event_digest(event: dict[str, Any]) -> str:
    return digest({k: v for k, v in event.items() if k != "audit_hash"})


def validate_command(snapshot: ReviewSnapshot, command: ReviewCommand) -> None:
    if command.snapshot_hash != snapshot.snapshot_hash:
        raise ReviewConflict("snapshot_changed")
    ids = {a["candidate_id"] for a in snapshot.data["extraction"]["atoms"]}
    if command.item_id not in ids and not (
        command.item_id == "case" and command.kind is ReviewKind.REQUEST_EVIDENCE
    ):
        raise ExtractionError("review item not in frozen snapshot")


class ReviewRepository(Protocol):
    def publish(self, snapshot: ReviewSnapshot, actor: UUID) -> None: ...
    def state(self, scope: Scope, actor: UUID) -> dict[str, Any]: ...
    def record(self, scope: Scope, actor: UUID, command: ReviewCommand) -> dict[str, Any]: ...
