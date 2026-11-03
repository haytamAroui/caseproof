"""Genuine signed-browser F3 acceptance on owned synthetic fixtures only.

No traces, screenshots or raw credential/error output. The protected wrapper
owns Auth/org cleanup; register matter and exact object paths before transfer.
"""

from __future__ import annotations

import hashlib
import io
import os
import re

from playwright.sync_api import Route, expect

from scripts.m05_registry import record, rows
from scripts.verify_dev_live_review_roundtrip import _server_start, _server_stop
from scripts.verify_dev_live_txt_journey import admin_rpc
from scripts.workspace_browser_live import ORIGIN, WorkspaceBrowserAcceptance
from tests.fixtures.dossier_journey import dossier_bundle
from tests.fixtures.factory import SyntheticSource

_LIVE_STAGE = "START"


def _stage(name: str) -> None:
    global _LIVE_STAGE
    if not re.fullmatch(r"[A-Z0-9_]+", name):
        raise ValueError("invalid acceptance stage")
    _LIVE_STAGE = name
    print("F5_STAGE_" + name, flush=True)


def _exercise() -> None:
    if os.getenv("GITHUB_REF") not in {
        "refs/heads/feat/f3-complete-intake",
        "refs/heads/main",
        "refs/pull/175/merge",
        "refs/pull/176/merge",
        "refs/pull/177/merge", "refs/heads/feat/f5-correction-recheck-workspace",
        "refs/pull/178/merge", "refs/pull/182/merge", "refs/pull/183/merge",
        "refs/heads/feat/f6-reviewed-export-and-historical-reopen",
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
    if os.getenv("CASEPROOF_F5_BROWSER_LIVE") == "YES":
        target = document.add_paragraph("Zie Stu")
        target.add_run("k 1, printed p. 4.").italic = True
    else:
        document.add_paragraph("Zie Stuk 1, printed p. 4.")
    document.add_paragraph("Voir Pièce 2, printed p. 7.")
    if os.getenv("CASEPROOF_F5_BROWSER_LIVE") == "YES":
        # Unrelated structures must not prevent a simple exact target. Keep the
        # table free of references so existing source mappings stay unchanged.
        document.add_table(rows=1, cols=1).cell(0, 0).text = "Synthetic background table"
        background = document.add_paragraph("Unrelated ")
        background.add_run("formatted text").bold = True
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
        _stage("CREATE_MATTER_SIGNIN")
        page.goto(ORIGIN + "/workspace/matters/new")
        acceptance.login(page)
        expect(page.get_by_role("heading", name="Create a private matter")).to_be_visible()
        _stage("SELECT_ORGANIZATION")
        page.get_by_label("Organization", exact=True).select_option(org)
        page.get_by_label("Matter title").fill("Owned synthetic F3 dossier")
        def own_created_matter(route: Route) -> None:
            nonlocal case
            response = route.fetch(timeout=90000)
            if response.status != 200:
                route.fulfill(response=response)
                return
            _stage("CAPTURE_CREATED_MATTER")
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("case_id"), str):
                raise RuntimeError("F3_CREATE_RESPONSE_INVALID")
            case = payload["case_id"]
            _stage("REGISTER_CREATED_MATTER")
            record(key, run, "matter", case, "CREATED")
            route.fulfill(response=response)
        page.route("**/v2/workspace/intake/matters", own_created_matter)
        _stage("CREATE_MATTER_REQUEST")
        with page.expect_response(lambda r: r.url.endswith("/intake/matters")) as created:
            page.get_by_role("button", name="Create matter", exact=True).click()
        if created.value.status != 200 or not case:
            raise RuntimeError("F3_BROWSER_CREATE_FAILED")
        page.unroute("**/v2/workspace/intake/matters", own_created_matter)
        expect(page.get_by_role("heading", name="Preserve the source bundle")).to_be_visible()
        _stage("SELECT_ORIGINALS")
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

        f6_old = None
        f6_new = None
        if os.getenv("CASEPROOF_F6_BROWSER_LIVE") == "YES":
            if (os.getenv("CASEPROOF_F4_BROWSER_LIVE") != "YES"
                    or os.getenv("CASEPROOF_F5_BROWSER_LIVE") != "YES"):
                raise RuntimeError("F6_REQUIRES_REAL_F4_F5")
            from scripts.workspace_f6_live import binding, export_one, fixture_export_grant
            owner = next(
                r["resource_id"].split(":", 1)[1]
                for r in rows(key, run)
                if r["resource_type"] == "auth_user"
                and r["resource_id"].startswith("owner:")
                and "@" not in r["resource_id"]
            )
            fixture_export_grant(key, run, owner, case, True)
            report_url = page.url
            old_brief, old_snapshot = binding(page)
            _stage("OLD_REVIEWED_RELEASE")
            f6_old = export_one(
                page, acceptance, case=case, brief=old_brief,
                snapshot=old_snapshot, pdf_version=registered[2]["version_id"],
                pdf_original=bundle[2].content, expect_reference="Stuk 1",
            )
            page.goto(report_url)
            acceptance.login(page)
            expect(page.get_by_role("heading", name="Review the evidence")).to_be_visible(timeout=90000)

        if os.getenv("CASEPROOF_F5_BROWSER_LIVE") == "YES":
            previous_url = page.url
            correction = page.get_by_role("region", name="Correction preview and recheck", exact=True)
            expect(correction.get_by_label("Exact original text")).to_be_visible(timeout=90000)
            before = correction.get_by_label("Exact original text").input_value()
            if "1" not in before:
                raise RuntimeError("F5_SYNTHETIC_REFERENCE_DIFFERS")
            _stage("EXACT_REFERENCE_PREVIEW")
            # F6's second release needs a newly checked *mapped* reference:
            # an edit to the reference's presentation preserves exhibit 1
            # while creating a genuinely new immutable draft version.
            # Renumbering to Stuk 2 would deliberately make its identity
            # unconfirmed, and the reviewer must abstain rather than fabricate
            # visual inspection of a non-existent source page.
            replacement = (
                before.replace("1", "1 ", 1)
                if os.getenv("CASEPROOF_F6_BROWSER_LIVE") == "YES"
                else before.replace("1", "2", 1)
            )
            if replacement == before:
                raise RuntimeError("F6_CORRECTION_NOT_CHANGED")
            correction.get_by_label("Replacement text").fill(replacement)
            correction.get_by_role("button", name="Validate exact preview").click()
            expect(correction.get_by_text("Proposed change (not committed)", exact=True)).to_be_visible(timeout=90000)
            writes = [0]
            correction_request = {}
            correction_headers = {}
            correction_base = [""]
            def lose_correction_ack(route: Route) -> None:
                writes[0] += 1
                correction_request.update(route.request.post_data_json)
                correction_headers['Authorization'] = route.request.headers['authorization']
                correction_base[0] = route.request.url.removesuffix('/corrections/commit')
                response = route.fetch(timeout=180000)
                if response.status != 200:
                    raise RuntimeError("F5_COMMIT_REJECTED")
                route.abort("failed")
            page.route("**/corrections/commit", lose_correction_ack)
            _stage("COMMIT_ACTIVATE")
            correction.get_by_role("button", name="Explicitly commit and activate new draft").click()
            correction.get_by_role("button", name="Reconcile identical operation").click(timeout=180000)
            _stage("RECHECK_COMPARE")
            correction.get_by_role("button", name="Recheck activated draft", exact=True).click(timeout=90000)
            expect(correction.get_by_role("heading", name="Previous report", exact=True)).to_be_visible(timeout=180000)
            expect(correction.get_by_role("heading", name="Rechecked report", exact=True)).to_be_visible(timeout=180000)
            if writes[0] != 1:
                raise RuntimeError("F5_DUPLICATE_COMMIT")
            old_original = page.request.get(
                correction_base[0] + '/history/' + correction_request['snapshot_hash'] +
                '/sources/' + registered[0]['version_id'] + '/original', headers=correction_headers,
            )
            if old_original.status != 200 or hashlib.sha256(old_original.body()).hexdigest() != hashlib.sha256(bundle[0].content).hexdigest():
                raise RuntimeError("F5_ORIGINAL_CHANGED_OR_UNAVAILABLE")
            print("F5_SIGNED_ORIGINAL_SHA256_UNCHANGED_PASSED", flush=True)
            print("F5_SPLIT_FORMATTED_REFERENCE_AND_UNRELATED_TABLE_CORRECTION_PASSED", flush=True)
            page.unroute("**/corrections/commit", lose_correction_ack)
            print("F5_SIGNED_PREVIEW_LOST_ACK_COMMIT_RECONCILE_RECHECK_COMPARE_PASSED", flush=True)
            _server_stop(proc)
            proc = _server_start()
            _stage("COLD_REOPEN")
            page.goto(previous_url)
            acceptance.login(page)
            expect(page.get_by_text("Historical report · read-only", exact=True)).to_be_visible(timeout=90000)
            recovery = page.get_by_role("region", name="Correction operation recovery", exact=True)
            recovery.get_by_role("button", name="Recheck activated draft", exact=True).click(timeout=90000)
            expect(page.get_by_role("heading", name="Review the evidence")).to_be_visible(timeout=180000)
            expect(page.get_by_text("No recorded human decision for this reference.", exact=True)).to_be_visible(timeout=90000)
            print("F5_SIGNED_COLD_REOPEN_ACTIVATED_DRAFT_INDEPENDENT_REVIEW_PASSED", flush=True)

            if os.getenv("CASEPROOF_F6_BROWSER_LIVE") == "YES":
                from scripts.workspace_f6_live import (
                    binding,
                    deny_after_revocation,
                    export_one,
                    fixture_export_grant,
                    reconfirm_corrected_bundle,
                    reopen_old,
                )
                if not f6_old:
                    raise RuntimeError("F6_OLD_RELEASE_MISSING")
                # Correction changed the bundle signature. Under the
                # evidence-first contract, its previous inventory/page
                # confirmation is stale: neither prior mapping nor human
                # review may be silently inherited by the new draft.
                _stage("RECONFIRM_CORRECTED_BUNDLE")
                reconfirm_corrected_bundle(
                    page, case=case, registered=registered
                )
                # Rechecking under the newly confirmed bundle creates a
                # new report; the reviewer must inspect the preserved source
                # and save an independent disposition before another release.
                _stage("NEW_DRAFT_INDEPENDENT_REVIEW")
                reviewer = page.get_by_role("region", name="Human review")
                expect(reviewer.get_by_role("button", name="Save human decision")).to_be_visible(timeout=120000)
                for checkbox in reviewer.get_by_role("checkbox").all():
                    checkbox.check()
                reviewer.get_by_label(
                    "Rationale (required, visible to authorized reviewers)"
                ).fill("Independent review of new synthetic draft after correction")
                reviewer.get_by_role("button", name="Save human decision").click()
                expect(page.get_by_role("list", name="Saved review history")).to_contain_text(
                    "Independent review of new synthetic draft after correction", timeout=90000
                )
                new_brief, new_snapshot = binding(page)
                _stage("NEW_RECHECKED_RELEASE")
                f6_new = export_one(
                    page, acceptance, case=case, brief=new_brief,
                    snapshot=new_snapshot, pdf_version=registered[2]["version_id"],
                    pdf_original=bundle[2].content, expect_reference="Stuk 1",
                )
                _server_stop(proc)
                proc = _server_start()
                _stage("HISTORICAL_RELEASE_COLD_REOPEN")
                reopen_old(page, acceptance, case=case, old=f6_old, new=f6_new)
                # Separate export grant can be revoked while matter reader
                # remains signed in; no old release may bypass live grants.
                fixture_export_grant(key, run, owner, case, False)
                deny_after_revocation(page, case=case, old=f6_old)
                page.goto(f6_old["page"])
                acceptance.login(page)
                expect(page.get_by_text("Release history is unavailable or access was revoked.")).to_be_visible(
                    timeout=90000
                )
                expect(page.get_by_role("button", name="End session")).to_be_visible()
                print("F6_SIGNED_EXPORT_ONLY_REVOKE_READER_SESSION_PRESERVED_PASSED", flush=True)
                # Restore the ephemeral export grant for the later whole-matter
                # revoke test; the outer fixture teardown always destroys it.
                fixture_export_grant(key, run, owner, case, True)
                print("F6_REAL_SIGNED_OLD_NEW_RELEASE_COLD_REOPEN_PASSED", flush=True)

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
        if os.getenv("CASEPROOF_F6_BROWSER_LIVE") == "YES" and f6_old:
            from scripts.workspace_f6_live import deny_after_revocation
            deny_after_revocation(page, case=case, old=f6_old)
        if os.getenv("CASEPROOF_F5_BROWSER_LIVE") == "YES":
            denied_recovery = page.request.get(
                correction_base[0] + '/snapshots/' + correction_request['snapshot_hash'] +
                '/references/' + correction_request['reference_id'] + '/correction-operations',
                headers=correction_headers,
            )
            if denied_recovery.status not in (403, 404):
                raise RuntimeError("F5_REVOKED_RECOVERY_NOT_DENIED")
            print("F5_GENUINE_SIGNED_REVOKED_RECOVERY_DENIED_PASSED", flush=True)
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
    except Exception as error:
        category = str(error) if isinstance(error, RuntimeError) else ""
        print("F5_FAILURE_STAGE_" + _LIVE_STAGE + "_TYPE_" + type(error).__name__, flush=True)
        if len(category) <= 128 and re.fullmatch(r"F[3456]_[A-Z0-9_]+", category):
            print("F5_FAILURE_CATEGORY_" + category, flush=True)
        # Playwright errors can contain fill arguments. The outer fixture
        # wrapper serializes exception text, so expose only a fixed category.
        raise RuntimeError("F3_PROTECTED_BROWSER_ACCEPTANCE_FAILED") from None
