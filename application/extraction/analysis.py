"""Evidence Intelligence review, reconciliation and repair planning.

Application-level, non-authoritative projections: no Kernel mutation, no approval
side effects, no provider calls. Every suggestion remains tied to original spans.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, Literal

from application.extraction.contracts import (
    EntityScope,
    ExtractionError,
    ExtractionRequest,
    Scope,
    Vocabulary,
    canonical,
    digest,
)

if TYPE_CHECKING:
    from application.extraction.pipeline import Atom

_DECIMAL = re.compile(r"^[+-]?[0-9]+(?:[.,][0-9]{1,2})?$")
_CURRENCY = re.compile(r"(?<![A-Z])(?:EUR|USD|GBP|CHF|AED|SAR)(?![A-Z])", re.I)
_AMENDMENT = re.compile(r"\b(amended|amendment|revised|replaces|supersedes|credit note|corrected|rectified)\b", re.I)


@dataclass(frozen=True)
class BoundaryReview:
    """Trusted *application* input; untrusted model output must never instantiate authority."""

    proposal_id: str
    reviewer_reference: str
    action: Literal["confirm", "reject"]
    source_sha256: str
    representation_sha256: str


def confirm_reviewed_boundaries(
    request: ExtractionRequest,
    discoveries: tuple[dict[str, Any], ...],
    decisions: tuple[BoundaryReview, ...],
    *,
    authorize: Callable[[Scope, str], bool],
) -> ExtractionRequest:
    """Only an authorized application decision can narrow an existing unconfirmed boundary.

    A scout quote cannot create a new claim/entity or widen access. The review reference
    must be verified by the calling application; this helper does not authenticate anyone.
    Rejections leave the request unchanged and are never silently converted to confirmations.
    Each confirmation freezes to the exact scout quote span, not the whole original document.
    """

    proposals = {d["id"]: d for d in discoveries if d.get("category") == "entities"}
    sources = {s.source_id: s for s in request.sources}
    changed = list(request.entities)
    seen: set[str] = set()
    for decision in decisions:
        if decision.proposal_id in seen:
            raise ExtractionError("duplicate boundary review")
        if decision.action not in {"confirm", "reject"}:
            raise ExtractionError("invalid boundary review action")
        seen.add(decision.proposal_id)
        if not decision.reviewer_reference.strip() or not authorize(request.scope, decision.reviewer_reference):
            raise ExtractionError("authorized boundary reviewer required")
        discovered = proposals.get(decision.proposal_id)
        if not discovered or discovered.get("state") != "proposed":
            raise ExtractionError("nonexistent or ungrounded boundary proposal")
        proposed = discovered["proposal"]
        if digest(proposed) != decision.proposal_id:
            raise ExtractionError("boundary proposal identity mismatch")
        source = sources.get(proposed["source_id"])
        start = discovered.get("start")
        end = start + len(proposed["quote"]) if type(start) is int else None
        if (
            source is None
            or not source.complete
            or type(start) is not int
            or source.content[start:end] != proposed["quote"]
            or source.source.sha256_hex != decision.source_sha256
            or source.representation.sha256_hex != decision.representation_sha256
        ):
            raise ExtractionError("stale or incomplete boundary evidence")
        if decision.action == "reject":
            continue
        matches = [
            i
            for i, e in enumerate(changed)
            if e.entity_id == proposed["entity_id"]
            and e.kind == proposed["kind"]
            and e.source_id == proposed["source_id"]
            and not e.confirmed
            and e.start <= start
            and end is not None
            and end <= e.end
        ]
        if len(matches) != 1 or end is None:
            raise ExtractionError("ambiguous, already confirmed or out-of-scope boundary")
        changed[matches[0]] = EntityScope(
            proposed["entity_id"], proposed["kind"], proposed["source_id"], start, end, True
        )
    return replace(request, entities=tuple(changed))


def scout_guidance(discoveries: tuple[dict[str, Any], ...], source_id: str) -> list[dict[str, Any]]:
    """Grounded, bounded hints for source targeting, never boundary authority."""

    guidance: list[dict[str, Any]] = []
    for discovery in discoveries:
        if (
            discovery.get("state") != "proposed"
            or type(discovery.get("start")) is not int
            or discovery.get("proposal", {}).get("source_id") != source_id
        ):
            continue
        proposal = discovery["proposal"]
        guidance.append(
            {
                "category": discovery["category"],
                "proposal_id": discovery["id"],
                "start": discovery["start"],
                "quote": proposal["quote"][:512],
                "kind": proposal["kind"],
                "entity_id": proposal.get("entity_id"),
                "authority": "unconfirmed_discovery_only",
            }
        )
        if len(guidance) == 8:
            break
    return guidance


def signal_decisions(atoms: tuple[Atom, ...], policy: Vocabulary) -> tuple[dict[str, Any], ...]:
    """Typed, versioned dispositions; lexical eligibility is never semantic approval."""

    return tuple(
        {
            "evidence_type": (
                getattr(getattr(policy, "definitions", {}).get(atom.signal), "value_type", "unregistered")
            ),
            "candidate_id": atom.candidate_id,
            "source_id": atom.source_id,
            "signal": atom.signal,
            "slot": atom.slot,
            "registry": policy.namespace,
            "registry_version": policy.version,
            "registered": atom.signal in policy.signals,
            "disposition": atom.state,
            "reason": atom.reason,
            "level": "candidate_validation_not_semantic_support",
            "input_fingerprint": digest(
                {
                    "source": atom.source_id,
                    "span": [atom.start, atom.end],
                    "signal": atom.signal,
                    "slot": atom.slot,
                    "value": atom.value,
                    "polarity": atom.polarity,
                    "quote": atom.quote,
                }
            ),
        }
        for atom in atoms
    )


def _money(value: str, quote: str) -> tuple[str, Decimal] | None:
    """Parse only bounded unambiguous decimal strings with an explicit currency marker."""

    if not _DECIMAL.fullmatch(value):
        return None
    currencies = {s.upper() for s in _CURRENCY.findall(quote)}
    if len(currencies) != 1:
        return None
    try:
        amount = Decimal(value.replace(",", "."))
    except InvalidOperation:
        return None
    if not amount.is_finite():
        return None
    return next(iter(currencies)), amount


def _iso_date(value: str, quote: str) -> date | None:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) or value not in quote:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def conflicting_pairs(atoms: tuple[Atom, ...]) -> tuple[tuple[str, str], ...]:
    return tuple(
        (a.candidate_id, b.candidate_id)
        for i, a in enumerate(atoms)
        for b in atoms[i + 1 :]
        if a.state in {"validated", "needs_review"}
        and b.state in {"validated", "needs_review"}
        and a.start is not None
        and b.start is not None
        and (a.entity_id, a.slot, a.signal) == (b.entity_id, b.slot, b.signal)
        and (a.value != b.value or a.polarity != b.polarity)
    )


def reconcile_facts(atoms: tuple[Atom, ...], pairs: tuple[tuple[str, str], ...]) -> tuple[dict[str, Any], ...]:
    """Deterministic difference classification, preserving contradictory original claims."""

    by_id = {a.candidate_id: a for a in atoms}
    findings = []
    for x, y in pairs:
        a, b = by_id[x], by_id[y]
        classification = "value_or_polarity_conflict"
        details: dict[str, Any] = {}
        money_a, money_b = _money(a.value, a.quote), _money(b.value, b.quote)
        date_a, date_b = _iso_date(a.value, a.quote), _iso_date(b.value, b.quote)
        if _AMENDMENT.search(a.quote) or _AMENDMENT.search(b.quote):
            classification = "amendment_requires_review"
        elif money_a is not None and money_b is not None:
            if money_a[0] != money_b[0]:
                classification = "cross_currency_not_comparable"
                details["currencies"] = sorted([money_a[0], money_b[0]])
            else:
                classification = "monetary_difference"
                details.update(currency=money_a[0], difference=str(money_a[1] - money_b[1]))
        elif date_a is not None and date_b is not None:
            classification = "temporal_difference"
            details["days_difference"] = (date_a - date_b).days
        findings.append(
            {
                "conflict_id": digest({"candidates": sorted([x, y])}),
                "candidate_ids": sorted([x, y]),
                "entity_id": a.entity_id,
                "slot": a.slot,
                "kind": classification,
                "details": details,
                "disposition": "human_review_required",
                "auto_supersede": False,
            }
        )
    return tuple(findings)


def evidence_matrix(
    request: ExtractionRequest,
    atoms: tuple[Atom, ...],
    pairs: tuple[tuple[str, str], ...],
) -> tuple[dict[str, Any], ...]:
    """Source-aware slot matrix which drives bounded, non-authoritative gap repair."""

    conflicting_ids = {item for pair in pairs for item in pair}
    matrix = []
    for slot in request.slots:
        matching = [
            a for a in atoms if a.entity_id == slot.entity_id and a.slot == slot.slot_id
        ]
        confirmed = any(
            e.confirmed and e.entity_id == slot.entity_id and e.source_id in slot.source_ids
            for e in request.entities
        )
        all_complete = all(
            src.complete for src in request.sources if src.source_id in slot.source_ids
        )
        has_conflict = any(a.candidate_id in conflicting_ids or a.relation == "contradicts" for a in matching)
        validated = any(a.state == "validated" for a in matching)
        reasons = sorted({a.reason for a in matching if a.state != "validated"})
        state = (
            "conflicting" if has_conflict else
            "missing" if not matching else
            "candidate_eligible" if validated else "unverified"
        )
        # Grounded disagreement or absent/invalid citations can merit another read.
        # A qualified assertion, incomplete parse or unconfirmed boundary requires humans.
        review_only = not confirmed or not all_complete or any(
            a.reason in {"unconfirmed_entity_boundary", "incomplete_representation"}
            for a in matching
        )
        repairable = (
            not review_only
            and (has_conflict or not validated)
            and (
                has_conflict
                or not matching
                or any(
                    a.reason in {
                        "unregistered_signal", "signal_semantics_unresolved",
                        "quote_not_found", "value_not_in_quote", "invalid_exact_offset",
                    }
                    for a in matching
                )
            )
        )
        matrix.append(
            {
                "entity_id": slot.entity_id,
                "slot": slot.slot_id,
                "source_ids": list(slot.source_ids),
                "candidate_ids": sorted({a.candidate_id for a in matching}),
                "state": state,
                "reasons": reasons,
                "repair_eligible": repairable,
                "human_review_required": True,
            }
        )
    return tuple(matrix)

def confirmed_boundaries_from_audit(
    request: ExtractionRequest,
    discoveries: tuple[dict[str, Any], ...],
    state: dict[str, Any],
    *,
    authorize: Callable[[Scope, str], bool],
) -> ExtractionRequest:
    """Replay *persisted, audited* boundary-review events into a NEW run request.

    Never accept client-submitted BoundaryReview objects as authorization. The
    caller must obtain state from a scoped authenticated review repository; its
    authorization callback must verify the recorded actor/audit reference.
    """

    from application.review.contracts import (
        ZERO_HASH,
        ReviewKind,
        ReviewSnapshot,
        boundary_proposal,
        event_digest,
    )

    if state.get("persistence") not in {"disposable_postgres", "session_memory"}:
        raise ExtractionError("unrecognized reviewed boundary event store")
    if state.get("approved") is not False or state.get("snapshot_hash") is None:
        raise ExtractionError("untrusted review state")
    snapshot = ReviewSnapshot(
        request.scope,
        state["snapshot_hash"],
        canonical(state["snapshot"]),
    )
    original = {
        s.source_id: (s.source.sha256_hex, s.representation.sha256_hex)
        for s in request.sources
    }
    recorded = {
        s["source_id"]: (s["sha256"], s["representation_sha256"])
        for s in snapshot.data["sources"]
    }
    if original != recorded:
        raise ExtractionError("reviewed boundary source revisions changed")
    events = state.get("events")
    if type(events) is not list or len(events) > 1000:
        raise ExtractionError("review history invalid")
    previous = ZERO_HASH
    decisions: list[BoundaryReview] = []
    for index, event in enumerate(events, 1):
        if (
            event.get("scope") != request.scope.namespace
            or event.get("schema") != "review-event-v1"
            or event.get("revision") != index
            or event.get("previous_hash") != previous
            or event_digest(event) != event.get("audit_hash")
            or event.get("authority") != "recommendation_only"
        ):
            raise ExtractionError("review event chain invalid")
        previous = event["audit_hash"]
        kind = event["command"].get("kind")
        if kind not in (ReviewKind.CONFIRM_BOUNDARY, ReviewKind.REJECT_BOUNDARY):
            continue
        if event["command"].get("snapshot_hash") != snapshot.snapshot_hash:
            raise ExtractionError("boundary confirmation belongs to older snapshot")
        proposal_id = event["command"].get("item_id")
        boundary_proposal(snapshot, proposal_id)
        if not authorize(request.scope, event["audit_hash"]):
            raise ExtractionError("boundary review actor not authorized")
        proposal = next((d for d in discoveries if d.get("id") == proposal_id), None)
        if proposal is None or proposal != boundary_proposal(snapshot, proposal_id):
            raise ExtractionError("boundary discovery differs from frozen reviewed proposal")
        doc = original[proposal["proposal"]["source_id"]]
        decisions.append(
            BoundaryReview(
                proposal_id=proposal_id,
                reviewer_reference=event["audit_hash"],
                action="confirm" if kind == ReviewKind.CONFIRM_BOUNDARY else "reject",
                source_sha256=doc[0],
                representation_sha256=doc[1],
            )
        )
    if previous != state.get("audit_head") or len(events) != state.get("revision"):
        raise ExtractionError("review audit head or revision invalid")
    if not decisions:
        return request
    return confirm_reviewed_boundaries(request, discoveries, tuple(decisions), authorize=authorize)
