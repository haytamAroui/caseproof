"""Reference-only FastAPI adapter; refuses requests without trusted scope injection."""
from collections.abc import Callable
from dataclasses import asdict

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from packages.evidence_kernel.domain.evidence import (
    CorroborationStatus,
    ExtractedClaim,
    ReviewDecision,
    ReviewStatus,
    SourceReference,
)
from packages.evidence_kernel.domain.workflow import (
    ClaimNotFound,
    CorroborationAssessment,
    DocumentVersion,
    EvidenceConflict,
    EvidenceWorkflow,
    EvidenceWorkflowError,
    SourceNotFound,
)


class SourceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)
    sha256_hex: str = Field(pattern=r"^[0-9a-f]{64}$")
    text: str


class ClaimInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)
    document_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    quote: str = Field(min_length=1)
    page: int | None = Field(default=None, ge=1)


class AssessmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: CorroborationStatus
    rationale: str = Field(min_length=1)


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reviewer_id: str = Field(min_length=1)
    disposition: ReviewStatus
    rationale: str = Field(min_length=1)


def create_kernel_app(
    workflow: EvidenceWorkflow | None = None,
    trusted_scope: Callable[[], str] | None = None,
) -> FastAPI:
    """No caller-supplied header or JWT is trusted by this demo adapter."""
    app = FastAPI(title="Evidence Kernel Reference API", version="0.2.0")
    service = workflow if workflow is not None else EvidenceWorkflow()

    def resolve_scope() -> str:
        if trusted_scope is None:
            raise HTTPException(status_code=503, detail="trusted scope resolver not configured")
        scope = trusted_scope()
        if not isinstance(scope, str) or not scope.strip():
            raise HTTPException(status_code=403, detail="invalid trusted scope")
        return scope

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/sources", status_code=201)
    def register(payload: SourceInput, scope: str = Depends(resolve_scope)) -> dict:
        try:
            return asdict(service.register_source(scope, DocumentVersion(**payload.model_dump())))
        except EvidenceConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except EvidenceWorkflowError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/v1/evidence-claims", status_code=201)
    def add_claim(payload: ClaimInput, scope: str = Depends(resolve_scope)) -> dict:
        try:
            source = SourceReference(payload.document_id, payload.document_sha256, payload.quote, payload.page)
            claim = ExtractedClaim(payload.claim_id, payload.statement, source)
            service.add_claim(scope, claim, payload.version_id)
            return asdict(claim)
        except EvidenceConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except SourceNotFound as exc:
            raise HTTPException(404, str(exc)) from exc
        except (ValueError, EvidenceWorkflowError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/v1/evidence-claims/{claim_id}")
    def get_claim(claim_id: str, scope: str = Depends(resolve_scope)) -> dict:
        try:
            return asdict(service.get_claim(scope, claim_id))
        except ClaimNotFound as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/v1/evidence-claims/{claim_id}/verify")
    def verify(claim_id: str, scope: str = Depends(resolve_scope)) -> dict:
        try:
            return asdict(service.verify_quote(scope, claim_id))
        except ClaimNotFound as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/v1/evidence-claims/{claim_id}/assess")
    def assess(claim_id: str, payload: AssessmentInput, scope: str = Depends(resolve_scope)) -> dict:
        try:
            return asdict(service.assess(scope, CorroborationAssessment(claim_id, payload.status, payload.rationale)))
        except ClaimNotFound as exc:
            raise HTTPException(404, str(exc)) from exc
        except EvidenceWorkflowError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/v1/evidence-claims/{claim_id}/review")
    def review(claim_id: str, payload: ReviewInput, scope: str = Depends(resolve_scope)) -> dict:
        try:
            decision = ReviewDecision(claim_id, payload.reviewer_id, payload.disposition, payload.rationale)
            return asdict(service.review(scope, decision))
        except ClaimNotFound as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    return app


app = create_kernel_app()
