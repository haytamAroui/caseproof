"""Offline exhibit reference resolution and file-byte coverage. A coverage aid, NOT evidence review.

What it does: finds "Pièce n°" / "Stuk nr." references in the brief text, resolves each number
against a local bordereau, and reads the actual files to record SHA-256, size, PDF page count and
whether text can be read. What it never does: compare an exhibit's CONTENT to what the brief
says. Every resolved reference stays UNDETERMINED: located, content not compared.
Declared hashes are never trusted: they are only checked against the bytes read.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import tomllib
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from application.litigation.corpus import CorpusError
from application.litigation.legal_references import LegalReferenceObservation
from application.litigation.rule_results import RuleStatus

BORDEREAU_FORMAT = "caseproof-bordereau-v1"
MAX_PIECES = 200
MAX_PIECE_BYTES = 30 * 1024 * 1024
_SUPPORTED = (".pdf", ".docx", ".txt")

R_LOCATED = "exhibit_located_by_number_bytes_read_content_not_compared"
R_ABSENT = "exhibit_number_absent_from_bordereau"
R_MISSING = "exhibit_listed_but_file_missing_check_impossible"
R_UNREADABLE = "exhibit_file_has_no_readable_text_check_impossible"
R_RANGE = "exhibit_range_endpoints_not_integers_not_expanded"
R_PAGE = "exhibit_page_reference_not_checked_pdf_page_vs_printed_number_unresolved"
EXHIBIT_REASONS = frozenset({R_LOCATED, R_ABSENT, R_MISSING, R_UNREADABLE, R_RANGE, R_PAGE})

_HEAD = re.compile(
    r"(?i)\b(?P<word>pi[èe]ces?|stuk(?:ken)?)\s*(?:n(?:°|º|o|r|rs)s?\.?\s*|nummers?\s*|numéros?\s*)?(?=\d)")
_NUM = re.compile(r"\d+(?:\s?(?:bis|ter|quater))?[A-Za-z]?(?![\w])")
_SEP = re.compile(r"(?i)\s*(?P<sep>,|;|\bet\b|\ben\b|\bà\b|\btot en met\b|\bt/m\b|\btot\b|[-–])\s*(?=\d)")
_PAGE = re.compile(r"(?i)^[\s,;(]*(?:pp?\.|pages?|blz\.?|pagina'?s?)\s*\d+")
_MONTH = re.compile(r"(?i)^\s*(?:janv|f[ée]vr|mars|avr|mai|juin|juil|ao[uû]t|sept|oct|nov|d[ée]c|januari|februari|maart|april|juni|juli|augustus|september|oktober|november|december)")
_RANGE_SEPS = {"à", "tot en met", "t/m", "tot", "-", "–"}


def load_exhibit_set(directory: Path, docx_text: Callable[[bytes], str] | None = None) -> dict[str, Any]:
    """Read bordereau.toml and the real files. Fail closed on any inconsistency; never trust declared hashes."""
    root = directory.resolve()
    manifest_path = root / "bordereau.toml"
    if not manifest_path.is_file():
        raise CorpusError("bordereau.toml required in the exhibit directory")
    data = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("format") != BORDEREAU_FORMAT:
        raise CorpusError("unknown bordereau format")
    rows = data.get("piece", [])
    if not isinstance(rows, list) or not rows or len(rows) > MAX_PIECES:
        raise CorpusError(f"bordereau needs 1 to {MAX_PIECES} pieces")
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        number = str(row.get("number", "")).strip()
        label, name = str(row.get("label", "")).strip(), str(row.get("file", "")).strip()
        if not number or not label or not name or number in seen:
            raise CorpusError("bordereau entry needs a unique number, a label and a file (ambiguous duplicate refused)")
        seen.add(number)
        path = (root / name)
        entry: dict[str, Any] = {"number": number, "label": label, "file": name, "language": row.get("language"),
                                 "present": False, "sha256": None, "size": None, "pages": None, "readable": None}
        if path.is_symlink() or root not in path.resolve().parents:
            raise CorpusError("exhibit file must be a regular file inside the exhibit directory")
        if path.is_file():
            raw = path.read_bytes()
            if len(raw) > MAX_PIECE_BYTES:
                raise CorpusError("exhibit file too large")
            digest = hashlib.sha256(raw).hexdigest()
            declared = row.get("declared_sha256")
            if declared is not None and str(declared).lower() != digest:
                raise CorpusError(f"declared hash does not match the file bytes for piece {number}")
            entry.update(present=True, sha256=digest, size=len(raw))
            entry["pages"], entry["readable"] = _inspect(name, raw, docx_text)
        out.append(entry)
    return {"format": BORDEREAU_FORMAT, "pieces": out, "set_sha256": _set_hash(out)}


def _inspect(name: str, raw: bytes, docx_text: Callable[[bytes], str] | None) -> tuple[int | None, bool | None]:
    suffix = Path(name).suffix.lower()
    try:
        if suffix == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            pages = len(reader.pages)
            return pages, any((p.extract_text() or "").strip() for p in reader.pages[:50])
        if suffix == ".docx" and docx_text is not None:
            return None, bool(docx_text(raw).strip())
        if suffix == ".txt":
            return None, bool(raw.decode("utf-8", "replace").strip())
    except Exception:  # noqa: BLE001 - an unreadable file is a visible finding, not a crash
        return None, False
    return None, None


def _set_hash(pieces: Sequence[Mapping[str, Any]]) -> str:
    return hashlib.sha256(json.dumps(list(pieces), sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def validate_manifest(exhibits: Mapping[str, Any]) -> list[dict[str, Any]]:
    pieces = exhibits.get("pieces")
    if exhibits.get("format") != BORDEREAU_FORMAT or not isinstance(pieces, list) or _set_hash(pieces) != exhibits.get("set_sha256"):
        raise CorpusError("exhibit manifest invalid or altered")
    return pieces


def find_references(text: str) -> list[dict[str, Any]]:
    """Every numbered exhibit mention: lists and integer ranges expanded to one entry per number."""
    found: list[dict[str, Any]] = []
    for head in _HEAD.finditer(text):
        word = head.group("word").lower()
        pos = head.end()
        tokens: list[tuple[str, int, int, str | None]] = []
        sep: str | None = None
        while True:
            m = _NUM.match(text, pos)
            if not m or (tokens and sep in {",", ";"} and (len(m.group(0)) > 3 or _MONTH.match(text[m.end():m.end() + 12]))):
                break
            tokens.append((m.group(0), m.start(), m.end(), sep))
            pos = m.end()
            s = _SEP.match(text, pos)
            if not s:
                break
            sep, pos = s.group("sep").lower(), s.end()
        page = bool(_PAGE.match(text[pos:pos + 40])) if tokens else False
        for i, (num, a, b, via) in enumerate(tokens):
            nums, reason = [re.sub(r"\s+", "", num).lower()], None
            if via in _RANGE_SEPS and i > 0:
                lo, hi = tokens[i - 1][0], num
                if lo.isdigit() and hi.isdigit() and 0 < int(hi) - int(lo) <= MAX_PIECES:
                    nums = [str(k) for k in range(int(lo) + 1, int(hi) + 1)]
                else:
                    reason = R_RANGE
            for n in nums:
                found.append({"number": n, "start": a, "end": b, "word": "Stuk" if word.startswith("stuk") else "Pièce",
                              "page": page and i == len(tokens) - 1, "reason": reason})
    return found


def exhibit_observations(text: str, exhibits: Mapping[str, Any], first_id: int) -> list[LegalReferenceObservation]:
    pieces = {str(p["number"]).lower(): p for p in validate_manifest(exhibits)}
    out: list[LegalReferenceObservation] = []
    n = first_id
    for ref in find_references(text):
        piece = pieces.get(ref["number"])
        quote = None
        if ref["reason"]:
            status, reason = RuleStatus.UNDETERMINED, ref["reason"]
        elif piece is None:
            status, reason = RuleStatus.UNVERIFIED, R_ABSENT
        else:
            quote = f"{piece['label']} · {piece['file']} · " + (f"SHA-256 {piece['sha256']}" if piece["present"] else "fichier absent")
            if not piece["present"]:
                status, reason = RuleStatus.UNDETERMINED, R_MISSING
            elif piece["readable"] is False:
                status, reason = RuleStatus.UNDETERMINED, R_UNREADABLE
            elif ref["page"]:
                status, reason = RuleStatus.UNDETERMINED, R_PAGE
            else:
                status, reason = RuleStatus.UNDETERMINED, R_LOCATED
        out.append(LegalReferenceObservation(
            reference_id=f"legal-ref-{n:02d}", raw_text=f"{ref['word']} {ref['number']}", start=ref["start"], end=ref["end"],
            act_code=None, article=None, language=None, status=status, reason=reason, quote=quote))
        n += 1
    return out


def coverage(text: str, exhibits: Mapping[str, Any]) -> dict[str, Any]:
    pieces = validate_manifest(exhibits)
    cited = {r["number"] for r in find_references(text)}
    return {"listed": len(pieces), "cited_numbers": sorted(cited),
            "unreferenced": [p["number"] for p in pieces if str(p["number"]).lower() not in cited],
            "missing_files": [p["number"] for p in pieces if not p["present"]],
            "unreadable": [p["number"] for p in pieces if p["present"] and p["readable"] is False]}
