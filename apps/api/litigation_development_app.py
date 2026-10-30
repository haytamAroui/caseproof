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
from apps.api.litigation_live_journey import create_live_journey_router
from apps.api.litigation_live_roundtrip import create_live_review_router
from apps.api.litigation_original_reader import AuthorizedOriginalReader
from apps.api.litigation_review_app import create_clearbrief_review_router
from apps.api.litigation_review_workspace import SignedReviewWorkspace
from apps.api.litigation_search_app import create_litigation_search_app
from apps.api.litigation_workspace_sources import create_clearbrief_sources_router
from apps.api.signed_supabase_matter_catalog import SignedMatterCatalog
from apps.api.signed_supabase_originals import MAX_BYTES, PrivateStorageDenied, PrivateStorageFailure
from apps.api.signed_supabase_source_library import SignedSourceLibrary
from infrastructure.parsers.pdf_ocr import LocalPDFOCR


def create_litigation_development_app(
    *, checker: AuthorizedLitigationChecker | None = None,
    originals: AuthorizedOriginalReader | None = None,
    signed_originals: SignedSourceLibrary | None = None,
    evidence: EvidenceReader | None = None,
    reviews: SignedReviewWorkspace | None = None,
    publishable_key: str | None = None,
    trusted_ingest_key: str | None = None,
    ocr: LocalPDFOCR | None = None,
) -> FastAPI:
    app = FastAPI(title="CaseProof loopback development", docs_url=None, redoc_url=None, openapi_url=None)
    # One shared checker ensures search and check use the same trust boundary.
    app.include_router(create_litigation_check_app(checker).router)
    app.include_router(create_litigation_search_app(AuthorizedEvidenceSearch(checker) if checker else None).router)
    app.include_router(create_evidence_app(evidence).router)
    app.include_router(create_clearbrief_sources_router(checker))
    app.include_router(create_clearbrief_review_router(
        reviews if checker is not None and reviews is not None and reviews.checker is checker else None,
    ))

    if publishable_key is not None and (
        not publishable_key.startswith("sb_publishable_")
        or len(publishable_key) > 512
        or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in publishable_key)
    ):
        raise ValueError("Only a public Supabase development publishable key is allowed")

    app.include_router(create_live_review_router(publishable_key))
    app.include_router(create_live_journey_router(publishable_key, trusted_ingest_key, ocr=ocr))

    @app.get("/dev/clearbrief/config", include_in_schema=False)
    def lawyer_config() -> dict[str, str | None]:
        return {"schema": "caseproof-clearbrief-dev-config-v1", "publishable_key": publishable_key}

    catalog = SignedMatterCatalog(publishable_key) if publishable_key else None

    @app.get("/dev/clearbrief/matters", include_in_schema=False)
    def lawyer_matters(authorization: str | None = Header(default=None)) -> dict[str, object]:
        if catalog is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return {"schema": "caseproof-clearbrief-matters-v1",
                "matters": catalog.list_matters(_token(authorization))}

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


    # Word's pinned localhost sideload origin now serves the same signed
    # application APIs. The browser receives only a publishable key. No
    # customer/public listener, admin credentials or production routes.
    _word = Path(__file__).resolve().parents[1] / "word_addin"
    _word_files = {
        "index.html": "text/html",
        "taskpane.js": "application/javascript",
        "taskpane.css": "text/css",
        "demo-session.js": "application/javascript",
        "auth/live-ui.js": "application/javascript",
        "auth/office-callback.js": "application/javascript",
        "auth-callback.html": "text/html",
        "dist/live-auth.js": "application/javascript",
        "manifest-live-dev.xml": "application/xml",
    }

    @app.get("/caseproof-public-config.json", include_in_schema=False)
    def word_public_config() -> dict[str, str]:
        if publishable_key is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return {"projectUrl": "https://ldwmocpxwskvhoojndrd.supabase.co",
                "publishableKey": publishable_key}

    @app.get("/index.html", include_in_schema=False)
    def signed_word_entry(request: Request) -> FileResponse:
        if request.query_params.get("demo") == "1" or publishable_key is None:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        return FileResponse(_word / "index.html", media_type="text/html")

    @app.get("/word-assets/{asset_path:path}", include_in_schema=False)
    def signed_word_asset(asset_path: str) -> FileResponse:
        # Exact allowlist. No path normalization, traversal or arbitrary
        # open-file primitive from the Office task pane.
        if publishable_key is None or asset_path not in _word_files:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED)
        return FileResponse(_word / asset_path, media_type=_word_files[asset_path])

    @app.get("/taskpane.js", include_in_schema=False)
    def word_taskpane_js() -> FileResponse:
        return signed_word_asset("taskpane.js")

    @app.get("/taskpane.css", include_in_schema=False)
    def word_taskpane_css() -> FileResponse:
        return signed_word_asset("taskpane.css")

    @app.get("/demo-session.js", include_in_schema=False)
    def word_demo_js() -> FileResponse:
        return signed_word_asset("demo-session.js")

    @app.get("/auth/live-ui.js", include_in_schema=False)
    def word_auth_ui() -> FileResponse:
        return signed_word_asset("auth/live-ui.js")

    @app.get("/auth/office-callback.js", include_in_schema=False)
    def word_auth_callback_js() -> FileResponse:
        return signed_word_asset("auth/office-callback.js")

    @app.get("/auth-callback.html", include_in_schema=False)
    def word_auth_callback_html() -> FileResponse:
        return signed_word_asset("auth-callback.html")

    @app.get("/dist/live-auth.js", include_in_schema=False)
    def word_auth_bundle() -> FileResponse:
        return signed_word_asset("dist/live-auth.js")

    @app.get("/manifest-live-dev.xml", include_in_schema=False)
    def word_live_manifest() -> FileResponse:
        return signed_word_asset("manifest-live-dev.xml")

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
        if request.url.path in {"/index.html", "/caseproof-public-config.json",
            "/taskpane.js", "/taskpane.css", "/demo-session.js",
            "/auth/live-ui.js", "/auth/office-callback.js", "/auth-callback.html",
            "/dist/live-auth.js", "/manifest-live-dev.xml"} or request.url.path.startswith("/word-assets/"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; script-src 'self' https://appsforoffice.microsoft.com; "
                "style-src 'self'; connect-src 'self' https://ldwmocpxwskvhoojndrd.supabase.co; "
                "img-src 'self' data:; base-uri 'none'; form-action 'none'; "
                "frame-ancestors 'self' https://*.office.com https://*.officeapps.live.com"
            )
        elif request.url.path.startswith("/dev/clearbrief"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; script-src 'self'; style-src 'self'; "
                "connect-src 'self' https://ldwmocpxwskvhoojndrd.supabase.co; "
                "img-src 'self'; base-uri 'none'; form-action 'self'; "
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

