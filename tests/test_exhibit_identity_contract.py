"""P3-04 contract regression tests: inventory absence is never negative evidence."""

import pytest

from domains.disputes.exhibit_identity import (
    IdentityState,
    InventoryStatus,
    resolve_exhibit_identity,
)


@pytest.mark.parametrize(
    "status",
    [
        InventoryStatus.MISSING,
        InventoryStatus.UNPARSEABLE,
        InventoryStatus.UNCONFIRMED,
        InventoryStatus.INCOMPLETE,
        InventoryStatus.OUT_OF_SCOPE,
    ],
)
def test_unusable_inventory_abstains(status: InventoryStatus) -> None:
    decision = resolve_exhibit_identity(
        inventory_status=status,
        matching_exhibit_ids=(),
        authorized_source_ids=frozenset(),
    )
    assert decision.state is IdentityState.NOT_ASSESSED
    assert decision.reason is status


def test_confirmed_complete_inventory_can_prove_listing_absence() -> None:
    decision = resolve_exhibit_identity(
        inventory_status=InventoryStatus.CONFIRMED_COMPLETE,
        matching_exhibit_ids=(),
        authorized_source_ids=frozenset(),
    )
    assert decision.state is IdentityState.NOT_IN_INVENTORY


def test_listed_but_source_missing_is_not_absent_inventory() -> None:
    decision = resolve_exhibit_identity(
        inventory_status=InventoryStatus.CONFIRMED_COMPLETE,
        matching_exhibit_ids=("stuk-4",),
        authorized_source_ids=frozenset(),
    )
    assert decision.state is IdentityState.SOURCE_MISSING
    assert decision.exhibit_id == "stuk-4"


def test_unique_identity_resolves_without_claiming_page() -> None:
    decision = resolve_exhibit_identity(
        inventory_status=InventoryStatus.CONFIRMED_COMPLETE,
        matching_exhibit_ids=("stuk-4", "stuk-4"),
        authorized_source_ids=frozenset({"stuk-4"}),
    )
    assert decision.state is IdentityState.RESOLVED
    assert decision.exhibit_id == "stuk-4"


def test_distinct_candidates_are_ambiguous() -> None:
    decision = resolve_exhibit_identity(
        inventory_status=InventoryStatus.CONFIRMED_COMPLETE,
        matching_exhibit_ids=("stuk-4a", "stuk-4b"),
        authorized_source_ids=frozenset({"stuk-4a", "stuk-4b"}),
    )
    assert decision.state is IdentityState.AMBIGUOUS


def test_blank_exhibit_id_rejected() -> None:
    with pytest.raises(ValueError):
        resolve_exhibit_identity(
            inventory_status=InventoryStatus.CONFIRMED_COMPLETE,
            matching_exhibit_ids=(" ",),
            authorized_source_ids=frozenset({" "}),
        )
