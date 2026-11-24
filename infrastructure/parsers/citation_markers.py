"""Deterministic French legal citation marker extraction from plain text.

Lexical extraction only: finds citation markers (parenthesized article
references and autonomous-act mentions) and their adjacent « ... » quotation.
No semantics, no source authority, no LLM: mapping a marker to an exhibit and
judging legal applicability stay downstream and explicit. A marker whose
quotation is absent is still reported (reference without quotation); a
quotation without a marker is reported as an orphan, never silently dropped.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

MAX_TEXT = 200_000
MAX_MARKERS = 128
_QUOTE_RE = re.compile(r"«\s*([^«»\n]{4,4000}?)\s*»")
_PAREN_RE = re.compile(r"\(([^()\n]{1,300})\)")
_ARTICLE_IN_PAREN_RE = re.compile(r"\bart(?:icle)?s?\.?\s*\d", re.IGNORECASE)
_AUTONOMOUS_RE = re.compile(
    r"\barticle\s+\d[\d\w°]*(?:\s*,\s*§\s*\d+\w*(?:\s+al\.\s*\d+\w*)?)*"
    r"\s+de\s+la\s+loi\s+du\s+\d{1,2}\s+[A-Za-zÀ-ÿ]+\s+\d{4}",
    re.IGNORECASE,
)
_GAP_RE = re.compile(r"^[\s:;,.\u2013-]{0,24}$")


class CitationExtractionError(ValueError):
    """Out-of-bounds extraction input."""


@dataclass(frozen=True, slots=True)
class CitationMarker:
    marker_id: str
    target: str
    form: str  # "parenthesized" | "autonomous_act"
    start: int
    end: int
    quote: str | None
    quote_start: int | None
    quote_end: int | None


@dataclass(frozen=True, slots=True)
class CitationExtraction:
    markers: tuple[CitationMarker, ...]
    orphan_quotes: tuple[tuple[int, int], ...]


def extract_citations(text: str) -> CitationExtraction:
    """Extract citation markers and their adjacent quotations from read text.

    Deterministic and lexical: the same text always yields the same markers.
    A quotation attaches to a marker only when only punctuation/space lies
    between them (no sentence boundary), so a marker never inherits a quote
    from another sentence.
    """
    if type(text) is not str or not text.strip() or len(text) > MAX_TEXT:
        raise CitationExtractionError(f"text must be 1..{MAX_TEXT} characters")

    quotes = [(m.start(), m.end(), m.group(1).strip()) for m in _QUOTE_RE.finditer(text)]
    consumed: set[int] = set()
    found: list[tuple[int, int, str, str, str | None, int | None, int | None]] = []

    for match in _PAREN_RE.finditer(text):
        inner = " ".join(match.group(1).split())
        if not _ARTICLE_IN_PAREN_RE.search(inner):
            continue
        quote = None
        quote_start = None
        quote_end = None
        for index, (start, end, content) in enumerate(quotes):
            if index in consumed or end > match.start():
                continue
            if _GAP_RE.fullmatch(text[end : match.start()]) is None:
                continue
            if quote_start is None or start > quote_start:
                quote, quote_start, quote_end = content, start, end
        if quote_start is not None:
            consumed.add(next(i for i, (s, _e, _c) in enumerate(quotes) if s == quote_start))
        found.append((match.start(), match.end(), "parenthesized", inner, quote, quote_start, quote_end))

    paren_spans = [(start, end) for start, end, *_ in found]
    for match in _AUTONOMOUS_RE.finditer(text):
        if any(start <= match.start() < end for start, end in paren_spans):
            continue
        if any(start <= match.start() < end for start, end, _c in quotes):
            continue
        target = " ".join(match.group(0).split())
        found.append((match.start(), match.end(), "autonomous_act", target, None, None, None))

    if len(found) > MAX_MARKERS:
        raise CitationExtractionError(f"more than {MAX_MARKERS} citation markers")

    found.sort(key=lambda entry: entry[0])
    markers = tuple(
        CitationMarker(
            f"cit-{position:02d}", target, form, start, end, quote, quote_start, quote_end
        )
        for position, (start, end, form, target, quote, quote_start, quote_end) in enumerate(found, 1)
    )
    orphans = tuple((start, end) for start, end, _c in quotes if (start, end) not in {
        (m.quote_start, m.quote_end) for m in markers if m.quote_start is not None
    })
    return CitationExtraction(markers, orphans)
