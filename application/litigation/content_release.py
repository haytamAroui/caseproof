"""Host-only, short-lived release binding. This value is never a model argument.

Only a trusted composition may issue it after its destination/consent policy passes.
It is not a portable credential, OAuth token, or replacement for current matter access.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class ContentRelease:
    case_id: str
    brief_id: str
    snapshot_hash: str
    destination: str
    caller_digest: str
    expires_at: datetime

    def permits(self, *, bearer: str, case_id: str, brief_id: str, snapshot_hash: str,
                destination: str | None, now: datetime) -> bool:
        return bool(
            self.case_id == case_id and self.brief_id == brief_id
            and re.fullmatch(r"[0-9a-f]{64}", self.snapshot_hash)
            and self.snapshot_hash == snapshot_hash
            and isinstance(destination, str) and 1 <= len(destination) <= 128
            and self.destination == destination
            and self.expires_at.tzinfo is not None and now.tzinfo is not None
            and 0 < (self.expires_at - now).total_seconds() <= 300
            and hmac.compare_digest(self.caller_digest, hashlib.sha256(bearer.encode()).hexdigest())
        )


def utc_now() -> datetime:
    return datetime.now(UTC)
