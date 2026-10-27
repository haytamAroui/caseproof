"""Disposable M2 correction journal: prepare → new graph → fresh check.

No user route, production credential, Word/DOCX write, signing, court release,
or legal approval. Actual byte preservation happens BEFORE prepare via the
trusted private Vault ingestion boundary. Corrections require a separately
preserved and verified new text/plain original; never rewrite source history.

Three independently durable audit stages support recovery after a process
crash. The graph CAS and stage event are different database transactions:
this is a safe replayable saga, NOT an atomic multi-resource transaction.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID, uuid4

from application.litigation.review_cycle import (
    CorrectionPreview,
    CorrectionProposal,
    preview_correction,
)
from application.litigation.unified_review import (
    BriefRepresentation,
    ReviewDisposition,
    VerificationRun,
)
from apps.api.disposable_litigation_brief_graph import (
    BriefGraphConflict,
    DisposableBriefGraphStore,
    VerifiedBriefBinding,
    _graph_identity,
)
from apps.api.disposable_litigation_review_ledger import DisposableM2ReviewLedger
from apps.api.litigation_check_service import AuthorizedLitigationChecker


class CorrectionConflict(ValueError):
    """Fail closed on incomplete provenance, stale review or permission."""


@dataclass(frozen=True, slots=True)
class CorrectionCommand:
    request_id: UUID
    original_run: VerificationRun
    proposal: CorrectionProposal
    new_representation: BriefRepresentation
    new_binding: VerifiedBriefBinding
    expected_brief_revision: int
    expected_review_revision: int

    def __post_init__(self) -> None:
        if (not isinstance(self.request_id, UUID) or self.request_id.version != 4
                or not isinstance(self.original_run, VerificationRun)
                or not isinstance(self.proposal, CorrectionProposal)
                or not isinstance(self.new_representation, BriefRepresentation)
                or not isinstance(self.new_binding, VerifiedBriefBinding)
                or type(self.expected_brief_revision) is not int
                or self.expected_brief_revision < 1
                or type(self.expected_review_revision) is not int
                or self.expected_review_revision < 1):
            raise CorrectionConflict("bounded versioned correction command required")


@dataclass(frozen=True, slots=True)
class CorrectionReceipt:
    request_id: UUID
    new_brief_version: str
    plan_sha256: str
    stage: str
    graph_sha256: str
    recheck_run_sha256: str | None = None
    release_authorized: bool = False


@dataclass(frozen=True, slots=True)
class _Verified:
    org: UUID
    case: UUID
    actor: UUID
    brief: UUID
    preview: CorrectionPreview
    plan_sha: str
    graph_sha: str


def _uuid(value: str | UUID) -> UUID:
    try:
        parsed = UUID(str(value))
        if parsed.int == 0 or (type(value) is str and value != str(parsed)):
            raise ValueError("noncanonical UUID")
        return parsed
    except (TypeError, ValueError, AttributeError):
        raise CorrectionConflict("canonical non-nil ID required") from None


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


class DisposableCorrectionCoordinator:
    """Explicit sealed command from server Auth; no request-asserted actor ID."""

    def __init__(
        self, connection_factory: Callable[[], Any],
        graph: DisposableBriefGraphStore,
        ledger: DisposableM2ReviewLedger,
        checker: AuthorizedLitigationChecker,
    ) -> None:
        self._connect = connection_factory
        self._graph = graph
        self._ledger = ledger
        self._checker = checker

    def _inspect(
        self, *, bearer: str, brief_id: UUID, command: CorrectionCommand,
    ) -> _Verified:
        case = _uuid(command.original_run.case_id)
        brief = _uuid(brief_id)
        try:
            # Both verifications are server-side. No actor/org/tenant input may
            # be furnished independently of the bearer.
            subject = self._checker._verified(bearer)
            scope = self._checker._scope(subject, str(case))
            actor, org = _uuid(subject.subject_id), _uuid(scope.org_id)
            if command.proposal.actor_id != str(actor):
                raise CorrectionConflict("reviewer identity mismatch")
            # Old version can be superseded on replay; the immutable old
            # check is still required to match its exact persisted payload.
            old = self._graph.load(
                org_id=org, actor_id=actor, case_id=case, brief_id=brief,
                version_id=_uuid(command.original_run.brief_version_id),
                require_current=False,
            )
            state = self._ledger.state(
                org_id=org, actor_id=actor, run=command.original_run,
            )
            if state.revision != command.expected_review_revision:
                raise CorrectionConflict("review changed before correction")
            reviewed = next((
                item for item in state.packet.decisions
                if item.observation_id == command.proposal.observation_id
            ), None)
            if reviewed is None or reviewed.disposition is not ReviewDisposition.CONFIRMED:
                raise CorrectionConflict("human-confirmed observation required")
            if (old.document_role != "own_draft"
                    or old.revision != command.expected_brief_revision
                    or old.representation.brief.version_id
                    != command.original_run.brief_version_id
                    or old.representation.brief.sha256_hex
                    != command.original_run.brief_sha256
                    or old.representation.text_sha256
                    != command.original_run.representation_sha256
                    or old.representation.brief.sha256_hex
                    != hashlib.sha256(old.representation.text.encode()).hexdigest()):
                raise CorrectionConflict("only an exact verified text-only draft may be revised")
            correction = preview_correction(
                run=command.original_run,
                text=old.representation.text, proposal=command.proposal,
            )
            next_rep = command.new_representation
            if (next_rep.text != correction.proposed_text
                    or next_rep.text_sha256 != correction.proposed_text_sha256
                    or next_rep.brief.sha256_hex != correction.proposed_text_sha256
                    or next_rep.brief.case_id != str(case)
                    or next_rep.brief.version_id ==
                    command.original_run.brief_version_id
                    or next_rep.parser_id != "fixture-utf8-v1"
                    or old.representation.parser_id != "fixture-utf8-v1"):
                raise CorrectionConflict("unverified corrected source or stale normalized text")
            graph_sha = _graph_identity(brief, command.new_binding, next_rep, "own_draft")
            plan_sha = _digest({
                "request": str(command.request_id),
                "org": str(org), "case": str(case), "actor": str(actor),
                "brief": str(brief), "old_run": command.original_run.snapshot_hash,
                "old_version": command.original_run.brief_version_id,
                "new_version": next_rep.brief.version_id,
                "graph_sha": graph_sha, "proposal": asdict(command.proposal),
                "expected_brief": command.expected_brief_revision,
                "expected_review": command.expected_review_revision,
                "binding": tuple(str(x) for x in (
                    command.new_binding.document_id,
                    command.new_binding.document_version_id,
                    command.new_binding.intent_id,
                )),
            })
            self._graph._verified_bytes(
                org=org, case=case, binding=command.new_binding,
                expected_sha=next_rep.brief.sha256_hex,
            )
            return _Verified(org, case, actor, brief, correction, plan_sha, graph_sha)
        except CorrectionConflict:
            raise
        except Exception:
            raise CorrectionConflict("current private review or evidence unavailable") from None

    @staticmethod
    def _authorize(conn: Any, ctx: _Verified) -> None:
        row = conn.execute(
            "select g.role from caseproof.cases c "
            "join caseproof.organization_members m on m.org_id=c.org_id "
            "and m.user_id=%s and m.active "
            "join caseproof._m1_matter_grants g on g.org_id=c.org_id "
            "and g.case_id=c.id and g.user_id=m.user_id and g.active "
            "where c.org_id=%s and c.id=%s "
            "and m.actions @> array['case:read','finding:write','review:request']::text[] "
            "and g.permissions @> array['case:read','draft:check','review:request']::text[] "
            "for share of c,m,g",
            (ctx.actor, ctx.org, ctx.case),
        ).fetchall()
        if len(row) != 1 or row[0][0] != "reviewer":
            raise CorrectionConflict("active per-matter reviewer privilege required")

    @staticmethod
    def _audit(
        conn: Any, ctx: _Verified, request_id: UUID,
        action: str, fingerprint: str,
    ) -> UUID:
        audit_id = uuid4()
        conn.execute(
            "insert into caseproof.audit_events("
            "id,org_id,case_id,actor_type,actor_user_id,action,"
            "event_schema_version,correlation_id,input_sha256_hex) "
            "values(%s,%s,%s,'human',%s,%s,'m2-correction-v1',%s,%s)",
            (audit_id, ctx.org, ctx.case, ctx.actor, action,
             request_id, fingerprint),
        )
        return audit_id

    @staticmethod
    def _keys(ctx: _Verified, cmd: CorrectionCommand) -> tuple[UUID, ...]:
        return (ctx.org, ctx.case, ctx.brief, cmd.request_id)

    @staticmethod
    def _plan(conn: Any, ctx: _Verified, cmd: CorrectionCommand) -> tuple[Any, ...] | None:
        return conn.execute(
            "select actor_id,input_sha,new_version_id,graph_sha,"
            "expected_brief_revision,expected_review_revision "
            "from caseproof._m2_correction_plans "
            "where org_id=%s and case_id=%s and brief_id=%s and request_id=%s",
            DisposableCorrectionCoordinator._keys(ctx, cmd),
        ).fetchone()

    def prepare(
        self, *, bearer: str, brief_id: UUID, command: CorrectionCommand,
    ) -> CorrectionReceipt:
        ctx = self._inspect(bearer=bearer, brief_id=brief_id, command=command)
        keys = self._keys(ctx, command)
        with self._connect() as conn:
            self._authorize(conn, ctx)
            old = self._plan(conn, ctx, command)
            if old is not None:
                if (old[0] != ctx.actor or old[1] != ctx.plan_sha
                        or str(old[2]) != command.new_representation.brief.version_id
                        or old[3] != ctx.graph_sha
                        or old[4] != command.expected_brief_revision
                        or old[5] != command.expected_review_revision):
                    raise CorrectionConflict("idempotency request changed")
            else:
                # An unrelated writer may not advance the head between preview
                # and the immutable prepared journal event.
                head = conn.execute(
                    "select revision,version_id from caseproof._m2_brief_heads "
                    "where org_id=%s and case_id=%s and brief_id=%s for share",
                    keys[:3],
                ).fetchone()
                if (head is None or head[0] != command.expected_brief_revision
                        or str(head[1]) != command.original_run.brief_version_id):
                    raise CorrectionConflict("stale brief head before prepare")
                # Current new version and Vault state rechecked AFTER bytes,
                # under a short shared source row lock (no Vault read inside).
                self._graph._source(
                    conn, org=ctx.org, case=ctx.case,
                    binding=command.new_binding,
                    expected_sha=command.new_representation.brief.sha256_hex,
                )
                media = conn.execute(
                    "select media_type from caseproof.document_versions "
                    "where org_id=%s and id=%s",
                    (ctx.org, command.new_binding.document_version_id),
                ).fetchone()
                if media is None or media[0] != "text/plain":
                    raise CorrectionConflict("only immutable UTF-8 text originals supported")
                audit = self._audit(
                    conn, ctx, command.request_id, "m2_correction_prepare",
                    ctx.plan_sha,
                )
                conn.execute(
                    "insert into caseproof._m2_correction_plans("
                    "org_id,case_id,brief_id,request_id,actor_id,old_run_sha,"
                    "old_version_id,new_version_id,new_document_version_id,"
                    "new_vault_intent_id,expected_brief_revision,"
                    "expected_review_revision,input_sha,corrected_text_sha,"
                    "graph_sha,audit_id) "
                    "values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (*keys, ctx.actor, command.original_run.snapshot_hash,
                     _uuid(command.original_run.brief_version_id),
                     _uuid(command.new_representation.brief.version_id),
                     command.new_binding.document_version_id,
                     command.new_binding.intent_id, command.expected_brief_revision,
                     command.expected_review_revision, ctx.plan_sha,
                     ctx.preview.proposed_text_sha256, ctx.graph_sha, audit),
                )
        return CorrectionReceipt(
            command.request_id, command.new_representation.brief.version_id,
            ctx.plan_sha, "prepared", ctx.graph_sha,
        )

    def apply(
        self, *, bearer: str, brief_id: UUID, command: CorrectionCommand,
    ) -> CorrectionReceipt:
        prepared = self.prepare(bearer=bearer, brief_id=brief_id, command=command)
        ctx = self._inspect(bearer=bearer, brief_id=brief_id, command=command)
        # Both graph writes and this stage are independently transactionally
        # audited. An OUTCOME_UNKNOWN between them can be retried with the
        # same immutable graph version + request UUID (idempotent replay).
        try:
            receipt = self._graph.publish(
                org_id=ctx.org, actor_id=ctx.actor, brief_id=ctx.brief,
                binding=command.new_binding,
                representation=command.new_representation,
                document_role="own_draft", request_id=command.request_id,
                expected_revision=command.expected_brief_revision,
            )
        except BriefGraphConflict:
            raise CorrectionConflict("stale, revoked or unverified corrected graph") from None
        if (receipt.graph_sha256 != ctx.graph_sha
                or receipt.version_id != _uuid(prepared.new_brief_version)):
            raise CorrectionConflict("source graph commit receipt inconsistent")
        keys = self._keys(ctx, command)
        with self._connect() as conn:
            self._authorize(conn, ctx)
            plan = self._plan(conn, ctx, command)
            if plan is None or plan[1] != ctx.plan_sha:
                raise CorrectionConflict("prepared event lost")
            head = conn.execute(
                "select revision,version_id from caseproof._m2_brief_heads "
                "where org_id=%s and case_id=%s and brief_id=%s for share",
                keys[:3],
            ).fetchone()
            if (head is None or head[0] != command.expected_brief_revision + 1
                    or head[1] != receipt.version_id):
                raise CorrectionConflict("superseded corrected graph cannot be acknowledged")
            event = conn.execute(
                "select graph_sha from caseproof._m2_correction_events "
                "where org_id=%s and case_id=%s and brief_id=%s and request_id=%s "
                "and phase='graph_applied'", keys,
            ).fetchone()
            if event is not None:
                if event[0] != ctx.graph_sha:
                    raise CorrectionConflict("changed graph on stage replay")
            else:
                audit = self._audit(
                    conn, ctx, command.request_id, "m2_correction_graph_applied",
                    ctx.graph_sha,
                )
                conn.execute(
                    "insert into caseproof._m2_correction_events("
                    "org_id,case_id,brief_id,request_id,phase,actor_id,graph_sha,"
                    "check_run_sha,audit_id) "
                    "values(%s,%s,%s,%s,'graph_applied',%s,%s,null,%s)",
                    (*keys, ctx.actor, ctx.graph_sha, audit),
                )
        return CorrectionReceipt(
            command.request_id, prepared.new_brief_version,
            ctx.plan_sha, "graph_applied", ctx.graph_sha,
        )

    def recheck(
        self, *, bearer: str, brief_id: UUID, command: CorrectionCommand,
    ) -> CorrectionReceipt:
        applied = self.apply(bearer=bearer, brief_id=brief_id, command=command)
        ctx = self._inspect(bearer=bearer, brief_id=brief_id, command=command)
        # The signed-boundary checker reads the NEW pinned graph and live
        # current exhibit/source universe, and publishes its own immutable run.
        run = self._checker.check(
            bearer=bearer, case_id=str(ctx.case),
            brief_version_id=applied.new_brief_version,
        )
        if (run.brief_version_id != applied.new_brief_version
                or run.snapshot_hash == command.original_run.snapshot_hash
                or run.representation_sha256
                != command.new_representation.text_sha256):
            raise CorrectionConflict("fresh verification run unavailable")
        keys = self._keys(ctx, command)
        with self._connect() as conn:
            self._authorize(conn, ctx)
            head = conn.execute(
                "select version_id from caseproof._m2_brief_heads "
                "where org_id=%s and case_id=%s and brief_id=%s for share",
                keys[:3],
            ).fetchone()
            source = conn.execute(
                "select snapshot_sha from caseproof._m2_check_runs "
                "where org_id=%s and case_id=%s and snapshot_sha=%s "
                "and brief_version_id=%s",
                (ctx.org, ctx.case, run.snapshot_hash, run.brief_version_id),
            ).fetchone()
            if (head is None or head[0] != _uuid(applied.new_brief_version)
                    or source is None):
                raise CorrectionConflict("correction recheck not source-bound")
            event = conn.execute(
                "select graph_sha,check_run_sha from "
                "caseproof._m2_correction_events "
                "where org_id=%s and case_id=%s and brief_id=%s and request_id=%s "
                "and phase='rechecked'", keys,
            ).fetchone()
            if event is not None:
                if event != (ctx.graph_sha, run.snapshot_hash):
                    raise CorrectionConflict("recheck replay changed result")
            else:
                audit = self._audit(
                    conn, ctx, command.request_id,
                    "m2_correction_rechecked", run.snapshot_hash,
                )
                conn.execute(
                    "insert into caseproof._m2_correction_events("
                    "org_id,case_id,brief_id,request_id,phase,actor_id,graph_sha,"
                    "check_run_sha,audit_id) "
                    "values(%s,%s,%s,%s,'rechecked',%s,%s,%s,%s)",
                    (*keys, ctx.actor, ctx.graph_sha, run.snapshot_hash, audit),
                )
        return CorrectionReceipt(
            command.request_id, applied.new_brief_version,
            ctx.plan_sha, "rechecked", ctx.graph_sha, run.snapshot_hash,
        )
