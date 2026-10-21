"""Ports for a future durable Evidence Kernel adapter.

The kernel defines its own interfaces and does not import SQL, HTTP, or Supabase.
"""
from typing import Protocol

from packages.evidence_kernel.domain.evidence import ExtractedClaim, ReviewDecision
from packages.evidence_kernel.domain.workflow import (
    CorroborationAssessment,
    DocumentVersion,
    SourceCheck,
)


class EvidenceRepository(Protocol):
    def register_source(self, scope: str, source: DocumentVersion) -> DocumentVersion: ...

    def add_claim(self, scope: str, claim: ExtractedClaim, version_id: str) -> ExtractedClaim: ...

    def get_claim(self, scope: str, claim_id: str) -> ExtractedClaim: ...

    def verify_quote(self, scope: str, claim_id: str) -> SourceCheck: ...

    def assess(self, scope: str, assessment: CorroborationAssessment) -> CorroborationAssessment: ...

    def review(self, scope: str, decision: ReviewDecision) -> ReviewDecision: ...
