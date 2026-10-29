"""Deterministic exhibit identity policy; never infer source or page correctness."""

from dataclasses import dataclass
from enum import StrEnum


class IdentityState(StrEnum):
    NOT_ASSESSED = "NOT_ASSESSED"
    NOT_IN_INVENTORY = "NOT_IN_INVENTORY"
    SOURCE_MISSING = "SOURCE_MISSING"
    AMBIGUOUS = "AMBIGUOUS"
    RESOLVED = "RESOLVED"


class InventoryStatus(StrEnum):
    MISSING = "INVENTORY_MISSING"
    UNPARSEABLE = "INVENTORY_UNPARSEABLE"
    UNCONFIRMED = "INVENTORY_UNCONFIRMED"
    INCOMPLETE = "INVENTORY_INCOMPLETE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    CONFIRMED_COMPLETE = "CONFIRMED_COMPLETE"


@dataclass(frozen=True)
class IdentityDecision:
    state: IdentityState
    reason: InventoryStatus | None = None
    exhibit_id: str | None = None


def resolve_exhibit_identity(
    *,
    inventory_status: InventoryStatus,
    matching_exhibit_ids: tuple[str, ...],
    authorized_source_ids: frozenset[str],
) -> IdentityDecision:
    """Resolve only against a confirmed complete inventory.

    The caller must supply deterministic exact/approved-alias matches, not fuzzy
    candidate matches. Page mapping and legal communication remain separate.
    """
    if inventory_status is not InventoryStatus.CONFIRMED_COMPLETE:
        return IdentityDecision(IdentityState.NOT_ASSESSED, reason=inventory_status)

    matches = tuple(dict.fromkeys(matching_exhibit_ids))
    if not matches:
        return IdentityDecision(IdentityState.NOT_IN_INVENTORY)
    if len(matches) > 1:
        return IdentityDecision(IdentityState.AMBIGUOUS)
    exhibit_id = matches[0]
    if not exhibit_id.strip():
        raise ValueError("exhibit_id must not be blank")
    if exhibit_id not in authorized_source_ids:
        return IdentityDecision(IdentityState.SOURCE_MISSING, exhibit_id=exhibit_id)
    return IdentityDecision(IdentityState.RESOLVED, exhibit_id=exhibit_id)
