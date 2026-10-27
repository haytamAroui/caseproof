"""Opt-in, unmounted private lexical evidence search HTTP adapter."""
from __future__ import annotations

from dataclasses import asdict
from typing import Protocol

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from apps.api.access_control import AccessRejected
from apps.api.litigation_evidence_app import _token
from apps.api.litigation_evidence_search import SearchResult


class SearchPort(Protocol):
    def search(self, *, bearer: str, case_id: str, brief_version_id: str, query: str) -> SearchResult: ...


class SearchBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str = Field(min_length=2, max_length=120)


def create_litigation_search_app(service: SearchPort | None = None) -> FastAPI:
    app = FastAPI(title="CaseProof private evidence search", docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(AccessRejected)
    async def denied(request: Request, exc: AccessRejected) -> JSONResponse:
        return JSONResponse({"error": exc.code.value}, status_code=exc.http_status)

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Do not echo query text or attacker-provided fields in errors.
        return JSONResponse({"error": "invalid_request"}, status_code=422)

    @app.post("/v2/matters/{case_id}/briefs/{brief_version_id}/evidence/search")
    def search(case_id: str, brief_version_id: str, body: SearchBody,
               authorization: str | None = Header(default=None)) -> dict:  # type: ignore[type-arg]
        if service is None:
            from apps.api.access_control import AccessFailure
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            result = service.search(bearer=_token(authorization), case_id=case_id,
                                    brief_version_id=brief_version_id, query=body.query)
        except ValueError:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail="Invalid search query") from None
        return {"schema": "caseproof-evidence-search-v1", **asdict(result)}

    return app
