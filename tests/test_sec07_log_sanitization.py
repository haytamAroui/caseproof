"""SEC-07 automated log-sanitization & error-redaction regression suite.

Proves via live logging capture that bearer tokens, confidential client quotes, and
personal identifiers never appear in logs or HTTP 4xx/5xx error responses across
export/release, filing PDF parity, partner demo, and data-rights telemetry paths.
"""

from __future__ import annotations

import hashlib
import io
import logging
from uuid import uuid4

from docx import Document
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from application.data_rights import Action, Decision, RightsPolicy
from apps.api.access_control import AccessRejected
from apps.api.data_rights_enforcement import SignedRightsGate
from apps.api.data_rights_shadow import observe_authorized_read
from apps.api.dossier_export_release import create_release_router
from scripts.run_prefiling_partner_demo import (
    DEMO_BRIEF_ID,
    DEMO_CASE_ID,
    create_partner_demo_app,
)

CANARY_TOKEN = "eyJhbGciOiJIUzI1NiJ9.CANARY_BEARER_SECRET_991122.sig"
CANARY_QUOTE = "CONFIDENTIAL_CLIENT_QUOTE_CANARY_884422"
CANARY_PII = "Maitre-Dupont-Canary-BE68539007547034"
CANARIES = (CANARY_TOKEN, CANARY_QUOTE, CANARY_PII)

CASE_ID = str(uuid4())
BRIEF_ID = str(uuid4())
SNAPSHOT = "a" * 64


class _MemoryLogHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(self.format(record))


def _docx_with_canary() -> bytes:
    doc = Document()
    doc.add_paragraph(f"Conclusion confidentielle: {CANARY_QUOTE} ({CANARY_PII}).")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _pdf_with_canary() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 760, f"Version stale: {CANARY_QUOTE} / {CANARY_PII}")
    c.showPage()
    c.save()
    return buf.getvalue()


class _SanitizationStore:
    def __init__(self) -> None:
        self.original = _docx_with_canary()
        self.active_brief = BRIEF_ID
        self.decisions = [
            {
                "reference_id": "ref-1",
                "decision": "CONFIRMED_SUPPORTED",
                "rationale": f"Verified {CANARY_PII}",
                "reviewer_id": str(uuid4()),
                "request_id": str(uuid4()),
                "timestamp": "2026-11-25T10:00:00+00:00",
            }
        ]
        self.report = {
            "schema": "caseproof-dossier-v1",
            "case_id": CASE_ID,
            "brief_id": BRIEF_ID,
            "snapshot_hash": SNAPSHOT,
            "bundle_signature": "b" * 64,
            "confirmation_id": str(uuid4()),
            "sources": [
                {
                    "role": "draft",
                    "version_id": BRIEF_ID,
                    "sha256": hashlib.sha256(self.original).hexdigest(),
                }
            ],
            "coverage": {
                "checked": 1,
                "unresolved": 0,
                "text_coverage_complete": True,
                "reference_recall_measured": False,
            },
            "findings": [{"reference_id": "ref-1", "visual_assessment": {"regions": []}}],
        }

    def release_actor(self, _bearer: str) -> dict[str, str]:
        return {
            "actor_id": str(uuid4()),
            "actor_label": CANARY_PII,
            "actor_label_type": "confirmed_email",
        }

    def current_draft_version(self, _bearer: str, _case_id: str) -> str:
        return self.active_brief

    def reopen(self, _bearer: str, _case_id: str, _brief_id: str, _snap: str) -> tuple[dict, bytes]:
        return self.report, self.original

    def rpc(self, _bearer: str, _case_id: str, _action: str, _data=None) -> dict:
        return {"decisions": self.decisions}

    def export_rpc(self, *_args, **_kwargs) -> dict:
        return {"state": "absent"}


def _assert_no_canary_leaks(logs: list[str], error_bodies: list[str]) -> None:
    joined_logs = "\n".join(logs)
    joined_errors = "\n".join(error_bodies)
    for canary in CANARIES:
        assert canary not in joined_logs, f"Canary leaked into runtime logs: {canary}"
        assert canary not in joined_errors, f"Canary leaked into error response: {canary}"


def test_sec07_routes_and_rights_loggers_never_emit_tokens_quotes_or_pii(monkeypatch) -> None:
    # Enable non-empty bearer acceptance via a dedicated canary token module-locally.
    monkeypatch.setattr(
        "apps.api.litigation_evidence_app._token",
        lambda auth: (auth or "").removeprefix("Bearer ").strip(),
    )

    handler = _MemoryLogHandler()
    root_logger = logging.getLogger()
    old_level = root_logger.level
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(handler)
    error_bodies: list[str] = []

    try:
        # 1. Exercise signed release + parity routes across 200 / 404 / 409 / 422 paths.
        store = _SanitizationStore()
        app = FastAPI()

        @app.exception_handler(AccessRejected)
        def _denied(_req, err):
            return JSONResponse({"error": err.code.value}, status_code=err.http_status)

        app.include_router(create_release_router(store))
        client = TestClient(app)

        pdf = _pdf_with_canary()
        pdf_sha = hashlib.sha256(pdf).hexdigest()
        parity_url = f"/v2/matters/{CASE_ID}/briefs/{BRIEF_ID}/dossier/releases/filing-pdf-parity"
        headers = {
            "Authorization": f"Bearer {CANARY_TOKEN}",
            "Content-Type": "application/pdf",
            "X-CaseProof-Snapshot-Hash": SNAPSHOT,
            "X-CaseProof-Filing-PDF-SHA256": pdf_sha,
            "X-CaseProof-Byte-Length": str(len(pdf)),
        }
        assert client.post(parity_url, content=pdf, headers=headers).status_code == 200

        # Invalid PDF body embedding CANARY_QUOTE + CANARY_PII triggers 422 error path.
        bad_pdf = f"%PDF-1.4\n{CANARY_QUOTE}\n{CANARY_PII}\n".encode()
        bad_res = client.post(
            parity_url,
            content=bad_pdf,
            headers={
                **headers,
                "X-CaseProof-Filing-PDF-SHA256": hashlib.sha256(bad_pdf).hexdigest(),
                "X-CaseProof-Byte-Length": str(len(bad_pdf)),
            },
        )
        assert bad_res.status_code == 422
        error_bodies.append(bad_res.text)

        # Superseded draft triggers 409 path.
        store.active_brief = str(uuid4())
        stale_res = client.post(parity_url, content=pdf, headers=headers)
        assert stale_res.status_code == 409
        error_bodies.append(stale_res.text)

        # Unknown release status check (200 absent vs 404 format).
        missing_art = client.get(
            f"/v2/matters/{CASE_ID}/briefs/{BRIEF_ID}/dossier/releases/{uuid4()}/artifacts/bogus",
            headers={"Authorization": f"Bearer {CANARY_TOKEN}"},
        )
        assert missing_art.status_code == 404
        error_bodies.append(missing_art.text)

        # 2. Exercise data-rights enforcement & shadow loggers with canary metadata.
        class _Reader:
            def read(self, *, bearer: str, case_id: str, document_id: str, version_id: str) -> RightsPolicy | None:
                assert bearer == CANARY_TOKEN
                if document_id == "boom":
                    raise RuntimeError(f"boom {CANARY_QUOTE} {CANARY_PII}")
                return RightsPolicy(
                    decision=Decision.DENY,
                    reason="policy_denied",
                    policy_version="v1",
                    actions=(Action.EXPORT,),
                )

        gate = SignedRightsGate(_Reader())
        for doc_id in ("doc-deny", "boom"):
            try:
                gate.require(
                    bearer=CANARY_TOKEN,
                    case_id=CASE_ID,
                    document_id=doc_id,
                    version_id="v1",
                    action=Action.EXPORT,
                )
            except AccessRejected as exc:
                error_bodies.append(str(exc))

        observe_authorized_read(
            policy_lookup=lambda: RightsPolicy(
                decision=Decision.ALLOW,
                reason="explicit_allow",
                policy_version="v1",
                actions=(Action.PROCESS,),
            )
        )
        observe_authorized_read(policy_lookup=lambda: (_ for _ in ()).throw(RuntimeError(CANARY_PII)))

        # 3. Exercise partner demo error paths carrying canary tokens/quotes.
        demo_client = TestClient(create_partner_demo_app())
        for path in (
            f"/v2/matters/{DEMO_CASE_ID}/briefs/{uuid4()}/dossier",
            f"/v2/matters/{DEMO_CASE_ID}/briefs/{DEMO_BRIEF_ID}/dossier/releases/filing-pdf-parity",
        ):
            r = demo_client.post(
                path,
                content=bad_pdf,
                headers={
                    "Authorization": f"Bearer {CANARY_TOKEN}",
                    "Content-Type": "application/pdf",
                    "X-CaseProof-Snapshot-Hash": SNAPSHOT,
                    "X-CaseProof-Filing-PDF-SHA256": hashlib.sha256(bad_pdf).hexdigest(),
                    "X-CaseProof-Byte-Length": str(len(bad_pdf)),
                },
            )
            assert r.status_code in (404, 405, 422)
            error_bodies.append(r.text)

        _assert_no_canary_leaks(handler.records, error_bodies)
    finally:
        root_logger.removeHandler(handler)
        root_logger.setLevel(old_level)
