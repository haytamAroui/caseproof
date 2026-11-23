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
import io
from collections.abc import Callable
from typing import cast
from uuid import UUID, uuid4

from application.litigation.exhibit_confirmation import serialized_entries
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
    SignedDocumentRegistration,
    SignedDocumentSummary,
    SignedDocumentVersionSummary,
    SignedExhibitConfirmation,
    SignedPublishOutcome,
)
from apps.api.signed_document_parse import parse_verified_original
from apps.api.signed_supabase_originals import MAX_BYTES, PrivateStorageDenied
from domains.disputes.exhibits import ExhibitEntry, ExhibitPage

_MAPPING_KEYS = {"pdf_page", "printed_page", "bundle_page"}
_MAX_PDF_PAGES = 64


def _page_value(value: object) -> bool:
    return type(value) is int and 1 <= value <= 100_000


def _pdf_page_count(original: bytes) -> int:
    """Physical page count of a VERIFIED original, parsed strictly.

    Fail-closed: encryption, malformed structure or an out-of-bounds count
    reject confirmation rather than guessing an inventory.
    """
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(original), strict=True)
    if reader.is_encrypted:
        raise ValueError("invalid exhibit declaration")
    count = len(reader.pages)
    if not 1 <= count <= _MAX_PDF_PAGES:
        raise ValueError("invalid exhibit declaration")
    return count


def _confirmed_pages(
    document_id: str, version_id: str, page_mappings: object, *, page_count: int | None
) -> tuple[ExhibitPage, ...]:
    """Physical inventory plus user-declared label mappings.

    page_count is the parser-derived physical page count of the verified
    original (None for a source with no physical pages). Nothing is
    invented: on a PDF the inventory is exactly pages 1..N and user
    mappings only annotate printed/bundle labels on real pages; on a
    non-paginated source the sole row is the explicit UNPAGINATED marker
    (every numbering space NOT MAPPED), never a fabricated page 1.
    Mappings on a non-paginated source, unknown keys, duplicates and
    out-of-inventory physical pages all fail closed.
    """
    if page_mappings is None:
        if page_count is None:
            return (ExhibitPage(document_id, version_id),)
        return tuple(
            ExhibitPage(document_id, version_id, pdf_page=page)
            for page in range(1, page_count + 1)
        )
    if not isinstance(page_mappings, (list, tuple)) or not 1 <= len(page_mappings) <= 512:
        raise ValueError("invalid exhibit declaration")
    if page_count is None:
        raise ValueError("invalid exhibit declaration")
    merged: dict[int, tuple[int | None, int | None]] = {}
    for mapping in page_mappings:
        if not isinstance(mapping, dict) or set(mapping) - _MAPPING_KEYS or "pdf_page" not in mapping:
            raise ValueError("invalid exhibit declaration")
        pdf = mapping["pdf_page"]
        printed = mapping.get("printed_page")
        bundle = mapping.get("bundle_page")
        if not _page_value(pdf) or pdf in merged or pdf > page_count:
            raise ValueError("invalid exhibit declaration")
        if any(v is not None and not _page_value(v) for v in (printed, bundle)):
            raise ValueError("invalid exhibit declaration")
        merged[pdf] = (cast("int | None", printed), cast("int | None", bundle))
    return tuple(
        ExhibitPage(
            document_id,
            version_id,
            pdf_page=page,
            printed_page=merged[page][0] if page in merged else None,
            bundle_page=merged[page][1] if page in merged else None,
        )
        for page in range(1, page_count + 1)
    )

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

    def confirm_exhibit(
        self,
        *,
        bearer: str,
        case_id: str,
        document_id: str,
        version_id: str,
        display_label: str,
        page_mappings: object = None,
    ) -> SignedExhibitConfirmation:
        subject = self._subject(bearer, case_id)
        scope = self._authorize(subject, case_id, MatterPermission.EXHIBIT_CONFIRM)
        case = _uuid(case_id)
        document = _uuid(document_id)
        version = _uuid(version_id)
        if (
            not isinstance(display_label, str)
            or not 0 < len(display_label.strip()) <= 200
            or "\r" in display_label
            or "\n" in display_label
        ):
            raise ValueError("invalid exhibit declaration")
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "select v.media_type from caseproof.document_versions v "
                "join caseproof.documents d on d.id=v.document_id and d.org_id=v.org_id "
                "where v.id=%s and d.id=%s and d.case_id=%s and d.org_id=%s",
                (version, document, case, _uuid(scope.org_id)),
            )
            media_rows = cur.fetchall()
            if len(media_rows) != 1 or not isinstance(media_rows[0][0], str):
                raise PrivateStorageDenied("Private source unavailable")
            media_type = media_rows[0][0]
            if media_type == "application/pdf":
                original = self._library.read(
                    bearer=bearer, case_id=case_id,
                    document_id=document_id, version_id=version_id,
                )
                page_count = _pdf_page_count(original)
            else:
                page_count = None
            pages = _confirmed_pages(
                str(document), str(version), page_mappings, page_count=page_count
            )
            cur.execute(
                "select revision,payload,payload_sha256 from caseproof._m1_exhibit_heads "
                "where org_id=%s and case_id=%s",
                (_uuid(scope.org_id), case),
            )
            rows = cur.fetchall()
            if len(rows) != 1:
                raise PrivateStorageDenied("Private source unavailable")
            revision, document_head, stored_sha = rows[0]
            # The register digest is DERIVED, never gated on the stored
            # column: the write RPC (reachable by any authenticated user
            # with confirm permission) cannot recompute sha256 without
            # pgcrypto, so a well-formed false stored digest must not be
            # able to poison availability. Content is the source of truth
            # and is fully validated below and at write time; the stored
            # column stays as audit correlation of the writer's claim.
            if stored_sha is not None and type(stored_sha) is not str:
                raise PrivateStorageDenied("Private source unavailable")
            if (
                type(revision) is not int
                or revision < 1
                or not isinstance(document_head, dict)
                or document_head.get("schema") != "caseproof-exhibit-register-v1"
                or type(document_head.get("entries")) is not list
            ):
                raise PrivateStorageDenied("Private source unavailable")
            try:
                entries = tuple(
                    ExhibitEntry(
                        exhibit_id=e["exhibit_id"],
                        display_label=e["display_label"],
                        aliases=tuple(e["aliases"]),
                        confirmed=e["confirmed"],
                        manual_inclusion=e["manual_inclusion"],
                        pages=tuple(ExhibitPage(**pg) for pg in e["pages"]),
                    )
                    for e in document_head["entries"]
                )
            except (KeyError, TypeError, ValueError):
                raise PrivateStorageDenied("Private source unavailable") from None
            exhibit_id = "piece-" + uuid4().hex[:12]
            augmented = entries + (
                ExhibitEntry(
                    exhibit_id,
                    display_label.strip(),
                    pages,
                    confirmed=True,
                ),
            )
            encoded = serialized_entries(augmented)
            import psycopg

            try:
                cur.execute(
                    "select * from caseproof._m1_disposable_confirm_exhibits(%s,%s,%s,%s,%s::jsonb,%s)",
                    (
                        _uuid(subject.subject_id),
                        case,
                        uuid4(),
                        revision,
                        encoded.decode("utf-8"),
                        hashlib.sha256(encoded).hexdigest(),
                    ),
                )
            except psycopg.Error:
                raise ValueError("exhibit confirmation conflict") from None
        return SignedExhibitConfirmation(exhibit_id=exhibit_id, exhibit_revision=revision + 1)

    def register_source_version(
        self,
        *,
        bearer: str,
        case_id: str,
        label: str,
        media_type: str,
        byte_length: int,
        sha256_hex: str,
    ) -> SignedDocumentRegistration:
        subject = self._subject(bearer, case_id)
        scope = self._authorize(subject, case_id, MatterPermission.EVIDENCE_UPLOAD)
        case = _uuid(case_id)
        if (
            not isinstance(label, str)
            or not 0 < len(label.strip()) <= 120
            or "\r" in label
            or "\n" in label
            or not isinstance(media_type, str)
            or not 1 <= len(media_type) <= 100
            or type(byte_length) is not int
            or not 0 < byte_length <= MAX_BYTES
            or not isinstance(sha256_hex, str)
            or len(sha256_hex) != 64
            or any(c not in "0123456789abcdef" for c in sha256_hex)
        ):
            raise ValueError("invalid registration")
        document_id, version_id = uuid4(), uuid4()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "insert into caseproof.documents(id,org_id,case_id,source_label) values(%s,%s,%s,%s)",
                (document_id, _uuid(scope.org_id), case, label.strip()),
            )
            cur.execute(
                "insert into caseproof.document_versions(id,org_id,document_id,version_number,"
                "original_sha256_hex,byte_length,media_type) values(%s,%s,%s,1,%s,%s,%s)",
                (version_id, _uuid(scope.org_id), document_id, sha256_hex, byte_length, media_type),
            )
        return SignedDocumentRegistration(document_id=str(document_id), version_id=str(version_id))

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
