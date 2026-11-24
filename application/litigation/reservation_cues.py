"""Literal reservation and negation cues around a quotation that matched an article word for word.

PARTIAL detection with fixed FR/NL word lists. It never reads meaning, never changes a status and never says the
quotation distorts the article. It only tells the lawyer where the stored article text carries reservation wording
outside the quoted passage, so the passage and its surroundings can be read together. An absent cue proves nothing.
Immutable once released: any change to a list or to the rule below needs a new RULES marker.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from application.litigation.corpus import CorpusError

RULES = "reservation-cue-v1"
_RESERVATION = (
    "sauf", "hormis", "excepté", "excepte", "à l'exception", "a l'exception", "à moins que", "a moins que",
    "sous réserve", "sous reserve", "sans préjudice", "sans prejudice", "pour autant que", "dans la mesure où",
    "tenzij", "behoudens", "onverminderd", "met uitzondering", "behalve", "onder voorbehoud",
)
# Negation words count only in the sentence right before or right after the quotation.
_NEGATION = ("ne ", "n'", " pas", "aucun", "nul ", "jamais", "niet", "geen", "nooit")
_SENT_END = ".;:!?"
_MAX_CUES = 12
_ADJ = 400


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u00a0", " ").replace("\u2019", "'")).strip()


def _find(text: str, words: Sequence[str]) -> list[str]:
    low = text.casefold()
    out = []
    for w in words:
        if w != w.strip() or w.endswith("'"):  # fragments such as "ne " or " pas": plain substring on the padded text
            hit = w in low
        else:
            hit = re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", low) is not None
        if hit:
            out.append(w.strip())
    return out


def cues_for(quote: str, article: str) -> list[dict[str, str]]:
    q, a = _norm(quote), _norm(article)
    start = a.find(q)
    if not q or start == -1:
        return []
    end = start + len(q)
    outside = a[:start] + " " + a[end:]
    found = [{"kind": "reservation", "cue": c} for c in sorted(set(_find(outside, _RESERVATION)))]
    before = a[max(0, start - _ADJ):start].rstrip()
    cut = max((before.rfind(ch, 0, len(before) - 1) for ch in _SENT_END), default=-1)
    prev_sentence = before[cut + 1:]
    after = a[end:end + _ADJ].lstrip()
    nxt = next((after[: i + 1] for i, ch in enumerate(after) if ch in _SENT_END), after)
    # An adjacent sentence only: the quoted passage itself is never searched for negations.
    neg = sorted(set(_find(" " + prev_sentence + " " + nxt + " ", _NEGATION)))
    found += [{"kind": "negation_adjacent", "cue": c} for c in neg]
    return found[:_MAX_CUES]


def build_section(references: Sequence[Mapping[str, Any]], records: Sequence[Any]) -> dict[str, Any]:
    by_hash = {r.derived_sha256: r for r in records}
    rows: list[dict[str, Any]] = []
    checked = 0
    for ref in references:
        quote, digest = ref.get("quote"), ref.get("corpus_text_sha256")
        if ref.get("status") not in ("PASS", "UNDETERMINED") or not quote or digest not in by_hash:
            continue
        cues = cues_for(quote, by_hash[digest].derived_text)
        if not _norm(quote) or _norm(quote) not in _norm(by_hash[digest].derived_text):
            continue  # a quotation absent from the article text is already a FAIL elsewhere
        checked += 1
        if cues:
            rows.append({"reference_id": ref["reference_id"], "corpus_text_sha256": digest, "cues": cues})
    return {"rules": RULES, "quotations_checked": checked, "flagged": rows}


def validate_section(section: Any, references: Sequence[Mapping[str, Any]], records: Sequence[Any]) -> None:
    if not isinstance(section, dict) or section.get("rules") != RULES or set(section) != {"rules", "quotations_checked", "flagged"}:
        raise CorpusError("reservation cue section malformed")
    if section != build_section(references, records):
        raise CorpusError("reservation cues do not replay")
