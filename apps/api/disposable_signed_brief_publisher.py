"""Loopback/disposable SignedBriefPublisher port.

Same failure semantics as the SignedBriefPublisher protocol declared in
apps/api/litigation_development_app.py, backed by the disposable PostgreSQL
graph store and the DisposableSignedSourceLibrary byte path instead of any
remote service. Never mounted in the main API: it exists so the loopback
development composition can exercise the genuine browser publication route
(``/dev/signed/matters/{case}/briefs/publish``) against a real isolated
backend without any Supabase credential.

The matter's working brief is derived deterministically from the case and
document role, so the browser only selects a registered document/version;
brief identifiers and the immutable head stay server-side. Reference
extraction and representation construction are injected callables: this
adapter owns identity, authorization, verified bytes and graph publication,
never the demo's extraction policy.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from uuid import UUID, uuid4

from application.litigation.matter_policy import MatterPermission, authorize_matter
from application.litigation.unified_review import BriefRepresentation
from apps.api.access_control import VerifiedSubject
from apps.api.disposable_litigation_brief_graph import (
    BriefGraphConflict,
    DisposableBriefGraphStore,
    VerifiedBriefBinding,
)
from apps.api.disposable_postgres_vault_ledger import Connection
from apps.api.disposable_signed_source_library import DisposableSignedSourceLibrary, version_intent
from apps.api.litigation_check_service import PrivateMatterAccess
from apps.api.litigation_development_app import (
    SignedDocumentSummary,
    SignedDocumentVersionSummary,
    SignedPublishOutcome,
)
from apps.api.signed_document_parse import parse_verified_original
from apps.api.signed_supabase_originals import PrivateStorageDenied

__all__ = ["DisposableSignedBriefPublisher", "working_brief_id"]

_MAX_BEARER = 8192


def working_brief_id(case_id: str, document_role: str) -> UUID:
    """Deterministic per-case working brief, stable across restarts.

    Derived from the immutable case identity and document role, with the
    UUIDv4 version/variant bits set; uniqueness comes from the digest. The
    graph head insert is idempotent, so the first publication creates the
    head and later ones advance it under optimistic concurrency.
    """
    raw = bytearray(
        hashlib.sha256(f"caseproof-working-brief:{document_role}:{case_id}".encode()).digest()[:16]
    )
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


class DisposableSignedBriefPublisher:
    """SignedBriefPublisher-compatible adapter over the disposable backend."""

    def __init__(
        self,
        *,
        connect: Callable[[], Connection],
        library: DisposableSignedSourceLibrary,
        graph: DisposableBriefGraphStore,
        verify_bearer: Callable[[str], VerifiedSubject],
        access_lookup: Callable[[str, str], PrivateMatterAccess | None],
        extract_references: Callable[[str], list[tuple[str, str, str]]],
        build_representation: Callable[..., BriefRepresentation],
    ) -> None:
        self._connect = connect
        self._library = library
        self._graph = graph
        self._verify = verify_bearer
        self._access = access_lookup
        self._extract = extract_references
        self._represent = build_representation

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
            raise PrivateStorageDenied("Private source unavailable") from None
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
            raise PrivateStorageDenied("Private source unavailable") from None
        if not decision.allowed:
            raise PrivateStorageDenied("Private source unavailable")
        return scope

    def list_documents(self, *, bearer: str, case_id: str) -> tuple[SignedDocumentSummary, ...]:
        subject = self._subject(bearer, case_id)
        scope = self._authorize(subject, case_id, MatterPermission.EVIDENCE_READ)
        case = _uuid(case_id)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "select d.id, d.source_label, v.id, v.version_number, "
                "v.media_type, v.byte_length, v.original_sha256_hex "
                "from caseproof.documents d "
                "join caseproof.document_versions v on v.document_id=d.id and v.org_id=d.org_id "
                "where d.case_id=%s and d.org_id=%s "
                "order by d.source_label, v.version_number",
                (case, _uuid(scope.org_id)),
            )
            rows = cur.fetchall()
        documents: dict[str, list[SignedDocumentVersionSummary]] = {}
        labels: dict[str, str] = {}
        for document_id, label, version_id, number, mime, length, digest in rows:
            if (
                type(number) is not int
                or type(length) is not int
                or not isinstance(mime, str)
                or not isinstance(digest, str)
                or len(digest) != 64
            ):
                continue
            key = str(document_id)
            labels[key] = str(label)
            documents.setdefault(key, []).append(
                SignedDocumentVersionSummary(
                    version_id=str(version_id),
                    version_number=number,
                    media_type=mime,
                    byte_length=length,
                    sha256_hex=digest,
                )
            )
        return tuple(
            SignedDocumentSummary(key, labels[key], tuple(versions)) for key, versions in documents.items()
        )

    def publish_uploaded(
        self,
        *,
        bearer: str,
        case_id: str,
        document_id: str,
        version_id: str,
        document_role: str,
        expected_revision: int,
    ) -> SignedPublishOutcome:
        if document_role not in {"own_draft", "opponent_brief"}:
            raise PrivateStorageDenied("Unknown document role")
        subject = self._subject(bearer, case_id)
        scope = self._authorize(subject, case_id, MatterPermission.DRAFT_CHECK)
        # Verified readback of the stored bytes: authorization, immutable
        # digest and length are enforced by the library before any parse.
        data = self._library.read(
            bearer=bearer, case_id=case_id, document_id=document_id, version_id=version_id
        )
        (_org, digest, _length), mime = self._library.source(
            bearer=bearer, case_id=case_id, document_id=document_id, version_id=version_id
        )
        if mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            text, _meta = parse_verified_original(
                document_id=document_id, version_id=version_id, data=data, media_type=mime
            )
        else:
            text = data.decode("utf-8")
        references = self._extract(text)
        brief_version_id = uuid4()
        brief_id = working_brief_id(case_id, document_role)
        representation = self._represent(
            case_id=_uuid(case_id),
            version_id=brief_version_id,
            text=text,
            references=references,
            original_sha256_hex=digest,
        )
        try:
            receipt = self._graph.publish(
                org_id=_uuid(scope.org_id),
                actor_id=_uuid(subject.subject_id),
                brief_id=brief_id,
                binding=VerifiedBriefBinding(
                    _uuid(document_id), _uuid(version_id), version_intent(version_id, digest)
                ),
                representation=representation,
                document_role=document_role,
                request_id=uuid4(),
                expected_revision=expected_revision,
            )
        except BriefGraphConflict as exc:
            raise ValueError(str(exc)) from None
        return SignedPublishOutcome(
            brief_id=str(receipt.brief_id),
            brief_version_id=str(receipt.version_id),
            published_revision=receipt.revision,
        )
