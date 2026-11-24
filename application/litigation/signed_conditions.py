"""Lawyer conditions on the SIGNED path: stored spec, trigger anchors in the brief, literal passages in readable sources.

Retrieval and routing for the lawyer, never a verdict and never PASS. Trigger and evidence words are literal,
case-insensitive substrings the lawyer chose. No synonyms, no meaning, no LLM, no OCR. Only sources the signed
pipeline marked ready, without warnings, with a stored text representation count as READ. "No passage found"
(UNVERIFIED) is only claimed when every targeted piece was read; otherwise the row stays UNDETERMINED and says why.
Excerpts come from the stored text representation of a source, not from verified original pages.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from application.litigation.corpus import CorpusError
from application.litigation.lawyer_conditions import (
    FORMAT,
    MAX_EXCERPT,
    MAX_PER_PIECE,
    R_FOUND,
    R_NONE,
    _sentences,
    anchors,
    validate_spec,
)

R_PARTIAL = "condition_no_passage_found_but_a_targeted_piece_was_not_read"
SCOPE = (
    "Condition defined by the lawyer for this matter: literal trigger words and literal words to find, "
    "no synonyms and no reading of meaning. Passages shown contain one of the requested words; they do not "
    "show that the condition is met. Excerpts come from the stored text of readable sources, not from "
    "verified original pages. Sources that were not read are listed.")


def _empty_text() -> tuple[str, str]:
    text = json.dumps({"format": FORMAT, "conditions": []}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return text, hashlib.sha256(text.encode()).hexdigest()


def canonical_text(spec: Mapping[str, Any]) -> tuple[str, str]:
    """The exact bytes the store hashes: canonical JSON of the body, and its SHA-256 (the spec hash).

    An empty list is a valid STORED revision here ("the lawyer cleared the conditions"), kept out of
    lawyer_conditions.validate_spec so the offline conditions.toml rules and legacy exports are untouched.
    """
    if not list(spec["conditions"]):
        return _empty_text()
    signed = validate_spec({"format": FORMAT, "conditions": list(spec["conditions"])}, sign=True)
    body = {"format": FORMAT, "conditions": signed["conditions"]}
    text = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(text.encode()).hexdigest()
    if digest != signed["spec_sha256"]:
        raise CorpusError("conditions spec hash is not reproducible")
    return text, digest


def normalise_input(conditions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Lawyer input to a validated spec. Same validation as the offline conditions.toml (empty = cleared)."""
    if not conditions:
        return {"format": FORMAT, "conditions": [], "spec_sha256": _empty_text()[1]}
    rows = [{"id": str(c.get("id", "")), "label": str(c.get("label", "")), "question": str(c.get("question", "")),
             "trigger": [str(t).strip() for t in c.get("trigger", [])],
             "evidence": [str(t).strip() for t in c.get("evidence", [])],
             "pieces": [str(p).strip().lower() for p in c.get("pieces", [])]} for c in conditions]
    return validate_spec({"format": FORMAT, "conditions": rows}, sign=True)


def load_stored(text: str, sha: str) -> dict[str, Any]:
    """A stored spec is trusted only if its bytes hash to the recorded digest and it validates."""
    if hashlib.sha256(text.encode()).hexdigest() != sha:
        raise CorpusError("stored conditions spec hash mismatch")
    body = json.loads(text)
    if isinstance(body, dict) and body.get("conditions") == [] and text == _empty_text()[0]:
        return {"format": FORMAT, "conditions": [], "spec_sha256": sha}
    spec = validate_spec({**body, "spec_sha256": sha})
    if canonical_text(spec)[0] != text:
        raise CorpusError("stored conditions spec is not canonical")
    return spec


def _readable(preview: Any) -> bool:
    row = preview.row
    return bool(row.status == "ready" and not row.warnings and row.representation_id and preview.text.strip())


def _page_at(spans: Sequence[Sequence[Any]], pos: int) -> int | None:
    for lo, hi, _kind, page0 in spans:
        if lo <= pos < hi and page0 is not None:
            return int(page0) + 1
    return None


def match_conditions(text: str, spec: Mapping[str, Any], previews: Sequence[Any],
                     labels: Mapping[str, str]) -> dict[str, Any]:
    by_id = {c["id"]: c for c in spec["conditions"]}
    readable = [p for p in previews if _readable(p)]
    unreadable = [p for p in previews if not _readable(p)]

    def label_of(p: Any) -> str:
        return labels.get(p.row.source_id) or f"source {p.row.source_id[:8]}"

    rows: list[dict[str, Any]] = []
    for n, anchor in enumerate(anchors(text, spec), start=1):
        cond = by_id[anchor["condition"]]
        wanted = set(cond["pieces"])

        def targeted(p: Any, wanted: set[str] = wanted) -> bool:
            return not wanted or labels.get(p.row.source_id, "").lower() in wanted

        read = [p for p in readable if targeted(p)]
        not_read = [p for p in unreadable if targeted(p)]
        known = {labels.get(p.row.source_id, "").lower() for p in previews}
        missing_labels = sorted(w for w in wanted if w not in known)
        found: list[dict[str, Any]] = []
        for p in sorted(read, key=label_of):
            hits = 0
            for lo, hi in _sentences(p.text):
                chunk = p.text[lo:hi]
                term = next((t for t in cond["evidence"] if t.casefold() in chunk.casefold()), None)
                if term is None or hits >= MAX_PER_PIECE:
                    continue
                excerpt = " ".join(chunk.split())[:MAX_EXCERPT]
                found.append({
                    "piece": label_of(p), "source_id": p.row.source_id, "version_id": p.row.version_id,
                    "original_sha256": p.row.original_sha256, "pdf_page": _page_at(p.spans, lo + chunk.casefold().index(term.casefold())),
                    "term": term, "excerpt": excerpt,
                    "excerpt_sha256": hashlib.sha256(excerpt.encode()).hexdigest()})
                hits += 1
        complete = bool(read) and not not_read and not missing_labels
        status, reason = (("UNDETERMINED", R_FOUND) if found
                          else ("UNVERIFIED", R_NONE) if complete else ("UNDETERMINED", R_PARTIAL))
        rows.append({
            "anchor_id": f"condition-anchor-{n:02d}", "condition_id": cond["id"], "label": cond["label"],
            "question": cond["question"], "start": anchor["start"], "end": anchor["end"],
            "sentence": anchor["sentence"], "status": status, "reason": reason, "found": found,
            "pieces_read": sorted({label_of(p) for p in read} - {label_of(p) for p in not_read}),
            "pieces_not_read": sorted({label_of(p) for p in not_read} | set(missing_labels))})
    return {
        "spec_sha256": spec["spec_sha256"], "scope": SCOPE, "anchors": rows,
        "coverage": {"conditions": len(by_id), "anchors": len(rows),
                     "sources_read": len(readable), "sources_not_read": len(unreadable),
                     "by_status": {s: sum(1 for r in rows if r["status"] == s)
                                   for s in ("PASS", "FAIL", "UNVERIFIED", "UNDETERMINED")}},
    }
