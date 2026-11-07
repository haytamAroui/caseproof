"""PR 2: explicit, fail-closed signed rights gate for protected operations.

A policy is never authorization by itself: callers MUST first resolve the exact
matter/source through the existing signed server authority. No bearer, matter,
policy authorization reference, or source bytes are logged.
"""
from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from application.data_rights import Action, Decision, Evaluation, RightsPolicy, evaluate_detail
from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.data_rights_signed import ShadowLookupUnavailable

LOGGER = logging.getLogger("caseproof.rights.enforcement")
MAX_BUNDLE_SOURCES = 32


class RightsPolicyReader(Protocol):
    def read(
        self, *, bearer: str, case_id: str, document_id: str, version_id: str,
    ) -> RightsPolicy | None: ...


@dataclass(frozen=True, slots=True)
class SignedRightsGate:
    reader: RightsPolicyReader

    def require(
        self, *, bearer: str, case_id: str, document_id: str,
        version_id: str, action: Action, same_matter: bool = True,
    ) -> Evaluation:
        """Require an explicit ALLOW; UNKNOWN, DENY and lookup errors never authorize."""
        if not isinstance(action, Action) or type(same_matter) is not bool:
            raise ValueError("A typed action and explicit scope are mandatory")
        try:
            policy = self.reader.read(
                bearer=bearer, case_id=case_id,
                document_id=document_id, version_id=version_id,
            )
            result = evaluate_detail(policy, action.value, same_matter=same_matter)
        except ShadowLookupUnavailable:
            LOGGER.warning("rights_enforce action=%s decision=unavailable", action.value)
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        except Exception:
            # An adapter bug must never silently allow processing or release.
            LOGGER.warning("rights_enforce action=%s decision=unavailable", action.value)
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        LOGGER.info(
            "rights_enforce action=%s decision=%s reason=%s policy_version=%s",
            action.value, result.decision.value, result.reason, result.policy_version,
        )
        if result.decision != Decision.ALLOW:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        return result

    def require_bundle(
        self, *, bearer: str, case_id: str,
        sources: Sequence[Mapping[str, object]], action: Action,
        same_matter: bool = True,
    ) -> tuple[Evaluation, ...]:
        """The caller supplies SERVER-RESOLVED source identities, never client metadata."""
        if not sources or len(sources) > MAX_BUNDLE_SOURCES:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        found: set[str] = set()
        results: list[Evaluation] = []
        for row in sources:
            if not isinstance(row, Mapping):
                raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
            document_id, version_id = row.get("document_id"), row.get("version_id")
            if (
                not isinstance(document_id, str)
                or not isinstance(version_id, str)
                or not document_id or not version_id
                or version_id in found
            ):
                raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
            found.add(version_id)
            results.append(self.require(
                bearer=bearer, case_id=case_id, document_id=document_id,
                version_id=version_id, action=action, same_matter=same_matter,
            ))
        return tuple(results)
