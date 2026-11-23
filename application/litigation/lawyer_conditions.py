"""Conditions defined by the lawyer for one dossier (MD "extension cible"). Retrieval and routing, never a verdict.

A condition says: when the brief talks about X (trigger words), show me the passages of the pieces that
contain Y (evidence words) and ask me. Example: a brief sentence about a "courrier" triggers a search of the
pieces for "reçu" / "ontvangen". The result is always handed back to the lawyer: UNDETERMINED when passages
were found (appraisal required), UNVERIFIED when no passage was found in the pieces that could be read.
Never PASS. Trigger and evidence words are literal, case-insensitive substrings chosen by the lawyer. There is
no synonym search, no meaning, no LLM, no OCR. Evidence excerpts are recorded at check time and cannot be
re-derived from the export (no piece bytes inside), so replay checks the trigger side and internal consistency only.
"""
from __future__ import annotations

import hashlib
import json
import re
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from application.litigation.corpus import CorpusError
from application.litigation.legal_references import LegalReferenceObservation
from application.litigation.rule_results import RuleStatus

FORMAT = "caseproof-conditions-v1"
MAX_CONDITIONS = 50
MAX_TERMS = 20
MAX_TERM = 80
MAX_ANCHORS = 200
MAX_PER_PIECE = 3
MAX_EXCERPT = 400
R_FOUND = "condition_passages_found_appraisal_required"
R_NONE = "condition_no_passage_found_in_pieces_read"
SCOPE = ("Condition définie par l'avocat pour ce dossier : mots déclencheurs et mots à retrouver littéraux, sans synonymes ni lecture du sens. "
         "Les passages montrés contiennent un des mots demandés ; ils ne prouvent pas que la condition est remplie. "
         "Extraits enregistrés au moment du contrôle : sans les octets des pièces, la relecture ne vérifie que la cohérence interne.")


def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _terms(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not 0 < len(value) <= MAX_TERMS:
        raise CorpusError(f"condition {field} must be a non-empty list")
    out = []
    for term in value:
        if not isinstance(term, str) or not 2 <= len(term.strip()) <= MAX_TERM:
            raise CorpusError(f"condition {field}: each word needs 2 to {MAX_TERM} characters")
        out.append(term.strip())
    return out


def load_conditions(path: Path) -> dict[str, Any]:
    """Read and validate conditions.toml into the recorded spec (with its own hash)."""
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise CorpusError("conditions file unreadable") from exc
    rows = raw.get("condition")
    if raw.get("format") != FORMAT or not isinstance(rows, list) or not 0 < len(rows) <= MAX_CONDITIONS:
        raise CorpusError("conditions file invalid")
    return validate_spec({"format": FORMAT, "conditions": [
        {"id": str(r.get("id", "")), "label": str(r.get("label", "")), "question": str(r.get("question", "")),
         "trigger": _terms(r.get("trigger"), "trigger"), "evidence": _terms(r.get("evidence"), "evidence"),
         "pieces": [str(p).lower() for p in r.get("pieces", [])]} for r in rows]}, sign=True)


def validate_spec(spec: Mapping[str, Any], sign: bool = False) -> dict[str, Any]:
    conditions = spec.get("conditions")
    if spec.get("format") != FORMAT or not isinstance(conditions, list) or not 0 < len(conditions) <= MAX_CONDITIONS:
        raise CorpusError("conditions spec invalid")
    ids: set[str] = set()
    for c in conditions:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", c["id"]) or c["id"] in ids or not 0 < len(c["label"]) <= 120 \
                or len(c["question"]) > 300:
            raise CorpusError("condition id, label or question invalid")
        ids.add(c["id"])
        _terms(c["trigger"], "trigger")
        _terms(c["evidence"], "evidence")
    body = {"format": FORMAT, "conditions": list(conditions)}
    digest = _sha(body)
    if sign:
        return {**body, "spec_sha256": digest}
    if spec.get("spec_sha256") != digest:
        raise CorpusError("conditions spec altered")
    return dict(spec)


def _sentences(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for i, ch in enumerate(text):
        if ch in ".!?\n" and not (ch == "." and i + 1 < len(text) and text[i + 1].isdigit() and i > 0 and text[i - 1].isdigit()):
            if text[start:i].strip():
                spans.append((start, i + 1))
            start = i + 1
    if text[start:].strip():
        spans.append((start, len(text)))
    return spans


def anchors(text: str, spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    """One anchor per (condition, brief sentence containing a trigger word). Depends only on text and spec."""
    out: list[dict[str, Any]] = []
    for lo, hi in _sentences(text):
        low = text[lo:hi].casefold()
        for c in validate_spec(spec)["conditions"]:
            hit = next((t for t in c["trigger"] if t.casefold() in low), None)
            if hit is not None:
                pos = lo + low.index(hit.casefold())
                out.append({"condition": c["id"], "start": pos, "end": pos + len(hit),
                            "sentence": " ".join(text[lo:hi].split())})
    if len(out) > MAX_ANCHORS:
        raise CorpusError("too many condition anchors")
    return out


def build_evidence(text: str, spec: Mapping[str, Any], piece_texts: Mapping[str, Sequence[str]]) -> list[dict[str, Any]]:
    by_id = {c["id"]: c for c in spec["conditions"]}
    entries = []
    for number, anchor in enumerate(anchors(text, spec), start=1):
        cond = by_id[anchor["condition"]]
        found: list[dict[str, Any]] = []
        for piece in sorted(piece_texts):
            if cond["pieces"] and piece not in cond["pieces"]:
                continue
            hits = 0
            for page_no, page in enumerate(piece_texts[piece], start=1):
                for lo, hi in _sentences(page):
                    chunk = page[lo:hi]
                    term = next((t for t in cond["evidence"] if t.casefold() in chunk.casefold()), None)
                    if term is not None and hits < MAX_PER_PIECE:
                        excerpt = " ".join(chunk.split())[:MAX_EXCERPT]
                        found.append({"piece": piece, "page": page_no, "term": term, "excerpt": excerpt,
                                      "excerpt_sha256": hashlib.sha256(excerpt.encode()).hexdigest()})
                        hits += 1
        entries.append({"anchor": number, "condition": cond["id"], "sentence": anchor["sentence"], "found": found,
                        "pieces_read": sorted(piece_texts) if not cond["pieces"] else sorted(set(cond["pieces"]) & set(piece_texts))})
    return entries


def validate_evidence(text: str, spec: Mapping[str, Any], evidence: Any) -> None:
    expected = anchors(text, spec)
    if not isinstance(evidence, list) or len(evidence) != len(expected):
        raise CorpusError("condition evidence does not match the brief")
    by_id = {c["id"]: c for c in spec["conditions"]}
    for number, (entry, anchor) in enumerate(zip(evidence, expected, strict=True), start=1):
        if entry["anchor"] != number or entry["condition"] != anchor["condition"] or entry["sentence"] != anchor["sentence"]:
            raise CorpusError("condition evidence anchor does not replay from the brief")
        terms = {t.casefold() for t in by_id[entry["condition"]]["evidence"]}
        for f in entry["found"]:
            if (hashlib.sha256(f["excerpt"].encode()).hexdigest() != f["excerpt_sha256"] or f["term"].casefold() not in terms
                    or f["term"].casefold() not in f["excerpt"].casefold() and len(f["excerpt"]) < MAX_EXCERPT):
                raise CorpusError("condition evidence excerpt inconsistent")


def condition_observations(text: str, spec: Mapping[str, Any], evidence: Sequence[Mapping[str, Any]],
                           first_id: int) -> list[LegalReferenceObservation]:
    by_id = {c["id"]: c for c in spec["conditions"]}
    out = []
    for n, (anchor, entry) in enumerate(zip(anchors(text, spec), evidence, strict=True), start=first_id):
        cond = by_id[anchor["condition"]]
        digest = _sha({"found": [[f["piece"], f["page"], f["excerpt_sha256"]] for f in entry["found"]]})
        found = bool(entry["found"])
        out.append(LegalReferenceObservation(
            reference_id=f"legal-ref-{n:02d}", raw_text=f"Condition {cond['id']}", start=anchor["start"], end=anchor["end"],
            act_code=None, article=None, language=None,
            status=RuleStatus.UNDETERMINED if found else RuleStatus.UNVERIFIED, reason=R_FOUND if found else R_NONE,
            quote=f"{cond['label']} · spec {spec['spec_sha256'][:12]} · passages {digest[:16]}"))
    return out
