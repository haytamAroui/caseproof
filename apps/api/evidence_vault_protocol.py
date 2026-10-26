"""S2-009a: internal-only staged Evidence Vault reference protocol.

Never connect this module directly to HTTP, Supabase, or a privileged service
role. No production repository, bucket or real reviewer authorization exists.

Key invariants:
- durable *pending* intent before the FIRST immutable object-store write;
- stable randomized object key, never the original filename or source digest;
- read back exact bytes + SHA-256 before a database *verified* publication;
- object-store write and DB commit are NOT one transaction;
- unknown commit acknowledgments require explicit reconciliation, not blind replay;
- every read rechecks independently authorized scope, immutable bytes and current
  availability; object disappearance invalidates availability and denies export;
- unavailability MUST be atomically audited + aggregate-revision bumped by the
  future repository adapter (not guaranteed by this Protocol).
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID

MAX_REFERENCE_BYTES = 5 * 1024 * 1024  # In-memory reference ONLY, not final upload limit
_ALLOWED_MIME = frozenset({
    "application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/xml", "text/xml", "text/plain", "message/rfc822",
})


class VaultError(Exception):
    """Non-sensitive, fail-closed vault error."""


class VaultMissing(VaultError):
    """No authorized record available; do not expose cross-tenant existence."""


class VaultUnavailable(VaultError):
    """Source missing, corrupt, or currently untrusted."""


class VaultUnknownOutcome(VaultError):
    """Mutation outcome unknown; stable request intent ID enables recovery."""

    def __init__(self, message: str, *, intent_id: UUID | None = None) -> None:
        super().__init__(message)
        self.intent_id = intent_id


class VaultConflict(VaultError):
    """Immutable upload intent changed or incompatible persisted state."""


class VaultState(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class VaultScope:
    """MUST originate in independently authorized server context."""

    org_id: UUID
    case_id: UUID

    def __post_init__(self) -> None:
        for value in (self.org_id, self.case_id):
            if not isinstance(value, UUID) or value.int == 0:
                raise ValueError("non-nil server-supplied scope required")


@dataclass(frozen=True, slots=True)
class UploadIntent:
    scope: VaultScope
    intent_id: UUID
    object_key: str
    sha256_hex: str
    byte_length: int
    media_type: str

    def __post_init__(self) -> None:
        if not isinstance(self.scope, VaultScope):
            raise ValueError("trusted scope object required")
        if not isinstance(self.intent_id, UUID) or self.intent_id.int == 0:
            raise ValueError("non-nil intent ID required")
        prefix = f"org/{self.scope.org_id.hex}/case/{self.scope.case_id.hex}/sources/"
        if not isinstance(self.object_key, str) or not self.object_key.startswith(prefix):
            raise ValueError("invalid scoped object key")
        tail = self.object_key[len(prefix):]
        if len(tail) != 32 or any(ch not in "0123456789abcdef" for ch in tail):
            raise ValueError("object key must use a randomized immutable hex suffix")
        if (not isinstance(self.sha256_hex, str) or len(self.sha256_hex) != 64
                or any(ch not in "0123456789abcdef" for ch in self.sha256_hex)):
            raise ValueError("invalid byte digest")
        if type(self.byte_length) is not int or not 0 < self.byte_length <= MAX_REFERENCE_BYTES:
            raise ValueError("invalid reference upload size")
        if self.media_type not in _ALLOWED_MIME:
            raise ValueError("unsupported test media type")


@dataclass(frozen=True, slots=True)
class VaultRecord:
    intent: UploadIntent
    state: VaultState
    revision: int
    availability_audit_id: UUID | None

    def __post_init__(self) -> None:
        if not isinstance(self.intent, UploadIntent) or not isinstance(self.state, VaultState):
            raise ValueError("invalid durable record")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("invalid record revision")
        if self.state != VaultState.PENDING and (
            not isinstance(self.availability_audit_id, UUID)
            or self.availability_audit_id.int == 0
        ):
            raise ValueError("availability transitions require durable audit identity")


class PrivateByteStore(Protocol):
    """Private store: put-once without upsert, read exact bytes or definitive None.

    Transport, timeouts or unverified origin responses MUST raise; None is
    permitted only for a confirmed missing key, never for a transient outage.
    """

    def put_once(self, key: str, data: bytes) -> None: ...
    def read_exact(self, key: str) -> bytes | None: ...


class VaultLedger(Protocol):
    """Future durable DB adapter must enforce auth and atomic audit/revision.

    PENDING insert is durable before object write. publish_verified() atomically
    inserts trusted audit event, availability revision, source-version link and
    case aggregate revision, with idempotent expected-revision CAS. update to
    UNAVAILABLE similarly invalidates any selected source/coverage heads.
    """

    def create_pending(self, intent: UploadIntent) -> VaultRecord: ...
    def get_scoped(self, scope: VaultScope, intent_id: UUID) -> VaultRecord | None: ...
    def publish_verified(self, expected: VaultRecord) -> VaultRecord: ...
    def mark_unavailable(self, expected: VaultRecord, reason_code: str) -> VaultRecord: ...


class VaultCoordinator:
    def __init__(self, *, store: PrivateByteStore, ledger: VaultLedger) -> None:
        self._store = store
        self._ledger = ledger

    def begin(
        self, *, scope: VaultScope, intent_id: UUID, sha256_hex: str,
        byte_length: int, media_type: str,
    ) -> UploadIntent:
        """Persist/replay one stable request identity, before blob dispatch.

        A trusted request handler must preserve intent_id across HTTP retries,
        and enforce current actor/tenant authority for this ID. Retrying with
        a fresh ID cannot safely reconcile an ambiguous commit.
        """
        if not isinstance(scope, VaultScope):
            raise ValueError("authenticated server scope required")
        if not isinstance(intent_id, UUID) or intent_id.version != 4:
            raise ValueError("stable random UUIDv4 request intent required")
        # Validate semantic inputs even if the record already exists; freeze
        # the original random object key on replay, never derive a new one.
        intent = UploadIntent(
            scope=scope,
            intent_id=intent_id,
            object_key=(
                f"org/{scope.org_id.hex}/case/{scope.case_id.hex}/sources/"
                + secrets.token_hex(16)
            ),
            sha256_hex=sha256_hex,
            byte_length=byte_length,
            media_type=media_type,
        )
        try:
            previous = self._ledger.get_scoped(scope, intent_id)
        except Exception as exc:
            raise VaultUnknownOutcome(
                "pending intent lookup uncertain", intent_id=intent_id
            ) from exc
        if previous is not None:
            saved = previous.intent
            if (saved.scope != scope or saved.intent_id != intent_id
                    or (saved.sha256_hex, saved.byte_length, saved.media_type)
                    != (sha256_hex, byte_length, media_type)):
                raise VaultConflict("same request ID with different immutable upload")
            return saved  # replay exact object key, even after lost create ACK
        try:
            record = self._ledger.create_pending(intent)
        except Exception as exc:
            raise VaultUnknownOutcome(
                "durable upload intent status uncertain", intent_id=intent_id
            ) from exc
        if record.intent != intent or record.state != VaultState.PENDING:
            raise VaultConflict("pending record does not match new upload intent")
        return intent

    def _get(self, scope: VaultScope, intent_id: UUID) -> VaultRecord:
        if not isinstance(scope, VaultScope) or not isinstance(intent_id, UUID):
            raise VaultMissing("source unavailable")
        try:
            record = self._ledger.get_scoped(scope, intent_id)
        except Exception as exc:
            raise VaultUnavailable("authoritative metadata lookup failed") from exc
        if record is None or record.intent.scope != scope or record.intent.intent_id != intent_id:
            raise VaultMissing("source unavailable")
        return record

    @staticmethod
    def _verify(data: bytes | None, intent: UploadIntent) -> bool:
        return (
            type(data) is bytes
            and len(data) == intent.byte_length
            and hashlib.sha256(data).hexdigest() == intent.sha256_hex
        )

    def _publish(self, record: VaultRecord) -> VaultRecord:
        try:
            completed = self._ledger.publish_verified(record)
        except Exception as exc:
            # A commit may have succeeded before its acknowledgment was lost.
            # Caller must query the ledger again, not replay an object write.
            raise VaultUnknownOutcome(
                "upload commit outcome unknown", intent_id=record.intent.intent_id
            ) from exc
        if (completed.intent != record.intent
                or completed.state != VaultState.VERIFIED
                or completed.revision <= record.revision):
            raise VaultConflict("invalid immutable publication result")
        return completed

    def _read_store(self, intent: UploadIntent) -> bytes | None:
        try:
            return self._store.read_exact(intent.object_key)
        except Exception as exc:
            raise VaultUnavailable("private object storage unavailable") from exc

    def upload(self, *, scope: VaultScope, intent_id: UUID, data: bytes) -> VaultRecord:
        """Publish only after exact read-back; never retry ambiguous PUT."""
        record = self._get(scope, intent_id)
        if record.state != VaultState.PENDING:
            raise VaultConflict("upload must target a pending intent")
        if not self._verify(data, record.intent):
            raise VaultConflict("upload bytes do not match frozen intent")
        try:
            self._store.put_once(record.intent.object_key, data)
        except Exception as exc:
            # Provider may have accepted the PUT. No automatic second write.
            raise VaultUnknownOutcome(
                "private object write outcome unknown", intent_id=intent_id
            ) from exc
        observed = self._read_store(record.intent)
        if not self._verify(observed, record.intent):
            raise VaultUnavailable("stored object is not verified")
        return self._publish(record)

    def reconcile_pending(self, *, scope: VaultScope, intent_id: UUID) -> VaultRecord:
        """Reconcile unknown outcomes WITHOUT issuing a new PUT or overwriting."""
        record = self._get(scope, intent_id)
        if record.state != VaultState.PENDING:
            return record
        observed = self._read_store(record.intent)
        if observed is None:
            return record  # still pending; no publication and no blind upload
        if not self._verify(observed, record.intent):
            raise VaultUnavailable("quarantined pending object failed read-back")
        return self._publish(record)

    def _mark_unavailable(self, record: VaultRecord, reason_code: str) -> None:
        try:
            new = self._ledger.mark_unavailable(record, reason_code)
        except Exception as exc:
            raise VaultUnavailable("object untrusted; availability commit uncertain") from exc
        if (new.intent != record.intent or new.state != VaultState.UNAVAILABLE
                or new.revision <= record.revision):
            raise VaultUnavailable("object untrusted; availability transition inconsistent")

    def read(self, *, scope: VaultScope, intent_id: UUID) -> bytes:
        """Revalidate every byte at use; availability loss denies immediately."""
        record = self._get(scope, intent_id)
        if record.state != VaultState.VERIFIED:
            raise VaultUnavailable("source is not verified and available")
        observed = self._read_store(record.intent)
        if not self._verify(observed, record.intent):
            self._mark_unavailable(
                record, "missing" if observed is None else "digest_mismatch"
            )
            raise VaultUnavailable("source became unavailable")
        # Best-effort post-read current-head recheck. Production approval/export
        # needs case-aggregate lock and verified Storage lifecycle under S2-009b.
        latest = self._get(scope, intent_id)
        if latest != record:
            raise VaultUnavailable("source availability changed during read")
        assert isinstance(observed, bytes)
        return observed
