"""Loopback-only synthetic/staging composition; never mounted in the main API.

Dependencies are injected. This factory does not construct a database role,
accept credentials from requests, install schemas or authorize live deployment.
"""
from __future__ import annotations

from ipaddress import ip_address
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response

from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.litigation_check_app import create_litigation_check_app
from apps.api.litigation_check_service import AuthorizedLitigationChecker
from apps.api.litigation_evidence_app import EvidenceReader, _token, create_evidence_app
from apps.api.litigation_evidence_search import AuthorizedEvidenceSearch
from apps.api.litigation_original_reader import AuthorizedOriginalReader
from apps.api.litigation_review_app import create_clearbrief_review_router
from apps.api.litigation_review_workspace import SignedReviewWorkspace
from apps.api.litigation_search_app import create_litigation_search_app
from apps.api.signed_supabase_originals import MAX_BYTES, PrivateStorageDenied, PrivateStorageFailure
from apps.api.signed_supabase_source_library import SignedSourceLibrary


def create_litigation_development_app(
    *, checker: AuthorizedLitigationChecker | None = None,
    originals: AuthorizedOriginalReader | None = None,
    signed_originals: SignedSourceLibrary | None = None,
    evidence: EvidenceReader | None = None,
    reviews: SignedReviewWorkspace | None = None,
) -> FastAPI:
    app = FastAPI(title="CaseProof loopback development", docs_url=None, redoc_url=None, openapi_url=None)
    # One shared checker ensures search and check use the same trust boundary.
    app.include_router(create_litigation_check_app(checker).router)
    app.include_router(create_litigation_search_app(AuthorizedEvidenceSearch(checker) if checker else None).router)
    app.include_router(create_evidence_app(evidence).router)
    app.include_router(create_clearbrief_review_router(
        reviews if checker is not None and reviews is not None and reviews.checker is checker else None,
    ))

    # Fixed static assets: no user-defined paths and no production mount.
    _workspace = Path(__file__).resolve().parents[1] / "web" / "clearbrief"

    @app.get("/dev/clearbrief", include_in_schema=False)
    def lawyer_workspace() -> FileResponse:
        return FileResponse(_workspace / "index.html", media_type="text/html")

    @app.get("/dev/clearbrief/{asset}", include_in_schema=False)
    def lawyer_asset(asset: str) -> FileResponse:
        if asset not in {"workspace.css", "workspace.js"}:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        return FileResponse(_workspace / asset)


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
        if request.url.path.startswith("/dev/clearbrief"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; script-src 'self'; style-src 'self'; "
                "connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'self'; "
                "frame-ancestors 'none'"
            )
        else:
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


    @app.get("/dev/signed/matters/{case_id}/documents/{document_id}/versions/{version_id}/original")
    def signed_original(case_id: str, document_id: str, version_id: str,
                        authorization: str | None = Header(default=None)) -> Response:
        if signed_originals is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            data = signed_originals.read(
                bearer=_token(authorization), case_id=case_id,
                document_id=document_id, version_id=version_id,
            )
        except PrivateStorageDenied:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
        except PrivateStorageFailure:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        return Response(
            content=data, media_type="application/octet-stream",
            headers={"Content-Disposition": "attachment; filename=caseproof-original"},
        )

    @app.put("/dev/signed/matters/{case_id}/documents/{document_id}/versions/{version_id}/original",
             status_code=201)
    async def signed_original_upload(
        case_id: str, document_id: str, version_id: str, request: Request,
        authorization: str | None = Header(default=None),
    ) -> Response:
        if signed_originals is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        bearer = _token(authorization)
        chunks: list[bytes] = []
        total = 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > MAX_BYTES:
                raise HTTPException(status_code=413, detail="Original exceeds size limit")
            chunks.append(chunk)
        if total == 0:
            raise HTTPException(status_code=422, detail="Empty original")
        try:
            signed_originals.put_once(
                bearer=bearer, case_id=case_id, document_id=document_id,
                version_id=version_id, data=b"".join(chunks),
            )
        except PrivateStorageDenied:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
        except PrivateStorageFailure:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        return Response(status_code=201)

    return app
