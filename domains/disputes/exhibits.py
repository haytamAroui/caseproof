"""PIV-06 pure exhibit identities and confirmed, versioned label mapping.

A display label (Stuk/Pièce/annex) is NOT a source identity, submission receipt,
communication proof or evidence of authenticity. No persistence/authorization here.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ExhibitError(ValueError):
    """Invalid or stale proposed exhibit register."""


def _name(value: object, field: str) -> str:
    if type(value) is not str or not value.strip() or len(value) > 160:
        raise ExhibitError(f"bounded {field} required")
    return value.strip()


def _page(value: object, field: str) -> None:
    if value is not None and (type(value) is not int or not 1 <= value <= 100_000):
        raise ExhibitError(f"invalid {field}")


@dataclass(frozen=True, slots=True)
class ExhibitPage:
    """Independent numbering spaces; none means NOT MAPPED, not page 1."""

    source_id: str
    version_id: str
    pdf_page: int | None = None
    printed_page: int | None = None
    bundle_page: int | None = None

    def __post_init__(self) -> None:
        _name(self.source_id, "source_id")
        _name(self.version_id, "version_id")
        for key in ("pdf_page", "printed_page", "bundle_page"):
            _page(getattr(self, key), key)
        if all(getattr(self, key) is None for key in ("pdf_page", "printed_page", "bundle_page")):
            raise ExhibitError("explicit page mapping required")


@dataclass(frozen=True, slots=True)
class ExhibitEntry:
    exhibit_id: str
    display_label: str
    pages: tuple[ExhibitPage, ...]
    aliases: tuple[str, ...] = ()
    confirmed: bool = False
    manual_inclusion: bool = False

    def __post_init__(self) -> None:
        _name(self.exhibit_id, "exhibit_id")
        _name(self.display_label, "display_label")
        if type(self.pages) is not tuple or not self.pages or len(self.pages) > 512:
            raise ExhibitError("bounded exhibit page inventory required")
        if not all(isinstance(page, ExhibitPage) for page in self.pages):
            raise ExhibitError("typed exhibit pages required")
        if type(self.aliases) is not tuple or len(self.aliases) > 64:
            raise ExhibitError("bounded aliases required")
        labels = [self.display_label.casefold().strip()]
        labels.extend(_name(alias, "alias").casefold() for alias in self.aliases)
        if len(labels) != len(set(labels)):
            raise ExhibitError("repeated alias within exhibit")
        if type(self.confirmed) is not bool or type(self.manual_inclusion) is not bool:
            raise ExhibitError("explicit confirmed/manual flags required")
        rows = [(p.source_id, p.version_id, p.pdf_page, p.printed_page, p.bundle_page) for p in self.pages]
        if len(rows) != len(set(rows)):
            raise ExhibitError("duplicate exhibit page mapping")


class MappingState(StrEnum):
    CONFIRMED = "confirmed"
    SUGGESTED = "suggested"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"
    PAGE_UNMAPPED = "page_unmapped"


@dataclass(frozen=True, slots=True)
class ExhibitResolution:
    state: MappingState
    exhibit_id: str | None = None
    page: ExhibitPage | None = None
    # Identity can be confirmed while the requested pinpoint remains unmapped.
    identity_confirmed: bool = False


@dataclass(frozen=True, slots=True)
class ExhibitRegister:
    revision: int
    entries: tuple[ExhibitEntry, ...]

    def __post_init__(self) -> None:
        if type(self.revision) is not int or self.revision < 1:
            raise ExhibitError("positive register revision required")
        if type(self.entries) is not tuple or len(self.entries) > 512:
            raise ExhibitError("bounded immutable exhibit register required")
        if not all(isinstance(entry, ExhibitEntry) for entry in self.entries):
            raise ExhibitError("typed register entries required")
        ids = [entry.exhibit_id for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ExhibitError("duplicate stable exhibit identity")

    def resolve(self, label: str, *, pdf_page: int | None = None) -> ExhibitResolution:
        key = _name(label, "exhibit reference").casefold()
        _page(pdf_page, "PDF page")
        matches = [
            entry for entry in self.entries
            if key in (entry.display_label.strip().casefold(), *(alias.strip().casefold() for alias in entry.aliases))
        ]
        if not matches:
            return ExhibitResolution(MappingState.UNRESOLVED)
        if len(matches) != 1:
            return ExhibitResolution(MappingState.AMBIGUOUS)
        entry = matches[0]
        if not entry.confirmed:
            return ExhibitResolution(MappingState.SUGGESTED, entry.exhibit_id)
        pages = [p for p in entry.pages if pdf_page is None or p.pdf_page == pdf_page]
        if len(pages) != 1:
            return ExhibitResolution(
                MappingState.PAGE_UNMAPPED if not pages else MappingState.AMBIGUOUS,
                entry.exhibit_id,
                identity_confirmed=True,
            )
        return ExhibitResolution(MappingState.CONFIRMED, entry.exhibit_id, pages[0], True)

    def revise(self, *, expected_revision: int, entries: tuple[ExhibitEntry, ...]) -> ExhibitRegister:
        """Pure CAS proposal; actual auth, transaction and audit belong to application."""
        if type(expected_revision) is not int or expected_revision != self.revision:
            raise ExhibitError("stale exhibit register revision")
        return ExhibitRegister(self.revision + 1, entries)
