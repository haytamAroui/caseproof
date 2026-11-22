"""Development-only lawyer decision endpoints (roadmap task 3): no production mount.

The four dispositions (confirmed, qualified, rejected, waived) pass through
this API with traceability. The client never supplies the machine result,
the actor or the validity: the server binds each decision to ITS OWN stored
RuleResult for the run, derives the actor from the bearer via the injected
resolver, and re-validates decisions against the current results on every
read (recompute invalidation is visible through the API).

A FAIL is never rewritten: responses always carry the original machine
status separately from the disposition. Persistence with signed actor
authorization is an integration gate; this router uses an in-memory ledger
for development only and grants no export or readiness rights (task 2).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Header
from pydantic import BaseModel, ConfigDict, Field

from application.litigation.lawyer_decisions import (
    DecisionValidity,
    Disposition,
    LawyerDecision,
    LawyerDecisionError,
    decision_views,
    record_decision,
)
from application.litigation.rule_results import RuleResult
from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.litigation_evidence_app import _token

_DISPOSITIONS = tuple(d.value for d in Disposition)


class DecisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    rule_id: str = Field(min_length=1, max_length=128)
    reference: str = Field(min_length=1, max_length=256)
    disposition: Literal["confirmed", "qualified", "rejected", "waived"]
    rationale: str = Field(min_length=1, max_length=2000)
    scope: str = Field(min_length=1, max_length=400)


@dataclass
class InMemoryDecisionLedger:
    """Development-only decision store; persistence is an integration gate."""

    decisions: list[LawyerDecision] = field(default_factory=list)

    def add(self, decision: LawyerDecision) -> None:
        self.decisions.append(decision)

    def for_run(self, rule_ids: set[str]) -> list[LawyerDecision]:
        return [d for d in self.decisions if d.rule_id in rule_ids]


def _render(decision: LawyerDecision, validity: DecisionValidity | None, detail: str) -> dict[str, Any]:
    return {
        "decision_id": decision.decision_id,
        "rule_id": decision.rule_id,
        "rule_version": decision.rule_version,
        "reference": decision.reference,
        "disposition": decision.disposition.value,
        "rationale": decision.rationale,
        "scope": decision.scope,
        "actor_id": decision.actor_id,
        "decided_at": decision.decided_at,
        "machine_status": decision.machine_status,
        "machine_reason": decision.machine_reason,
        "content_hash": decision.content_hash,
        "result_fingerprint": decision.result_fingerprint,
        "validity": validity.value if validity else None,
        "validity_detail": detail,
    }


def create_lawyer_decision_router(
    results_provider: Callable[[str], tuple[RuleResult, ...]] | None = None,
    actor_resolver: Callable[[str | None], str | None] | None = None,
    ledger: InMemoryDecisionLedger | None = None,
) -> APIRouter:
    """Router over server-held rule results; None provider means unavailable."""
    router = APIRouter()
    store = ledger if ledger is not None else InMemoryDecisionLedger()
    base = "/v2/rule-runs/{run_id}/decisions"

    def _results(run_id: str) -> tuple[RuleResult, ...]:
        if results_provider is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return results_provider(run_id)

    def _actor(authorization: str | None) -> str:
        if actor_resolver is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        actor = actor_resolver(_token(authorization))
        if not actor:
            raise AccessRejected(AccessFailure.AUTHENTICATION_REQUIRED)
        return actor

    @router.get(base)
    def list_decisions(
        run_id: str, authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        _actor(authorization)
        results = _results(run_id)
        views = decision_views(list(results), store.for_run({r.rule_id for r in results}))
        return {
            "run_id": run_id,
            "decisions": [
                _render(view.decision, view.validity, view.validity_detail)
                for view in views if view.decision is not None
            ],
            "results_without_decision": [
                {"rule_id": view.result.rule_id, "reference": view.result.reference,
                 "machine_status": view.machine_status}
                for view in views if view.decision is None
            ],
        }

    @router.post(base)
    def record(
        run_id: str, body: DecisionBody,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        actor = _actor(authorization)
        results = _results(run_id)
        matching = [r for r in results if r.rule_id == body.rule_id and r.reference == body.reference]
        if not matching:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        try:
            decision = record_decision(
                matching[0],
                actor_id=actor,
                disposition=Disposition(body.disposition),
                rationale=body.rationale,
                scope=body.scope,
                decided_at=datetime.now(UTC).isoformat(timespec="seconds"),
            )
        except LawyerDecisionError as exc:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED) from exc
        store.add(decision)
        view = decision_views([matching[0]], [decision])[0]
        return _render(decision, view.validity, view.validity_detail)

    return router


__all__ = [
    "DecisionBody",
    "InMemoryDecisionLedger",
    "create_lawyer_decision_router",
]
