"""P0 guarded-term review warnings, never semantic verification.

Only an exact, unique quotation in the source *derived page text* gives
a lexical window. That is NOT an independently validated PDF crop or proof
of legal support. Missing terms are prompts to inspect original pixels.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

GUARD_VERSION = "caseproof-paraphrase-review-guard-v1"
_MAX_DRAFT = 1200
_MAX_SOURCE = 4000
_MAX_WARNINGS = 24

_AMOUNT = re.compile(r"(?<!\w)(?:€|EUR)\s*\d[\d .,]{0,26}\d|(?<!\w)(?:€|EUR)\s*\d", re.I)
_DATE = re.compile(
    r"(?<!\d)(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|"
    r"\d{1,2}\s+(?:januari|februari|maart|april|mei|juni|juli|augustus|"
    r"september|oktober|november|december|janvier|février|fevrier|mars|"
    r"avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|"
    r"décembre|decembre)\s+\d{4})(?!\d)", re.I,
)
_ARTICLE = re.compile(r"\b(?:art\.|article|artikel)\s*\d+(?:[./-]\d+)*\b", re.I)
_PARTY = re.compile(
    r"\b(?:madame|monsieur|mme\.?|mevrouw|de heer|partij|partie|"
    r"société|vennootschap|bv|srl|nv|sa)\s+"
    r"([A-ZÀ-ÖØ-Þ][\w'’.-]{1,45}(?:\s+[A-ZÀ-ÖØ-Þ][\w'’.-]{1,45}){0,2})",
    re.I,
)
_NUMBER = re.compile(r"(?<![\w])\d{1,6}(?:[.,]\d{1,3})?(?!\w)")
_NEGATION = re.compile(r"\b(?:niet|geen|nooit|nimmer|not|never|without|"
                       r"pas|jamais|aucun|aucune|non|sans)\b", re.I)
_QUALIFIER = re.compile(
    r"\b(?:slechts|uitsluitend|minstens|hoogstens|ongeveer|vermoedelijk|"
    r"mogelijk|voorwaardelijk|ten minste|ten hoogste|onder voorbehoud|"
    r"seulement|uniquement|environ|présumé|présumée|probablement|"
    r"peut-être|sous réserve|au moins|au plus|approximately|only|"
    r"allegedly|possibly|at least|at most|subject to)\b", re.I,
)
_REFERENCE_NUMBER = re.compile(r"(?:stuk(?:ken)?|pièce(?:s)?|piece(?:s)?|"
                                r"exhibit|pdf\s+p\.?|p\.?|pages?)\s*$", re.I)


def _fold(text: str) -> str:
    return " ".join(
        "".join(
            ch for ch in unicodedata.normalize("NFKD", text.casefold())
            if not unicodedata.combining(ch)
        ).split()
    )


def _terms(paragraph: str) -> list[tuple[str, str]]:
    """Bounded lexical candidates, ordered by occurrence, never model claims."""
    occupied: list[tuple[int, int]] = []
    located: list[tuple[int, str, str]] = []
    for kind, pattern in (
        ("amount", _AMOUNT), ("date", _DATE), ("article", _ARTICLE),
        ("party_name", _PARTY),
    ):
        for match in pattern.finditer(paragraph):
            term = match.group(1) if kind == "party_name" else match.group()
            occupied.append(match.span())
            located.append((match.start(), kind, term.strip()))
    for match in _NUMBER.finditer(paragraph):
        if any(a <= match.start() < b for a, b in occupied):
            continue
        if _REFERENCE_NUMBER.search(paragraph[max(0, match.start() - 20):match.start()]):
            continue
        located.append((match.start(), "number", match.group()))
    for kind, pattern in (("negation", _NEGATION), ("qualifier", _QUALIFIER)):
        located.extend((m.start(), kind, m.group()) for m in pattern.finditer(paragraph))
    unique: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for _, kind, term in sorted(located, key=lambda x: (x[0], x[1])):
        key = (kind, _fold(term))
        if key not in seen and term:
            unique.append((kind, term[:96]))
            seen.add(key)
    return unique


def guard_paraphrase(
    *,
    draft_region: str,
    reference_start: int,
    reference_end: int,
    quoted_text: str | None,
    source_text_context: str | None,
    source_version_id: str | None,
    source_sha256: str | None,
    pdf_page: int | None,
    ocr_uncertain: bool,
    source_text_partial: bool,
    draft_language: str | None = None,
    source_language: str | None = None,
) -> dict[str, Any]:
    """Returns a snapshot-ready *advisory*, never positive semantic support.

    Precondition: caller has independently authorized and resolved the signed
    source version. This pure function never performs authorization or reads
    external data. Absent passage, duplicate quote, different languages, OCR
    uncertainty and truncated text all require human source inspection.
    """
    if (
        not isinstance(draft_region, str) or len(draft_region) > 150_000
        or type(reference_start) is not int or type(reference_end) is not int
        or not 0 <= reference_start <= reference_end <= len(draft_region)
    ):
        raise ValueError("guard requires valid immutable DOCX region offsets")
    begin = draft_region.rfind("\n", 0, reference_start) + 1
    end = draft_region.find("\n", reference_end)
    if end < 0:
        end = len(draft_region)
    paragraph = draft_region[begin:end]
    reasons: list[str] = []
    warnings: list[dict[str, str]] = []
    source_excerpt = ""
    anchor_basis = "unavailable"
    candidate_terms = _terms(paragraph[:_MAX_DRAFT])
    if not paragraph.strip() or len(paragraph) > _MAX_DRAFT:
        reasons.append("DRAFT_PARAGRAPH_MISSING_OR_UNBOUNDED")
    if not source_version_id or not source_sha256 or pdf_page is None:
        reasons.append("SOURCE_PINPOINT_UNRESOLVED")
    if not source_text_context or len(source_text_context) > _MAX_SOURCE:
        reasons.append("SOURCE_TEXT_UNAVAILABLE")
    if source_text_partial:
        reasons.append("SOURCE_TEXT_PARTIAL")
    if ocr_uncertain:
        reasons.append("OCR_OR_VISUAL_FIDELITY_UNCERTAIN")
    if (
        draft_language and source_language
        and draft_language != source_language
    ):
        reasons.append("CROSS_LANGUAGE_LEXICAL_COMPARISON_UNSUPPORTED")
    if not quoted_text:
        reasons.append("NO_UNIQUE_VERBATIM_ANCHOR")
    elif source_text_context and len(source_text_context) <= _MAX_SOURCE:
        first = source_text_context.find(quoted_text)
        if first < 0:
            reasons.append("QUOTE_NOT_FOUND_IN_DERIVED_PAGE_TEXT")
        elif source_text_context.find(quoted_text, first + 1) >= 0:
            reasons.append("DUPLICATE_QUOTE_AMBIGUOUS")
        elif not ocr_uncertain and not source_text_partial:
            # Text offset is navigational only, never a verified PDF polygon.
            anchor_basis = "unique_exact_quote_in_derived_page_text"
            a = max(0, first - 360)
            b = min(len(source_text_context), first + len(quoted_text) + 360)
            source_excerpt = source_text_context[a:b]
    # No negative lexical inference from absent or otherwise unreliable text.
    if (
        anchor_basis != "unavailable"
        and len(paragraph) <= _MAX_DRAFT
        and not (
            draft_language and source_language
            and draft_language != source_language
        )
    ):
        normalized_source = _fold(source_excerpt)
        for kind, term in candidate_terms:
            if _fold(term) not in normalized_source:
                warnings.append({
                    "kind": kind,
                    "term": term,
                    "reason_code": "TERM_NOT_SEEN_IN_NEARBY_DERIVED_TEXT",
                })
                if len(warnings) == _MAX_WARNINGS:
                    reasons.append("GUARDED_TERM_LIMIT_REACHED")
                    break
        if warnings:
            reasons.append("GUARDED_TERMS_REQUIRE_MANUAL_REVIEW")
    elif candidate_terms:
        reasons.append("GUARDED_TERMS_NOT_COMPARABLE")
    return {
        "schema": GUARD_VERSION,
        "state": "needs_manual_review" if reasons or warnings else "not_assessed",
        "semantic_support": "not_assessed",
        "anchor_basis": anchor_basis,
        "source_version_id": source_version_id,
        "source_sha256": source_sha256,
        "pdf_page": pdf_page,
        "draft_excerpt": paragraph[:_MAX_DRAFT],
        "source_excerpt": source_excerpt,
        "warnings": warnings,
        "reason_codes": list(dict.fromkeys(reasons)),
        "notice": (
            "Guarded-term differences are review priorities, not contradictions. "
            "Inspect original PDF pixels and adjacent paragraphs before a human decision."
        ),
    }
