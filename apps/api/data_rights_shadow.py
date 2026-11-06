"""Observation-only rights decision telemetry.

No policy is assumed for legacy documents. Never log bearer tokens, source
contents, firm authorization references, or personal identifiers.
"""
from __future__ import annotations

import logging
from collections.abc import Callable

from application.data_rights import RightsPolicy, evaluate_detail

LOGGER = logging.getLogger("caseproof.rights.shadow")


def observe_authorized_read(
    *, policy_lookup: Callable[[], RightsPolicy | None], action: str = "process",
    same_matter: bool = True,
) -> None:
    """Call after existing authorization; never let shadow failures change a response."""
    try:
        decision = evaluate_detail(policy_lookup(), action, same_matter=same_matter)
        LOGGER.info(
            "rights_shadow action=%s decision=%s reason=%s policy_version=%s",
            action, decision.decision.value, decision.reason, decision.policy_version,
        )
    except Exception:
        LOGGER.warning("rights_shadow evaluation_unavailable", exc_info=False)
