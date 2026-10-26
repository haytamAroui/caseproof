"""M1 application use case: reviewer-confirmed exhibit register with atomic audit.

This module owns no HTTP, database, identity provider or extraction provider.
The store port MUST authorize and commit on the same locked database transaction.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from domains.disputes.exhibits import ExhibitEntry, ExhibitRegister


class ExhibitConfirmationError(ValueError):
    """Reject unverified source, scope, command, reviewer or stale snapshot."""


@dataclass(frozen=True, slots=True)
class ExhibitPrincipal:
    """Must be constructed by the server after signed bearer verification."""

    subject_id: UUID
    org_id: UUID
    case_id: UUID
    human_verified: bool

    def __post_init__(self) -> None:
        if any(v.int == 0 for v in (self.subject_id, self.org_id, self.case_id)):
            raise ExhibitConfirmationError("non-nil trusted identity required")
        if type(self.human_verified) is not bool:
            raise ExhibitConfirmationError("human identity verification required")


@dataclass(frozen=True, slots=True)
class KnownSourceVersion:
    source_id: str
    version_id: str
    sha256_hex: str

    def __post_init__(self) -> None:
        if not self.source_id or not self.version_id:
            raise ExhibitConfirmationError("source/version identity required")
        if len(self.sha256_hex) != 64 or any(x not in "0123456789abcdef" for x in self.sha256_hex):
            raise ExhibitConfirmationError("frozen source digest required")


@dataclass(frozen=True, slots=True)
class ExhibitCommit:
    request_id: UUID
    expected_revision: int
    entries: tuple[ExhibitEntry, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, UUID) or self.request_id.version != 4:
            raise ExhibitConfirmationError("stable random UUIDv4 request ID required")
        if type(self.expected_revision) is not int or self.expected_revision < 0:
            raise ExhibitConfirmationError("nonnegative expected revision required")
        if type(self.entries) is not tuple or len(self.entries) > 512:
            raise ExhibitConfirmationError("bounded exhibit command required")
        ExhibitRegister(self.expected_revision + 1, self.entries)


@dataclass(frozen=True, slots=True)
class ConfirmedExhibits:
    register: ExhibitRegister
    payload_sha256: str
    audit_id: UUID
    actor_id: UUID
    request_id: UUID


def serialized_entries(entries: tuple[ExhibitEntry, ...]) -> bytes:
    """Canonical, versioned register payload: identity is never an exhibit label."""
    return json.dumps(
        {
            "schema": "caseproof-exhibit-register-v1",
            "entries": [
                {
                    "exhibit_id": e.exhibit_id,
                    "display_label": e.display_label,
                    "aliases": list(e.aliases),
                    "confirmed": e.confirmed,
                    "manual_inclusion": e.manual_inclusion,
                    "pages": [
                        {
                            "source_id": p.source_id,
                            "version_id": p.version_id,
                            "pdf_page": p.pdf_page,
                            "printed_page": p.printed_page,
                            "bundle_page": p.bundle_page,
                        }
                        for p in e.pages
                    ],
                }
                for e in entries
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


class ExhibitConfirmationStore(Protocol):
    def permitted_versions(self, principal: ExhibitPrincipal) -> tuple[KnownSourceVersion, ...]:
        """Trusted server-side source ledger; NEVER inferred from client payload."""

    def commit(
        self, principal: ExhibitPrincipal, command: ExhibitCommit, payload: bytes,
    ) -> ConfirmedExhibits:
        """MUST atomically authorize current actor, source versions, CAS and append audit."""

    def current(self, principal: ExhibitPrincipal) -> ConfirmedExhibits | None:
        """MUST read only after current case-level authorization."""


class ExhibitConfirmationUseCase:
    def __init__(self, store: ExhibitConfirmationStore) -> None:
        self.store = store

    def confirm(self, principal: ExhibitPrincipal, command: ExhibitCommit) -> ConfirmedExhibits:
        if not principal.human_verified:
            raise ExhibitConfirmationError("human attestation required for exhibit confirmation")
        known = {(x.source_id, x.version_id) for x in self.store.permitted_versions(principal)}
        if not known:
            raise ExhibitConfirmationError("no authorized preserved sources")
        for entry in command.entries:
            if not entry.confirmed:
                raise ExhibitConfirmationError("only explicitly confirmed entries may commit")
            for page in entry.pages:
                if (page.source_id, page.version_id) not in known:
                    raise ExhibitConfirmationError("page points outside authorized source universe")
        payload = serialized_entries(command.entries)
        if len(payload) > 256_000:
            raise ExhibitConfirmationError("exhibit register payload exceeds budget")
        committed = self.store.commit(principal, command, payload)
        if (
            committed.actor_id != principal.subject_id
            or committed.request_id != command.request_id
            or committed.register.revision != command.expected_revision + 1
            or committed.register.entries != command.entries
            or committed.payload_sha256 != hashlib.sha256(payload).hexdigest()
            or not isinstance(committed.audit_id, UUID)
            or committed.audit_id.int == 0
        ):
            raise ExhibitConfirmationError("atomic audit/CAS receipt inconsistent; outcome unknown")
        return committed

    def current(self, principal: ExhibitPrincipal) -> ConfirmedExhibits | None:
        return self.store.current(principal)
