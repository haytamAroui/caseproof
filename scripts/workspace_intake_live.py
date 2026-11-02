"""Genuine signed-browser F3 acceptance on owned synthetic fixtures only.

No traces, screenshots or raw credential/error output. The protected wrapper
owns Auth/org cleanup; register matter and exact object paths before transfer.
"""

from __future__ import annotations

import hashlib
import io
import os

from playwright.sync_api import expect

from scripts.m05_registry import record, rows
from scripts.verify_dev_live_review_roundtrip import _server_start, _server_stop
from scripts.verify_dev_live_txt_journey import admin_rpc
from scripts.workspace_browser_live import ORIGIN, WorkspaceBrowserAcceptance
from tests.fixtures.dossier_journey import dossier_bundle
from tests.fixtures.factory import SyntheticSource


def _exercise() -> None:
    if os.getenv("GITHUB_REF") not in {
        "refs/heads/feat/f3-complete-intake",
        "refs/heads/main",
        "refs/pull/175/merge",
        "refs/pull/176/merge",
    }:
        raise RuntimeError("F3_PROTECTED_BRANCH_REQUIRED")
    key, run, org = (
        os.environ[n] for n in ("CASEPROOF_DEV_AUTH_ADMIN_KEY", "CASEPROOF_P3_RUN_ID", "CASEPROOF_P3_ORG_ID")
    )
    bundle = list(dossier_bundle())
    # Owned real-format fixture: the printed label on physical PDF page 6 is 4.
    # Keep the original inventory and scanned second exhibit unchanged.
    from docx import Document
    from reportlab.pdfgen import canvas

    document = Document()
    document.add_paragraph("Zie Stuk 1, printed p. 4.")
    document.add_paragraph("Voir Pièce 2, printed p. 7.")
    draft = io.BytesIO()
    document.save(draft)
    bundle[0] = SyntheticSource(bundle[0].filename, bundle[0].role, bundle[0].media_type, draft.getvalue())
    rendered = io.BytesIO()
    six_pages = canvas.Canvas(rendered, pagesize=(595, 842), invariant=1)
    for number in range(1, 7):
        six_pages.drawString(60, 760, f"STUK 1 PRESERVED SYNTHETIC PDF PHYSICAL PAGE {number}")
        if number == 6:
            six_pages.drawString(60, 720, "PRINTED PAGE 4 - INSPECTED PDF PAGE 6")
        six_pages.showPage()
    six_pages.save()
    bundle[2] = SyntheticSource(bundle[2].filename, bundle[2].role, bundle[2].media_type, rendered.getvalue())
    proc = _server_start()
    acceptance = WorkspaceBrowserAcceptance("", "")
    page = acceptance.page
    page.set_default_timeout(45000)
    registered: list[dict] = []
    case = ""
    try:
        page.goto(ORIGIN + "/workspace/matters/new")
        acceptance.login(page)
        expect(page.get_by_role("heading", name="Create a private matter")).to_be_visible()
        page.get_by_label("Organization", exact=True).select_option(org)
        page.get_by_label("Matter title").fill("Owned synthetic F3 dossier")
        with page.expect_response(lambda r: r.url.endswith("/intake/matters")) as created:
            page.get_by_role("button", name="Create matter", exact=True).click()
        if created.value.status != 200:
            raise RuntimeError("F3_BROWSER_CREATE_FAILED")
        case = created.value.json()["case_id"]
        record(key, run, "matter", case, "CREATED")
        expect(page.get_by_role("heading", name="Preserve the source bundle")).to_be_visible()
        labels = ("DOCX draft", "UTF-8 inventory", "First PDF exhibit", "Second PDF exhibit or scan")
        for label, source in zip(labels, bundle, strict=True):
            page.get_by_label(label, exact=True).set_input_files(
                {"name": source.filename, "mimeType": source.media_type, "buffer": source.content}
            )
        page.get_by_label(labels[-1], exact=True).set_input_files(
            {"name": bundle[-1].filename, "mimeType": "application/pdf", "buffer": b"%PDF-1.7 corrupt"}
        )
        with page.expect_response(lambda r: r.url.endswith("/reservations")) as rejected:
            page.get_by_role("button", name="Preserve or reconcile originals").click()
        if rejected.value.status != 422:
            raise RuntimeError("F3_CORRUPT_FINAL_NOT_REJECTED")
        expect(page.get_by_text("No completed intake receipt was received.", exact=False)).to_be_visible()
        print("F3_BROWSER_CORRUPT_FINAL_PREFLIGHT_REJECTED", flush=True)
        page.get_by_label(labels[-1], exact=True).set_input_files(
            {"name": bundle[-1].filename, "mimeType": bundle[-1].media_type, "buffer": bundle[-1].content}
        )

        def own_reservation(route) -> None:
            response = route.fetch(timeout=180000)
            print(f"F3_RESERVATION_HTTP_{response.status}", flush=True)
            if response.status != 200:
                raise RuntimeError("F3_RESERVATION_FAILED")
            rows = response.json()["sources"]
            if len(rows) != 4:
                raise RuntimeError("F3_RESERVATION_NOT_FOUR")
            registered[:] = rows
            for row, source in zip(rows, bundle, strict=True):
                if row["sha256"] != hashlib.sha256(source.content).hexdigest():
                    raise RuntimeError("F3_RESERVATION_HASH_DIFFERS")
                path = "/".join((org, case, row["document_id"], row["version_id"], row["sha256"]))
                record(key, run, "storage_file", path)
            route.fulfill(response=response)

        page.route("**/intake/matters/*/reservations", own_reservation)
        count = 0
        transfer_status = 0

        def lose_first_ack(route) -> None:
            nonlocal count, transfer_status
            count += 1
            if count == 1:
                response = route.fetch(timeout=180000)
                transfer_status = response.status
                print(f"F3_FIRST_TRANSFER_HTTP_{response.status}", flush=True)
                if response.status != 200:
                    route.fulfill(response=response)
                    return
                route.abort("failed")  # Actual server writes committed; browser gets no acknowledgement.
            else:
                route.continue_()

        page.route("**/intake/matters/*/sources", lose_first_ack)
        page.get_by_role("button", name="Preserve or reconcile originals").click()
        expect(page.get_by_text("No completed intake receipt was received.", exact=False)).to_be_visible(
            timeout=180000
        )
        if transfer_status != 200:
            raise RuntimeError(f"F3_REAL_TRANSFER_HTTP_{transfer_status}")
        original_ids = [r["version_id"] for r in registered]
        with page.expect_response(lambda r: r.url.endswith("/sources"), timeout=180000) as repeated:
            page.get_by_role("button", name="Preserve or reconcile originals").click()
        print(f"F3_REPEATED_TRANSFER_HTTP_{repeated.value.status}", flush=True)
        if repeated.value.status != 200:
            raise RuntimeError("F3_REPEATED_TRANSFER_FAILED")
        expect(
            page.get_by_text("All originals passed fresh authorized hash readback.", exact=False)
        ).to_be_visible(timeout=180000)
        if [r["version_id"] for r in registered] != original_ids:
            raise RuntimeError("F3_RETRY_DUPLICATED_ORIGINALS")
        print("F3_REAL_UPLOAD_LOST_ACK_EXACT_READBACK_REPLAY_PASSED", flush=True)
        _server_stop(proc)
        proc = _server_start()
        page.reload()
        acceptance.login(page)
        expect(
            page.get_by_text("All originals passed fresh authorized hash readback.", exact=False)
        ).to_be_visible(timeout=180000)
        page.get_by_role("link", name="Review inventory and page mappings").click()
        expect(page.get_by_role("heading", name="Confirm inventory")).to_be_visible()
        expect(page.get_by_label("Preserved exhibit").first).to_be_visible(timeout=120000)
        page.get_by_label("Preserved exhibit").first.select_option(registered[2]["version_id"])
        page.get_by_role("button", name="Add alternative source binding").first.click()
        expect(page.get_by_label("Preserved exhibit")).to_have_count(5)
        page.get_by_role("button", name="Remove alternative binding for stuk 1", exact=True).last.click()
        expect(page.get_by_label("Preserved exhibit")).to_have_count(4)
        page.get_by_label("Page label", exact=True).first.fill("12")
        page.get_by_label("Physical PDF page", exact=True).first.fill("1")
        page.get_by_label("Mapping rationale").first.fill("Inspected synthetic PDF page")
        page.get_by_role("button", name="Add inspected mapping").first.click()
        page.get_by_label("Page label", exact=True).first.fill("4")
        page.get_by_label("Physical PDF page", exact=True).first.fill("6")
        page.get_by_label("Mapping rationale").first.fill("Inspected printed four on physical PDF page six")
        page.get_by_role("button", name="Add inspected mapping").first.click()
        page.get_by_role("checkbox").check()
        page.get_by_role("button", name="Save inventory confirmation").click()
        expect(
            page.get_by_text("Inventory confirmation saved and freshly read back.", exact=False)
        ).to_be_visible(timeout=120000)
        page.reload()
        acceptance.login(page)
        expect(page.get_by_role("button", name="Run explicit check")).to_be_enabled(timeout=120000)
        page.get_by_role("button", name="Run explicit check").click()
        expect(page.get_by_role("heading", name="Review the evidence")).to_be_visible(timeout=180000)
        expect(page.get_by_text("PDF page 6 of 6", exact=True)).to_be_visible(timeout=180000)
        expect(page.get_by_text("Source page rendered.", exact=True)).to_be_visible(timeout=180000)
        print("F3_SIGNED_UPLOAD_CONFIRMED_PRINTED_4_PDF_6_REPORT_VIEWER_PASSED", flush=True)
        if os.getenv("CASEPROOF_F4_BROWSER_LIVE") == "YES":
            reviewer = page.get_by_role("region", name="Human review")
            expect(reviewer.get_by_role("heading", name="Human decision and durable receipt")).to_be_visible(timeout=60000)
            expect(page.get_by_role("heading", name="Preserved DOCX reference context")).to_be_visible()
            for checkbox in reviewer.get_by_role("checkbox").all():
                checkbox.check()
            reviewer.get_by_label("Rationale (required, visible to authorized reviewers)").fill(
                "Reviewed original synthetic page and draft context"
            )
            requests = [0]
            def lost_review_ack(route) -> None:
                requests[0] += 1
                response = route.fetch(timeout=90000)
                if response.status != 200:
                    raise RuntimeError("F4_REVIEW_WRITE_REJECTED")
                route.abort("failed")
            page.route("**/dossier/reviews", lost_review_ack)
            reviewer.get_by_role("button", name="Save human decision").click()
            expect(reviewer.get_by_role("button", name="Reconcile durable receipt")).to_be_visible(timeout=90000)
            reviewer.get_by_role("button", name="Reconcile durable receipt").click()
            expect(reviewer.get_by_text(
                "The exact decision is persisted in the authorized review ledger."
            )).to_be_visible(timeout=90000)
            page.unroute("**/dossier/reviews", lost_review_ack)
            if requests[0] != 1:
                raise RuntimeError("F4_REVIEW_NOT_EXACTLY_ONCE")
            print("F4_GENUINE_SIGNED_LOST_ACK_DURABLE_REVIEW_RECONCILED_PASSED", flush=True)
            _server_stop(proc)
            proc = _server_start()
            page.reload()
            acceptance.login(page)
            expect(page.get_by_role("heading", name="Review the evidence")).to_be_visible(timeout=90000)
            expect(page.get_by_role("list", name="Saved review history")).to_contain_text(
                "Reviewed original synthetic page and draft context", timeout=90000
            )
            expect(page.get_by_text("PDF page 6 of 6", exact=True)).to_be_visible(timeout=90000)
            print("F4_GENUINE_REVIEW_COLD_REOPEN_SOURCE_AND_RECEIPT_PASSED", flush=True)

        print("F3_BROWSER_COLD_PROCESS_SIGNIN_INVENTORY_RECEIPT_REOPEN_EXPLICIT_CHECK_PASSED", flush=True)
        for role in ("ungranted", "foreign"):
            context = acceptance.browser.new_context()
            denied = context.new_page()
            try:
                denied.goto(ORIGIN + f"/workspace/matters/{case}/sources")
                with denied.expect_response(lambda r: r.url.endswith("/intake/matters/" + case)) as response:
                    acceptance.login(denied, role)
                if response.value.status not in (403, 404):
                    raise RuntimeError("F3_UNGRANTED_INTAKE_NOT_DENIED")
                expect(denied.get_by_role("button", name="Sign in", exact=True)).to_be_visible()
            finally:
                context.close()
        if acceptance.external or page.evaluate("() => localStorage.length + sessionStorage.length"):
            raise RuntimeError("F3_BROWSER_EGRESS_OR_PERSISTENCE")
        owner = next(
            r["resource_id"].split(":", 1)[1]
            for r in rows(key, run)
            if r["resource_type"] == "auth_user"
            and r["resource_id"].startswith("owner:")
            and "@" not in r["resource_id"]
        )
        admin_rpc(key, "revoke", {"p_run": run, "p_owner": owner, "p_case": case})
        page.goto(ORIGIN + f"/workspace/matters/{case}/sources")
        acceptance.login(page)
        expect(page.get_by_role("button", name="Sign in", exact=True)).to_be_visible(timeout=120000)
        expect(page.get_by_role("heading", name="Preserve the source bundle")).to_have_count(0)
        print("F3_GENUINE_BROWSER_CREATE_INTAKE_CONFIRM_COLD_RESUME_DENIAL_REVOCATION_PASSED", flush=True)
    finally:
        acceptance.close()
        _server_stop(proc)


def main() -> None:
    try:
        _exercise()
    except Exception:
        # Playwright errors can contain fill arguments. The outer fixture
        # wrapper serializes exception text, so expose only a fixed category.
        raise RuntimeError("F3_PROTECTED_BROWSER_ACCEPTANCE_FAILED") from None
