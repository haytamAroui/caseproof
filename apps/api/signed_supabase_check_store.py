"""Live PrivateMatterCheckStore over the signed read RPC surface.

Targets the proposed signed read RPCs (migration NOT applied):
caseproof_signed_matter_access and caseproof_signed_check_bundle. Each RPC
is security definer and authorizes by the caller's own JWT; this adapter is
a per-request object bound to one verified bearer and asserts the
RPC-resolved actor identity matches the verified subject, so a server-side
snapshot can never be swapped onto another user. All content is rehydrated
through the same fail-closed domain types as the disposable store; digests
are derived from returned content, never trusted from stored columns.
Verified original bytes come from the injected signed source library
(digest + length + drift recheck), mirroring the disposable _preview rules:
identity-utf8 fast path, bounded indexer for PDF/DOCX when supplied,
page-lineage warnings instead of false quote verdicts.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from application.documents.intake import CapturedDocument
from application.litigation.brief_checks import DraftReference, VersionedBrief
from application.litigation.factual_values import FactAssertion, FactKind, FactRole
from application.litigation.library import EvidenceIndexer, EvidencePreview, EvidenceRow
from application.litigation.matter_policy import (
    CurrentMatterGrant,
    CurrentOrganizationGrant,
    MatterPermission,
    OrganizationPermission,
)
from application.litigation.unified_review import BriefRepresentation, SourceScope
from apps.api.litigation_check_service import (
    CheckBundle,
    MatterCheckUnavailable,
    PrivateMatterAccess,
)
from apps.api.postgres_litigation_check_store import PrivateCheckStoreError
from apps.api.signed_source_binding import valid_storage_binding
from domains.disputes.exhibits import ExhibitEntry, ExhibitPage, ExhibitRegister
from packages.evidence_kernel.domain.source_versions import SourceVersion

__all__ = ["LiveMatterCheckStore"]

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MEDIA_TYPES = {
    "application/pdf",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_MAX_PAGE = 100_000


def _uuid(value: object) -> str:
    if type(value) is not str or not _UUID_RE.fullmatch(value):
        raise PrivateCheckStoreError("untrusted private matter read context")
    return value


def _permissions(raw: object, enum: Any) -> frozenset[Any]:
    if not isinstance(raw, list):
        raise PrivateCheckStoreError("invalid trusted permission snapshot")
    return frozenset(enum(a) for a in raw if isinstance(a, str) and a in enum._value2member_map_)


class LiveMatterCheckStore:
    """Per-request live check store bound to one verified bearer."""

    def __init__(
        self, *, call_rpc: Callable[..., Any], publishable_key: str, bearer: str,
        library: Any, indexer: EvidenceIndexer | None = None,
    ) -> None:
        if not callable(call_rpc) or not isinstance(publishable_key, str):
            raise ValueError("invalid live check store composition")
        self._rpc = call_rpc
        self._key = publishable_key
        self._bearer = bearer
        self._library = library
        self._indexer = indexer

    def _call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        try:
            result = self._rpc(publishable_key=self._key, bearer=self._bearer,
                               name=name, args=args)
        except Exception:
            raise PrivateCheckStoreError("untrusted private matter read context") from None
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise PrivateCheckStoreError("untrusted private matter read context")
        return result

    def current_access(
        self, subject_id: str, case_id: str,
    ) -> PrivateMatterAccess | None:
        try:
            case = _uuid(case_id)
            subject = _uuid(subject_id)
        except PrivateCheckStoreError:
            return None
        try:
            result = self._call("caseproof_signed_matter_access", {"p_case": case})
        except PrivateCheckStoreError:
            return None
        org_id = _uuid(result.get("org_id"))
        actor_id = result.get("actor_id")
        case_revision = result.get("case_revision")
        membership_revision = result.get("membership_revision")
        grant_revision = result.get("grant_revision")
        if (
            actor_id != subject
            or type(case_revision) is not int or case_revision < 1
            or type(membership_revision) is not int or membership_revision < 1
            or type(grant_revision) is not int or grant_revision < 1
        ):
            raise PrivateCheckStoreError("invalid trusted permission snapshot")
        member = CurrentOrganizationGrant(
            subject, org_id, True,
            _permissions(result.get("member_actions"), OrganizationPermission),
            membership_revision,
        )
        grant = CurrentMatterGrant(
            subject, org_id, case, True,
            _permissions(result.get("grant_permissions"), MatterPermission),
            grant_revision,
        )
        return PrivateMatterAccess(case, org_id, member, grant, case_revision)

    def _register(self, payload: object, revision: object) -> ExhibitRegister:
        if (
            type(revision) is not int or revision < 1
            or not isinstance(payload, dict)
            or payload.get("schema") != "caseproof-exhibit-register-v1"
            or not isinstance(payload.get("entries"), list)
        ):
            raise PrivateCheckStoreError("untrusted private matter read context")
        try:
            entries = tuple(
                ExhibitEntry(
                    e["exhibit_id"], e["display_label"],
                    tuple(
                        ExhibitPage(
                            p["source_id"], p["version_id"],
                            pdf_page=p["pdf_page"], printed_page=p["printed_page"],
                            bundle_page=p["bundle_page"],
                        ) for p in e["pages"]
                    ),
                    aliases=tuple(e["aliases"]), confirmed=e["confirmed"],
                    manual_inclusion=e["manual_inclusion"],
                ) for e in payload["entries"]
            )
            return ExhibitRegister(revision, entries)
        except (KeyError, TypeError, ValueError):
            raise PrivateCheckStoreError("untrusted private matter read context") from None

    def _representation(self, access: PrivateMatterAccess, brief: dict[str, Any],
                        bundle: dict[str, Any]) -> BriefRepresentation:
        version_id = brief.get("version_id")
        document_id = brief.get("document_id")
        document_version_id = brief.get("document_version_id")
        intent_id = brief.get("vault_intent_id")
        original_sha = brief.get("original_sha256")
        rep_sha = brief.get("representation_sha256")
        parser_id = brief.get("parser_id")
        text = brief.get("representation")
        role = brief.get("document_role")
        graph_sha = brief.get("graph_sha256")
        if (
            type(_uuid(version_id)) is not str
            or type(_uuid(document_id)) is not str
            or type(_uuid(document_version_id)) is not str
            or intent_id is not None
            or brief.get("source_binding_kind") != "trusted_storage_source_v1"
            or not valid_storage_binding(
                brief.get("source_binding"), org=access.org_id, case=access.case_id,
                document=str(document_id), version=str(document_version_id),
                original_sha=original_sha, representation_sha=rep_sha,
            )
            or type(original_sha) is not str or not _SHA256_RE.fullmatch(original_sha)
            or type(rep_sha) is not str or not _SHA256_RE.fullmatch(rep_sha)
            or type(parser_id) is not str or not 1 <= len(parser_id) <= 256
            or type(text) is not str or not text
            or role not in {"own_draft", "opponent_brief"}
            or type(graph_sha) is not str or not _SHA256_RE.fullmatch(graph_sha)
            or type(brief.get("revision")) is not int or brief["revision"] < 1
            or type(brief.get("case_revision")) is not int
            or type(brief.get("exhibit_revision")) is not int
        ):
            raise PrivateCheckStoreError("invalid stored graph representation")
        # Digests are derived from content, never trusted from stored columns.
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != rep_sha:
            raise PrivateCheckStoreError("invalid stored graph representation")
        refs_raw = bundle.get("references")
        claims_raw = bundle.get("assertions")
        if not isinstance(refs_raw, list) or not isinstance(claims_raw, list):
            raise PrivateCheckStoreError("invalid stored graph representation")
        try:
            references = tuple(
                DraftReference(
                    r["reference_id"], r["exhibit_label"], r.get("exact_quote"),
                    pdf_page=r.get("pdf_page"),
                ) for r in refs_raw
            )
            assertions = tuple(
                FactAssertion(
                    a["claim_id"], a["reference_id"], a["assertion_text"],
                    a["text_start"], a["text_end"],
                    FactKind(a["kind"]), FactRole(a["fact_role"]),
                    a["language"], a["source_language"],
                ) for a in claims_raw
            )
            versioned = VersionedBrief(
                access.case_id, _uuid(version_id), str(original_sha), references)
            return BriefRepresentation(versioned, text, rep_sha, parser_id, assertions)
        except (KeyError, TypeError, ValueError):
            raise PrivateCheckStoreError("invalid stored graph representation") from None

    def _preview(self, *, access: PrivateMatterAccess, source: dict[str, Any],
                 require_page_lineage: bool = False) -> EvidencePreview:
        document_id = _uuid(source.get("document_id"))
        version_id = _uuid(source.get("version_id"))
        sha256_hex = source.get("original_sha256_hex")
        media_type = source.get("media_type")
        byte_length = source.get("byte_length")
        if (
            type(sha256_hex) is not str or not _SHA256_RE.fullmatch(sha256_hex)
            or media_type not in _MEDIA_TYPES
            or type(byte_length) is not int or not 1 <= byte_length <= 5_242_880
            or not valid_storage_binding(
                source.get("source_binding"), org=access.org_id, case=access.case_id,
                document=document_id, version=version_id, original_sha=sha256_hex,
                byte_length=byte_length, media_type=media_type,
            )
        ):
            raise PrivateCheckStoreError("verified source bytes unavailable")
        try:
            raw = self._library.read(
                bearer=self._bearer, case_id=access.case_id,
                document_id=document_id, version_id=version_id,
            )
        except Exception:
            raise PrivateCheckStoreError("verified source bytes unavailable") from None
        if (type(raw) is not bytes or len(raw) != byte_length
                or hashlib.sha256(raw).hexdigest() != sha256_hex):
            raise PrivateCheckStoreError("verified source bytes changed")
        if self._indexer is not None and media_type in {
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }:
            try:
                immutable = SourceVersion(
                    document_id, version_id, sha256_hex, raw,
                    datetime(1970, 1, 1, tzinfo=UTC), media_type,
                )
                preview = self._indexer.preview(CapturedDocument(document_id, immutable))
            except Exception:
                raise PrivateCheckStoreError("bounded source parsing failed") from None
            if require_page_lineage and media_type != "application/pdf":
                return EvidencePreview(
                    EvidenceRow(
                        preview.row.source_id, preview.row.document_id,
                        preview.row.version_id, preview.row.original_sha256,
                        preview.row.media_type, "partial", preview.row.parser_id,
                        preview.row.representation_id, preview.row.pages,
                        (*preview.row.warnings, "page_lineage_unverified"),
                    ), preview.text, preview.spans,
                )
            return preview
        status: str
        warnings: tuple[str, ...]
        if media_type == "text/plain" and not require_page_lineage:
            try:
                content = raw.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                raise PrivateCheckStoreError("non-UTF8 source needs normalization") from None
            if not content or len(content) > 120_000:
                raise PrivateCheckStoreError("text source outside parser budget")
            status, warnings = "ready", ()
            parser_id: str | None = "identity-utf8-v1"
            rep: str | None = "rep:" + hashlib.sha256(
                (version_id + sha256_hex).encode()).hexdigest()
            spans: tuple[tuple[int, int, str, int | None], ...] = (
                (0, len(content), "identity_utf8", None),)
        else:
            reason = ("page_lineage_unverified" if require_page_lineage
                      else "parser_lineage_not_integrated")
            status, warnings = "partial", (reason,)
            content, parser_id, rep, spans = "", None, None, ()
        row = EvidenceRow(
            document_id, document_id, version_id, sha256_hex, media_type,
            status, parser_id, rep, (), warnings,
        )
        return EvidencePreview(row, content, spans)

    def load_bundle(
        self, *, case_id: str, brief_version_id: str, access: PrivateMatterAccess,
    ) -> CheckBundle:
        if access.case_id != case_id or not access.grant.active:
            raise PrivateCheckStoreError("untrusted private matter read context")
        version = _uuid(brief_version_id)
        bundle = self._call("caseproof_signed_check_bundle",
                            {"p_case": case_id, "p_brief_version": version})
        register = self._register(bundle.get("register"), bundle.get("register_revision"))
        brief = bundle.get("brief")
        if (
            not isinstance(brief, dict)
            or brief.get("case_revision") != access.case_revision
            or brief.get("exhibit_revision") != register.revision
        ):
            # Stale published snapshot: the service's typed stale signal so
            # the route answers 409, never an opaque 503.
            raise MatterCheckUnavailable()
        representation = self._representation(access, brief, bundle)
        declared = tuple(sorted({
            (p.source_id, p.version_id) for e in register.entries
            if e.confirmed for p in e.pages
        }))
        if not declared or len(declared) > 32:
            raise PrivateCheckStoreError("bounded confirmed source universe required")
        sources_raw = bundle.get("sources")
        if not isinstance(sources_raw, list):
            raise PrivateCheckStoreError("untrusted private matter read context")
        by_version = {}
        for source in sources_raw:
            if isinstance(source, dict) and type(source.get("version_id")) is str:
                by_version[source["version_id"]] = source
        requested_physical_page = any(
            reference.pdf_page is not None
            for reference in representation.brief.references
        )
        page_scoped = {
            (page.source_id, page.version_id)
            for entry in register.entries for page in entry.pages
            if entry.confirmed and page.pdf_page is not None
        }
        previews = []
        for source_id, version_id in declared:
            source = by_version.get(version_id)
            if source is None or _uuid(source.get("document_id")) != source_id:
                raise PrivateCheckStoreError("bounded confirmed source universe required")
            previews.append(self._preview(
                access=access, source=source,
                require_page_lineage=(
                    requested_physical_page or (source_id, version_id) in page_scoped),
            ))
        return CheckBundle(representation, register, tuple(previews), SourceScope(declared))

    def still_current(self, *, access: PrivateMatterAccess, bundle: CheckBundle) -> bool:
        # Full read-after-check revalidation, including original bytes and
        # materializer outputs. Heavy by design; no optimistic stale answers.
        try:
            latest = self.current_access(access.member.actor_id, access.case_id)
            if latest != access:
                return False
            refreshed = self.load_bundle(
                case_id=access.case_id,
                brief_version_id=bundle.representation.brief.version_id,
                access=access,
            )
            return refreshed == bundle
        except Exception:
            return False
