"""Conservative extraction of explicit Belgian exhibit references from text regions.

Discovery only: no claim that an exhibit exists, matches, or supports a proposition.
Offsets refer to the supplied Unicode string, not original PDF byte positions.
"""

import re
from dataclasses import dataclass

_REFERENCE = re.compile(
    r"(?<![\w])(?P<label>stuk(?:ken)?|pi[eè]ce(?:s)?)"
    r"\s*(?:n[°ºo.]?\s*)?(?P<number>[0-9]{1,4})"
    r"(?P<suffix>\s*(?:bis|ter))?(?![0-9])"
    r"(?:\s*[,;]?\s*(?:p\.|page|pagina)\s*(?P<page>[0-9]{1,5}))?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ExhibitReference:
    label: str
    number: str
    raw: str
    start: int
    end: int
    region: str
    # Unlabeled page number ("pièce 12, p. 3"). Never pre-assigned to a
    # page space: physical/printed/bundle resolution needs a confirmed
    # unique mapping downstream, otherwise abstain.
    page_hint: int | None = None


def detect_exhibit_references(text: str, *, region: str) -> tuple[ExhibitReference, ...]:
    """Return explicit references with resolvable text offsets; never infer ranges."""
    if not region.strip():
        raise ValueError("region must identify the source representation")
    found: list[ExhibitReference] = []
    for match in _REFERENCE.finditer(text):
        number = match.group("number") + (match.group("suffix") or "").strip().lower()
        page = match.group("page")
        found.append(
            ExhibitReference(
                label=match.group("label").lower(),
                number=number,
                raw=match.group(0),
                start=match.start(),
                end=match.end(),
                region=region,
                page_hint=int(page) if page is not None else None,
            )
        )
    return tuple(found)


_UNSUPPORTED_EXHIBIT = re.compile(
    r"(?<![\w])(?P<label>(?i:exhibits?))\s+(?P<number>[A-Z](?:[-.]?\d{1,4})?|\d{1,4})(?![\w])",
)


def detect_unsupported_references(text: str, *, region: str) -> tuple[ExhibitReference, ...]:
    """Surface explicit English labels without granting Belgian inventory identity."""
    if not region.strip():
        raise ValueError("region must identify the source representation")
    return tuple(ExhibitReference(label='exhibit', number=match['number'].upper(),
                                 raw=match.group(0), start=match.start(), end=match.end(), region=region)
                 for match in _UNSUPPORTED_EXHIBIT.finditer(text))
