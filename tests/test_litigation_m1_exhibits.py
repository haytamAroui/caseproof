"""PIV-06 pure exhibit resolution and revision tests (not authorized writes)."""
from dataclasses import replace

import pytest

from domains.disputes.exhibits import (
    ExhibitEntry,
    ExhibitError,
    ExhibitPage,
    ExhibitRegister,
    MappingState,
)


def entry(label="Stuk 1", *, confirmed=True, aliases=(), pages=None):
    return ExhibitEntry(
        "stable-exhibit-a", label,
        pages or (ExhibitPage("source-a", "v1", 2, 9, 18),),
        aliases=aliases, confirmed=confirmed,
    )


def test_confirmed_alias_maps_exact_version_and_independent_page_spaces():
    register = ExhibitRegister(1, (entry(aliases=("Pièce 1",)),))
    resolved = register.resolve("Pièce 1", pdf_page=2)
    assert resolved.state == MappingState.CONFIRMED
    assert resolved.page == ExhibitPage("source-a", "v1", 2, 9, 18)
    assert register.resolve("Stuk 1", pdf_page=9).state == MappingState.PAGE_UNMAPPED


def test_repeated_labels_across_exhibits_must_never_first_match():
    first = entry(confirmed=True)
    second = ExhibitEntry(
        "stable-exhibit-b", "Pièce 4",
        (ExhibitPage("source-b", "v2", 1),),
        aliases=("Stuk 1",), confirmed=True,
    )
    register = ExhibitRegister(1, (first, second))
    assert register.resolve("Stuk 1").state == MappingState.AMBIGUOUS
    assert register.resolve("Pièce 4", pdf_page=1).exhibit_id == "stable-exhibit-b"


def test_proposed_mapping_is_not_confirmation():
    register = ExhibitRegister(1, (entry(confirmed=False),))
    assert register.resolve("Stuk 1").state == MappingState.SUGGESTED
    assert register.resolve("Stuk 999").state == MappingState.UNRESOLVED


def test_multi_file_exhibit_with_no_page_selector_is_ambiguous():
    one = entry(pages=(
        ExhibitPage("source-a", "v1", 1, 1, 10),
        ExhibitPage("source-b", "v2", 2, 4, 20),
    ))
    register = ExhibitRegister(1, (one,))
    assert register.resolve("Stuk 1").state == MappingState.AMBIGUOUS
    assert register.resolve("Stuk 1", pdf_page=2).page.source_id == "source-b"


def test_revision_is_pure_cas_and_original_remains_frozen():
    old = ExhibitRegister(2, (entry(),))
    changed = old.revise(expected_revision=2, entries=(replace(entry(), display_label="Pièce 1"),))
    assert old.revision == 2 and old.entries[0].display_label == "Stuk 1"
    assert changed.revision == 3 and changed.entries[0].display_label == "Pièce 1"
    with pytest.raises(ExhibitError, match="stale"):
        changed.revise(expected_revision=2, entries=())


@pytest.mark.parametrize("bad", [0, -2, True, 1.25, "2"])
def test_invalid_page_rejected(bad):
    with pytest.raises(ExhibitError, match="page"):
        ExhibitPage("source-a", "v1", pdf_page=bad)


def test_invalid_alias_and_identity_rejected():
    with pytest.raises(ExhibitError, match="repeated alias"):
        entry(aliases=("stuk 1",))
    with pytest.raises(ExhibitError, match="duplicate stable"):
        ExhibitRegister(1, (entry(), entry()))


def test_manual_uncited_entry_is_preserved_when_another_entry_changes():
    manual = ExhibitEntry(
        "uncited", "Annexe A", (ExhibitPage("manual-source", "v1", 1),),
        manual_inclusion=True, confirmed=True,
    )
    old = ExhibitRegister(1, (entry(), manual))
    changed = old.revise(expected_revision=1, entries=(replace(entry(), display_label="Stuk 2"), manual))
    assert old.entries[1] == changed.entries[1] == manual


def test_label_whitespace_does_not_create_false_unresolved_reference():
    exhibit = entry(label="  Stuk 1  ", aliases=(" Pièce 1 ",))
    register = ExhibitRegister(1, (exhibit,))
    assert register.resolve("Stuk 1").state == MappingState.CONFIRMED
    assert register.resolve("Pièce 1").state == MappingState.CONFIRMED
