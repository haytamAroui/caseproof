"""Unreleased FastAPI v2 M2 check facade; injected signed-session service only.

NOT mounted in apps/api/main.py. Do not advertise this as production.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Protocol

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.litigation_check_service import AuthorizedLitigationChecker
from application.litigation.unified_review import VerificationRun


class AuthorizedCheckPort(Protocol):
    def check(self, *, bearer: str, case_id: str, brief_version_id: str) -> VerificationRun: ...


def create_litigation_check_app(
    service: AuthorizedCheckPort | AuthorizedLitigationChecker | None = None,
) -> FastAPI:
    app = FastAPI(
        title="CaseProof protected litigation checks",
        openapi_url=None, docs_url=None, redoc_url=None,
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response

    @app.exception_handler(AccessRejected)
    async def forbidden(request: Request, exc: AccessRejected) -> JSONResponse:
        return JSONResponse({"error": exc.code.value}, status_code=exc.http_status)

    @app.post("/v2/matters/{case_id}/briefs/{brief_version_id}/check")
    def check(
        case_id: str, brief_version_id: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        # Missing composition is never an anonymous or org-wide fallback.
        if service is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        if (not isinstance(authorization, str) or not authorization.startswith("Bearer ")
                or len(authorization) > 8300 or authorization.count(" ") != 1
                or not authorization[7:].strip()):
            raise AccessRejected(AccessFailure.AUTHENTICATION_REQUIRED)
        result = service.check(
            bearer=authorization[7:], case_id=case_id, brief_version_id=brief_version_id,
        )
        # Observation snapshots only; no raw original bytes, no approval/filing endpoint.
        return {"schema": "caseproof-m2-check-headless-v1", **asdict(result)}

    return app
