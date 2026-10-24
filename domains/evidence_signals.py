"""Pure, domain-owned typed observation definitions. Never a semantic approval."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal

ValueType = Literal["scalar", "money", "iso_date"]
_ALLOWED_CURRENCIES = re.compile(r"(?<![A-Z])(?:EUR|USD|GBP|CHF|AED|SAR)(?![A-Z])", re.I)
_DECIMAL_VALUE = re.compile(r"^[+-]?[0-9]+(?:[.,][0-9]{1,2})?$")
_ISO_VALUE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class SignalDefinition:
    """Versioned policy entries describe candidate shape, not observed truth."""

    trigger: str
    allowed_kinds: frozenset[str]
    value_type: ValueType = "scalar"


def validate_observation(
    *,
    signal: str,
    slot: str,
    quote: str,
    value: str,
    kind: str,
    definitions: dict[str, SignalDefinition],
) -> tuple[str, str]:
    spec = definitions.get(signal)
    if spec is None:
        return "needs_review", "unregistered_signal"
    if slot != signal or kind not in spec.allowed_kinds:
        return "rejected", "signal_consumer_mismatch"
    if not re.search(spec.trigger, quote, re.IGNORECASE):
        return "needs_review", "signal_semantics_unresolved"
    if not re.search(r"(?<![\w+-])(?<!\d[.,])" + re.escape(value) + r"(?!\w|[.,]\d)", quote):
        return "rejected", "value_not_in_quote"
    if spec.value_type == "money":
        if not _DECIMAL_VALUE.fullmatch(value):
            return "needs_review", "typed_money_unparseable"
        currencies = {m.upper() for m in _ALLOWED_CURRENCIES.findall(quote)}
        if len(currencies) != 1:
            return "needs_review", "typed_currency_ambiguous"
        try:
            amount = Decimal(value.replace(",", "."))
        except InvalidOperation:
            return "needs_review", "typed_money_unparseable"
        if not amount.is_finite():
            return "needs_review", "typed_money_unparseable"
    if spec.value_type == "iso_date":
        if not _ISO_VALUE.fullmatch(value):
            return "needs_review", "typed_date_unparseable"
        try:
            date.fromisoformat(value)
        except ValueError:
            return "needs_review", "typed_date_unparseable"
    return "validated", "proposal_lexically_consistent"
