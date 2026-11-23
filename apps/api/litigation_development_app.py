"""Loopback-only synthetic/staging composition; never mounted in the main API.

Dependencies are injected. This factory does not construct a database role,
accept credentials from requests, install schemas or authorize live deployment.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import Path
from typing import Any, Protocol

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response

from apps.api.access_control import AccessFailure, AccessRejected
from apps.api.data_rights_enforcement import SignedRightsGate
from apps.api.dossier_journey import DossierStore, create_dossier_router
from apps.api.dossier_viewer import create_dossier_viewer_router
from apps.api.litigation_check_app import create_litigation_check_app
from apps.api.litigation_check_service import AuthorizedLitigationChecker
from apps.api.litigation_evidence_app import EvidenceReader, _token, create_evidence_app
from apps.api.litigation_evidence_search import AuthorizedEvidenceSearch
from apps.api.litigation_headless_verification import HeadlessMatterStore, create_headless_review_router
from apps.api.litigation_live_journey import create_live_journey_router
from apps.api.litigation_live_roundtrip import create_live_review_router
from apps.api.litigation_original_reader import AuthorizedOriginalReader
from apps.api.litigation_review_app import create_clearbrief_review_router
from apps.api.litigation_review_workspace import SignedReviewWorkspace
from apps.api.litigation_search_app import create_litigation_search_app
from apps.api.litigation_workspace_sources import create_clearbrief_sources_router
from apps.api.review_record_qr import build_qr_payload, render_qr_png
from apps.api.signed_supabase_matter_catalog import SignedMatterCatalog
from apps.api.signed_supabase_originals import MAX_BYTES, PrivateStorageDenied, PrivateStorageFailure
from apps.api.signed_supabase_source_library import SignedSourceLibrary
from apps.api.signed_workbench_routes import create_signed_workbench_router
from apps.api.workspace_auth import SupabaseWorkspaceAuth, create_workspace_auth_router
from apps.api.workspace_catalog import create_workspace_catalog_router
from apps.api.workspace_intake import WorkspaceIntake, create_workspace_intake_router
from apps.api.workspace_reports import WorkspaceReports, create_workspace_reports_router
from infrastructure.parsers.pdf_ocr import LocalPDFOCR, OCRUnavailable
from infrastructure.parsers.pdf_source_crop import render_pdf_page


@dataclass(frozen=True, slots=True)
class SignedDocumentVersionSummary:
    version_id: str
    version_number: int
    media_type: str
    byte_length: int
    sha256_hex: str


@dataclass(frozen=True, slots=True)
class SignedDocumentSummary:
    document_id: str
    label: str
    versions: tuple[SignedDocumentVersionSummary, ...]


@dataclass(frozen=True, slots=True)
class SignedPublishOutcome:
    brief_id: str
    brief_version_id: str
    published_revision: int


@dataclass(frozen=True, slots=True)
class SignedDocumentRegistration:
    document_id: str
    version_id: str


@dataclass(frozen=True, slots=True)
class SignedExhibitConfirmation:
    exhibit_id: str
    exhibit_revision: int


class SignedBriefPublisher(Protocol):
    """Loopback-only port: publish one brief version bound to its verified
    uploaded original. Implementations must verify the bearer, read back the
    stored bytes, derive the checked representation with the real parser and
    refuse stale expected revisions. The port resolves the matter's working
    brief itself: the browser selects a registered document/version and never
    manages brief identifiers; optimistic concurrency stays internal through
    expected_revision. Raises PrivateStorageDenied for masked or unauthorized
    access, PrivateStorageFailure for uncertain storage outcomes and
    ValueError for an immutable graph conflict (stale revision, duplicate
    version)."""

    def list_documents(self, *, bearer: str, case_id: str) -> tuple[SignedDocumentSummary, ...]: ...

    def register_source_version(
        self,
        *,
        bearer: str,
        case_id: str,
        label: str,
        media_type: str,
        byte_length: int,
        sha256_hex: str,
    ) -> SignedDocumentRegistration:
        """Declare a new document and first version (label, size, digest)
        before any byte upload; the later upload must match the declared
        digest or fail closed."""
        ...

    def confirm_exhibit(
        self,
        *,
        bearer: str,
        case_id: str,
        document_id: str,
        version_id: str,
        display_label: str,
        page_mappings: object = None,
    ) -> SignedExhibitConfirmation:
        """Append a registered, already-uploaded source to the matter's
        confirmed exhibit register at the current revision (optimistic
        concurrency); the check denominator changes only through this
        explicit interactive confirmation. Optional user-declared page
        mappings keep each numbering space independent; nothing is
        inferred when absent."""
        ...

    def publish_uploaded(
        self,
        *,
        bearer: str,
        case_id: str,
        document_id: str,
        version_id: str,
        document_role: str,
        expected_revision: int,
    ) -> SignedPublishOutcome: ...


class SignedReviewRecord(Protocol):
    """Loopback-only port: export a content-addressed record of the recorded
    state of a matter's working brief (published head, recorded check runs,
    hash-chained human review events). Implementations must verify the bearer
    and matter grant, recompute recorded digests and replay the review hash
    chain, and fail closed on any mismatch. The record is a transcript of
    recorded state, never a reassessment, approval or filing. Raises
    PrivateStorageDenied for masked or unauthorized access and ValueError for
    inconsistent recorded state."""

    def record(self, *, bearer: str, case_id: str, document_role: str) -> dict[str, object]: ...


def create_litigation_development_app(
    *,
    checker: AuthorizedLitigationChecker | None = None,
    originals: AuthorizedOriginalReader | None = None,
    signed_originals: SignedSourceLibrary | None = None,
    signed_brief_publisher: SignedBriefPublisher | None = None,
    signed_review_record: SignedReviewRecord | None = None,
    evidence: EvidenceReader | None = None,
    reviews: SignedReviewWorkspace | None = None,
    signed_workbench_factory: Callable[[str], Any] | None = None,
    signed_source_ingest: Callable[..., object] | None = None,
    publishable_key: str | None = None,
    trusted_ingest_key: str | None = None,
    ocr: LocalPDFOCR | None = None,
    headless: HeadlessMatterStore | None = None,
    page_worker_secret: str | None = None,
    rights_gate: SignedRightsGate | None = None,
    workspace_directory: Path | None = None,
) -> FastAPI:
    app = FastAPI(title="CaseProof loopback development", docs_url=None, redoc_url=None, openapi_url=None)
    # When rights enforcement is active, older optional checker ports lack
    # source-version rights propagation. Disable them fail-closed instead of
    # allowing an independently injected checker to bypass signed policies.
    legacy_checker = checker if rights_gate is None else None
    app.include_router(create_litigation_check_app(legacy_checker).router)
    app.include_router(
        create_litigation_search_app(
            AuthorizedEvidenceSearch(legacy_checker) if legacy_checker else None,
        ).router
    )
    app.include_router(create_evidence_app(evidence if rights_gate is None else None).router)
    app.include_router(create_clearbrief_sources_router(legacy_checker))
    app.include_router(
        create_clearbrief_review_router(
            reviews
            if legacy_checker is not None and reviews is not None and reviews.checker is legacy_checker
            else None,
        )
    )

    app.include_router(create_signed_workbench_router(signed_workbench_factory))

    if publishable_key is not None and (
        not publishable_key.startswith("sb_publishable_")
        or len(publishable_key) > 512
        or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
            for c in publishable_key
        )
    ):
        raise ValueError("Only a public Supabase development publishable key is allowed")

    dossier_store = (
        DossierStore(publishable_key, trusted_ingest_key, rights_gate=rights_gate)
        if publishable_key
        else None
    )
    app.include_router(create_dossier_router(dossier_store))
    app.include_router(
        create_workspace_intake_router(
            WorkspaceIntake(dossier_store.client, dossier_store) if dossier_store else None
        )
    )
    app.include_router(create_dossier_viewer_router(dossier_store))
    if dossier_store is not None and page_worker_secret is not None:
        from apps.api.signed_page_jobs import SignedPageJobs, create_page_job_router

        app.include_router(create_page_job_router(SignedPageJobs(dossier_store, page_worker_secret)))
    app.include_router(create_headless_review_router(headless))
    # The direct legacy RPCs are now wrapped with transactional rights checks
    # by the PR2 signed-legacy-RPC migration; preserve their genuine signed
    # review/correction flow. This remains a no-op when no publishable key is
    # configured, and never expands the underlying actor's matter grants.
    app.include_router(create_live_review_router(publishable_key))
    app.include_router(
        create_live_journey_router(
            publishable_key,
            trusted_ingest_key,
            ocr=ocr,
            **({"rights_gate": rights_gate} if rights_gate is not None else {}),
        )
    )

    @app.get("/dev/clearbrief/config", include_in_schema=False)
    def lawyer_config() -> dict[str, str | bool | None]:
        return {
            "schema": "caseproof-clearbrief-dev-config-v1",
            "publishable_key": publishable_key,
            "signed_workbench": signed_workbench_factory is not None,
        }

    catalog = SignedMatterCatalog(publishable_key) if publishable_key else None
    app.include_router(create_workspace_catalog_router(catalog))
    app.include_router(
        create_workspace_reports_router(WorkspaceReports(publishable_key) if publishable_key else None)
    )
    app.include_router(
        create_workspace_auth_router(SupabaseWorkspaceAuth(publishable_key) if publishable_key else None)
    )

    @app.get("/dev/clearbrief/matters", include_in_schema=False)
    def lawyer_matters(authorization: str | None = Header(default=None)) -> dict[str, object]:
        if catalog is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        return {
            "schema": "caseproof-clearbrief-matters-v1",
            "matters": catalog.list_matters(_token(authorization)),
        }

    if workspace_directory is not None:
        root = workspace_directory.resolve(strict=True)
        assets = {str(p.relative_to(root)): p for p in root.rglob("*") if p.is_file() and not p.is_symlink()}
        if "index.html" not in assets:
            raise ValueError("Built workspace index required")

        @app.get("/workspace", include_in_schema=False)
        @app.get("/workspace/{workspace_path:path}", include_in_schema=False)
        def workspace_asset(workspace_path: str = "") -> FileResponse:
            if workspace_path.startswith("assets/"):
                if workspace_path not in assets:
                    raise AccessRejected(AccessFailure.RESOURCE_MASKED)
                return FileResponse(assets[workspace_path])
            return FileResponse(assets["index.html"], media_type="text/html")

    # Fixed static assets: no user-defined paths and no production mount.
    _workspace = Path(__file__).resolve().parents[1] / "web" / "clearbrief"

    @app.get("/dev/clearbrief", include_in_schema=False)
    def lawyer_workspace() -> FileResponse:
        return FileResponse(_workspace / "index.html", media_type="text/html")

    @app.get("/dev/clearbrief/{asset}", include_in_schema=False)
    def lawyer_asset(asset: str) -> FileResponse:
        if asset not in {"workspace.css", "workspace.js", "fidelity-panel.js"}:
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
        return {"projectUrl": "https://ldwmocpxwskvhoojndrd.supabase.co", "publishableKey": publishable_key}

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
        if request.method == "POST" and request.url.path.startswith("/v2/workspace/intake/"):
            chunks = []
            size = 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > 17_000_000:
                    return JSONResponse({"error": "intake_body_too_large"}, status_code=413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path in {
            "/index.html",
            "/caseproof-public-config.json",
            "/taskpane.js",
            "/taskpane.css",
            "/demo-session.js",
            "/auth/live-ui.js",
            "/auth/office-callback.js",
            "/auth-callback.html",
            "/dist/live-auth.js",
            "/manifest-live-dev.xml",
        } or request.url.path.startswith("/word-assets/"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; script-src 'self' https://appsforoffice.microsoft.com; "
                "style-src 'self'; connect-src 'self' https://ldwmocpxwskvhoojndrd.supabase.co; "
                "img-src 'self' data:; base-uri 'none'; form-action 'none'; "
                "frame-ancestors 'self' https://*.office.com https://*.officeapps.live.com"
            )
        elif request.url.path == "/workspace" or request.url.path.startswith("/workspace/"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; script-src 'self'; style-src 'self'; "
                "connect-src 'self'; img-src 'self' blob:; font-src 'self'; worker-src 'self'; "
                "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
            )
        elif request.url.path.startswith("/dev/clearbrief"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; script-src 'self'; style-src 'self'; "
                "connect-src 'self' https://ldwmocpxwskvhoojndrd.supabase.co; "
                "img-src 'self' blob:; base-uri 'none'; form-action 'self'; "
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

    @app.get(
        "/v2/matters/{case_id}/briefs/{brief_version_id}/evidence/{source_id}/versions/{version_id}/original"
    )
    def original(
        case_id: str,
        brief_version_id: str,
        source_id: str,
        version_id: str,
        authorization: str | None = Header(default=None),
    ) -> Response:
        if originals is None or checker is None or originals.checker is not checker:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        item = originals.read(
            bearer=_token(authorization),
            case_id=case_id,
            brief_version_id=brief_version_id,
            source_id=source_id,
            version_id=version_id,
        )
        # Original bytes are never interpreted as active HTML or shown inline.
        return Response(
            item.data,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": "attachment; filename=caseproof-original",
                "X-CaseProof-Original-SHA256": item.sha256_hex,
                "X-CaseProof-Original-Media-Type": item.media_type,
            },
        )

    @app.get(
        "/v2/matters/{case_id}/briefs/{brief_version_id}"
        "/evidence/{source_id}/versions/{version_id}/pages/{pdf_page}"
    )
    def original_page(
        case_id: str,
        brief_version_id: str,
        source_id: str,
        version_id: str,
        pdf_page: int,
        authorization: str | None = Header(default=None),
    ) -> Response:
        """Physical-page PNG rendering of the verified original bytes.

        Same authorized, digest-bound read as the original-bytes route; the
        image is a display rendering, never a visual-verification verdict.
        Unavailable pages (non-PDF source, invalid or out-of-range page)
        fail closed as 404; infrastructure absence stays 503.
        """
        if originals is None or checker is None or originals.checker is not checker:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        item = originals.read(
            bearer=_token(authorization),
            case_id=case_id,
            brief_version_id=brief_version_id,
            source_id=source_id,
            version_id=version_id,
        )
        if item.media_type != "application/pdf":
            raise HTTPException(status_code=404, detail="physical_page_unavailable")
        try:
            png = render_pdf_page(item.data, page_number=pdf_page)
        except OCRUnavailable as exc:
            if str(exc) in {"crop_rasterizer_unavailable", "crop_pillow_unavailable"}:
                raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
            raise HTTPException(status_code=404, detail="physical_page_unavailable") from None
        return Response(
            png,
            media_type="image/png",
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "X-CaseProof-Original-SHA256": item.sha256_hex,
                "X-CaseProof-Physical-Page": str(pdf_page),
            },
        )

    @app.get("/dev/signed/matters/{case_id}/documents/{document_id}/versions/{version_id}/original")
    def signed_original(
        case_id: str, document_id: str, version_id: str, authorization: str | None = Header(default=None)
    ) -> Response:
        if signed_originals is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            data = signed_originals.read(
                bearer=_token(authorization),
                case_id=case_id,
                document_id=document_id,
                version_id=version_id,
            )
        except PrivateStorageDenied:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
        except PrivateStorageFailure:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        return Response(
            content=data,
            media_type="application/octet-stream",
            headers={"Content-Disposition": "attachment; filename=caseproof-original"},
        )

    @app.put(
        "/dev/signed/matters/{case_id}/documents/{document_id}/versions/{version_id}/original",
        status_code=201,
    )
    async def signed_original_upload(
        case_id: str,
        document_id: str,
        version_id: str,
        request: Request,
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
                bearer=bearer,
                case_id=case_id,
                document_id=document_id,
                version_id=version_id,
                data=b"".join(chunks),
            )
        except PrivateStorageDenied:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
        except PrivateStorageFailure:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        if signed_source_ingest is not None:
            # Server-side step after the verified write: the privileged ingest
            # port derives the registry payload from the verified READBACK,
            # never from the request body. Without this port a published
            # brief cannot cite the new source.
            try:
                verified = signed_originals.read(
                    bearer=bearer, case_id=case_id, document_id=document_id,
                    version_id=version_id,
                )
                ref, _length = signed_originals.source(
                    bearer=bearer, case_id=case_id, document_id=document_id,
                    version_id=version_id,
                )
                signed_source_ingest(
                    case_id=case_id, document_id=document_id, version_id=version_id,
                    data=verified, media_type=ref.content_type,
                )
            except PrivateStorageDenied:
                raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
            except (PrivateStorageFailure, ValueError):
                raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        return Response(status_code=201)

    @app.get("/dev/signed/matters/{case_id}/documents")
    def signed_documents(case_id: str, authorization: str | None = Header(default=None)) -> JSONResponse:
        if signed_brief_publisher is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            documents = signed_brief_publisher.list_documents(bearer=_token(authorization), case_id=case_id)
        except PrivateStorageDenied:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
        except PrivateStorageFailure:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        head = getattr(signed_brief_publisher, "brief_head_revision", None)
        try:
            revision = (
                head(bearer=_token(authorization), case_id=case_id)
                if callable(head) else None
            )
        except PrivateStorageDenied:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
        except PrivateStorageFailure:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        return JSONResponse(
            {
                "schema": "caseproof-signed-documents-v1",
                "own_draft_revision": revision,
                "documents": [
                    {
                        "document_id": document.document_id,
                        "label": document.label,
                        "versions": [
                            {
                                "version_id": version.version_id,
                                "version_number": version.version_number,
                                "media_type": version.media_type,
                                "byte_length": version.byte_length,
                                "sha256_hex": version.sha256_hex,
                            }
                            for version in document.versions
                        ],
                    }
                    for document in documents
                ],
            }
        )

    @app.post("/dev/signed/matters/{case_id}/documents", status_code=201)
    async def signed_document_register(
        case_id: str,
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        if signed_brief_publisher is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            payload = await request.json()
        except Exception:
            raise HTTPException(status_code=422, detail="invalid_request") from None
        if not isinstance(payload, dict) or set(payload) != {
            "label",
            "media_type",
            "byte_length",
            "sha256_hex",
        }:
            raise HTTPException(status_code=422, detail="invalid_request")
        label = payload["label"]
        media_type = payload["media_type"]
        byte_length = payload["byte_length"]
        sha256_hex = payload["sha256_hex"]
        if (
            not isinstance(label, str)
            or not 0 < len(label.strip()) <= 120
            or "\r" in label
            or "\n" in label
            or not isinstance(media_type, str)
            or not 1 <= len(media_type) <= 100
            or type(byte_length) is not int
            or byte_length <= 0
            or not isinstance(sha256_hex, str)
            or len(sha256_hex) != 64
            or any(c not in "0123456789abcdef" for c in sha256_hex)
        ):
            raise HTTPException(status_code=422, detail="invalid_request")
        try:
            registration = signed_brief_publisher.register_source_version(
                bearer=_token(authorization),
                case_id=case_id,
                label=label.strip(),
                media_type=media_type,
                byte_length=byte_length,
                sha256_hex=sha256_hex,
            )
        except PrivateStorageDenied:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
        except PrivateStorageFailure:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        except ValueError:
            raise HTTPException(status_code=422, detail="invalid_request") from None
        return JSONResponse(
            {
                "schema": "caseproof-signed-document-register-v1",
                "document_id": registration.document_id,
                "version_id": registration.version_id,
            },
            status_code=201,
        )

    @app.post("/dev/signed/matters/{case_id}/exhibits/confirm", status_code=201)
    async def signed_exhibit_confirm(
        case_id: str,
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        if signed_brief_publisher is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            payload = await request.json()
        except Exception:
            raise HTTPException(status_code=422, detail="invalid_request") from None
        if not isinstance(payload, dict) or not {
            "document_id",
            "version_id",
            "display_label",
        } <= set(payload) <= {
            "document_id",
            "version_id",
            "display_label",
            "page_mappings",
        }:
            raise HTTPException(status_code=422, detail="invalid_request")
        if "page_mappings" in payload and not isinstance(payload["page_mappings"], list):
            raise HTTPException(status_code=422, detail="invalid_request")
        ids = [payload["document_id"], payload["version_id"]]
        label = payload["display_label"]
        if (
            any(type(v) is not str or len(v) != 36 for v in ids)
            or not isinstance(label, str)
            or not 0 < len(label.strip()) <= 200
            or "\r" in label
            or "\n" in label
        ):
            raise HTTPException(status_code=422, detail="invalid_request")
        try:
            confirmation = signed_brief_publisher.confirm_exhibit(
                bearer=_token(authorization),
                case_id=case_id,
                document_id=payload["document_id"],
                version_id=payload["version_id"],
                display_label=label.strip(),
                page_mappings=payload.get("page_mappings"),
            )
        except PrivateStorageDenied:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
        except PrivateStorageFailure:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        except ValueError:
            raise HTTPException(status_code=409, detail="exhibit confirmation conflict") from None
        return JSONResponse(
            {
                "schema": "caseproof-signed-exhibit-confirm-v1",
                "exhibit_id": confirmation.exhibit_id,
                "exhibit_revision": confirmation.exhibit_revision,
            },
            status_code=201,
        )

    @app.post("/dev/signed/matters/{case_id}/briefs/publish", status_code=201)
    async def signed_brief_publish(
        case_id: str,
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        if signed_brief_publisher is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            payload = await request.json()
        except Exception:
            raise HTTPException(status_code=422, detail="invalid_request") from None
        if not isinstance(payload, dict) or set(payload) != {
            "document_id",
            "version_id",
            "document_role",
            "expected_revision",
        }:
            raise HTTPException(status_code=422, detail="invalid_request")
        ids = [payload[k] for k in ("document_id", "version_id")]
        if (
            any(type(v) is not str or len(v) != 36 for v in ids)
            or payload["document_role"] not in {"own_draft", "opponent_brief"}
            or type(payload["expected_revision"]) is not int
            or payload["expected_revision"] < 0
        ):
            raise HTTPException(status_code=422, detail="invalid_request")
        try:
            outcome = signed_brief_publisher.publish_uploaded(
                bearer=_token(authorization),
                case_id=case_id,
                document_id=payload["document_id"],
                version_id=payload["version_id"],
                document_role=payload["document_role"],
                expected_revision=payload["expected_revision"],
            )
        except PrivateStorageDenied:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
        except PrivateStorageFailure:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        except ValueError:
            raise HTTPException(status_code=409, detail="immutable publication conflict") from None
        return JSONResponse(
            {
                "schema": "caseproof-signed-brief-publish-v1",
                "brief_id": outcome.brief_id,
                "brief_version_id": outcome.brief_version_id,
                "published_revision": outcome.published_revision,
            },
            status_code=201,
        )

    @app.get("/dev/signed/matters/{case_id}/review-record")
    def signed_review_record_read(
        case_id: str,
        role: str = Query(default="own_draft", pattern="^(own_draft|opponent_brief)$"),
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        if signed_review_record is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            body = signed_review_record.record(
                bearer=_token(authorization), case_id=case_id, document_role=role
            )
        except PrivateStorageDenied:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
        except ValueError:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        return JSONResponse(body)

    @app.get("/dev/signed/matters/{case_id}/review-record/verification-qr")
    def signed_review_record_qr(
        case_id: str,
        role: str = Query(default="own_draft", pattern="^(own_draft|opponent_brief)$"),
        authorization: str | None = Header(default=None),
    ) -> Response:
        """Bounded offline-verification QR for the record (digest + key).

        No URL, no case text, no secret: scanning cannot imply hosted
        public verification. Same authorized read as the record route.
        """
        if signed_review_record is None:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE)
        try:
            body = signed_review_record.record(
                bearer=_token(authorization), case_id=case_id, document_role=role
            )
            png = render_qr_png(build_qr_payload(body))
        except PrivateStorageDenied:
            raise AccessRejected(AccessFailure.RESOURCE_MASKED) from None
        except ValueError:
            raise AccessRejected(AccessFailure.SERVICE_UNAVAILABLE) from None
        return Response(
            png, media_type="image/png",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    return app
