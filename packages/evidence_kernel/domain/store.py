"""Sector-neutral in-memory evidence repository; replace via adapter in production."""
from dataclasses import dataclass, field
from threading import RLock
from packages.evidence_kernel.domain.evidence import ExtractedClaim


class DuplicateClaimError(ValueError):
    pass


class MissingClaimError(KeyError):
    pass


@dataclass
class InMemoryEvidenceStore:
    _claims: dict[tuple[str, str], ExtractedClaim] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    def add(self, tenant_id: str, claim: ExtractedClaim) -> ExtractedClaim:
        if not tenant_id.strip():
            raise ValueError("tenant_id is required")
        key = (tenant_id, claim.claim_id)
        with self._lock:
            if key in self._claims:
                raise DuplicateClaimError("claim ID already exists")
            self._claims[key] = claim
        return claim

    def get(self, tenant_id: str, claim_id: str) -> ExtractedClaim:
        with self._lock:
            try:
                return self._claims[(tenant_id, claim_id)]
            except KeyError as exc:
                raise MissingClaimError(claim_id) from exc
