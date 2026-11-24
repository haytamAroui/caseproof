"""Live signed review ledger over the proposed masked review RPCs.

Per-request adapter bound to one verified bearer, mirroring
DisposableM2ReviewLedger semantics without ever trusting the transport:
the adapter re-derives the payload digest and the whole event chain from
the returned content, folds the packet with the domain revise_review and
refuses any drift. The RPCs own authorization, staleness, custody, the
decision contract, replay-before-CAS idempotency and the SQL-side event
digest; a non-canonical stored decision can never verify here (fail
closed). Technical review records only: NEVER legal, filing or release
approval.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict
from typing import Any
from uuid import UUID

from application.litigation.review_cycle import ReviewPacket, revise_review
from application.litigation.unified_review import (
    ObservationReview,
    ReviewDisposition,
    VerificationRun,
    verification_record,
)
from apps.api.disposable_litigation_review_ledger import (
    ZERO_HASH,
    M2LedgerConflict,
    M2LedgerState,
    _canonical,
    _digest,
)

__all__ = ["LiveReviewLedger"]


def _uuid(value: UUID | str) -> UUID:
    try:
        result = UUID(str(value))
        if result.int == 0:
            raise ValueError("nil")
        return result
    except (TypeError, ValueError, AttributeError):
        raise M2LedgerConflict("non-nil server UUID required") from None


class LiveReviewLedger:
    """Per-request live review ledger bound to one verified bearer."""

    persistence = "live_signed_supabase"

    def __init__(self, *, call_rpc: Callable[..., Any], publishable_key: str,
                 bearer: str) -> None:
        if not callable(call_rpc) or not isinstance(publishable_key, str):
            raise ValueError("invalid live review ledger composition")
        self._rpc = call_rpc
        self._key = publishable_key
        self._bearer = bearer

    def _call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        try:
            result = self._rpc(publishable_key=self._key, bearer=self._bearer,
                               name=name, args=args)
        except Exception:
            raise M2LedgerConflict("private review ledger unavailable") from None
        if not isinstance(result, dict) or result.get("ok") is not True:
            error = result.get("error") if isinstance(result, dict) else None
            if error in {"invalid", "conflict", "stale"}:
                raise M2LedgerConflict(f"review ledger refused: {error}")
            raise M2LedgerConflict("private review ledger unavailable")
        return result

    @staticmethod
    def _payload(run: VerificationRun) -> tuple[str, str]:
        if not isinstance(run, VerificationRun):
            raise M2LedgerConflict("trusted M2 run required")
        encoded = verification_record(run).decode("utf-8")
        if len(encoded.encode("utf-8")) > 262144 or len(run.snapshot_hash) != 64:
            raise M2LedgerConflict("bounded versioned run required")
        return encoded, _digest(encoded)

    def publish(self, *, org_id: UUID | str, actor_id: UUID | str,
                run: VerificationRun) -> bool:
        """Store immutable check record; duplicate exact snapshot is replay."""
        _uuid(org_id)
        _uuid(actor_id)
        _uuid(run.case_id)
        encoded, payload_sha = self._payload(run)
        result = self._call("caseproof_signed_review_run_publish", {
            "p_case": str(_uuid(run.case_id)),
            "p_snapshot_sha": run.snapshot_hash,
            "p_brief_version": run.brief_version_id,
            "p_exhibit_revision": run.exhibit_revision,
            "p_payload": encoded,
            "p_payload_sha": payload_sha,
        })
        replay = result.get("replay")
        if type(replay) is not bool:
            raise M2LedgerConflict("malformed review ledger response")
        return not replay

    def _fold(self, run: VerificationRun, head: dict[str, Any],
              events: list[dict[str, Any]]) -> M2LedgerState:
        """Re-derive the chain from returned content; never trust the head."""
        revision = head.get("revision")
        event_sha = head.get("event_sha")
        if (type(revision) is not int or revision < 0 or revision > 256
                or not isinstance(event_sha, str) or len(event_sha) != 64
                or not isinstance(events, list) or len(events) != revision):
            raise M2LedgerConflict("incomplete or unbounded review history")
        current = ZERO_HASH
        packet = ReviewPacket(run.snapshot_hash, 0)
        for row in events:
            rev = row.get("revision")
            if rev != packet.revision + 1 or row.get("previous_sha") != current:
                raise M2LedgerConflict("broken event revision chain")
            try:
                item = json.loads(row["decision"])
                actor = str(_uuid(row["actor_id"]))
                request = str(_uuid(row["request_id"]))
                decision = ObservationReview(
                    item["observation_id"], actor,
                    ReviewDisposition(item["disposition"]), item["rationale"],
                )
            except (KeyError, TypeError, ValueError):
                raise M2LedgerConflict("tampered review event") from None
            digest = _digest(_canonical({
                "run": run.snapshot_hash, "revision": rev,
                "request": request, "actor": actor,
                "previous_sha": current, "decision": item,
            }))
            if digest != row.get("event_sha") or item.get("actor_id") != actor:
                raise M2LedgerConflict("tampered review event")
            packet = revise_review(run=run, packet=packet,
                                   expected_revision=packet.revision,
                                   decision=decision)
            current = digest
        if current != event_sha:
            raise M2LedgerConflict("review head hash mismatch")
        return M2LedgerState(run.snapshot_hash, packet.revision, current,
                             packet, len(events))

    def state(self, *, org_id: UUID, actor_id: UUID,
              run: VerificationRun) -> M2LedgerState:
        _uuid(org_id)
        _uuid(actor_id)
        encoded, payload_sha = self._payload(run)
        result = self._call("caseproof_signed_review_state", {
            "p_case": str(_uuid(run.case_id)),
            "p_snapshot_sha": run.snapshot_hash,
        })
        stored = result.get("run")
        head = result.get("head")
        events = result.get("events")
        if (not isinstance(stored, dict) or not isinstance(head, dict)
                or not isinstance(events, list)):
            raise M2LedgerConflict("malformed review ledger response")
        # Stored payload must be the exact record of THIS run, digest included.
        if (stored.get("payload") != encoded
                or stored.get("payload_sha") != payload_sha
                or stored.get("brief_version_id") != run.brief_version_id
                or stored.get("exhibit_revision") != run.exhibit_revision):
            raise M2LedgerConflict("run payload, source or case snapshot changed")
        return self._fold(run, head, events)

    def record(self, *, org_id: UUID, actor_id: UUID, run: VerificationRun,
               request_id: UUID, expected_revision: int,
               decision: ObservationReview) -> tuple[M2LedgerState, bool]:
        org, actor, request = _uuid(org_id), _uuid(actor_id), _uuid(request_id)
        if (not isinstance(decision, ObservationReview)
                or decision.actor_id != str(actor)
                or type(expected_revision) is not int or expected_revision < 0):
            raise M2LedgerConflict("signed reviewer and expected revision required")
        encoded = _canonical(asdict(decision))
        result = self._call("caseproof_signed_review_decision", {
            "p_case": str(_uuid(run.case_id)),
            "p_snapshot_sha": run.snapshot_hash,
            "p_request": str(request),
            "p_expected": expected_revision,
            "p_decision": encoded,
        })
        replay = result.get("replay")
        if type(replay) is not bool:
            raise M2LedgerConflict("malformed review ledger response")
        # Re-read and re-verify the folded state from content, never the
        # write response alone.
        return self.state(org_id=org, actor_id=actor, run=run), replay
