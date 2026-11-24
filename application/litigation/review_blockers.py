"""Blocker inventory only. No release verdict or inferred waiver policy."""
from __future__ import annotations

from typing import Any


def review_blockers(run: Any, decisions: tuple[Any, ...] = ()) -> dict[str, Any]:
    rows: list[dict[str, str]] = []
    reviewed = {d.observation_id: d.disposition.value for d in decisions}
    ids: list[str] = []

    def add(oid: str, reason: str) -> None:
        rows.append({"observation_id": oid, "reason": reason,
                     "review_disposition": reviewed.get(oid, "not_recorded")})

    for c in run.citation_observations:
        oid = "citation:" + c.reference_id
        ids.append(oid)
        if c.state not in {"exact_match", "reference_checked_no_quotation"}:
            add(oid, c.state.value)
    for f in run.factual_observations:
        oid = "fact:" + f.claim_id
        ids.append(oid)
        if f.state != "value_match":
            add(oid, f.explanation)
    for legal in run.legal_observations:
        oid = "legal:" + legal.reference_id
        ids.append(oid)
        if legal.status != "PASS":
            add(oid, legal.reason)
    for s in run.suitability_observations:
        oid = "suitability:" + s.rule_id
        ids.append(oid)
        if s.status != "PASS":
            add(oid, s.reason)
    for e in run.event_observations:
        oid = "event:" + e.observation_id
        ids.append(oid)
        add(oid, e.reason)
    for flag in run.passage_flags:
        oid = "flag:" + str(flag["id"])
        ids.append(oid)
        add(oid, "human_reported_passage" if flag["binding_current"] else "human_passage_binding_changed")
    for oid in ids:
        if oid not in reviewed:
            add(oid, "human_review_not_recorded")
    for source, version in run.incomplete:
        add("scope:" + source + ":" + version, "source_incomplete")
    for source, version in run.excluded:
        add("scope:" + source + ":" + version, "source_excluded")
    return {"schema": "caseproof-blocker-inventory-v1", "snapshot_hash": run.snapshot_hash,
            "items": rows, "verdict": "not_computed", "release_authorized": False,
            "waiver_policy": "not_decided",
            "note": "Blocker inventory only, not readiness or permission to file. A recorded disposition does not waive a machine observation. No final verdict is computed until the owner sets the waiver policy. Coverage is limited to the named detectors."}
