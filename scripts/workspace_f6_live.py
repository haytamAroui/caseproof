"""F6 genuine signed export acceptance, synthetic owned fixtures only.

Integrated after the real F3/F4 review and F5 correction. Never logs bearer,
credentials, raw text, document bytes or provider response bodies.
"""
from __future__ import annotations

import hashlib
import http.client
import io
import json
import os
from typing import Any
from urllib.parse import parse_qs, urlsplit
from uuid import UUID
from zipfile import ZipFile

from docx import Document
from playwright.sync_api import Page, Route, expect
from pypdf import PdfReader

from scripts.workspace_browser_live import ORIGIN, WorkspaceBrowserAcceptance

DEV_HOST = "ldwmocpxwskvhoojndrd.supabase.co"


def fixture_export_grant(key: str, run: str, owner: str, case: str, enabled: bool) -> None:
    """Only admin for the exact registered ephemeral owner+case may toggle."""
    if not (key.startswith("sb_secret_") or key.startswith("eyJ")):
        raise RuntimeError("F6_ADMIN_KEY_TYPE")
    payload = {
        "p_run": str(UUID(run)), "p_owner": str(UUID(owner)),
        "p_case": str(UUID(case)), "p_enable": enabled,
    }
    conn = http.client.HTTPSConnection(DEV_HOST, timeout=20)
    headers = {"apikey": key, "Content-Type": "application/json"}
    if key.startswith("eyJ"):
        headers["Authorization"] = "Bearer " + key
    try:
        conn.request(
            "POST", "/rest/v1/rpc/caseproof_f6_fixture_export_grant",
            json.dumps(payload).encode(), headers,
        )
        res = conn.getresponse()
        status, raw = res.status, res.read(1025)
    except (OSError, http.client.HTTPException):
        raise RuntimeError("F6_ADMIN_GRANT_UNAVAILABLE") from None
    finally:
        conn.close()
    if status != 200 or len(raw) > 1024 or raw.strip() != b"true":
        raise RuntimeError("F6_ADMIN_GRANT_FAILED")


def binding(page: Page) -> tuple[str, str]:
    """Read only the current synthetically generated address; no page guessing."""
    url = urlsplit(page.url)
    brief = url.path.rsplit("/briefs/", 1)[-1].split("/", 1)[0]
    snapshot = parse_qs(url.query).get("snapshot", [""])[0]
    if not 0 < len(brief) <= 64 or not (
        len(snapshot) == 64 and all(x in "0123456789abcdef" for x in snapshot)
    ):
        raise RuntimeError("F6_BROWSER_BINDING_UNAVAILABLE")
    return brief, snapshot


def scoped_base(case: str, brief: str) -> str:
    return f"{ORIGIN}/v2/matters/{case}/briefs/{brief}/dossier"


def reconfirm_corrected_bundle(
    page: Page, *, case: str, registered: list[dict[str, Any]],
) -> None:
    """Explicit fresh inventory attestation after a changed draft signature.

    The former confirmation was valid for an older bundle; it is never
    silently carried forward or treated as reviewer evidence for this draft.
    The physical page was previously verified from immutable original bytes.
    """
    # Avoid a second cold browser reload: navigation to a protected form
    # must preserve the already authenticated session, not reacquire a user
    # or accidentally discard the newly checked review context.
    def observe_intake(response: Any) -> None:
        if response.url.split("?", 1)[0].endswith(
            f"/v2/workspace/intake/matters/{case}"
        ):
            print(f"F6_CHANGED_INTAKE_READ_HTTP_{response.status}", flush=True)
            if response.status == 200:
                try:
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise ValueError("unexpected intake shape")
                    # Fixed metadata only: never log case IDs, source IDs,
                    # inventory text, document bytes or user credentials.
                    print("F6_CHANGED_INTAKE_CONTRACT_" + json.dumps({
                        "sources": len(payload.get("sources", [])),
                        "entries": len(payload.get("entries", [])),
                        "readback_complete": payload.get("readback_complete"),
                        "confirmed": payload.get("confirmation_id") is not None,
                        "draft_count": sum(
                            row.get("role") == "draft"
                            for row in payload.get("sources", [])
                            if isinstance(row, dict)
                        ),
                        "unique_source_versions": len({
                            row.get("version_id") for row in payload.get("sources", [])
                            if isinstance(row, dict)
                        }),
                        "unique_source_names": len({
                            row.get("filename") for row in payload.get("sources", [])
                            if isinstance(row, dict)
                        }),
                        "all_entries_unbound": all(
                            isinstance(row, dict) and row.get("source_version_id") is None
                            for row in payload.get("entries", [])
                        ),
                    }, sort_keys=True), flush=True)
                except (ValueError, TypeError):
                    print("F6_CHANGED_INTAKE_CONTRACT_UNREADABLE", flush=True)

    page.on("response", observe_intake)
    link = page.get_by_role(
        "link", name="Reconfirm inventory and page mappings"
    )
    expect(link).to_be_visible(timeout=15000)
    link.click()
    print("F6_INVENTORY_NAVIGATION_STARTED", flush=True)
    heading = page.get_by_role("heading", name="Confirm inventory")
    print("F6_INVENTORY_HEADING_PRESENT_" + str(heading.is_visible()).upper(), flush=True)
    expect(heading).to_be_visible(timeout=30000)
    print("F6_INVENTORY_HEADING_CONFIRMED", flush=True)
    bindings = page.get_by_label("Preserved exhibit", exact=True)
    print("F6_INVENTORY_RENDERED_" + json.dumps({
        "selectors": bindings.count(),
        "entry_legends": page.locator("fieldset > legend").count(),
        "unavailable": page.get_by_text(
            "Inventory is unavailable. No cached confirmation can be submitted.",
            exact=True,
        ).is_visible(),
        "incomplete": page.get_by_text(
            "Preserve all originals before confirming inventory.",
            exact=True,
        ).is_visible(),
    }, sort_keys=True), flush=True)
    # Rights-cleared inventory intentionally has four identities: Stuk 1,
    # Pièce 2, missing Stuk 3 and ambiguous Stuk 4. The final two must not
    # gain invented source identities just to make an export pass.
    try:
        expect(bindings).to_have_count(4, timeout=15000)
    except AssertionError:
        # Report fixed UI-state categories after the request completes, not
        # just the empty form state observed while React Query is loading.
        # Never print browser HTML, inventory text, IDs or error bodies.
        print("F6_INVENTORY_POST_READ_UI_" + json.dumps({
            "selectors": bindings.count(),
            "heading": heading.is_visible(),
            "entry_count_4": page.get_by_text(
                "Inventory entries (4)", exact=True,
            ).is_visible(),
            "loading": page.get_by_text(
                "Reading inventory and current revision…", exact=True,
            ).is_visible(),
            "unavailable": page.get_by_text(
                "Inventory is unavailable. No cached confirmation can be submitted.",
                exact=True,
            ).is_visible(),
            "incomplete": page.get_by_text(
                "Preserve all originals before confirming inventory.",
                exact=True,
            ).is_visible(),
            "comboboxes": page.get_by_role("combobox").count(),
        }, sort_keys=True), flush=True)
        raise
    print("F6_INVENTORY_FOUR_SELECTOR_COUNT_CONFIRMED", flush=True)
    for index, expected in ((0, registered[2]["version_id"]),
                            (1, registered[3]["version_id"])):
        # Presence is checked without logging potentially sensitive source IDs.
        available = bindings.nth(index).locator("option").evaluate_all(
            "(options, id) => options.some(option => option.value === id)",
            expected,
        )
        print(f"F6_INVENTORY_OPTION_{index}_PRESENT_{str(available).upper()}", flush=True)
        if not available:
            raise RuntimeError("F6_CONFIRMED_EXHIBIT_OPTION_MISSING")
        bindings.nth(index).select_option(expected)
        print(f"F6_INVENTORY_OPTION_{index}_SELECTED", flush=True)
    print("F6_INVENTORY_FOUR_IDENTITIES_WITH_UNRESOLVED_SOURCES_PASSED", flush=True)
    # Source PDF page 6 was independently rendered, downloaded and SHA-256
    # checked earlier in this same signed journey. Do not infer a page offset.
    page.get_by_label("Page label", exact=True).first.fill("4")
    page.get_by_label("Physical PDF page", exact=True).first.fill("6")
    page.get_by_label("Mapping rationale").first.fill(
        "Inspected unchanged synthetic original: printed 4 on physical PDF page 6"
    )
    page.get_by_role("button", name="Add inspected mapping").first.click()
    page.get_by_role("checkbox").check()
    page.get_by_role("button", name="Save inventory confirmation").click()
    expect(
        page.get_by_text(
            "Inventory confirmation saved and freshly read back.", exact=False
        )
    ).to_be_visible(timeout=120000)
    print("F6_CHANGED_BUNDLE_FRESH_INVENTORY_CONFIRMATION_PASSED", flush=True)
    page.get_by_role("button", name="Run explicit check").click()
    expect(page.get_by_role("heading", name="Review the evidence")).to_be_visible(
        timeout=180000
    )
    expect(page.get_by_text("PDF page 6 of 6", exact=True)).to_be_visible(
        timeout=180000
    )
    expect(page.get_by_text("Source page rendered.", exact=True)).to_be_visible(
        timeout=180000
    )
    print("F6_FRESH_CHECK_RESTORED_VERIFIED_PHYSICAL_MAPPING_PASSED", flush=True)


def export_one(
    page: Page, acceptance: WorkspaceBrowserAcceptance,
    *, case: str, brief: str, snapshot: str, pdf_version: str, pdf_original: bytes,
    expect_reference: str,
) -> dict[str, Any]:
    """A real browser issues the POST and receives the exact downloaded DOCX."""
    url = f"{ORIGIN}/workspace/matters/{case}/exports?brief={brief}&snapshot={snapshot}"
    page.goto(url)
    acceptance.login(page)
    expect(page.get_by_role("heading", name="Reviewed exports and history")).to_be_visible(timeout=90000)
    expect(page.get_by_role("heading", name="Preview release scope")).to_be_visible(timeout=90000)
    preview_state = page.locator("section[aria-label='Release readiness']")
    preview_button = page.get_by_role("button", name="Review release details")
    expect(preview_button).to_be_visible(timeout=90000)
    if page.get_by_label("I acknowledge this release is partial and some detected findings remain unreviewed.").count() == 1:
        release_type = "partial_review"
        acknowledge = page.get_by_label("I acknowledge this release is partial and some detected findings remain unreviewed.")
        expect(preview_button).to_be_disabled()
        acknowledge.check()
    else:
        release_type = "complete_review"
    expect(preview_button).to_be_enabled(timeout=90000)
    preview_button.click()
    expect(page.get_by_role("heading", name="Confirm this exact reviewed release")).to_be_visible()
    action = page.get_by_role("button", name="Acknowledge and create release")
    expect(action).to_be_enabled()
    previous = page.url
    writes = [0]
    captured: dict[str, Any] = {}

    def lost_release_ack(route: Route) -> None:
        if route.request.method != "POST":
            route.continue_()
            return
        writes[0] += 1
        captured["authorization"] = route.request.headers["authorization"]
        response = route.fetch(timeout=180000)
        if response.status != 200:
            raise RuntimeError("F6_SIGNED_RELEASE_REJECTED")
        receipt = response.json()
        if receipt.get("state") != "released":
            raise RuntimeError("F6_RELEASE_RECEIPT_MISSING")
        captured["record"] = receipt
        route.abort("failed")

    page.route("**/dossier/releases", lost_release_ack)
    action.click()
    expect(page.get_by_role("button", name="Reconcile previous release")).to_be_visible(timeout=90000)
    page.get_by_role("button", name="Reconcile previous release").click()
    expect(page.get_by_text("The previously submitted release was found and recovered.")).to_be_visible(timeout=90000)
    page.unroute("**/dossier/releases", lost_release_ack)
    if writes != [1] or "record" not in captured or "authorization" not in captured:
        raise RuntimeError("F6_DUPLICATE_RELEASE_OR_MISSING_RECEIPT")
    receipt = captured["record"]
    manifest = receipt.get("manifest", {})
    if (manifest.get("snapshot_hash") != snapshot or manifest.get("brief_id") != brief
            or manifest.get("review_count", 0) < 1 or len(manifest.get("server_receipt", "")) != 64
            or manifest.get("sources") is None):
        raise RuntimeError("F6_MANIFEST_SCOPE_OR_REVIEW_INVALID")
    ack = manifest.get("release_acknowledgement", {})
    if (ack.get("schema") != "caseproof-release-ack-v1"
            or ack.get("release_id") != receipt.get("release_id")
            or ack.get("snapshot_hash") != snapshot
            or not ack.get("actor_id")
            or ack.get("release_type") != release_type):
        raise RuntimeError("F6_RELEASE_ACKNOWLEDGEMENT_NOT_FROZEN")
    print("F6_SIGNED_RELEASE_ACKNOWLEDGEMENT_VERIFIED", flush=True)
    completeness = manifest.get("review_completeness", {})
    if (completeness.get("policy_version") != "caseproof-release-completeness-v1"
            or completeness.get("release_type") != release_type
            or completeness.get("total_findings") != manifest.get("finding_count")
            or completeness.get("reviewed_findings") != manifest.get("review_count")
            or completeness.get("partial_acknowledged") != (release_type == "partial_review")
            or (release_type == "complete_review" and not completeness.get("review_complete"))
            or (release_type == "partial_review" and completeness.get("review_complete"))):
        raise RuntimeError("F6_SIGNED_RELEASE_COMPLETENESS_SCOPE_INVALID")
    if os.getenv("CASEPROOF_RIGHTS_SIGNED_LIVE") == "YES":
        attestation = manifest.get("rights_attestation")
        sources = manifest.get("sources", [])
        if not isinstance(attestation, dict) or (
            attestation.get("schema") != "caseproof-export-rights-v1"
            or attestation.get("action") != "export"
            or attestation.get("scope") != "same_matter"
            or attestation.get("decision") != "allow"
        ):
            raise RuntimeError("PR203_SIGNED_RIGHTS_MANIFEST_MISSING")
        rights_sources = attestation.get("sources")
        if not isinstance(rights_sources, list) or len(rights_sources) != len(sources):
            raise RuntimeError("PR203_SIGNED_RIGHTS_SOURCE_COUNT_MISMATCH")
        for source in sources:
            evidence = [
                x for x in rights_sources if isinstance(x, dict)
                and x.get("version_id") == source.get("version_id")
            ]
            if len(evidence) != 1 or (
                evidence[0].get("original_sha256") != source.get("sha256")
                or evidence[0].get("decision") != "allow"
                or type(evidence[0].get("policy_version")) is not int
                or evidence[0]["policy_version"] < 1
            ):
                raise RuntimeError("PR203_SIGNED_RIGHTS_SOURCE_POLICY_MISMATCH")
        print("PR203_GENUINE_SIGNED_EXPORT_RIGHTS_MANIFEST_PASSED", flush=True)
    print("F6_GENUINE_SIGNED_RELEASE_" + release_type.upper() + "_SCOPE_PASSED", flush=True)
    source_links = manifest.get("source_links", [])
    original_destination = (
        f"/v2/matters/{case}/briefs/{brief}/dossier/history/{snapshot}"
        f"/sources/{pdf_version}/original"
    )
    if not any(
        row.get("version_id") == pdf_version and row.get("original_path") == original_destination
        and row.get("sha256") == hashlib.sha256(pdf_original).hexdigest()
        for row in source_links
    ):
        raise RuntimeError("F6_FROZEN_SOURCE_LINK_WRONG_VERSION")
    reference_links = manifest.get("reference_links", [])
    if expect_reference == "Stuk 1":
        mapped = [
            row for row in reference_links
            if row.get("source_version_id") == pdf_version
            and row.get("pdf_page") == 6
            and row.get("page_space") == "physical_pdf_page"
        ]
        if not mapped:
            raise RuntimeError("F6_PRINTED_PAGE_LINK_NOT_PHYSICAL_SIX")
        reference_id = mapped[0]["reference_id"]
        link = page.get_by_role(
            "link", name="Inspect preserved reference " + reference_id
        )
        expect(link).to_be_visible(timeout=90000)
        link.click()
        expect(page.get_by_text("PDF page 6 of 6", exact=True)).to_be_visible(timeout=90000)
        print("F6_REAL_BROWSER_LINK_TO_PDF_PHYSICAL_PAGE_SIX_PASSED", flush=True)
        page.goto(previous)
        acceptance.login(page)
        expect(page.get_by_role("heading", name="Reviewed exports and history")).to_be_visible(timeout=90000)
        # Re-open the same exact stored release, never create a second one.
        page.get_by_role("button", name="Select release " + receipt["release_id"][:8]).click()
    print("F6_SIGNED_LOST_ACK_RELEASE_RECONCILED_ONCE_PASSED", flush=True)

    # Only exact downloaded bytes are accepted: digest/length and real
    # DOCX package reopening, not an API JSON success or a ZIP signature.
    with page.expect_download(timeout=120000) as started:
        page.get_by_role("button", name="Verify SHA-256 and download DOCX").click()
    download = started.value
    out = io.BytesIO()
    with open(download.path(), "rb") as fp:
        while (chunk := fp.read(65536)):
            out.write(chunk)
            if out.tell() > 5_242_880:
                raise RuntimeError("F6_DOWNLOADED_DOCX_OVERSIZED")
    output = out.getvalue()
    info = manifest["artifacts"]["docx"]
    if len(output) != info["byte_length"] or hashlib.sha256(output).hexdigest() != info["sha256"]:
        raise RuntimeError("F6_DOCX_SHA_MISMATCH")
    document = Document(io.BytesIO(output))
    paragraphs = [paragraph.text for paragraph in document.paragraphs]
    if not any(expect_reference in line for line in paragraphs):
        raise RuntimeError("F6_DRAFT_REFERENCE_LOST")
    if not any("scoped review annotations" in line for line in paragraphs):
        raise RuntimeError("F6_ANNOTATION_MISSING")
    with ZipFile(io.BytesIO(output)) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("F6_BROKEN_DOCX_MEMBER")
        if any(name.startswith("word/embeddings/") for name in archive.namelist()):
            raise RuntimeError("F6_UNSAFE_EMBEDDED_OUTPUT")
    print("F6_GENUINE_SIGNED_DOCX_BYTES_FORMAT_AND_SHA256_REOPEN_PASSED", flush=True)

    # Exact historical source URL. Both source bytes and their physical page
    # are checked; a printed page '4' must not be confused with PDF page 4.
    original_url = (scoped_base(case, brief)
                    + f"/history/{snapshot}/sources/{pdf_version}/original")
    source = page.request.get(
        original_url, headers={"Authorization": captured["authorization"]},
        timeout=90000,
    )
    if source.status != 200 or source.body() != pdf_original:
        raise RuntimeError("F6_HISTORICAL_ORIGINAL_LINK_BYTES_MISMATCH")
    pages = PdfReader(io.BytesIO(source.body())).pages
    if len(pages) < 6 or "PRINTED PAGE 4" not in (pages[5].extract_text() or ""):
        raise RuntimeError("F6_PHYSICAL_PAGE_6_PRINTED_4_MISMATCH")
    if source.headers.get("x-caseproof-original-sha256") != hashlib.sha256(pdf_original).hexdigest():
        raise RuntimeError("F6_HISTORICAL_SOURCE_HASH_UNBOUND")
    print("F6_HISTORICAL_SOURCE_LINK_PRINTED4_PDF6_PASSED", flush=True)

    return {
        "release_id": receipt["release_id"],
        "brief": brief, "snapshot": snapshot, "sha256": info["sha256"],
        "bytes": output, "authorization": captured["authorization"],
        "page": previous,
    }


def reopen_old(
    page: Page, acceptance: WorkspaceBrowserAcceptance, *,
    case: str, old: dict[str, Any], new: dict[str, Any],
) -> None:
    """Cold process and signed-browser readback of both immutable outputs."""
    if old["release_id"] == new["release_id"] or old["snapshot"] == new["snapshot"] or old["brief"] == new["brief"]:
        raise RuntimeError("F6_OLD_NEW_RELEASE_NOT_INDEPENDENT")
    page.goto(old["page"])
    acceptance.login(page)
    expect(page.get_by_role("heading", name="Reviewed exports and history")).to_be_visible(timeout=90000)
    expect(page.get_by_text("Frozen release history")).to_be_visible(timeout=90000)
    selector = page.get_by_role("button", name="Select release " + old["release_id"][:8])
    expect(selector).to_be_visible(timeout=90000)
    selector.click()
    with page.expect_download(timeout=120000) as download_info:
        page.get_by_role("button", name="Verify SHA-256 and download DOCX").click()
    with open(download_info.value.path(), "rb") as fd:
        reopened = fd.read(5_242_881)
    if reopened != old["bytes"] or hashlib.sha256(reopened).hexdigest() != old["sha256"]:
        raise RuntimeError("F6_COLD_HISTORICAL_RELEASE_MUTATED")
    print("F6_SIGNED_COLD_REOPEN_EXACT_OLD_EXPORT_BYTES_PASSED", flush=True)


def deny_after_revocation(
    page: Page, *, case: str, old: dict[str, Any]
) -> None:
    artifact = (
        scoped_base(case, old["brief"])
        + f"/releases/{old['release_id']}/artifacts/docx"
    )
    denied = page.request.get(
        artifact, headers={"Authorization": old["authorization"]}, timeout=30000
    )
    if denied.status not in (403, 404):
        raise RuntimeError("F6_REVOKED_EXPORT_REMAINED_READABLE")
    print("F6_GENUINE_SIGNED_REVOKED_EXPORT_DENIED_PASSED", flush=True)
