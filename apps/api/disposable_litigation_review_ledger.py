"""M2 durable review ledger over disposable PostgreSQL, never a live API.

The caller MUST provide a server-computed VerificationRun from verified source
bytes. Actor UUIDs are synthetic test principals here. A production adapter
must bind real signed identity to least-privilege DB sessions before exposure.
This store records technical reviews, NEVER legal/filing approvals.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID, uuid4

from application.litigation.review_cycle import ReviewPacket, revise_review
from application.litigation.unified_review import (
    ObservationReview,
    ReviewDisposition,
    VerificationRun,
    verification_record,
)

ZERO_HASH = "0" * 64


class M2LedgerConflict(ValueError):
    """Fail closed on denied, stale, corrupt or conflicting M2 ledger state."""


def _canonical(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _uuid(value: UUID | str) -> UUID:
    try:
        result = UUID(str(value))
        if result.int == 0:
            raise ValueError("nil")
        return result
    except (TypeError, ValueError, AttributeError):
        raise M2LedgerConflict("non-nil server UUID required") from None


@dataclass(frozen=True, slots=True)
class M2LedgerState:
    run_snapshot_hash: str
    revision: int
    event_sha: str
    packet: ReviewPacket
    event_count: int
    customer_release_authorized: bool = False


class DisposableM2ReviewLedger:
    """PostgreSQL transaction/append-only adapter; no production wiring."""

    persistence = "disposable_postgres_only"

    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connect = connection_factory

    @staticmethod
    def _authorize(conn: Any, *, org: UUID, case: UUID, actor: UUID,
                   action: str) -> tuple[int, int]:
        if action not in {"draft:check", "review:request"}:
            raise M2LedgerConflict("invalid review permission")
        org_action = ["case:read"] if action == "draft:check" else ["case:read", "review:request"]
        row = conn.execute(
            "select c.case_revision,h.revision "
            "from caseproof.cases c "
            "join caseproof.organization_members m on m.org_id=c.org_id "
            "and m.user_id=%s and m.active "
            "join caseproof._m1_matter_grants g on g.org_id=c.org_id "
            "and g.case_id=c.id and g.user_id=m.user_id and g.active "
            "join caseproof._m1_exhibit_heads h on h.org_id=c.org_id and h.case_id=c.id "
            "where c.org_id=%s and c.id=%s and m.actions @> %s::text[] "
            "and g.permissions @> array['case:read',%s]::text[] "
            "and (%s != 'review:request' or g.role='reviewer') "
            "for share of c,m,g,h",
            (actor, org, case, org_action, action, action),
        ).fetchall()
        if len(row) != 1 or type(row[0][0]) is not int or type(row[0][1]) is not int:
            raise M2LedgerConflict("private matter or current grant unavailable")
        return row[0][0], row[0][1]

    @staticmethod
    def _verified_sources(conn: Any, *, org: UUID, case: UUID,
                          run: VerificationRun) -> None:
        """Verify processed document/version lineage; incomplete may remain unknown."""
        if (len(run.declared) > 32 or len(run.processed) > 32
                or not set(run.processed) <= set(run.declared)
                or not set(run.incomplete) <= set(run.declared)
                or not set(run.excluded) <= set(run.declared)
                or set(run.processed) & set(run.incomplete)
                or set(run.processed) & set(run.excluded)):
            raise M2LedgerConflict("invalid source denominator")
        for source_id, version_id in run.processed:
            document, version = _uuid(source_id), _uuid(version_id)
            row = conn.execute(
                "select v.original_sha256_hex "
                "from caseproof.documents d "
                "join caseproof.document_versions v on v.org_id=d.org_id "
                "and v.document_id=d.id "
                "join caseproof._s2_009b_vault_intents i on i.org_id=v.org_id "
                "and i.case_id=d.case_id and i.document_id=d.id "
                "and i.document_version_id=v.id and i.sha256_hex=v.original_sha256_hex "
                "and i.state='verified' "
                "where d.org_id=%s and d.case_id=%s and d.id=%s and v.id=%s",
                (org, case, document, version),
            ).fetchall()
            if len(row) != 1 or not isinstance(row[0][0], str):
                raise M2LedgerConflict("processed original not in verified private custody")
            for citation in run.citation_observations:
                if citation.source_id == source_id and citation.source_version_id == version_id:
                    if citation.source_sha256 != row[0][0]:
                        raise M2LedgerConflict("source digest changed")
            for fact in run.factual_observations:
                if fact.source_id == source_id and fact.source_version_id == version_id:
                    if fact.source_sha256 != row[0][0]:
                        raise M2LedgerConflict("factual citation digest changed")

    @staticmethod
    def _stored_payload(conn: Any, org: UUID, case: UUID,
                        run: VerificationRun, expected_case_revision: int) -> str:
        row = conn.execute(
            "select payload,payload_sha,case_revision,exhibit_revision,brief_version_id "
            "from caseproof._m2_check_runs "
            "where org_id=%s and case_id=%s and snapshot_sha=%s",
            (org, case, run.snapshot_hash),
        ).fetchone()
        if row is None:
            raise M2LedgerConflict("unknown versioned check run")
        encoded = verification_record(run).decode("utf-8")
        if (row[0] != encoded or row[1] != _digest(row[0])
                or row[2] != expected_case_revision or row[3] != run.exhibit_revision
                or row[4] != run.brief_version_id):
            raise M2LedgerConflict("run payload, source or case snapshot changed")
        return encoded

    def publish(self, *, org_id: UUID, actor_id: UUID,
                run: VerificationRun) -> bool:
        """Store immutable check record; duplicate exact snapshot is replay."""
        if not isinstance(run, VerificationRun):
            raise M2LedgerConflict("trusted M2 run required")
        org, actor, case = _uuid(org_id), _uuid(actor_id), _uuid(run.case_id)
        encoded = verification_record(run).decode("utf-8")
        if len(encoded.encode("utf-8")) > 262144 or len(run.snapshot_hash) != 64:
            raise M2LedgerConflict("bounded versioned run required")
        with self._connect() as conn:
            case_rev, exhibit_rev = self._authorize(
                conn, org=org, case=case, actor=actor, action="draft:check"
            )
            if run.exhibit_revision != exhibit_rev:
                raise M2LedgerConflict("stale exhibit register")
            self._verified_sources(conn, org=org, case=case, run=run)
            keys = (org, case, run.snapshot_hash)
            inserted = conn.execute(
                "insert into caseproof._m2_check_runs "
                "(org_id,case_id,snapshot_sha,payload_sha,payload,brief_version_id,"
                "case_revision,exhibit_revision,actor_id) "
                "values(%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "on conflict do nothing returning snapshot_sha",
                (*keys, _digest(encoded), encoded, run.brief_version_id,
                 case_rev, exhibit_rev, actor),
            ).fetchone()
            self._stored_payload(conn, org, case, run, case_rev)
            conn.execute(
                "insert into caseproof._m2_review_heads "
                "(org_id,case_id,snapshot_sha,event_sha) values(%s,%s,%s,%s) "
                "on conflict do nothing", (*keys, ZERO_HASH),
            )
            return inserted is not None

    @staticmethod
    def _events(conn: Any, keys: tuple[UUID, UUID, str],
                run: VerificationRun, expected_revision: int,
                expected_head: str) -> M2LedgerState:
        rows = conn.execute(
            "select revision,request_id,actor_id,previous_sha,event_sha,decision "
            "from caseproof._m2_review_events "
            "where org_id=%s and case_id=%s and snapshot_sha=%s "
            "order by revision limit 257", keys,
        ).fetchall()
        if len(rows) != expected_revision or len(rows) > 256:
            raise M2LedgerConflict("incomplete or unbounded review history")
        current = ZERO_HASH
        packet = ReviewPacket(run.snapshot_hash, 0)
        for rev, request_id, actor_id, previous, event_sha, encoded in rows:
            if rev != packet.revision + 1 or previous != current:
                raise M2LedgerConflict("broken event revision chain")
            item = json.loads(encoded)
            actor = str(_uuid(actor_id))
            decision = ObservationReview(
                item["observation_id"], actor,
                ReviewDisposition(item["disposition"]), item["rationale"],
            )
            digest = _digest(_canonical({
                "run": run.snapshot_hash, "revision": rev,
                "request": str(_uuid(request_id)), "actor": actor,
                "previous_sha": current, "decision": item,
            }))
            if digest != event_sha or item["actor_id"] != actor:
                raise M2LedgerConflict("tampered review event")
            packet = revise_review(run=run, packet=packet,
                                   expected_revision=packet.revision, decision=decision)
            current = digest
        if current != expected_head:
            raise M2LedgerConflict("review head hash mismatch")
        return M2LedgerState(run.snapshot_hash, packet.revision,
                             current, packet, len(rows))

    def state(self, *, org_id: UUID, actor_id: UUID,
              run: VerificationRun) -> M2LedgerState:
        org, actor, case = _uuid(org_id), _uuid(actor_id), _uuid(run.case_id)
        with self._connect() as conn:
            case_rev, exhibit_rev = self._authorize(
                conn, org=org, case=case, actor=actor, action="review:request"
            )
            if exhibit_rev != run.exhibit_revision:
                raise M2LedgerConflict("review stale after exhibit change")
            self._verified_sources(conn, org=org, case=case, run=run)
            self._stored_payload(conn, org, case, run, case_rev)
            keys = (org, case, run.snapshot_hash)
            head = conn.execute(
                "select revision,event_sha from caseproof._m2_review_heads "
                "where org_id=%s and case_id=%s and snapshot_sha=%s",
                keys,
            ).fetchone()
            if head is None:
                raise M2LedgerConflict("review head unavailable")
            return self._events(conn, keys, run, int(head[0]), str(head[1]))

    def _audit(self, conn: Any, org: UUID, case: UUID, actor: UUID,
               request_id: UUID, fingerprint: str) -> UUID:
        audit_id = uuid4()
        conn.execute(
            "insert into caseproof.audit_events("
            "id,org_id,case_id,actor_type,actor_user_id,action,"
            "event_schema_version,correlation_id,input_sha256_hex) "
            "values(%s,%s,%s,'human',%s,'m2_review_disposition','m2-v1',%s,%s)",
            (audit_id, org, case, actor, request_id, fingerprint),
        )
        return audit_id

    def record(self, *, org_id: UUID, actor_id: UUID, run: VerificationRun,
               request_id: UUID, expected_revision: int,
               decision: ObservationReview) -> tuple[M2LedgerState, bool]:
        org, actor, case, request = (_uuid(org_id), _uuid(actor_id),
                                     _uuid(run.case_id), _uuid(request_id))
        if (not isinstance(decision, ObservationReview) or decision.actor_id != str(actor)
                or type(expected_revision) is not int or expected_revision < 0):
            raise M2LedgerConflict("signed reviewer and expected revision required")
        encoded = _canonical(asdict(decision))
        fingerprint = _digest(_canonical({
            "run": run.snapshot_hash, "actor": str(actor),
            "request": str(request), "expected": expected_revision, "decision": encoded,
        }))
        keys = (org, case, run.snapshot_hash)
        with self._connect() as conn:
            case_rev, exhibit_rev = self._authorize(
                conn, org=org, case=case, actor=actor, action="review:request"
            )
            if exhibit_rev != run.exhibit_revision:
                raise M2LedgerConflict("stale exhibit mapping")
            self._verified_sources(conn, org=org, case=case, run=run)
            self._stored_payload(conn, org, case, run, case_rev)
            row = conn.execute(
                "select revision,event_sha from caseproof._m2_review_heads "
                "where org_id=%s and case_id=%s and snapshot_sha=%s for update", keys,
            ).fetchone()
            if row is None:
                raise M2LedgerConflict("no persisted review head")
            packet_state = self._events(conn, keys, run, int(row[0]), str(row[1]))
            old = conn.execute(
                "select input_sha,revision,event_sha from caseproof._m2_review_receipts "
                "where org_id=%s and case_id=%s and snapshot_sha=%s and request_id=%s",
                (*keys, request),
            ).fetchone()
            if old is not None:
                if old[0] != fingerprint:
                    raise M2LedgerConflict("idempotency key reused with different review")
                if old[1] > packet_state.revision or old[2] == ZERO_HASH:
                    raise M2LedgerConflict("invalid persisted review receipt")
                return packet_state, True
            updated = revise_review(
                run=run, packet=packet_state.packet,
                expected_revision=expected_revision, decision=decision,
            )
            if updated.revision > 256:
                raise M2LedgerConflict("review event budget exhausted")
            event_sha = _digest(_canonical({
                "run": run.snapshot_hash, "revision": updated.revision,
                "request": str(request), "actor": str(actor),
                "previous_sha": packet_state.event_sha, "decision": json.loads(encoded),
            }))
            audit_id = self._audit(conn, org, case, actor, request, fingerprint)
            conn.execute(
                "insert into caseproof._m2_review_events("
                "org_id,case_id,snapshot_sha,revision,request_id,actor_id,"
                "previous_sha,event_sha,decision,audit_id) "
                "values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (*keys, updated.revision, request, actor, packet_state.event_sha,
                 event_sha, encoded, audit_id),
            )
            conn.execute(
                "insert into caseproof._m2_review_receipts("
                "org_id,case_id,snapshot_sha,request_id,input_sha,revision,event_sha) "
                "values(%s,%s,%s,%s,%s,%s,%s)",
                (*keys, request, fingerprint, updated.revision, event_sha),
            )
            conn.execute(
                "update caseproof._m2_review_heads set revision=%s,event_sha=%s "
                "where org_id=%s and case_id=%s and snapshot_sha=%s",
                (updated.revision, event_sha, *keys),
            )
            return M2LedgerState(run.snapshot_hash, updated.revision,
                                 event_sha, updated, updated.revision), False
