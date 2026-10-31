"""Trusted host-side content release adapter for an approved consent service.

This is a dependency adapter, NOT a consent database, OAuth grant endpoint or
model tool. An authorized host must provide a decision callable that *reads*
current actor/client/matter/snapshot/destination grants on each invocation.
The callback cannot receive raw bearer secrets; failure always denies release.
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from application.litigation.content_release import ContentRelease

# Each decision is a fresh host-side permission check. There is no process-wide
# allow switch; the caller identity and OAuth client are both inputs.
ConsentDecision = Callable[[str, str, str, str, str, str], bool]


@dataclass(frozen=True, slots=True)
class CallbackHostContentGate:
    decision: ConsentDecision
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def resolve(self, *, subject: str, client_id: str, bearer: str, destination: str,
                case_id: str, brief_id: str, snapshot_hash: str) -> ContentRelease | None:
        if not all(type(v) is str and v for v in
                   (subject, client_id, bearer, destination, case_id, brief_id, snapshot_hash)):
            return None
        try:
            now = self.clock()
            if (now.tzinfo is None or now.utcoffset() is None or
                    self.decision(subject, client_id, destination, case_id, brief_id, snapshot_hash) is not True):
                return None
            return ContentRelease(
                case_id=case_id, brief_id=brief_id, snapshot_hash=snapshot_hash,
                destination=destination,
                caller_digest=hashlib.sha256(bearer.encode()).hexdigest(),
                expires_at=now + timedelta(seconds=60))
        except Exception:
            # No accidental disclosure on host consent backend outage or bug.
            return None
