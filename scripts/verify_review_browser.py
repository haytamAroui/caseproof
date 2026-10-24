"""Real Chromium synthetic workbench flow. Fails if browser/dependencies unavailable."""

from __future__ import annotations

import json
import os
import shutil
import socket
import threading
import time
from pathlib import Path
from uuid import uuid4

import uvicorn
from playwright.sync_api import expect, sync_playwright

from application.dossiers.pack import verify_pack
from apps.api.synthetic_review_app import create_demo_app


def main() -> None:
    executable = (
        os.environ.get("CASEPROOF_CHROME") or shutil.which("google-chrome") or shutil.which("chromium")
    )
    app = create_demo_app()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            app, host="127.0.0.1", port=port, proxy_headers=False, access_log=False, log_level="error"
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("synthetic server did not start")
        time.sleep(0.05)
    output = Path(os.environ.get("CASEPROOF_REVIEW_SCREENSHOTS", "/tmp/caseproof-review-browser"))
    output.mkdir(parents=True, exist_ok=True)
    checks = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path=executable, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1536, "height": 1100}, accept_downloads=True)
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            url = f"http://127.0.0.1:{port}/demo"
            page.goto(url)
            expect(page.locator("#finding-count")).to_have_text("4")
            expect(page.locator("#source-text mark")).to_have_count(1)
            expect(page.locator("#missing-count")).to_have_text("1")
            expect(page.locator("#conflict-count")).to_have_text("1")
            checks.append("loaded_sources_conflicts_gaps")
            page.get_by_role("button", name="Save recommendation").click()
            expect(page.locator("#note-error")).to_contain_text("rationale")
            expect(page.locator("#note")).to_be_focused()
            page.locator("#action").select_option("correct")
            page.locator("#correction").fill("The supplier amount requires confirmation.")
            page.locator("#note").fill(
                "Review <script>window.__injected=true</script> against the original source."
            )
            page.locator("#save").click()
            expect(page.locator("#review-count")).to_have_text("1")
            expect(page.locator("#history")).to_contain_text("requires confirmation")
            assert page.evaluate("window.__injected === undefined")
            page.reload()
            expect(page.locator("#review-count")).to_have_text("1")
            expect(page.locator("#note")).to_have_value("")
            checks.append("save_correction_history_refresh_xss")
            page.locator("#note").fill("Unsaved rationale")
            page.locator(".finding").nth(1).click()
            expect(page.locator("#discard")).to_be_visible()
            page.locator("#stay").click()
            expect(page.locator("#note")).to_have_value("Unsaved rationale")
            page.locator(".finding").nth(1).click()
            page.locator("#discard-draft").click()
            expect(page.locator("#note")).to_have_value("")
            checks.append("unsaved_dialog_keyboard_focus")
            page.locator("#action").focus()
            page.locator("#action").press("ArrowDown")
            page.locator("#action").press("Enter")
            assert page.locator("#action").input_value() == "reject"
            page.locator("#note").fill("Retry the same recommendation after an uncertain acknowledgement.")

            def lost_ack(route):
                route.fetch()  # Server really commits, browser loses its acknowledgement.
                route.abort()

            page.route("**/demo/api/reviews", lost_ack)
            page.locator("#save").click()
            expect(page.locator("#failure")).to_contain_text("outcome unknown")
            expect(page.locator("#note")).to_be_disabled()
            expect(page.locator("#action")).to_be_disabled()
            page.unroute("**/demo/api/reviews", lost_ack)
            page.get_by_role("button", name="Retry save").click()
            expect(page.locator("#review-count")).to_have_text("2")
            expect(page.locator("#status")).to_contain_text("receipt recovered")
            checks.append("lost_ack_idempotent_recovery")
            state = page.request.get(url.replace("/demo", "/demo/api/state")).json()
            stale_item = state["snapshot"]["extraction"]["atoms"][0]["candidate_id"]
            body = {
                "request_id": str(uuid4()),
                "snapshot_hash": state["snapshot_hash"],
                "expected_revision": state["revision"],
                "item_id": stale_item,
                "kind": "request_evidence",
                "note": "Second reviewer requests evidence.",
                "correction": None,
            }
            response = page.request.post(
                url.replace("/demo", "/demo/api/reviews"),
                data=body,
                headers={"Origin": f"http://127.0.0.1:{port}", "X-Review-Session": state["session"]},
            )
            assert response.ok
            page.locator("#note").fill("Stale view review")
            page.locator("#save").click()
            expect(page.locator("#failure")).to_contain_text("revision changed")
            page.locator("#reload").click()
            page.locator("#discard-draft").click()
            expect(page.locator("#review-count")).to_have_text("3")
            checks.append("stale_review_requires_reload")
            with page.expect_download() as download:
                page.locator("#export").click()
            packed = output / "synthetic-review-pack.zip"
            download.value.save_as(packed)
            expected_hash = page.locator("#pack-hash").input_value()
            verification = verify_pack(packed.read_bytes(), expected_manifest=expected_hash)
            assert verification["review_events"] == 3 and not verification["approved"]
            checks.append("download_and_offline_verification")
            page.evaluate("highlight('A😀B café',1,2)")
            expect(page.locator("#source-text mark")).to_have_text("😀")
            page.reload()
            expect(page.locator("#finding-count")).to_have_text("4")
            page.locator("#findings .finding").filter(has_text="invoice ·").click()
            page.screenshot(path=str(output / "desktop.png"), full_page=True)
            if os.environ.get("CASEPROOF_BROWSER_LOG_SCREENSHOT") == "YES":
                import base64

                thumb = page.screenshot(type="jpeg", quality=55, full_page=False)
                print("SYNTHETIC_REVIEW_SCREENSHOT:" + base64.b64encode(thumb).decode())
            page.set_viewport_size({"width": 390, "height": 844})
            page.emulate_media(reduced_motion="reduce")
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.locator("#note").focus()
            assert page.locator("#note").evaluate("el => el.getBoundingClientRect().width") > 200
            page.screenshot(path=str(output / "mobile.png"), full_page=True)
            checks.append("unicode_highlight_mobile_reduced_motion")
            page.route(
                "**/demo/api/state",
                lambda route: route.fulfill(status=503, json={"error": "synthetic_outage"}),
            )
            page.reload()
            expect(page.locator("#failure")).to_contain_text("could not be loaded")
            page.unroute("**/demo/api/state")
            page.locator("#reload").click()
            expect(page.locator("#finding-count")).to_have_text("4")
            checks.append("load_failure_retry")
            expect(page.locator("#entity-suggestions .finding")).to_have_count(1)
            page.locator("#entity-suggestions .finding").click()
            expect(page.locator("#action")).to_have_value("confirm_boundary")
            expect(page.locator("#source-text mark")).to_have_count(1)
            page.locator("#note").fill("Reviewed this exact text boundary for the next extraction.")
            page.locator("#save").click()
            expect(page.locator("#review-count")).to_have_text("4")
            expect(page.locator("#history")).to_contain_text("Confirm evidence boundary")
            checks.append("audited_entity_boundary_confirmation")
            assert errors == [], errors
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
    (output / "browser-evidence.json").write_text(
        json.dumps({"checks": checks, "passed": len(checks), "synthetic_only": True}, indent=2)
    )
    print(json.dumps({"browser_checks_passed": len(checks), "checks": checks, "screenshots": str(output)}))


if __name__ == "__main__":
    main()
