"""Deterministic fact-assertion extraction from a verified brief text.

No LLM, no classifier: a fact assertion is produced only when every
condition compare_fact will re-verify holds at extraction time:

* the money/date token sits inside one sentence of at most 1000
  characters (longer sentences abstain rather than risking a cut token);
* that sentence contains exactly ONE token of the assertion's kind —
  compare_fact refuses multi-token passages, so extraction never emits
  one it would reject;
* exactly one factual role is safe in the sentence (_safe_context
  already abstains on negation, uncertainty markers, signed amounts and
  mixed roles); ambiguity means abstention, never a guess;
* the money value parses identically in French and English grouping, or
  only one grouping parses — conflicting readings abstain;
* a citation span precedes the token: the assertion attaches to the
  nearest preceding reference, because compare_fact only compares
  against the cited exhibit. A fact with no preceding citation is
  reported nowhere — explicit abstention.

Everything here is pure and reproducible: the same text and citations
always yield the same assertions, and claim ids derive from content
offsets so replays are stable.
"""
from __future__ import annotations

from application.litigation.factual_values import (
    FactAssertion,
    FactKind,
    FactRole,
    _date_value,
    _extract,
    _money_value,
    _safe_context,
)

_MAX_SENTENCE = 1000
_MAX_ASSERTIONS = 2048
_BOUNDARIES = ".!?\n"

_FR_MONTHS = {
    "janvier", "février", "fevrier", "mars", "avril", "mai", "juin",
    "juillet", "août", "aout", "septembre", "octobre", "novembre",
    "décembre", "decembre",
}
_NL_MONTHS = {
    "januari", "februari", "maart", "april", "mei", "juni", "juli",
    "augustus", "september", "oktober", "november", "december",
}
_EN_MONTHS = {
    "january", "february", "march", "may", "june", "july", "august",
    "october", "december",
}


def _is_boundary(text: str, i: int) -> bool:
    ch = text[i]
    if ch not in _BOUNDARIES:
        return False
    # A dot between digits is a thousands or decimal separator ("1.250,00"), not a sentence end.
    return not (ch == "." and 0 < i < len(text) - 1 and text[i - 1].isdigit() and text[i + 1].isdigit())


def _sentence(text: str, start: int, end: int) -> tuple[int, int]:
    left = next((i for i in range(start - 1, -1, -1) if _is_boundary(text, i)), -1) + 1
    right = next((i for i in range(end, len(text)) if _is_boundary(text, i)), len(text))
    while left < right and text[left] in " \t":
        left += 1
    while right > left and text[right - 1] in " \t\r":
        right -= 1
    return left, right


def _money_language(token: str) -> tuple[str, object] | None:
    value_fr = _money_value(token, "fr")
    value_en = _money_value(token, "en")
    if value_fr is not None and value_en is not None:
        if value_fr != value_en:
            return None  # ambiguous grouping: abstain, never guess
        return "fr", value_fr
    if value_fr is not None:
        return "fr", value_fr
    if value_en is not None:
        return "en", value_en
    return None


def _date_language(token: str) -> str:
    parts = token.lower().split()
    if len(parts) == 3:
        month = parts[1]
        if month in _FR_MONTHS and month not in _NL_MONTHS | _EN_MONTHS:
            return "fr"
        if month in _NL_MONTHS and month not in _FR_MONTHS | _EN_MONTHS:
            return "nl"
        if month in _EN_MONTHS and month not in _FR_MONTHS | _NL_MONTHS:
            return "en"
    # Numeric dates and shared month names parse identically in every
    # supported language; the field carries no parsing effect here.
    return "fr"


def extract_fact_assertions(
    text: str,
    citations: tuple[tuple[str, int], ...],
) -> tuple[FactAssertion, ...]:
    """Extract deterministic fact assertions, abstaining on any ambiguity.

    citations: (reference_id, citation_end_offset) pairs in text order;
    an assertion attaches to the nearest citation ending before its token.
    """
    if type(text) is not str or not text:
        raise ValueError("nonempty verified text required")
    ordered = sorted(citations, key=lambda item: item[1])
    if any(
        type(ref) is not str or not ref or type(end) is not int
        or not 0 <= end <= len(text)
        for ref, end in ordered
    ):
        raise ValueError("citation spans outside the verified text")
    assertions: list[FactAssertion] = []
    for kind in (FactKind.MONEY, FactKind.DATE):
        for token, token_start, _token_end, _parsed in _extract(text, kind, "fr"):
            start, end = _sentence(text, token_start, token_end_offset(token, token_start, text, kind))
            if not 0 < end - start <= _MAX_SENTENCE:
                continue
            window = text[start:end]
            if len(_extract(window, kind, "fr")) != 1:
                continue
            if kind is FactKind.MONEY:
                resolved = _money_language(token)
                if resolved is None:
                    continue
                language, value = resolved
            else:
                if _date_value(token) is None:
                    continue
                language = _date_language(token)
            roles = [role for role in FactRole if _safe_context(window, role)]
            if len(roles) != 1:
                continue
            reference_id = next(
                (ref for ref, citation_end in reversed(ordered) if citation_end <= token_start),
                None,
            )
            if reference_id is None:
                continue
            assertions.append(
                FactAssertion(
                    claim_id=f"claim-{reference_id}-{kind.value}-{start}",
                    reference_id=reference_id,
                    text=window,
                    text_start=start,
                    text_end=end,
                    kind=kind,
                    role=roles[0],
                    language=language,
                    source_language=language,
                )
            )
            if len(assertions) > _MAX_ASSERTIONS:
                raise ValueError("fact assertions outside the signed contract")
    return tuple(assertions)


def token_end_offset(token: str, start: int, text: str, kind: FactKind) -> int:
    """End offset of the token occurrence at start (exact slice check)."""
    end = start + len(token)
    if text[start:end] != token:
        raise ValueError("token outside the verified text")
    return end


__all__ = ["extract_fact_assertions"]
