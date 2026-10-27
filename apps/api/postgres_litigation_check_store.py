"""M2-B protected private-matter read composition: disposable backend candidate.

No public route, no live Supabase migration, no service-role bypass. Signed
identity is checked by AuthorizedLitigationChecker, never by this repository.
The trusted server DB session returns current org and per-matter permissions.
Bytes come only from a separately verified Vault coordinator. The currently
supported fast path is exact UTF-8 text/plain; PDF/DOCX is explicitly
INCOMPLETE until its independent page/representation adapter is installed.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from application.litigation.library import EvidencePreview, EvidenceRow
from application.litigation.matter_policy import (
    CurrentMatterGrant,
    CurrentOrganizationGrant,
    MatterPermission,
    OrganizationPermission,
)
from application.litigation.unified_review import SourceScope
from apps.api.disposable_litigation_brief_graph import DisposableBriefGraphStore
from apps.api.litigation_check_service import CheckBundle, PrivateMatterAccess
from domains.disputes.exhibits import ExhibitEntry, ExhibitPage, ExhibitRegister


class PrivateCheckStoreError(ValueError):
    """Fail closed when trust, scope, parser, or immutable snapshot is unknown."""


@dataclass(frozen=True, slots=True)
class CustodySource:
    document_id: UUID
    version_id: UUID
    intent_id: UUID
    sha256_hex: str
    media_type: str


class PostgresPrivateMatterCheckStore:
    """A private read-side adapter, not a public/privileged production API."""

    def __init__(
        self,
        connection_factory: Callable[[], Any],
        graph_store: DisposableBriefGraphStore,
        read_original: Callable[[UUID, UUID, UUID], bytes],
    ) -> None:
        self._connect = connection_factory
        self._graph = graph_store
        self._read_original = read_original

    @staticmethod
    def _uuid(raw: str) -> UUID:
        try:
            parsed = UUID(raw)
            if raw != str(parsed) or parsed.int == 0:
                raise ValueError("noncanonical")
            return parsed
        except (TypeError, ValueError, AttributeError):
            raise PrivateCheckStoreError("invalid or masked case identifier") from None

    def current_access(
        self, subject_id: str, case_id: str,
    ) -> PrivateMatterAccess | None:
        # One joined query: a foreign same-organization case is not discoverable.
        try:
            actor, case = self._uuid(subject_id), self._uuid(case_id)
        except PrivateCheckStoreError:
            return None
        with self._connect() as conn:
            rows = conn.execute(
                "select c.org_id,c.case_revision,m.active,m.actions,"
                "m.membership_revision,g.active,g.permissions,g.revision "
                "from caseproof.cases c "
                "join caseproof.organization_members m on m.org_id=c.org_id "
                "and m.user_id=%s and m.active "
                "join caseproof._m1_matter_grants g on g.org_id=c.org_id "
                "and g.case_id=c.id and g.user_id=m.user_id and g.active "
                "where c.id=%s", (actor, case),
            ).fetchall()
        if not rows:
            return None
        if len(rows) != 1:
            raise PrivateCheckStoreError("ambiguous current matter grant")
        org, rev, member_active, org_actions, member_rev, grant_active, grants, grant_rev = rows[0]
        if (type(rev) is not int or rev < 1
                or type(member_rev) is not int or member_rev < 1
                or type(grant_rev) is not int or grant_rev < 1
                or member_active is not True or grant_active is not True
                or not isinstance(org_actions, (list, tuple))
                or not isinstance(grants, (list, tuple))):
            raise PrivateCheckStoreError("invalid trusted permission snapshot")
        org_id = str(org)
        member = CurrentOrganizationGrant(
            str(actor), org_id, True, frozenset(
                x for a in org_actions if a in OrganizationPermission._value2member_map_
                for x in (OrganizationPermission(a),)
            ), member_rev,
        )
        grant = CurrentMatterGrant(
            str(actor), org_id, str(case), True, frozenset(
                MatterPermission(a) for a in grants
                if a in MatterPermission._value2member_map_
            ), grant_rev,
        )
        return PrivateMatterAccess(str(case), org_id, member, grant, rev)

    def _register(self, *, access: PrivateMatterAccess) -> ExhibitRegister:
        with self._connect() as conn:
            rows = conn.execute(
                "select revision,payload,payload_sha256 from "
                "caseproof._m1_exhibit_heads where org_id=%s and case_id=%s",
                (UUID(access.org_id), UUID(access.case_id)),
            ).fetchall()
        if len(rows) != 1:
            raise PrivateCheckStoreError("confirmed exhibit head required")
        revision, document, expected_sha = rows[0]
        if (type(revision) is not int or revision < 1
                or not isinstance(document, dict)
                or document.get("schema") != "caseproof-exhibit-register-v1"
                or type(document.get("entries")) is not list
                or len(document["entries"]) > 512):
            raise PrivateCheckStoreError("malformed confirmed exhibit head")
        digest = hashlib.sha256(json.dumps(
            document, sort_keys=True, ensure_ascii=False,
            separators=(",", ":"),
        ).encode()).hexdigest()
        if digest != expected_sha:
            raise PrivateCheckStoreError("exhibit snapshot hash mismatch")
        try:
            entries = tuple(
                ExhibitEntry(
                    exhibit_id=e["exhibit_id"], display_label=e["display_label"],
                    aliases=tuple(e["aliases"]), confirmed=e["confirmed"],
                    manual_inclusion=e["manual_inclusion"],
                    pages=tuple(ExhibitPage(**p) for p in e["pages"]),
                ) for e in document["entries"]
            )
            return ExhibitRegister(revision, entries)
        except (KeyError, TypeError, ValueError):
            raise PrivateCheckStoreError("unreadable persisted exhibit mapping") from None

    def _source(self, *, access: PrivateMatterAccess,
                source_id: str, version_id: str) -> CustodySource:
        document, version = self._uuid(source_id), self._uuid(version_id)
        with self._connect() as conn:
            rows = conn.execute(
                "select v.original_sha256_hex,v.media_type,i.intent_id "
                "from caseproof.documents d "
                "join caseproof.document_versions v on v.org_id=d.org_id "
                "and v.document_id=d.id "
                "join caseproof._s2_009b_vault_intents i on i.org_id=d.org_id "
                "and i.case_id=d.case_id and i.document_id=d.id "
                "and i.document_version_id=v.id "
                "and i.sha256_hex=v.original_sha256_hex and i.state='verified' "
                "where d.org_id=%s and d.case_id=%s and d.id=%s and v.id=%s",
                (UUID(access.org_id), UUID(access.case_id), document, version),
            ).fetchall()
        if len(rows) != 1:
            raise PrivateCheckStoreError("exhibit source out of current verified custody")
        sha, media, intent = rows[0]
        if not isinstance(sha, str) or len(sha) != 64 or not isinstance(media, str):
            raise PrivateCheckStoreError("malformed verified source metadata")
        return CustodySource(document, version, intent, sha, media)

    def _preview(self, *, access: PrivateMatterAccess,
                 source: CustodySource) -> EvidencePreview:
        try:
            raw = self._read_original(
                UUID(access.org_id), UUID(access.case_id), source.intent_id,
            )
        except Exception:
            raise PrivateCheckStoreError("verified source bytes unavailable") from None
        if (type(raw) is not bytes or len(raw) > 5_242_880
                or hashlib.sha256(raw).hexdigest() != source.sha256_hex):
            raise PrivateCheckStoreError("verified source bytes changed")
        warnings: tuple[str, ...]
        spans: tuple[tuple[int, int, str, int | None], ...]
        if source.media_type == "text/plain":
            try:
                content = raw.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                raise PrivateCheckStoreError("non-UTF8 source needs normalization") from None
            if not content or len(content) > 120_000:
                raise PrivateCheckStoreError("text source outside parser budget")
            status, warnings = "ready", ()
            parser_id, rep = "identity-utf8-v1", "rep:" + hashlib.sha256(
                (str(source.version_id) + source.sha256_hex).encode(),
            ).hexdigest()
            spans = ((0, len(content), "identity_utf8", None),)
        else:
            # Zero chance a PDF image or DOCX is mistaken for checked text.
            status, warnings = "partial", ("parser_lineage_not_integrated",)
            content, parser_id, rep, spans = "", None, None, ()
        row = EvidenceRow(
            str(source.document_id), str(source.document_id),
            str(source.version_id), source.sha256_hex, source.media_type,
            status, parser_id, rep, (), warnings,
        )
        return EvidencePreview(row, content, spans)

    def load_bundle(
        self, *, case_id: str, brief_version_id: str,
        access: PrivateMatterAccess,
    ) -> CheckBundle:
        if access.case_id != case_id or not access.grant.active:
            raise PrivateCheckStoreError("untrusted private matter read context")
        # UUID here is a physical immutable version, not a user-supplied blob.
        version = self._uuid(brief_version_id)
        register = self._register(access=access)
        with self._connect() as conn:
            rows = conn.execute(
                "select brief_id from caseproof._m2_brief_versions "
                "where org_id=%s and case_id=%s and version_id=%s limit 2",
                (UUID(access.org_id), UUID(case_id), version),
            ).fetchall()
        if len(rows) != 1:
            raise PrivateCheckStoreError("unknown or ambiguous private brief version")
        graph = self._graph.load(
            org_id=UUID(access.org_id), actor_id=UUID(access.member.actor_id),
            case_id=UUID(case_id), brief_id=rows[0][0], version_id=version,
        )
        declared = tuple(sorted({
            (p.source_id, p.version_id) for e in register.entries
            if e.confirmed for p in e.pages
        }))
        if not declared or len(declared) > 32:
            raise PrivateCheckStoreError("bounded confirmed source universe required")
        previews = tuple(self._preview(access=access, source=self._source(
            access=access, source_id=source_id, version_id=version_id,
        )) for source_id, version_id in declared)
        return CheckBundle(graph.representation, register, previews, SourceScope(declared))

    def still_current(
        self, *, access: PrivateMatterAccess, bundle: CheckBundle,
    ) -> bool:
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
