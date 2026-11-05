"""Genuine signed caseproof-dev document-wide DOCX activation (synthetic owned run).

No user documents, credentials, bearer headers or document bytes in logs.
"""
from __future__ import annotations

import hashlib
import http.client
import io
import json
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from docx import Document
from playwright.sync_api import Page, Route, expect

from scripts.m05_registry import record
from scripts.workspace_browser_live import ORIGIN
from scripts.workspace_f6_live import binding, reconfirm_corrected_bundle

_DEV_HOST = "ldwmocpxwskvhoojndrd.supabase.co"


def fixture_editor_grant(
    key: str, run: str, owner: str, case: str, enable: bool,
) -> None:
    """Service-only, exact M0.5 owned-run grant; no unrelated matter changes."""
    if not (key.startswith("sb_secret_") or key.startswith("eyJ")):
        raise RuntimeError("F5_DOCX_ADMIN_KEY_REQUIRED")
    data = {
        "p_run": str(UUID(run)), "p_owner": str(UUID(owner)),
        "p_case": str(UUID(case)), "p_enable": enable,
    }
    conn = http.client.HTTPSConnection(_DEV_HOST, timeout=20)
    headers = {"apikey": key, "Content-Type": "application/json"}
    if key.startswith("eyJ"):
        headers["Authorization"] = "Bearer " + key
    try:
        conn.request(
            "POST", "/rest/v1/rpc/caseproof_docx_fixture_editor_grant",
            json.dumps(data).encode(), headers,
        )
        response = conn.getresponse()
        status, body = response.status, response.read(1025)
    except (OSError, http.client.HTTPException):
        raise RuntimeError("F5_DOCX_ADMIN_GRANT_UNAVAILABLE") from None
    finally:
        conn.close()
    if status != 200 or len(body) > 1024 or body.strip() != b"true":
        raise RuntimeError("F5_DOCX_ADMIN_GRANT_FAILED")


def signed_docx_activation(
    page: Page, *, key: str, run: str, owner: str, case: str,
    org: str, registered: list[dict], login: Callable[[Page], None],
) -> None:
    # A preceding F5 correction invalidates inventory mappings. Re-attest,
    # then check the fresh bundle before granting document-wide edit access.
    reconfirm_corrected_bundle(page, case=case, registered=registered)
    old_brief, old_snapshot = binding(page)
    old_report = page.url
    print("F5_DOCX_FRESH_SOURCE_CONFIRMATION_PASSED", flush=True)

    fixture_editor_grant(key, run, owner, case, True)
    commit_headers: dict[str, str] = {}
    review_binding: dict = {}
    commit_id = ""
    try:
        page.get_by_role(
            "link", name="Edit current DOCX candidate (not committed)"
        ).click()
        native = page.get_by_role(
            "region", name="Full Microsoft Word editing and signed import"
        )
        expect(native.get_by_role(
            "heading", name="Author in Microsoft Word, verify in CaseProof"
        )).to_be_visible(timeout=90000)
        with page.expect_download(timeout=90000) as download:
            native.get_by_role(
                "button", name="1. Download preserved DOCX for Word"
            ).click()
        source = Path(download.value.path()).read_bytes()
        if not 1 <= len(source) <= 5_242_880:
            raise RuntimeError("F5_DOCX_SOURCE_SIZE_INVALID")
        original_sha = hashlib.sha256(source).hexdigest()
        word = Document(io.BytesIO(source))
        if not word.paragraphs or not word.tables:
            raise RuntimeError("F5_DOCX_WORD_STRUCTURE_MISSING")
        word.paragraphs[0].text += " Edited by native Word acceptance."
        word.tables[0].cell(0, 0).text = "Word-native signed document edit"
        word.add_paragraph("Document-wide reviewed addition — synthetic.")
        out = io.BytesIO()
        word.save(out)
        candidate = out.getvalue()
        candidate_sha = hashlib.sha256(candidate).hexdigest()
        if candidate_sha == original_sha:
            raise RuntimeError("F5_DOCX_IDENTICAL_CANDIDATE")
        native.locator('input[type="file"]').set_input_files({
            "name": "reviewed-word-synthetic.docx",
            "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "buffer": candidate,
        })
        expect(native.get_by_text(
            "DOCX staged in browser memory", exact=False
        )).to_be_visible(timeout=90000)
        native.get_by_role(
            "button", name="3. Inspect imported Word document"
        ).click()
        expect(native.get_by_text(
            "Word-native candidate validated", exact=False
        )).to_be_visible(timeout=90000)
        print("F5_DOCX_NATIVE_SIGNED_SOURCE_BOUND_PREVIEW_PASSED", flush=True)

        def observe_review(route: Route) -> None:
            nonlocal review_binding
            body = route.request.post_data_json
            if not isinstance(body, dict):
                raise RuntimeError("F5_DOCX_REVIEW_REQUEST_MALFORMED")
            review_binding = {
                "review_request_id": body.get("review_request_id", ""),
                "snapshot_hash": body.get("snapshot_hash", ""),
                "original_sha256": body.get("original_sha256", ""),
                "candidate_sha256": body.get("candidate_sha256", ""),
            }
            result = route.fetch(timeout=90000)
            if result.status != 200:
                raise RuntimeError("F5_DOCX_REVIEW_NOT_SAVED")
            route.fulfill(response=result)

        page.route("**/dossier/editor/native/review", observe_review)
        native.get_by_label("Human full-document review rationale").fill(
            "Reviewed all synthetic Word document edits including its modified table."
        )
        native.get_by_role("button", name="4. Save whole-document review").click()
        expect(native.get_by_text(
            "Signed whole-document review saved", exact=False
        )).to_be_visible(timeout=90000)
        page.unroute("**/dossier/editor/native/review", observe_review)
        if (review_binding.get("snapshot_hash") != old_snapshot
            or review_binding.get("original_sha256") != original_sha
            or review_binding.get("candidate_sha256") != candidate_sha):
            raise RuntimeError("F5_DOCX_REVIEW_SOURCE_MISMATCH")
        print("F5_DOCX_NATIVE_SIGNED_HUMAN_REVIEW_RECEIPT_PASSED", flush=True)

        def lose_ack(route: Route) -> None:
            nonlocal commit_id
            commit_id = route.request.headers.get("idempotency-key", "")
            if route.request.headers.get("x-caseproof-review-request-id") != review_binding["review_request_id"]:
                raise RuntimeError("F5_DOCX_REVIEW_ID_NOT_BOUND_TO_COMMIT")
            commit_headers["authorization"] = route.request.headers.get("authorization", "")
            commit_headers["content-type"] = "application/json"
            response = route.fetch(timeout=180000)
            if response.status != 200:
                raise RuntimeError("F5_DOCX_SIGNED_ACTIVATION_REFUSED")
            data = response.json()
            version = str(UUID(data.get("version_id", "")))
            # Register derived Storage before dropping the network ACK:
            # the independent scoped M0.5 teardown removes this exact file.
            path = "/".join((
                org, case, registered[0]["document_id"], version, candidate_sha,
            ))
            record(key, run, "storage_file", path)
            route.abort("failed")

        page.route("**/dossier/editor/native/commit", lose_ack)
        native.get_by_role("button", name="5. Commit reviewed Word DOCX").click()
        expect(native.get_by_role(
            "button", name="Reconcile signed commit"
        )).to_be_enabled(timeout=90000)
        native.get_by_role("button", name="Reconcile signed commit").click()
        expect(native.get_by_text(
            "Activation reconciled", exact=False
        )).to_be_visible(timeout=180000)
        page.unroute("**/dossier/editor/native/commit", lose_ack)
        if len(commit_id) != 36:
            raise RuntimeError("F5_DOCX_IDEMPOTENCY_NOT_RECORDED")
        print("F5_DOCX_NATIVE_SIGNED_LOST_ACK_ACTIVATION_RECONCILED_PASSED", flush=True)

        native.get_by_role("button", name="6. Recheck activated draft").click()
        expect(page.get_by_role("heading", name="Review the evidence")).to_be_visible(
            timeout=180000
        )
        new_brief, new_snapshot = binding(page)
        if new_brief == old_brief or new_snapshot == old_snapshot:
            raise RuntimeError("F5_DOCX_RECHECK_OLD_VERSION_REUSED")
        print("F5_DOCX_NATIVE_SIGNED_RECHECK_NEW_VERSION_PASSED", flush=True)

        old_source_url = (
            f"{ORIGIN}/v2/matters/{case}/briefs/{old_brief}/dossier/history/"
            f"{old_snapshot}/sources/{old_brief}/original"
        )
        historical = page.request.get(old_source_url, headers=commit_headers)
        if (historical.status != 200
            or hashlib.sha256(historical.body()).hexdigest() != original_sha):
            raise RuntimeError("F5_DOCX_HISTORICAL_SOURCE_MUTATED")
        print("F5_DOCX_NATIVE_HISTORICAL_SOURCE_IMMUTABLE_PASSED", flush=True)

        fixture_editor_grant(key, run, owner, case, False)
        denied = page.request.post(
            f"{ORIGIN}/v2/matters/{case}/briefs/{old_brief}/dossier/editor/native/status",
            data={**review_binding, "byte_length": len(candidate), "request_id": commit_id},
            headers=commit_headers,
        )
        if denied.status not in (403, 404):
            raise RuntimeError("F5_DOCX_EDIT_REVOKE_STATUS_NOT_DENIED")
        expect(page.get_by_role(
            "heading", name="Review the evidence"
        )).to_be_visible(timeout=90000)
        print("F5_DOCX_NATIVE_SIGNED_EDIT_PERMISSION_REVOKE_DENIED_PASSED", flush=True)

        # A full page reload intentionally clears the in-memory bearer.
        # Sign in again before inspecting historical data; a missing session
        # is not evidence that the historical report is unavailable.
        page.goto(old_report)
        login(page)
        expect(page.get_by_role(
            "heading", name="Review the evidence"
        )).to_be_visible(timeout=90000)
        expect(page.get_by_text(
            "Historical report · read-only", exact=True
        )).to_be_visible(timeout=90000)
        print(
            "F5_DOCX_DOCUMENT_WIDE_SIGNED_ACTIVATION_RECHECK_REVOKE_COLD_REOPEN_PASSED",
            flush=True,
        )
    finally:
        # Independent outer cleanup also erases exact Storage objects, user,
        # matter and M0.5 ledger. Never leave this synthetic edit permission.
        fixture_editor_grant(key, run, owner, case, False)
