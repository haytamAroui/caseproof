"""Local, append-only review decisions for the offline legal-reference slice.

A decision binds to one exact finding: the cited reference, its status, the
quoted words, the chosen article text and the corpus pack. If any of them
changes, the old decision stays visible but no longer answers the new finding.
Decisions here carry a free-text local label. They are not authenticated lawyer
decisions and never authorise filing.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from application.litigation.corpus import CorpusError

ACTIONS = ("confirm", "qualify", "reject", "waive")
ATTRIBUTION = "local_unauthenticated_label"
_REASON_REQUIRED = ("qualify", "reject", "waive")


def finding_fingerprint(ref: Mapping[str, Any], article_sha: Mapping[str, str], pack_sha: str) -> str:
    key = ref.get("corpus_key")
    identity = {"raw_text": ref["raw_text"], "status": ref["status"], "quote": ref.get("quote"),
                "corpus_key": key, "article_text_sha256": article_sha.get(key) if key else None,
                "corpus_pack_sha256": pack_sha}
    return hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def fingerprints(references: Sequence[Mapping[str, Any]], articles: Sequence[Mapping[str, Any]],
                 article_index: Sequence[Mapping[str, Any]], pack_sha: str) -> list[str]:
    by_key = {row["key"]: articles[row["index"]]["derived_sha256"] for row in article_index}
    return [finding_fingerprint(r, by_key, pack_sha) for r in references]


def make_decision(*, fingerprint: str, action: str, reason: str, reviewer_label: str,
                  revision: int) -> dict[str, Any]:
    if action not in ACTIONS:
        raise CorpusError("unknown decision action")
    reason = reason.strip()
    if len(reason) > 2000 or (action in _REASON_REQUIRED and not reason):
        raise CorpusError("a reason is required for this decision")
    label = reviewer_label.strip()
    if not 0 < len(label) <= 80:
        raise CorpusError("a local reviewer label is required")
    return {"fingerprint": fingerprint, "action": action, "reason": reason, "reviewer_label": label,
            "attribution": ATTRIBUTION, "decided_in_revision": revision, "origin": "new"}


def validate_review(review: Mapping[str, Any], current: Sequence[str]) -> None:
    """Every decision must be well formed and answer a finding present in this review."""
    seen: set[str] = set()
    for d in review.get("decisions", []):
        if (d.get("attribution") != ATTRIBUTION or d.get("action") not in ACTIONS
                or d.get("origin") not in ("new", "carried") or d["fingerprint"] not in current
                or d["fingerprint"] in seen
                or (d["action"] in _REASON_REQUIRED and not str(d.get("reason", "")).strip())):
            raise CorpusError("review decision does not match a finding in this review")
        seen.add(d["fingerprint"])
    for old in review.get("superseded", []):
        if old.get("fingerprint") in current or not review.get("prior_checkpoint"):
            raise CorpusError("superseded decision must come from a prior review")
    if review.get("release_authorized", False) is not False:
        raise CorpusError("local decisions cannot authorise release")


def carry(prior_review: Mapping[str, Any], prior_checkpoint: str, current: Sequence[str]) -> dict[str, Any]:
    """Keep a prior decision only for a finding with the identical fingerprint.

    Anything else stays visible as superseded and the new finding needs a new decision.
    """
    kept, superseded = [], []
    for d in prior_review.get("decisions", []):
        if d["fingerprint"] in current:
            kept.append({**d, "origin": "carried", "carried_from": prior_checkpoint})
        else:
            superseded.append(d)
    superseded += [s for s in prior_review.get("superseded", []) if s["fingerprint"] not in current]
    return {"decisions": kept, "superseded": superseded, "prior_checkpoint": prior_checkpoint}
