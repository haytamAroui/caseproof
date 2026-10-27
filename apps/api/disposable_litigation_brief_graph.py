"""Disposable M2 source-bound versioned brief graph (no live Auth/API).

Only trusted callers may construct BriefRepresentation. This adapter independently
reads actual private Vault bytes and verifies source/version/intent lineage in a
PostgreSQL transaction. It neither runs OCR/LLMs nor writes Word files.
Actor IDs are SYNTHETIC in disposable CI: no signed-user claim.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid4

from application.litigation.brief_checks import DraftReference, VersionedBrief
from application.litigation.factual_values import FactAssertion, FactKind, FactRole
from application.litigation.unified_review import BriefRepresentation


class BriefGraphConflict(ValueError):
    """Reject untrusted/stale/ambiguous graph identities and transactions."""


@dataclass(frozen=True, slots=True)
class VerifiedBriefBinding:
    document_id: UUID
    document_version_id: UUID
    intent_id: UUID

    def __post_init__(self) -> None:
        if any(not isinstance(x, UUID) or x.int == 0 for x in (
            self.document_id, self.document_version_id, self.intent_id,
        )):
            raise BriefGraphConflict("exact non-nil physical source binding required")


@dataclass(frozen=True, slots=True)
class StoredBriefGraph:
    brief_id: UUID
    revision: int
    representation: BriefRepresentation
    binding: VerifiedBriefBinding
    document_role: str
    graph_sha256: str
    is_current: bool


@dataclass(frozen=True, slots=True)
class BriefWriteReceipt:
    brief_id: UUID
    version_id: UUID
    revision: int
    graph_sha256: str
    replayed: bool
    release_authorized: bool = False


def _uuid(value: UUID | str) -> UUID:
    try:
        parsed = UUID(str(value))
        if parsed.int == 0:
            raise ValueError("nil")
        return parsed
    except (TypeError, ValueError, AttributeError):
        raise BriefGraphConflict("non-nil UUID required") from None


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _hash(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _graph_identity(brief_id: UUID, binding: VerifiedBriefBinding,
                    representation: BriefRepresentation,
                    document_role: str) -> str:
    return _hash({
        "brief_id": str(brief_id), "case": representation.brief.case_id,
        "version_id": representation.brief.version_id,
        "original_sha256": representation.brief.sha256_hex,
        "representation_sha256": representation.text_sha256,
        "parser_id": representation.parser_id,
        "document_id": str(binding.document_id),
        "source_version": str(binding.document_version_id),
        "intent": str(binding.intent_id),
        "role": document_role,
        "references": [asdict(r) for r in representation.brief.references],
        "assertions": [asdict(a) for a in representation.claims],
    })


class DisposableBriefGraphStore:
    """Explicit-CAS heads, immutable graph rows and audit in local Postgres."""

    def __init__(
        self, connection_factory: Callable[[], Any],
        read_original: Callable[[UUID, UUID, UUID], bytes],
    ) -> None:
        self._connect = connection_factory
        self._read_original = read_original

    @staticmethod
    def _authorize(conn: Any, org: UUID, case: UUID,
                   actor: UUID) -> tuple[int, int]:
        # For this disposable normalization packet only, draft:check is the
        # server-owned authorization for recording a checked representation.
        # Production draft edits need a separately reviewed draft:write action.
        rows = conn.execute(
            "select c.case_revision,h.revision from caseproof.cases c "
            "join caseproof.organization_members m on m.org_id=c.org_id "
            "and m.user_id=%s and m.active "
            "join caseproof._m1_matter_grants g on g.org_id=c.org_id "
            "and g.case_id=c.id and g.user_id=m.user_id and g.active "
            "join caseproof._m1_exhibit_heads h on h.org_id=c.org_id "
            "and h.case_id=c.id "
            "where c.org_id=%s and c.id=%s "
            "and m.actions @> array['case:read','finding:write']::text[] "
            "and g.permissions @> array['case:read','draft:check']::text[] "
            "for share of c,m,g,h", (actor, org, case),
        ).fetchall()
        if len(rows) != 1:
            raise BriefGraphConflict("current private matter grant unavailable")
        case_revision, exhibit_revision = rows[0]
        if type(case_revision) is not int or type(exhibit_revision) is not int:
            raise BriefGraphConflict("invalid server snapshot revision")
        return case_revision, exhibit_revision

    def _source(self, conn: Any, *, org: UUID, case: UUID,
                binding: VerifiedBriefBinding, expected_sha: str) -> None:
        rows = conn.execute(
            "select v.original_sha256_hex from caseproof.documents d "
            "join caseproof.document_versions v on v.org_id=d.org_id "
            "and v.document_id=d.id "
            "join caseproof._s2_009b_vault_intents i on i.org_id=v.org_id "
            "and i.case_id=d.case_id and i.document_id=d.id "
            "and i.document_version_id=v.id and i.sha256_hex=v.original_sha256_hex "
            "and i.state='verified' "
            "where d.org_id=%s and d.case_id=%s and d.id=%s "
            "and v.id=%s and i.intent_id=%s "
            "for share of d,v,i",
            (org, case, binding.document_id, binding.document_version_id,
             binding.intent_id),
        ).fetchall()
        if len(rows) != 1 or rows[0][0] != expected_sha:
            raise BriefGraphConflict("private immutable source/version unavailable")

    def _verified_bytes(
        self, *, org: UUID, case: UUID, binding: VerifiedBriefBinding,
        expected_sha: str,
    ) -> None:
        """Never call Vault recovery under an open source/case row lock.

        Missing/tampered Vault bytes may mark the intent unavailable, which is
        itself a DB write. Call this strictly BETWEEN an initial authorization
        transaction and the final reauthorization/lineage lock.
        """
        try:
            raw = self._read_original(org, case, binding.intent_id)
        except Exception:
            raise BriefGraphConflict("original byte verification unavailable") from None
        if (type(raw) is not bytes or len(raw) > 16_000_000
                or sha256(raw).hexdigest() != expected_sha):
            raise BriefGraphConflict("original byte digest or budget mismatch")

    def publish(
        self, *, org_id: UUID, actor_id: UUID, brief_id: UUID,
        binding: VerifiedBriefBinding, representation: BriefRepresentation,
        document_role: str, request_id: UUID, expected_revision: int,
        commit_guard: Callable[[Any, int, int], None] | None = None,
    ) -> BriefWriteReceipt:
        org, actor, logical, request = (
            _uuid(org_id), _uuid(actor_id), _uuid(brief_id), _uuid(request_id),
        )
        if (not isinstance(binding, VerifiedBriefBinding)
                or not isinstance(representation, BriefRepresentation)
                or document_role not in {"own_draft", "opponent_brief"}
                or type(expected_revision) is not int or expected_revision < 0):
            raise BriefGraphConflict("typed immutable graph command required")
        case = _uuid(representation.brief.case_id)
        version = _uuid(representation.brief.version_id)
        # Hashing the caller's raw spelling would make a valid persisted
        # graph unrecoverable when the reader reconstructs canonical UUIDs.
        # Reject noncanonical spellings instead of silently changing source
        # identity or normalizing a security-sensitive caller value.
        if (representation.brief.case_id != str(case)
                or representation.brief.version_id != str(version)):
            raise BriefGraphConflict("canonical case/version UUID spelling required")
        graph_sha = _graph_identity(logical, binding, representation, document_role)
        if not representation.text or len(representation.text.encode("utf-8")) > 480000:
            raise BriefGraphConflict("bounded nonempty representation required")
        # First authorize WITHOUT retaining locks across Vault byte reads:
        # Vault may atomically mark a corrupted original unavailable.
        with self._connect() as conn:
            self._authorize(conn, org, case, actor)
        self._verified_bytes(org=org, case=case, binding=binding,
                             expected_sha=representation.brief.sha256_hex)
        with self._connect() as conn:
            # Reauthorize and re-check current verified Vault lineage under
            # row locks immediately before the immutable graph transaction.
            case_rev, exhibit_rev = self._authorize(conn, org, case, actor)
            self._source(conn, org=org, case=case, binding=binding,
                         expected_sha=representation.brief.sha256_hex)
            # Optional trusted application check executed AFTER reauthorizing
            # and locking the case/grants/source, in this same commit transaction.
            # Corrections use it to lock their reviewer snapshot and reject
            # revocation or changed decisions BEFORE mutating the brief head.
            if commit_guard is not None:
                commit_guard(conn, case_rev, exhibit_rev)
            keys = (org, case, logical)
            conn.execute(
                "insert into caseproof._m2_brief_heads(org_id,case_id,brief_id) "
                "values(%s,%s,%s) on conflict do nothing", keys,
            )
            head = conn.execute(
                "select revision,version_id from caseproof._m2_brief_heads "
                "where org_id=%s and case_id=%s and brief_id=%s for update",
                keys,
            ).fetchone()
            if head is None:
                raise BriefGraphConflict("no lockable brief head")
            prior_rev, prior_version = head
            prior = conn.execute(
                "select e.revision,e.version_id,e.actor_id,e.graph_sha256,"
                "e.expected_revision from caseproof._m2_brief_events e "
                "where e.org_id=%s and e.case_id=%s and e.brief_id=%s "
                "and e.request_id=%s", (*keys, request),
            ).fetchone()
            if prior is not None:
                if (prior[2] != actor or prior[3] != graph_sha
                        or prior[4] != expected_revision
                        or prior[1] != version):
                    raise BriefGraphConflict("request ID reused for different input")
                return BriefWriteReceipt(logical, version, prior[0], graph_sha, True)
            if prior_rev != expected_revision:
                raise BriefGraphConflict("stale brief revision")
            if prior_version == version:
                raise BriefGraphConflict("immutable version ID cannot be reused")
            if prior_version is not None:
                previous = conn.execute(
                    "select document_role,document_version_id from "
                    "caseproof._m2_brief_versions where org_id=%s and case_id=%s "
                    "and brief_id=%s and version_id=%s", (*keys, prior_version),
                ).fetchone()
                if (previous is None or previous[0] != document_role
                        or previous[1] == binding.document_version_id):
                    raise BriefGraphConflict("new version requires new preserved source")
            new_rev = prior_rev + 1
            conn.execute(
                "insert into caseproof._m2_brief_versions("
                "org_id,case_id,brief_id,version_id,revision,parent_version_id,"
                "document_id,document_version_id,vault_intent_id,original_sha256,"
                "representation_sha256,parser_id,representation,document_role,"
                "graph_sha256,case_revision,exhibit_revision,actor_id) "
                "values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (*keys, version, new_rev, prior_version,
                 binding.document_id, binding.document_version_id, binding.intent_id,
                 representation.brief.sha256_hex, representation.text_sha256,
                 representation.parser_id, representation.text, document_role,
                 graph_sha, case_rev, exhibit_rev, actor),
            )
            for index, reference in enumerate(representation.brief.references):
                conn.execute(
                    "insert into caseproof._m2_brief_references("
                    "org_id,case_id,brief_id,version_id,reference_order,"
                    "reference_id,exhibit_label,exact_quote,pdf_page) "
                    "values(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (*keys, version, index, reference.reference_id,
                     reference.exhibit_label, reference.exact_quote, reference.pdf_page),
                )
            for index, assertion in enumerate(representation.claims):
                conn.execute(
                    "insert into caseproof._m2_brief_assertions("
                    "org_id,case_id,brief_id,version_id,claim_order,claim_id,"
                    "reference_id,text_start,text_end,assertion_text,kind,fact_role,"
                    "language,source_language) "
                    "values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (*keys, version, index, assertion.claim_id, assertion.reference_id,
                     assertion.text_start, assertion.text_end, assertion.text,
                     assertion.kind.value, assertion.role.value,
                     assertion.language, assertion.source_language),
                )
            audit = uuid4()
            conn.execute(
                "insert into caseproof.audit_events("
                "id,org_id,case_id,actor_type,actor_user_id,action,"
                "event_schema_version,correlation_id,input_sha256_hex) "
                "values(%s,%s,%s,'human',%s,'m2_brief_graph_publish','m2-v1',%s,%s)",
                (audit, org, case, actor, request, graph_sha),
            )
            conn.execute(
                "insert into caseproof._m2_brief_events("
                "org_id,case_id,brief_id,revision,request_id,actor_id,version_id,"
                "graph_sha256,expected_revision,audit_id) "
                "values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (*keys, new_rev, request, actor, version, graph_sha,
                 expected_revision, audit),
            )
            conn.execute(
                "update caseproof._m2_brief_heads "
                "set revision=%s,version_id=%s "
                "where org_id=%s and case_id=%s and brief_id=%s",
                (new_rev, version, *keys),
            )
            return BriefWriteReceipt(logical, version, new_rev, graph_sha, False)

    def load(
        self, *, org_id: UUID, actor_id: UUID, case_id: UUID,
        brief_id: UUID, version_id: UUID | None = None,
        require_current: bool = True,
    ) -> StoredBriefGraph:
        org, actor, case, logical = (
            _uuid(org_id), _uuid(actor_id), _uuid(case_id), _uuid(brief_id),
        )
        keys = (org, case, logical)
        # Preflight: authorize the actor and obtain a provisional source
        # identity, then release ALL locks before asking Vault to read bytes.
        with self._connect() as conn:
            self._authorize(conn, org, case, actor)
            pre_head = conn.execute(
                "select version_id from caseproof._m2_brief_heads "
                "where org_id=%s and case_id=%s and brief_id=%s",
                keys,
            ).fetchone()
            if pre_head is None or pre_head[0] is None:
                raise BriefGraphConflict("unknown or empty brief graph")
            pre_version = pre_head[0] if version_id is None else _uuid(version_id)
            source = conn.execute(
                "select document_id,document_version_id,vault_intent_id,"
                "original_sha256 from caseproof._m2_brief_versions "
                "where org_id=%s and case_id=%s and brief_id=%s and version_id=%s",
                (*keys, pre_version),
            ).fetchone()
            if source is None:
                raise BriefGraphConflict("unknown pinned original")
        pre_binding = VerifiedBriefBinding(source[0], source[1], source[2])
        self._verified_bytes(org=org, case=case, binding=pre_binding,
                             expected_sha=source[3])
        with self._connect() as conn:
            # Reauthorize after Vault verification; final source/check linkage
            # is locked and cannot silently drift while rehydrating the graph.
            case_rev, exhibit_rev = self._authorize(conn, org, case, actor)
            head = conn.execute(
                "select revision,version_id from caseproof._m2_brief_heads "
                "where org_id=%s and case_id=%s and brief_id=%s for share",
                keys,
            ).fetchone()
            if head is None or head[1] is None:
                raise BriefGraphConflict("unknown or empty brief graph")
            current_version = head[1]
            version = current_version if version_id is None else _uuid(version_id)
            if require_current and version != current_version:
                raise BriefGraphConflict("requested version superseded")
            row = conn.execute(
                "select revision,document_id,document_version_id,vault_intent_id,"
                "original_sha256,representation_sha256,parser_id,representation,"
                "document_role,graph_sha256,case_revision,exhibit_revision "
                "from caseproof._m2_brief_versions "
                "where org_id=%s and case_id=%s and brief_id=%s and version_id=%s",
                (*keys, version),
            ).fetchone()
            if row is None or (require_current and (
                row[10] != case_rev or row[11] != exhibit_rev
            )):
                raise BriefGraphConflict("brief snapshot stale or absent")
            binding = VerifiedBriefBinding(row[1], row[2], row[3])
            if (version != pre_version or binding != pre_binding
                    or row[4] != source[3]):
                raise BriefGraphConflict("pinned source changed during byte read")
            self._source(conn, org=org, case=case, binding=binding, expected_sha=row[4])
            refs = conn.execute(
                "select reference_id,exhibit_label,exact_quote,pdf_page "
                "from caseproof._m2_brief_references "
                "where org_id=%s and case_id=%s and brief_id=%s and version_id=%s "
                "order by reference_order", (*keys, version),
            ).fetchall()
            claims = conn.execute(
                "select claim_id,reference_id,text_start,text_end,assertion_text,"
                "kind,fact_role,language,source_language "
                "from caseproof._m2_brief_assertions "
                "where org_id=%s and case_id=%s and brief_id=%s and version_id=%s "
                "order by claim_order", (*keys, version),
            ).fetchall()
            try:
                references = tuple(DraftReference(*entry) for entry in refs)
                assertions = tuple(FactAssertion(
                    a[0], a[1], a[4], a[2], a[3],
                    FactKind(a[5]), FactRole(a[6]), a[7], a[8],
                ) for a in claims)
                brief = VersionedBrief(
                    str(case), str(version), row[4], references,
                )
                representation = BriefRepresentation(
                    brief, row[7], row[5], row[6], assertions,
                )
            except (ValueError, TypeError, KeyError):
                raise BriefGraphConflict("invalid stored graph representation") from None
            if (_graph_identity(logical, binding, representation, row[8]) != row[9]):
                raise BriefGraphConflict("graph identity digest mismatch")
            return StoredBriefGraph(
                logical, row[0], representation, binding, row[8], row[9],
                (version == current_version and row[10] == case_rev
                 and row[11] == exhibit_rev),
            )
