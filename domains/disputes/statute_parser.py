"""Deterministic Level-1 Belgian NL/FR statutory citation parser.

Scope boundary (ADR 0018 / ADR 0019):
- Format and structural syntax validation only (Level 1).
- Does NOT fetch Justel, Moniteur belge/Belgisch Staatsblad, or any external source.
- Does NOT verify statutory existence, historical version, entry into force, or legal validity.
- Uses existing Evidence Kernel TextSpan anchors for representation-local offsets.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from packages.evidence_kernel.domain.anchors import TextSpan

PARSER_VERSION = "caseproof-statute-citation-parser-v1"

_ROMAN_BOOK = r"(?:XX|X(?:IX|IV|V?I{0,3})|IX|IV|V?I{1,3}|V)"
_LATIN_SUFFIX = r"(?:bis|ter|quater|quinquies|sexies|septies|octies|novies|decies)"
_NUMERIC_ARTICLE = (
    r"[1-9][0-9]{0,3}"
    r"(?:\.[1-9][0-9]{0,2})?"
    r"(?:/[1-9][0-9]{0,2})?"
    rf"{_LATIN_SUFFIX}?"
)
_ROMAN_ARTICLE = (
    rf"{_ROMAN_BOOK}"
    rf"(?:\.[1-9][0-9]{{0,3}}(?:/[1-9][0-9]{{0,2}})?{_LATIN_SUFFIX}?)?"
)
_ARTICLE_TOKEN = rf"(?:{_ROMAN_ARTICLE}|{_NUMERIC_ARTICLE})"

_NL_MONTHS = (
    "januari|februari|maart|april|mei|juni|juli|"
    "augustus|september|oktober|november|december"
)
_FR_MONTHS = (
    "janvier|février|fevrier|mars|avril|mai|juin|juillet|"
    "août|aout|septembre|octobre|novembre|décembre|decembre"
)
_DAY = r"(?:[1-9]|[12][0-9]|3[01])"
_FR_DAY = r"(?:1er|[1-9]|[12][0-9]|3[01])"
_YEAR = r"(?:18|19|20)[0-9]{2}"

_NL_ACT = rf"(?P<nl_act>Wet\s+van\s+(?P<nl_date>{_DAY}\s+(?:{_NL_MONTHS})\s+{_YEAR}))"
_FR_ACT = rf"(?P<fr_act>Loi\s+du\s+(?P<fr_date>{_FR_DAY}\s+(?:{_FR_MONTHS})\s+{_YEAR}))"

_CODE_SPEC: tuple[tuple[str, str, Literal["nl", "fr"], str], ...] = (
    ("nl_gerw_abbr", r"Ger\.\s*W\.", "nl", "Ger.W."),
    ("nl_gerw_full", r"(?:van\s+het\s+)?Gerechtelijk\s+Wetboek", "nl", "Ger.W."),
    ("fr_cjud_abbr", r"C\.\s*jud\.", "fr", "Ger.W."),
    ("fr_cjud_full", r"(?:du\s+)?Code\s+judiciaire", "fr", "Ger.W."),
    ("fr_cciv_abbr", r"C\.\s*civ\.", "fr", "C.civ."),
    ("fr_cciv_full", r"(?:du\s+)?Code\s+civil", "fr", "C.civ."),
    ("nl_bw_abbr", r"(?:N?BW|B\.\s*W\.)", "nl", "C.civ."),
    ("nl_bw_full", r"(?:van\s+het\s+)?(?:Nieuw\s+)?Burgerlijk\s+Wetboek", "nl", "C.civ."),
    ("nl_wer_abbr", r"WER", "nl", "WER"),
    ("nl_wer_full", r"(?:van\s+het\s+)?Wetboek\s+van\s+economisch\s+recht", "nl", "WER"),
    ("fr_cde_abbr", r"CDE", "fr", "WER"),
    ("fr_cde_full", r"(?:du\s+)?Code\s+de\s+droit\s+[ée]conomique", "fr", "WER"),
)

_CODE_UNION = "|".join(f"(?P<{name}>{pattern})" for name, pattern, _, _ in _CODE_SPEC)
_ACT_IN_ARTICLE = (
    rf"(?:van\s+de\s+)?(?P<art_nl_act>Wet\s+van\s+(?P<art_nl_date>{_DAY}\s+(?:{_NL_MONTHS})\s+{_YEAR}))"
    rf"|(?:de\s+la\s+)?(?P<art_fr_act>Loi\s+du\s+(?P<art_fr_date>{_FR_DAY}\s+(?:{_FR_MONTHS})\s+{_YEAR}))"
)

_ARTICLE_CITATION_PATTERN = re.compile(
    r"(?<![\w.])"
    r"(?P<prefix>Art\.|Artikel|Article)"
    r"\s+"
    rf"(?P<article>{_ARTICLE_TOKEN})"
    r"(?:\s*,?\s*§\s*(?P<paragraph>[1-9][0-9]{0,2}(?:bis|ter|quater)?))?"
    r"\s+"
    rf"(?:{_CODE_UNION}|{_ACT_IN_ARTICLE})"
    r"(?![\w])"
)

_STANDALONE_ACT_PATTERN = re.compile(
    rf"(?<![\w.])(?:{_NL_ACT}|{_FR_ACT})(?![\w])"
)

_MAX_DAYS_BY_MONTH: dict[str, int] = {
    "januari": 31, "janvier": 31,
    "februari": 29, "février": 29, "fevrier": 29,
    "maart": 31, "mars": 31,
    "april": 30, "avril": 30,
    "mei": 31, "mai": 31,
    "juni": 30, "juin": 30,
    "juli": 31, "juillet": 31,
    "augustus": 31, "août": 31, "aout": 31,
    "september": 30, "septembre": 30,
    "oktober": 31, "octobre": 31,
    "november": 30, "novembre": 30,
    "december": 31, "décembre": 31, "decembre": 31,
}


class CitationParseError(ValueError):
    """Raised when a statutory citation string is malformed or language-inconsistent."""


class StatuteCitation(BaseModel):
    """Normalized Belgian NL/FR statutory citation (Level-1 format representation only)."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    code: str = Field(min_length=1, max_length=128)
    article: str = Field(min_length=1, max_length=64)
    paragraph: str | None = Field(
        default=None,
        pattern=r"^§\s*[1-9][0-9]{0,2}(?:bis|ter|quater)?$",
    )
    language: Literal["nl", "fr"]
    raw_text: str = Field(min_length=1, max_length=512)


@dataclass(frozen=True, slots=True)
class AnchoredStatuteCitation:
    """Binds a parsed StatuteCitation to an Evidence Kernel TextSpan locator."""

    citation: StatuteCitation
    span: TextSpan


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def _validate_act_date(date_str: str) -> str:
    normalized = _normalize_whitespace(date_str)
    day_token, month_token, year_token = normalized.split()
    day = 1 if day_token == "1er" else int(day_token)
    year = int(year_token)
    month_key = month_token.lower()
    max_day = _MAX_DAYS_BY_MONTH.get(month_key, 31)
    if month_key in {"februari", "février", "fevrier"}:
        is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
        max_day = 29 if is_leap else 28
    if day < 1 or day > max_day:
        raise CitationParseError(f"invalid calendar day in statutory date: {normalized!r}")
    return normalized


def _build_from_article_match(match: re.Match[str]) -> StatuteCitation:
    prefix = match.group("prefix")
    article = match.group("article")
    para_num = match.group("paragraph")
    paragraph = f"§ {para_num}" if para_num is not None else None

    code: str | None = None
    code_lang: Literal["nl", "fr"] | None = None

    for name, _, lang, canonical_code in _CODE_SPEC:
        if match.group(name) is not None:
            code = canonical_code
            code_lang = lang
            break

    if code is None:
        if match.group("art_nl_act") is not None:
            _validate_act_date(match.group("art_nl_date"))
            code = _normalize_whitespace(match.group("art_nl_act"))
            code_lang = "nl"
        elif match.group("art_fr_act") is not None:
            _validate_act_date(match.group("art_fr_date"))
            code = _normalize_whitespace(match.group("art_fr_act"))
            code_lang = "fr"

    if code is None or code_lang is None:
        raise CitationParseError("unrecognized statutory code")

    if prefix == "Artikel" and code_lang != "nl":
        raise CitationParseError("Dutch 'Artikel' prefix cannot be combined with a French code")
    if prefix == "Article" and code_lang != "fr":
        raise CitationParseError("French 'Article' prefix cannot be combined with a Dutch code")

    return StatuteCitation(
        code=code,
        article=article,
        paragraph=paragraph,
        language=code_lang,
        raw_text=match.group(0),
    )


def _build_from_act_match(match: re.Match[str]) -> StatuteCitation:
    if match.group("nl_act") is not None:
        act = _normalize_whitespace(match.group("nl_act"))
        date_str = _validate_act_date(match.group("nl_date"))
        return StatuteCitation(
            code=act,
            article=date_str,
            paragraph=None,
            language="nl",
            raw_text=match.group(0),
        )
    if match.group("fr_act") is not None:
        act = _normalize_whitespace(match.group("fr_act"))
        date_str = _validate_act_date(match.group("fr_date"))
        return StatuteCitation(
            code=act,
            article=date_str,
            paragraph=None,
            language="fr",
            raw_text=match.group(0),
        )
    raise CitationParseError("unrecognized statutory act citation")


def parse_statute_citation(text: str) -> StatuteCitation:
    """Parse a single Belgian NL/FR statutory citation or raise CitationParseError."""
    if not isinstance(text, str):
        raise CitationParseError("citation text must be a string")
    candidate = text.strip()
    if not candidate:
        raise CitationParseError("citation text must not be empty")

    art_match = _ARTICLE_CITATION_PATTERN.fullmatch(candidate)
    if art_match is not None:
        return _build_from_article_match(art_match)

    act_match = _STANDALONE_ACT_PATTERN.fullmatch(candidate)
    if act_match is not None:
        return _build_from_act_match(act_match)

    raise CitationParseError(f"malformed or unsupported Belgian statutory citation: {text!r}")


def extract_statute_citations(text: str) -> list[StatuteCitation]:
    """Extract all valid Belgian NL/FR statutory citations from a text passage."""
    return [item.citation for item in extract_anchored_statute_citations(text)]


def extract_anchored_statute_citations(text: str) -> list[AnchoredStatuteCitation]:
    """Extract citations bound to Evidence Kernel TextSpan locators."""
    if not isinstance(text, str) or not text:
        return []
    results: list[AnchoredStatuteCitation] = []
    cursor = 0
    while cursor < len(text):
        art_match = _ARTICLE_CITATION_PATTERN.search(text, cursor)
        act_match = _STANDALONE_ACT_PATTERN.search(text, cursor)

        chosen: re.Match[str] | None = None
        is_article = True
        if art_match is not None and (act_match is None or art_match.start() <= act_match.start()):
            chosen = art_match
            is_article = True
        elif act_match is not None:
            chosen = act_match
            is_article = False

        if chosen is None:
            break

        try:
            citation = (
                _build_from_article_match(chosen)
                if is_article
                else _build_from_act_match(chosen)
            )
            results.append(
                AnchoredStatuteCitation(
                    citation=citation,
                    span=TextSpan(start=chosen.start(), end=chosen.end()),
                )
            )
        except CitationParseError:
            pass
        cursor = chosen.end()
    return results
