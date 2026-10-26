"""PIV-09 conservative trilingual source-linked factual token comparisons.

This is NOT finance reconciliation, legal reasoning, automatic role discovery,
or evidence of source authenticity. Roles are explicit typed draft-assertion
metadata and independently checked for lexical cues in BOTH passages.
Unknown/ambiguous context never becomes a purported contradiction.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from application.litigation.library import EvidencePreview


class FactError(ValueError):
    """Malformed or ungrounded deterministic fact comparison."""


class FactKind(StrEnum):
    MONEY = "money"
    DATE = "date"


class FactRole(StrEnum):
    PAYMENT = "payment"
    DUE = "due"
    DELIVERY = "delivery"
    INVOICE = "invoice"


class FactState(StrEnum):
    MATCH = "value_match"
    DIFFERENCE = "candidate_difference"
    NEEDS_CONTEXT = "needs_context"
    NOT_ASSESSED = "not_assessed"


# Conservative lexicons, not semantic classifiers. All supported language
# variants must be tested on exact excerpts; negated/mixed roles abstain.
_ROLE_TERMS: dict[FactRole, tuple[str, ...]] = {
    FactRole.PAYMENT: ("paiement", "payé", "payée", "betaling", "betaald", "payment", "paid"),
    FactRole.DUE: ("échéance", "echeance", "vervaldatum", "due date", "verschuldigd"),
    FactRole.DELIVERY: ("livraison", "geleverd", "levering", "delivery", "delivered"),
    FactRole.INVOICE: ("facture", "factuur", "invoice"),
}
_UNCERTAINTY = ("peut-être", "waarschijnlijk", "perhaps", "possibly",
                "voorlopig", "estimated", "estimé", "ongeveer",
                "approximately", "about", "environ", "circa", "niet ", "not ",
                "non ", "sans ", "zonder ", "no ", "creditnota", "credit note",
                "avenant", "amendment", "wijziging")
_BASIS_MARKERS = ("htva", "ttc", "tva", "btw", "vat", "excl.", "incl.",
                  "hors taxe", "inclusief", "exclusief", "gross", "net", "brut")
_MONEY = re.compile(
    r"(?<![\w])(?:€\s*|EUR\s*)(?:\d{1,3}(?:[ .]\d{3})+(?:[,.]\d{2})?|\d+(?:[,.]\d{2})?)(?![\w])",
    re.IGNORECASE,
)
_DATE = re.compile(
    r"(?<!\d)(?:\d{4}-\d{2}-\d{2}|\d{1,2}\s+"
    r"(?:januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|"
    r"november|december|janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|"
    r"septembre|octobre|novembre|décembre|decembre|january|february|march|may|june|"
    r"july|august|october|december)\s+\d{4}|\d{1,2}/\d{1,2}/\d{4})(?!\d)",
    re.IGNORECASE,
)
_MONTHS = {
    "januari": 1, "janvier": 1, "january": 1,
    "februari": 2, "février": 2, "fevrier": 2, "february": 2,
    "maart": 3, "mars": 3, "march": 3,
    "april": 4, "avril": 4,
    "mei": 5, "mai": 5, "may": 5,
    "juni": 6, "juin": 6, "june": 6,
    "juli": 7, "juillet": 7, "july": 7,
    "augustus": 8, "août": 8, "aout": 8, "august": 8,
    "september": 9, "septembre": 9,
    "oktober": 10, "octobre": 10, "october": 10,
    "november": 11, "novembre": 11,
    "december": 12, "décembre": 12, "decembre": 12,
}


@dataclass(frozen=True, slots=True)
class FactAssertion:
    claim_id: str
    reference_id: str
    text: str
    text_start: int
    text_end: int
    kind: FactKind
    role: FactRole

    def __post_init__(self) -> None:
        if not all(type(s) is str and 0 < len(s) <= 160 for s in (self.claim_id, self.reference_id)):
            raise FactError("bounded fact/reference IDs required")
        if type(self.text) is not str or not self.text.strip() or len(self.text) > 4000:
            raise FactError("bounded assertion passage required")
        if (type(self.text_start) is not int or type(self.text_end) is not int
                or not 0 <= self.text_start < self.text_end):
            raise FactError("validated assertion text bounds required")
        if not isinstance(self.kind, FactKind) or not isinstance(self.role, FactRole):
            raise FactError("typed fact kind and explicitly assigned role required")


@dataclass(frozen=True, slots=True)
class FactObservation:
    claim_id: str
    reference_id: str
    kind: FactKind
    role: FactRole
    state: FactState
    brief_token: str | None
    source_token: str | None
    source_id: str | None
    source_version_id: str | None
    representation_id: str | None
    source_start: int | None
    source_end: int | None
    explanation: str


def _extract(text: str, kind: FactKind) -> list[tuple[str, int, int, Decimal | date | None]]:
    pattern = _MONEY if kind is FactKind.MONEY else _DATE
    result: list[tuple[str, int, int, Decimal | date | None]] = []
    for match in pattern.finditer(text):
        token = match.group(0)
        value: Decimal | date | None = _money_value(token) if kind is FactKind.MONEY else _date_value(token)
        result.append((token, match.start(), match.end(), value))
    return result


def _money_value(token: str) -> Decimal | None:
    raw = re.sub(r"^(?:€|EUR)\s*", "", token, flags=re.IGNORECASE).replace(" ", "")
    # One 3-digit trailing separator is ambiguous (14,500 == 14.5 or 14500).
    if re.fullmatch(r"\d+[,.]\d{3}", raw):
        return None
    if "." in raw and "," in raw:
        sep = "." if raw.rfind(".") > raw.rfind(",") else ","
        other = "," if sep == "." else "."
        if len(raw.rsplit(sep, 1)[1]) != 2:
            return None
        raw = raw.replace(other, "").replace(sep, ".")
    elif re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", raw):
        raw = raw.replace(".", "").replace(",", "")
    else:
        raw = raw.replace(",", ".")
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    return value if value.is_finite() and value >= 0 else None


def _date_value(token: str) -> date | None:
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", token):
            return date.fromisoformat(token)
        if "/" in token:
            day, month, year = (int(x) for x in token.split("/"))
            # Without explicit locale a 04/05 date is genuinely ambiguous.
            if day <= 12 and month <= 12:
                return None
            return date(year, month, day)
        day_text, month_text, year_text = token.lower().split()
        month = _MONTHS.get(month_text)
        return date(int(year_text), month, int(day_text)) if month is not None else None
    except (TypeError, ValueError):
        return None


def _safe_context(text: str, role: FactRole) -> bool:
    low = text.casefold()
    if any(marker in low for marker in _UNCERTAINTY):
        return False
    if not any(token in low for token in _ROLE_TERMS[role]):
        return False
    return not any(
        other_role is not role and any(token in low for token in terms)
        for other_role, terms in _ROLE_TERMS.items()
    )


def _basis(text: str) -> frozenset[str]:
    low = text.casefold()
    return frozenset(x for x in _BASIS_MARKERS if x in low)


def compare_fact(
    assertion: FactAssertion,
    *,
    verified_brief_text: str,
    preview: EvidencePreview | None,
    pdf_page: int | None,
) -> FactObservation:
    """Compare tokens ONLY inside one source-mapped span of the cited exhibit.

    Calling application must already verify case membership, source custody,
    exact representation and exhibit version. Missing authorization is not a
    valid reason to call this pure function.
    """
    if (not isinstance(assertion, FactAssertion)
            or type(verified_brief_text) is not str
            or assertion.text_end > len(verified_brief_text)
            or verified_brief_text[assertion.text_start:assertion.text_end] != assertion.text):
        raise FactError("assertion is not an exact brief representation span")
    if pdf_page is not None and (type(pdf_page) is not int or pdf_page < 1):
        raise FactError("invalid verified physical page")

    def obs(state: FactState, explanation: str, *, brief: str | None = None,
            source: str | None = None, anchor: tuple[int, int] | None = None) -> FactObservation:
        row = preview.row if preview is not None else None
        return FactObservation(
            assertion.claim_id, assertion.reference_id, assertion.kind, assertion.role, state,
            brief, source, row.source_id if row else None, row.version_id if row else None,
            row.representation_id if row else None,
            anchor[0] if anchor else None, anchor[1] if anchor else None, explanation,
        )

    if preview is None or preview.row.status != "ready" or preview.row.warnings or not preview.row.representation_id:
        return obs(FactState.NOT_ASSESSED, "source_missing_or_incomplete")
    if len(preview.text) > 120_000 or not preview.spans:
        return obs(FactState.NOT_ASSESSED, "source_representation_unavailable")
    if any(
        type(a) is not int or type(b) is not int or not 0 <= a < b <= len(preview.text)
        for a, b, _, _ in preview.spans
    ):
        raise FactError("invalid verified source span")

    claim_tokens = _extract(assertion.text, assertion.kind)
    if len(claim_tokens) != 1 or claim_tokens[0][3] is None or not _safe_context(assertion.text, assertion.role):
        return obs(FactState.NEEDS_CONTEXT, "assertion_value_or_role_ambiguous")
    claim_token, _, _, claim_value = claim_tokens[0]
    assert claim_value is not None

    # A source may have several pages or paragraphs. Require a unique
    # role-aligned candidate inside ONE verified page-local span.
    possibilities: list[tuple[str, int, int, Decimal | date, str]] = []
    for start, end, _, page_index in preview.spans:
        if pdf_page is not None and (page_index is None or page_index + 1 != pdf_page):
            continue
        passage = preview.text[start:end]
        if not _safe_context(passage, assertion.role):
            continue
        for token, a, b, val in _extract(passage, assertion.kind):
            if val is not None:
                possibilities.append((token, start + a, start + b, val, passage))
    if len(possibilities) != 1:
        return obs(FactState.NEEDS_CONTEXT, "source_role_or_value_not_unique", brief=claim_token)
    token, start, end, source_value, source_context = possibilities[0]
    if _basis(assertion.text) != _basis(source_context):
        return obs(FactState.NEEDS_CONTEXT, "vat_or_net_gross_basis_unverified", brief=claim_token)
    return obs(
        FactState.MATCH if claim_value == source_value else FactState.DIFFERENCE,
        "same_role_typed_tokens_equal" if claim_value == source_value else "same_role_candidate_difference",
        brief=claim_token, source=token, anchor=(start, end),
    )
