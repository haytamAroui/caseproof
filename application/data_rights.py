"""Pure rights evaluator; shadow observations never authorize access."""
from dataclasses import dataclass
from enum import StrEnum

class Decision(StrEnum):
    ALLOW = 'allow'
    DENY = 'deny'
    UNKNOWN = 'unknown'

@dataclass(frozen=True)
class RightsPolicy:
    version: int
    authorization_reference: str | None
    permissions: dict[str, bool]


def evaluate(policy: RightsPolicy | None, action: str, *, same_matter: bool) -> Decision:
    if policy is None:
        return Decision.UNKNOWN
    if policy.version < 1 or (action == 'export' and not same_matter):
        return Decision.DENY
    if action == 'process' and not policy.authorization_reference:
        return Decision.DENY
    return Decision.ALLOW if policy.permissions.get(action) is True else Decision.DENY
