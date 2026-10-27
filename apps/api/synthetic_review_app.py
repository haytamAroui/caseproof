"""Explicitly separate loopback synthetic workbench; never mounted by main.py."""

from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from application.extraction.contracts import ExtractionError
from application.review.contracts import ReviewCommand, ReviewConflict, ReviewKind
from application.review.memory import MemoryReviewRepository
from apps.api.access_control import (
    AccessRejected,
    CaseAccessService,
    CaseAction,
    StoredCase,
    StoredMembership,
    VerifiedSubject,
)
from apps.api.review_workbench import AuthenticatedReviewWorkbench, ReviewMaterial
from scripts.extraction_fixtures import NOW
from scripts.review_demo_fixture import ACTOR, demo_material

ASSETS = Path(__file__).resolve().parents[1] / "web/review"


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    request_id: str
    snapshot_hash: str
    expected_revision: int = Field(ge=0)
    item_id: str
    kind: str
    note: str = Field(min_length=1, max_length=4000)
    correction: str | None = Field(default=None, max_length=8192)


def memory_demo() -> tuple[AuthenticatedReviewWorkbench, str]:
    from datetime import timedelta

    snapshot, documents = demo_material(boundary_review=True)

    class Verifier:
        def verify_bearer(self, token: str) -> VerifiedSubject:
            return VerifiedSubject(str(ACTOR), "synthetic", "demo", NOW, NOW + timedelta(days=1), False)

    class Repository:
        def lookup_case_membership(
            self, subject: str, case_id: str
        ) -> tuple[StoredCase, StoredMembership] | None:
            if case_id != str(snapshot.scope.case_id):
                return None
            return (
                StoredCase(case_id, str(snapshot.scope.org_id), snapshot.data["case_revision"], str(ACTOR)),
                StoredMembership(
                    str(ACTOR),
                    str(snapshot.scope.org_id),
                    True,
                    frozenset(
                        {
                            CaseAction.READ_CASE,
                            CaseAction.READ_EVIDENCE,
                            CaseAction.READ_COVERAGE,
                            CaseAction.PROPOSE_REVIEW,
                        }
                    ),
                ),
            )

    access = CaseAccessService(Verifier(), Repository(), "synthetic", "demo", lambda: NOW)
    repo = MemoryReviewRepository()
    material = ReviewMaterial(snapshot, documents)
    service = AuthenticatedReviewWorkbench(access, lambda _: material, repo)
    return service, str(snapshot.scope.case_id)


def create_demo_app(
    *, service: AuthenticatedReviewWorkbench | None = None, case_id: str | None = None
) -> FastAPI:
    if service is None:
        service, case_id = memory_demo()
    if case_id is None:
        raise ExtractionError("synthetic case context required")
    app = FastAPI(title="Synthetic reviewer workbench", docs_url=None, redoc_url=None, openapi_url=None)
    session = secrets.token_urlsafe(32)
    workbench = service
    selected_case = case_id

    @app.middleware("http")
    async def guard(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if request.url.hostname not in {"127.0.0.1", "localhost", "::1", "testserver"}:
            return JSONResponse({"error": "loopback_demo_only"}, status_code=403)
        if request.method not in {"GET", "HEAD", "POST"}:
            return JSONResponse({"error": "method_not_allowed"}, status_code=405)
        if request.method == "POST":
            origin = request.headers.get("origin", "")
            try:
                parsed = urlsplit(origin)
            except ValueError:
                return JSONResponse({"error": "origin_rejected"}, status_code=403)
            if parsed.scheme != request.url.scheme or parsed.netloc != request.headers.get("host"):
                return JSONResponse({"error": "origin_rejected"}, status_code=403)
            if not secrets.compare_digest(request.headers.get("x-review-session", ""), session):
                return JSONResponse({"error": "session_rejected"}, status_code=403)
            if request.headers.get("content-type", "").split(";", 1)[0] != "application/json":
                return JSONResponse({"error": "json_required"}, status_code=415)
            length = request.headers.get("content-length", "")
            if not length.isascii() or not length.isdecimal() or int(length) > 20_000:
                return JSONResponse({"error": "request_limit"}, status_code=413)
            raw = await request.body()
            if len(raw) > 20_000:
                return JSONResponse({"error": "request_limit"}, status_code=413)
        response = await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": "default-src 'none'; script-src 'self'; "
                "style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
            }
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse({"error": "invalid_review_input"}, status_code=422)

    @app.exception_handler(ReviewConflict)
    async def conflict(request: Request, exc: ReviewConflict) -> JSONResponse:
        return JSONResponse({"error": "review_conflict", "message": str(exc)}, status_code=409)

    @app.exception_handler(ExtractionError)
    async def rejected(request: Request, exc: ExtractionError) -> JSONResponse:
        return JSONResponse({"error": "review_unavailable"}, status_code=422)

    @app.exception_handler(AccessRejected)
    async def denied(request: Request, exc: AccessRejected) -> JSONResponse:
        return JSONResponse({"error": "access_denied"}, status_code=exc.http_status)

    @app.exception_handler(Exception)
    async def unknown(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            {"error": "review_outcome_unknown", "message": "Retry the same request ID to reconcile."},
            status_code=503,
        )

    @app.get("/demo")
    def index() -> FileResponse:
        return FileResponse(ASSETS / "index.html", media_type="text/html")

    @app.get("/demo/assets/{name}")
    def asset(name: str) -> Response:
        if name not in {"workbench.css", "workbench.js"}:
            return Response(status_code=404)
        return FileResponse(
            ASSETS / name, media_type="text/css" if name.endswith("css") else "text/javascript"
        )

    @app.get("/demo/api/state")
    def state() -> dict[str, Any]:
        return {
            **workbench.view(bearer="synthetic-fixture-only", case_id=selected_case),
            "session": session,
            "identity_mode": "synthetic_fixture",
        }

    @app.post("/demo/api/reviews")
    def record(body: ReviewInput) -> dict[str, Any]:
        try:
            command = ReviewCommand(
                UUID(body.request_id),
                body.snapshot_hash,
                body.expected_revision,
                body.item_id,
                ReviewKind(body.kind),
                body.note,
                body.correction,
            )
        except (ValueError, TypeError):
            raise ExtractionError("review input rejected") from None
        return workbench.record(bearer="synthetic-fixture-only", case_id=selected_case, command=command)

    @app.get("/demo/api/export")
    def export() -> Response:
        data, manifest = workbench.export(bearer="synthetic-fixture-only", case_id=selected_case)
        return Response(
            data,
            media_type="application/zip",
            headers={
                "Content-Disposition": 'attachment; filename="draft-evidence-review.zip"',
                "X-Pack-Manifest-SHA256": manifest,
            },
        )

    @app.get("/demo/api/source/{source_id}")
    def original(source_id: str) -> Response:
        context, material = workbench._current("synthetic-fixture-only", selected_case)
        document = next((p for p in material.documents if p.evidence.source_id == source_id), None)
        if document is None:
            return Response(status_code=404)
        return Response(
            document.evidence.source.content,
            media_type="application/octet-stream",
            headers={"Content-Disposition": 'attachment; filename="captured-original.bin"'},
        )

    return app
