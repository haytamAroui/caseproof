"""Loopback/disposable port of the signed source library contract.

Same public surface and failure semantics as SignedSourceLibrary
(apps/api/signed_supabase_source_library.py), backed by the disposable
PostgreSQL schema and the filesystem vault byte store instead of remote
Supabase REST/Storage. Never mounted in the main API: it exists so the
loopback development composition can exercise the genuine browser
upload/read routes (``/dev/signed/matters/.../original``) against a real
isolated backend without any Supabase credential.

Authorization mirrors the signed path: the bearer is verified by an
injected verifier, membership and matter grant are loaded from the
disposable schema, and ``authorize_matter`` decides; masked matters stay
masked. Bytes are never overwritten (put-once), the SHA-256 declared at
version registration is enforced before any write, and every write is
followed by a verified readback, like the remote implementation.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from application.litigation.matter_policy import MatterPermission, authorize_matter
from apps.api.access_control import VerifiedSubject
from apps.api.disposable_postgres_vault_ledger import (
    Connection,
    DisposablePostgresVaultLedger,
    DisposableVaultActorContext,
)
from apps.api.evidence_vault_protocol import (
    VaultConflict,
    VaultCoordinator,
    VaultError,
    VaultMissing,
    VaultScope,
    VaultUnavailable,
    VaultUnknownOutcome,
)
from apps.api.litigation_check_service import PrivateMatterAccess
from apps.api.private_filesystem_byte_store import PrivateFilesystemByteStore
from apps.api.signed_supabase_originals import (
    MAX_BYTES,
    MIME,
    PrivateStorageDenied,
    PrivateStorageExists,
    PrivateStorageFailure,
    PrivateStorageIntegrityError,
    PrivateStorageOutcomeUnknown,
)

__all__ = ["DisposableSignedSourceLibrary", "version_intent"]

_MAX_BEARER = 8192


def version_intent(version_id: str, digest: str) -> UUID:
    """Stable per-version intent, replayable across HTTP retries.

    Derived from the immutable version identity and declared digest, with
    the UUIDv4 version/variant bits set because the vault ledger contract
    requires a v4-shaped identifier; uniqueness comes from the digest.
    """
    raw = bytearray(hashlib.sha256(f"{version_id}:{digest}".encode()).digest()[:16])
    raw[6] = (raw[6] & 0x0F) | 0x40
    raw[8] = (raw[8] & 0x3F) | 0x80
    return UUID(bytes=bytes(raw))


def _uuid(raw: object) -> UUID:
    try:
        parsed = UUID(str(raw))
    except (TypeError, ValueError, AttributeError):
        raise PrivateStorageDenied("Missing or invalid signed identity") from None
    if str(parsed) != str(raw) or parsed.int == 0:
        raise PrivateStorageDenied("Noncanonical identifier")
    return parsed


class DisposableSignedSourceLibrary:
    """SignedSourceLibrary-compatible adapter over the disposable backend."""

    def __init__(
        self,
        *,
        connect: Callable[[], Connection],
        byte_store_root: Path,
        verify_bearer: Callable[[str], VerifiedSubject],
        access_lookup: Callable[[str, str], PrivateMatterAccess | None],
    ) -> None:
        self._connect = connect
        self._root = Path(byte_store_root)
        self._verify = verify_bearer
        self._access = access_lookup

    def _subject(self, bearer: str, case_id: str) -> VerifiedSubject:
        if (
            not isinstance(bearer, str)
            or not 0 < len(bearer) <= _MAX_BEARER
            or ("\r" in bearer or "\n" in bearer)
        ):
            raise PrivateStorageDenied("Missing or invalid signed identity")
        if not isinstance(case_id, str) or len(case_id) > 128 or not case_id.strip():
            raise PrivateStorageDenied("Missing or invalid signed identity")
        try:
            subject = self._verify(bearer)
        except Exception:
            raise PrivateStorageDenied("Missing or invalid signed identity") from None
        if not isinstance(subject, VerifiedSubject):
            raise PrivateStorageDenied("Missing or invalid signed identity")
        return subject

    def _authorize(
        self, subject: VerifiedSubject, case_id: str, action: MatterPermission
    ) -> PrivateMatterAccess:
        try:
            scope = self._access(subject.subject_id, case_id)
        except Exception:
            raise PrivateStorageOutcomeUnknown("Private source lookup unavailable") from None
        if not isinstance(scope, PrivateMatterAccess) or scope.case_id != case_id:
            raise PrivateStorageDenied("Private source unavailable")
        try:
            decision = authorize_matter(
                actor_id=subject.subject_id,
                org_id=scope.org_id,
                case_id=case_id,
                action=action,
                membership=scope.member,
                grant=scope.grant,
            )
        except ValueError:
            raise PrivateStorageOutcomeUnknown("Private source lookup unavailable") from None
        if not decision.allowed:
            raise PrivateStorageDenied("Private source unavailable")
        return scope

    def _row(self, case_id: str, document_id: str, version_id: str) -> tuple[str, str, int, str]:
        case, document, version = (_uuid(case_id), _uuid(document_id), _uuid(version_id))
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "select v.org_id, v.original_sha256_hex, v.byte_length, v.media_type "
                "from caseproof.document_versions v "
                "join caseproof.documents d on d.id=v.document_id and d.org_id=v.org_id "
                "where d.case_id=%s and v.document_id=%s and v.id=%s",
                (case, document, version),
            )
            rows = cur.fetchall()
        if len(rows) != 1:
            raise PrivateStorageDenied("Source version not uniquely authorized")
        org_id, digest, length, mime = rows[0]
        if (
            type(length) is not int
            or not 0 < length <= MAX_BYTES
            or not isinstance(digest, str)
            or len(digest) != 64
            or not isinstance(mime, str)
            or mime not in MIME
        ):
            raise PrivateStorageIntegrityError("Private source metadata inconsistent")
        return str(org_id), digest, length, mime

    def source(
        self, *, bearer: str, case_id: str, document_id: str, version_id: str
    ) -> tuple[tuple[str, str, int], str]:
        subject = self._subject(bearer, case_id)
        scope = self._authorize(subject, case_id, MatterPermission.EVIDENCE_READ)
        org_id, digest, length, mime = self._row(case_id, document_id, version_id)
        if org_id != scope.org_id:
            raise PrivateStorageDenied("Private source unavailable")
        return (org_id, digest, length), mime

    def _coordinator(self, subject: VerifiedSubject, version_id: str) -> VaultCoordinator:
        return VaultCoordinator(
            store=PrivateFilesystemByteStore(self._root),
            ledger=DisposablePostgresVaultLedger(
                self._connect,
                DisposableVaultActorContext(UUID(subject.subject_id), _uuid(version_id)),
            ),
        )

    def read(self, *, bearer: str, case_id: str, document_id: str, version_id: str) -> bytes:
        subject = self._subject(bearer, case_id)
        scope = self._authorize(subject, case_id, MatterPermission.EVIDENCE_READ)
        org_id, digest, length, _ = self._row(case_id, document_id, version_id)
        if org_id != scope.org_id:
            raise PrivateStorageDenied("Private source unavailable")
        vault = self._coordinator(subject, version_id)
        intent = version_intent(version_id, digest)
        try:
            data = vault.read(scope=VaultScope(UUID(scope.org_id), UUID(case_id)), intent_id=intent)
        except (VaultMissing, VaultUnavailable):
            raise PrivateStorageDenied("Original unavailable to signed user") from None
        except VaultError:
            raise PrivateStorageOutcomeUnknown("Storage read outcome unverified") from None
        if not 0 < len(data) <= MAX_BYTES or len(data) != length:
            raise PrivateStorageIntegrityError("Empty or oversized original")
        if hashlib.sha256(data).hexdigest() != digest:
            raise PrivateStorageIntegrityError("Stored original checksum mismatch")
        # Requery after the byte read to reject metadata drift, mirroring the
        # double signed read of the remote implementation.
        current = self._row(case_id, document_id, version_id)
        if current[:3] != (org_id, digest, length):
            raise PrivateStorageFailure("Private source changed during read")
        return data

    def put_once(
        self,
        *,
        bearer: str,
        case_id: str,
        document_id: str,
        version_id: str,
        data: bytes,
    ) -> None:
        subject = self._subject(bearer, case_id)
        scope = self._authorize(subject, case_id, MatterPermission.EVIDENCE_UPLOAD)
        org_id, digest, length, mime = self._row(case_id, document_id, version_id)
        if org_id != scope.org_id:
            raise PrivateStorageDenied("Private source unavailable")
        if not isinstance(data, bytes) or not 0 < len(data) <= MAX_BYTES:
            raise ValueError("Original size outside allowed bounds")
        if len(data) != length:
            raise PrivateStorageIntegrityError("Original length mismatch")
        if hashlib.sha256(data).hexdigest() != digest:
            raise PrivateStorageIntegrityError("Original SHA-256 mismatch")
        vault = self._coordinator(subject, version_id)
        scope_v = VaultScope(UUID(scope.org_id), UUID(case_id))
        intent = version_intent(version_id, digest)
        store = PrivateFilesystemByteStore(self._root)
        try:
            record = vault.begin(
                scope=scope_v,
                intent_id=intent,
                sha256_hex=digest,
                byte_length=length,
                media_type=mime,
            )
        except VaultError:
            raise PrivateStorageOutcomeUnknown("durable upload intent status uncertain") from None
        # put-once: refuse before any write when verified bytes already exist.
        try:
            existing = store.read_exact(record.object_key)
        except OSError:
            raise PrivateStorageOutcomeUnknown("Storage read outcome unverified") from None
        if existing is not None:
            raise PrivateStorageExists("Original already exists; no overwrite")
        try:
            vault.upload(scope=scope_v, intent_id=intent, data=data)
        except VaultConflict:
            raise PrivateStorageExists("Original already exists; no overwrite") from None
        except VaultUnknownOutcome:
            raise PrivateStorageOutcomeUnknown("Storage write outcome unverified") from None
        except VaultError:
            raise PrivateStorageFailure("Private source write failed") from None
        # Verify real bytes after writing, never just the write's success.
        if (
            self.read(
                bearer=bearer,
                case_id=case_id,
                document_id=document_id,
                version_id=version_id,
            )
            != data
        ):
            raise PrivateStorageIntegrityError("Original readback mismatch")
