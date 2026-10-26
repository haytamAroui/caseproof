"""Opt-in M1 authenticated JSON evidence read API; no public upload/write surface.

Not mounted by legacy main.py. Production composition requires actual signed
Supabase verifier, restricted case grants, verified private Vault and security
approval. An unconfigured service fails closed.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Protocol

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from application.extraction.contracts import ExtractionError
from application.litigation.library import EvidenceInventory, EvidencePreview
from apps.api.access_control import AccessRejected
from apps.api.evidence_vault_protocol import VaultError


class EvidenceReader(Protocol):
    def inventory(self, *, bearer: str, case_id: str) -> EvidenceInventory: ...
    def preview(self, *, bearer: str, case_id: str, source_id: str) -> EvidencePreview: ...


def create_evidence_app(service: EvidenceReader | None = None) -> FastAPI:
    app = FastAPI(
        title="CaseProof authenticated evidence library",
        docs_url=None, redoc_url=None, openapi_url=None,
    )

    @app.middleware("http")
    async def secure_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response

    @app.exception_handler(AccessRejected)
    async def denied(request: Request, exc: AccessRejected) -> JSONResponse:
        return JSONResponse({"error": exc.code.value}, status_code=exc.http_status)

    @app.exception_handler(ExtractionError)
    @app.exception_handler(VaultError)
    async def unavailable(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse({"error": "evidence_unavailable"}, status_code=503)

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse({"error": "invalid_request"}, status_code=422)

    @app.get("/v2/matters/{case_id}/evidence")
    def inventory(case_id: str, authorization: str | None = Header(default=None)) -> dict:
        if service is None:
            return {"status": "unavailable", "enabled": False}
        token = _token(authorization)
        result = service.inventory(bearer=token, case_id=case_id)
        return {"schema": "caseproof-evidence-library-v1", **asdict(result)}

    @app.get("/v2/matters/{case_id}/evidence/{source_id}")
    def preview(
        case_id: str, source_id: str, authorization: str | None = Header(default=None)
    ) -> dict:
        if service is None:
            return {"status": "unavailable", "enabled": False}
        token = _token(authorization)
        result = service.preview(bearer=token, case_id=case_id, source_id=source_id)
        return {"schema": "caseproof-evidence-preview-v1", **asdict(result)}

    return app


def _token(authorization: str | None) -> str:
    if (
        type(authorization) is not str
        or not authorization.startswith("Bearer ")
        or authorization.count(" ") != 1
        or len(authorization) > 8300
        or not authorization[7:].strip()
    ):
        from apps.api.access_control import AccessFailure

        raise AccessRejected(AccessFailure.AUTHENTICATION_REQUIRED)
    return authorization[7:]
