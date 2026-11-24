"""Passage retrieval for exhibit references. Shows where the cited piece contains the same typed values. No verdict.

For a reference like "pièce 1", the sentence of the brief around it is read for dates and amounts.
The pages of the piece are searched for sentences holding the same normalised values. The lawyer sees
the claim and the passages side by side. A value found nowhere in the piece is a CANDIDATE DIFFERENCE to
examine, never a conclusion. This does not read meaning: "envoyé pour signature" and "signé" with the
same date both match, and the lawyer has to see the wording in the passage. No OCR, no paraphrase judgment.
"""
from __future__ import annotations

import hashlib
import io
import re
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from application.litigation.corpus import CorpusError
from application.litigation.exhibit_coverage import R_LOCATED, R_PAGE
from application.litigation.factual_values import typed_values

MAX_PAGES = 200
# Fixed FR/NL cue lists. Partial detection of ONE contradiction shape, not a reading of meaning.
_SIGNED = ("signé", "signée", "signés", "signées", "ondertekend", "getekend")
_PENDING = ("pour signature", "à signer", "en attente de signature", "non signé", "non signée", "pas signé", "pas encore signé",
            "ter ondertekening", "voor ondertekening", "nog niet ondertekend", "niet ondertekend", "nog niet getekend")
MAX_EXCERPT = 400
MAX_FOUND_PER_VALUE = 3
SCOPE = ("Passages proposés par correspondance de dates et de montants identiques, plus un drapeau partiel de mot d'état (liste fixe FR/NL : « signé » contre « pour signature », « non signé »). "
         "Le drapeau ne sait pas QUI signe (une autre partie peut avoir signé), ni si la phrase de la pièce porte sur la même chose. Aucune lecture du sens : une même date peut figurer "
         "dans « envoyé pour signature » comme dans « signé ». Une valeur absente de la pièce est une différence candidate, pas une conclusion. "
         "Extraits enregistrés au moment du contrôle. Sans les octets des pièces, la relecture ne vérifie que la cohérence interne et l'empreinte : "
         "elle ne prouve pas la fidélité des extraits, et une modification suivie d'un nouveau calcul d'empreinte passerait.")


# Frozen text of exports without a rules marker (delivered v5 pack). Never edit: the reading view is replayed byte for byte.
SCOPE_LEGACY = ("Passages proposés par correspondance de dates et de montants identiques. Aucune lecture du sens : une même date peut figurer "
         "dans « envoyé pour signature » comme dans « signé ». Une valeur absente de la pièce est une différence candidate, pas une conclusion. "
         "Extraits enregistrés au moment du contrôle. Sans les octets des pièces, la relecture ne vérifie que la cohérence interne et l'empreinte : "
         "elle ne prouve pas la fidélité des extraits, et une modification suivie d'un nouveau calcul d'empreinte passerait.")


_PRINTED = re.compile(r"^(?:page|p\.|blz\.?|pagina)?\s*(\d{1,4})(?:\s*(?:/|sur|van|of)\s*\d{1,4})?$", re.IGNORECASE)


def printed_number(page_text: str) -> str | None:
    """Literal footer or header number: the last, else first, non-empty line that is only a number (optionally 'page 3 / 9')."""
    lines = [ln.strip() for ln in page_text.splitlines() if ln.strip()]
    for line in (lines[-1:] + lines[:1]):
        m = _PRINTED.match(line)
        if m:
            return m.group(1)
    return None


def page_meta(directory: Path, exhibits: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Per PDF page: its position in the file, the label the PDF itself defines (if any) and the printed number read from page text."""
    from pypdf import PdfReader
    root = directory.resolve()
    out: dict[str, list[dict[str, Any]]] = {}
    for piece in exhibits["pieces"]:
        if not piece["present"] or piece["readable"] is not True or Path(piece["file"]).suffix.lower() != ".pdf":
            continue
        reader = PdfReader(io.BytesIO((root / piece["file"]).read_bytes()))
        has_labels = "/PageLabels" in dict(reader.trailer["/Root"])  # type: ignore[call-overload]
        rows = []
        for i, page in enumerate(reader.pages[:MAX_PAGES]):
            label = str(reader.page_labels[i])[:40] if has_labels else None
            rows.append({"index": i + 1, "label": label, "printed": printed_number(page.extract_text() or "")})
        out[str(piece["number"]).lower()] = rows
    return out


def read_piece_texts(directory: Path, exhibits: Mapping[str, Any],
                     docx_text: Callable[[bytes], str] | None = None) -> dict[str, list[str]]:
    """Per-page text of readable pieces, re-reading the bytes and requiring the recorded SHA-256."""
    root = directory.resolve()
    out: dict[str, list[str]] = {}
    for piece in exhibits["pieces"]:
        if not piece["present"] or piece["readable"] is not True:
            continue
        raw = (root / piece["file"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != piece["sha256"]:
            raise CorpusError(f"piece {piece['number']} changed while it was being read")
        suffix = Path(piece["file"]).suffix.lower()
        if suffix == ".pdf":
            from pypdf import PdfReader
            out[str(piece["number"]).lower()] = [(p.extract_text() or "") for p in PdfReader(io.BytesIO(raw)).pages[:MAX_PAGES]]
        elif suffix == ".txt":
            out[str(piece["number"]).lower()] = [raw.decode("utf-8", "replace")]
        elif suffix == ".docx" and docx_text is not None:
            out[str(piece["number"]).lower()] = [docx_text(raw)]
    return out


_NEGATION = re.compile(r"\b(?:pas|jamais|non|ne|n'|aucun|aucune|niet|nooit|geen|nog niet)\b|\bn['’]", re.IGNORECASE)


def _cue(text: str, cues: tuple[str, ...]) -> str | None:
    low = text.casefold()
    return next((c for c in cues if c in low), None)


def status_mismatch(claim: str, excerpt: str) -> dict[str, str] | None:
    """Claim says signed while the passage with the same value only has a not-yet-signed wording (partial cue check)."""
    claim_cue = _cue(claim, _SIGNED)
    pending = _cue(excerpt, _PENDING)
    if claim_cue is None or pending is None or _cue(claim, _PENDING) is not None or _NEGATION.search(claim):
        return None  # any negation in the claim sentence: abstain rather than guess its scope
    rest = excerpt.casefold()
    for cue in _PENDING:
        rest = rest.replace(cue, " ")
    if _cue(rest, _SIGNED) is not None:  # the passage also says signed somewhere: no mismatch claimed
        return None
    return {"claim_cue": claim_cue, "passage_cue": pending}


def _claim(text: str, start: int, end: int) -> tuple[str, list[dict[str, Any]]]:
    lo, hi = next(((a, b) for a, b in _sentences(text) if a <= start < b), (0, len(text)))
    sentence = " ".join(text[lo:hi].split())
    values = [{"kind": k, "token": t, "key": key} for k, t, _s, _e, key in typed_values(text[lo:hi])]
    return sentence, values


def build_passages(text: str, observations: Sequence[Any], texts: Mapping[str, Sequence[str]],
                   meta: Mapping[str, Sequence[Mapping[str, Any]]] | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for obs in observations:
        if obs.reason not in (R_LOCATED, R_PAGE):
            continue
        number = obs.raw_text.split(" ", 1)[1].lower()
        pages = texts.get(number)
        if pages is None:
            continue
        sentence, values = _claim(text, obs.start, obs.end)
        found: list[dict[str, Any]] = []
        missing: list[str] = []
        for key in sorted({v["key"] for v in values if v["key"]}):
            hits = 0
            for page_no, page in enumerate(pages, start=1):
                for lo, hi in _sentences(page):
                    chunk = page[lo:hi]
                    if key in {k for *_x, k in typed_values(chunk)} and hits < MAX_FOUND_PER_VALUE:
                        excerpt = " ".join(chunk.split())[:MAX_EXCERPT]
                        row = {"key": key, "page": page_no, "excerpt": excerpt,
                               "excerpt_sha256": hashlib.sha256(excerpt.encode()).hexdigest()}
                        refs = (meta or {}).get(number)
                        if refs is not None and page_no <= len(refs):
                            row["page_ref"] = dict(refs[page_no - 1])
                        mismatch = status_mismatch(sentence, excerpt)
                        if mismatch is not None:
                            row["status_cue_mismatch"] = mismatch
                        found.append(row)
                        hits += 1
            if hits == 0:
                missing.append(key)
        out.append({"reference_id": obs.reference_id, "piece": number, "claim": sentence, "claim_values": values,
                    "found": found, "missing_values": missing,
                    "ambiguous_values": [v["token"] for v in values if v["key"] is None]})
    return out


def _sentences(page: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for i, ch in enumerate(page):
        if ch in ".!?\n" and not (ch == "." and i + 1 < len(page) and page[i + 1].isdigit()):
            if page[start:i].strip():
                spans.append((start, i + 1))
            start = i + 1
    if page[start:].strip():
        spans.append((start, len(page)))
    return spans


RULES_V2 = "status-cue-v2"  # IMMUTABLE: exports made before page references
RULES = "status-cue-v3"  # v2 + optional page_ref per excerpt (see page_meta). IMMUTABLE once released.
_OLD_RULES = "status-cue-v2"  # IMMUTABLE behaviour: cue lists + negation rule below. Any change needs status-cue-v3 and keeps v2 replaying. v1 (no negation rule) was never in an artifact.


def validate_passages(text: str, observations: Sequence[Mapping[str, Any]], passages: Any, rules: str | None = None) -> None:
    """Replay check. The claim side is recomputed from the brief. Excerpts are checked only for internal integrity."""
    if not isinstance(passages, list):
        raise CorpusError("passages malformed")
    by_id = {o["reference_id"]: o for o in observations if o["reason"] in (R_LOCATED, R_PAGE)}
    seen: set[str] = set()
    for entry in passages:
        obs = by_id.get(entry.get("reference_id"))
        if obs is None or entry["reference_id"] in seen:
            raise CorpusError("passage does not match a located exhibit reference")
        seen.add(entry["reference_id"])
        sentence, values = _claim(text, int(obs["start"]), int(obs["end"]))
        if entry["claim"] != sentence or entry["claim_values"] != values:
            raise CorpusError("passage claim does not replay from the brief")
        keys = {v["key"] for v in values if v["key"]}
        if not set(entry["missing_values"]) <= keys or any(f["key"] not in keys for f in entry["found"]):
            raise CorpusError("passage values do not match the claim")
        if set(entry["missing_values"]) & {f["key"] for f in entry["found"]}:
            raise CorpusError("a value cannot be both found and missing")
        if any(hashlib.sha256(f["excerpt"].encode()).hexdigest() != f["excerpt_sha256"] for f in entry["found"]):
            raise CorpusError("passage excerpt altered")
        for f in entry["found"]:
            ref = f.get("page_ref")
            if ref is not None:
                ok = (rules == RULES and isinstance(ref, dict) and set(ref) == {"index", "label", "printed"}
                      and type(ref["index"]) is int and ref["index"] == f["page"]
                      and (ref["label"] is None or isinstance(ref["label"], str) and len(ref["label"]) <= 40)
                      and (ref["printed"] is None or isinstance(ref["printed"], str) and re.fullmatch(r"\d{1,4}", ref["printed"])))
                if not ok:
                    raise CorpusError("passage page reference invalid or without its rules marker")
        if rules is None:
            if any("status_cue_mismatch" in f for f in entry["found"]):
                raise CorpusError("status cue without its rules marker")
        elif rules not in (RULES, _OLD_RULES):
            raise CorpusError("unknown passage rules")
        elif any(f.get("status_cue_mismatch") != status_mismatch(sentence, f["excerpt"]) for f in entry["found"]):
            raise CorpusError("passage status cue does not replay")
