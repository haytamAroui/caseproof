"""Bounded lexical event review, not semantic support or legal reasoning.

Detects explicit signature/dispatch wording, including uncited candidates. Only
an existing unique exact quotation resolves a source. No date equality verdict.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from application.litigation.library import EvidencePreview

VERSION = "event-language-review-v1"
_SENT = re.compile(r"\b(?:envoy[ée]e?\s+pour\s+signature|sent\s+for\s+signature|ter\s+ondertekening\s+verzonden)\b", re.I)
_SIGNED = re.compile(r"\b(?:a\s+[ée]t[ée]\s+sign[ée]e?|is\s+signed|was\s+signed|werd\s+ondertekend|is\s+ondertekend)\b", re.I)
_UNCERTAIN = re.compile(r"\b(?:pas|jamais|non|sans|not|never|niet|geen|peut-être|possibly|mogelijk|sous\s+r[ée]serve)\b", re.I)
_QUOTES = re.compile(r'«[^»]*»|“[^”]*”|"[^"\n]*"')


def events(text: str) -> tuple[str, ...]:
    return tuple(name for name, pattern in (("sent_for_signature", _SENT), ("signed", _SIGNED)) if pattern.search(text))


@dataclass(frozen=True, slots=True)
class EventObservation:
    observation_id: str
    reference_id: str | None
    draft_text: str
    draft_start: int
    draft_end: int
    draft_events: tuple[str, ...]
    source_events: tuple[str, ...]
    state: str
    reason: str
    source_id: str | None = None
    source_version_id: str | None = None
    source_sha256: str | None = None
    representation_id: str | None = None
    text_start: int | None = None
    text_end: int | None = None
    source_text: str | None = None
    semantic_support: str = "not_assessed"
    detector_version: str = VERSION


def review_events(text: str, references: tuple[Any, ...], citations: tuple[Any, ...],
                  previews: tuple[EvidencePreview, ...]) -> tuple[EventObservation, ...]:
    """Lexical candidates per paragraph, bound only by a unique existing quote.

    A same-event result still needs human judgment. A different-event result
    is not a contradiction: the document may describe both events elsewhere.
    Uncited/multi-anchor candidates remain visible with no source inference.
    """
    out: list[EventObservation] = []
    by_ref = {c.reference_id: c for c in citations}
    offset = 0
    for paragraph in text.splitlines(keepends=True):
        start, end = offset, offset + len(paragraph.rstrip("\r\n"))
        offset += len(paragraph)
        claim = _QUOTES.sub("", paragraph)
        found = events(claim)
        if not found:
            continue
        if len(out) >= 128:
            raise ValueError("event candidates outside bounded review contract")
        anchors = [r for r in references if r.exact_quote and r.exact_quote in paragraph
                   and sum(r.exact_quote in q.group() for q in _QUOTES.finditer(text)) == 1]
        reason = "no_unique_explicit_quote_anchor"
        ref = anchors[0] if len(anchors) == 1 else None
        kwargs: dict[str, Any] = {}
        source_events: tuple[str, ...] = ()
        if len(paragraph) > 4000 or len(found) != 1 or _UNCERTAIN.search(claim):
            reason = "draft_event_context_ambiguous"
        elif ref is not None:
            c = by_ref[ref.reference_id]
            p = next((p for p in previews if p.row.source_id == c.source_id
                      and p.row.version_id == c.source_version_id), None)
            reason = "source_anchor_unavailable_or_incomplete"
            if (c.state == "exact_match" and p is not None and p.row.status == "ready"
                    and not p.row.warnings and p.row.representation_id
                    and c.text_start is not None and c.text_end is not None):
                spans = [(a, b) for a, b, _, _ in p.spans if a <= c.text_start < c.text_end <= b]
                if len(spans) == 1 and spans[0][1] - spans[0][0] <= 4000:
                    a, b = spans[0]
                    passage = p.text[a:b]
                    source_events = events(passage)
                    kwargs = dict(source_id=p.row.source_id, source_version_id=p.row.version_id,
                                  source_sha256=p.row.original_sha256, representation_id=p.row.representation_id,
                                  text_start=a, text_end=b, source_text=passage)
                    if _UNCERTAIN.search(passage) or len(source_events) != 1:
                        reason = "source_event_context_ambiguous"
                    elif found != source_events:
                        reason = "different_event_wording_requires_human_review"
                    else:
                        reason = "same_event_wording_support_not_assessed"
        out.append(EventObservation(f"event-{start}", ref.reference_id if ref else None,
                                    text[start:end], start, end, found, source_events,
                                    "needs_context", reason, **kwargs))
    return tuple(out)
