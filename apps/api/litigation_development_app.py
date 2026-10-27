"""Loopback-only synthetic/staging composition; never mounted in the main API.

Dependencies are injected. This factory does not construct a database role,
accept credentials from requests, install schemas or authorize live deployment.
"""
from __future__ import annotations

from ipaddress import ip_address

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.litigation_check_app import create_litigation_check_app
from apps.api.litigation_check_service import AuthorizedLitigationChecker
from apps.api.litigation_evidence_app import _token
from apps.api.litigation_evidence_search import AuthorizedEvidenceSearch
from apps.api.litigation_original_reader import AuthorizedOriginalReader
from apps.api.litigation_search_app import create_litigation_search_app


def create_litigation_development_app(
    *, checker: AuthorizedLitigationChecker | None = None,
    originals: AuthorizedOriginalReader | None = None,
) -> FastAPI:
    app = FastAPI(title="CaseProof loopback development", docs_url=None, redoc_url=None, openapi_url=None)
    # One shared checker ensures search and check use the same trust boundary.
    app.include_router(create_litigation_check_app(checker).router)
    app.include_router(create_litigation_search_app(AuthorizedEvidenceSearch(checker) if checker else None).router)

    @app.middleware("http")
    async def local_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        try:
            local = request.client is not None and ip_address(request.client.host).is_loopback
        except ValueError:
            local = False
        if not local:
            return JSONResponse({"error": "loopback_only"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response

    @app.exception_handler(AccessRejected)
    async def denied(request: Request, exc: AccessRejected) -> JSONResponse:
        return JSONResponse({"error": exc.code.value}, status_code=exc.http_status)

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse({"error": "invalid_request"}, status_code=422)

    @app.get("/v2/matters/{case_id}/briefs/{brief_version_id}/evidence/{source_id}/versions/{version_id}/original")
    def original(case_id: str, brief_version_id: str, source_id: str, version_id: str,
                 authorization: str | None = Header(default=None)) -> Response:
        if originals is None or checker is None or originals.checker is not checker:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        item = originals.read(bearer=_token(authorization), case_id=case_id,
                              brief_version_id=brief_version_id, source_id=source_id, version_id=version_id)
        # Original bytes are never interpreted as active HTML or shown inline.
        return Response(item.data, media_type="application/octet-stream", headers={
            "Content-Disposition": "attachment; filename=caseproof-original",
            "X-CaseProof-Original-SHA256": item.sha256_hex,
            "X-CaseProof-Original-Media-Type": item.media_type,
        })

    return app
