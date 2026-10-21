"""Development-only FastAPI adapter for evidence-kernel primitives."""
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from packages.evidence_kernel.domain.evidence import (
    CorroborationStatus,
    ExtractedClaim,
    SourceReference,
    SourceStatus,
)
from packages.evidence_kernel.domain.store import (
    DuplicateClaimError,
    InMemoryEvidenceStore,
    MissingClaimError,
)


class SourceInput(BaseModel):
    document_id: str
    document_sha256: str
    quote: str
    page: int | None = None


class ClaimInput(BaseModel):
    claim_id: str
    statement: str
    source: SourceInput


class ClaimOutput(BaseModel):
    claim_id: str
    statement: str
    source: SourceInput
    source_status: SourceStatus
    corroboration: CorroborationStatus


def serialize(claim: ExtractedClaim) -> ClaimOutput:
    return ClaimOutput(
        claim_id=claim.claim_id,
        statement=claim.statement,
        source=SourceInput(
            document_id=claim.source.document_id,
            document_sha256=claim.source.document_sha256,
            quote=claim.source.quote,
            page=claim.source.page,
        ),
        source_status=claim.source_status,
        corroboration=claim.corroboration,
    )


def create_app(store: InMemoryEvidenceStore | None = None) -> FastAPI:
    app = FastAPI(title="Evidence Kernel API", version="0.1.0")
    app.state.evidence_store = store if store is not None else InMemoryEvidenceStore()

    def tenant_id(x_tenant_id: str | None = Header(default=None)) -> str:
        # DEVELOPMENT ONLY: header is caller-controlled, NOT verified tenancy.
        if not x_tenant_id or not x_tenant_id.strip():
            raise HTTPException(status_code=401, detail="Missing tenant context")
        return x_tenant_id

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/claims", response_model=ClaimOutput, status_code=201)
    def create_claim(payload: ClaimInput, tenant: str = Depends(tenant_id)) -> ClaimOutput:
        try:
            source = SourceReference(**payload.source.model_dump())
            claim = ExtractedClaim(claim_id=payload.claim_id, statement=payload.statement, source=source)
            return serialize(app.state.evidence_store.add(tenant, claim))
        except DuplicateClaimError:
            raise HTTPException(status_code=409, detail="Claim ID already exists") from None
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/v1/claims/{claim_id}", response_model=ClaimOutput)
    def get_claim(claim_id: str, tenant: str = Depends(tenant_id)) -> ClaimOutput:
        try:
            return serialize(app.state.evidence_store.get(tenant, claim_id))
        except MissingClaimError:
            raise HTTPException(status_code=404, detail="Claim not found") from None

    return app


app = create_app()
