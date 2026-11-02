"""Genuine signed-browser F3 acceptance on owned synthetic fixtures only.

No traces, screenshots or raw credential/error output. The protected wrapper
owns Auth/org cleanup; register matter and exact object paths before transfer.
"""
from __future__ import annotations

import hashlib
import os

from playwright.sync_api import expect

from scripts.m05_registry import record, rows
from scripts.verify_dev_live_review_roundtrip import _server_start, _server_stop
from scripts.verify_dev_live_txt_journey import admin_rpc
from scripts.workspace_browser_live import ORIGIN, WorkspaceBrowserAcceptance
from tests.fixtures.dossier_journey import dossier_bundle


def main() -> None:
    if os.getenv('GITHUB_REF') not in {'refs/heads/feat/f3-complete-intake', 'refs/heads/main'}:
        raise RuntimeError('F3_PROTECTED_BRANCH_REQUIRED')
    key, run, org = (os.environ[n] for n in ('CASEPROOF_DEV_AUTH_ADMIN_KEY', 'CASEPROOF_P3_RUN_ID', 'CASEPROOF_P3_ORG_ID'))
    bundle = dossier_bundle()
    proc = _server_start()
    acceptance = WorkspaceBrowserAcceptance('', '')
    page = acceptance.page
    page.set_default_timeout(45000)
    registered: list[dict] = []
    case = ''
    try:
        page.goto(ORIGIN + '/workspace/matters/new')
        acceptance.login(page)
        expect(page.get_by_role('heading', name='Create a private matter')).to_be_visible()
        page.get_by_label('Organization', exact=True).select_option(org)
        page.get_by_label('Matter title').fill('Owned synthetic F3 dossier')
        with page.expect_response(lambda r: r.url.endswith('/intake/matters')) as created:
            page.get_by_role('button', name='Create matter', exact=True).click()
        if created.value.status != 200:
            raise RuntimeError('F3_BROWSER_CREATE_FAILED')
        case = created.value.json()['case_id']
        record(key, run, 'matter', case, 'CREATED')
        expect(page.get_by_role('heading', name='Preserve the source bundle')).to_be_visible()
        labels = ('DOCX draft', 'UTF-8 inventory', 'First PDF exhibit', 'Second PDF exhibit or scan')
        for label, source in zip(labels, bundle, strict=True):
            page.get_by_label(label, exact=True).set_input_files({'name': source.filename, 'mimeType': source.media_type, 'buffer': source.content})
        page.get_by_label(labels[-1], exact=True).set_input_files({'name': bundle[-1].filename, 'mimeType': 'application/pdf', 'buffer': b'%PDF-1.7 corrupt'})
        with page.expect_response(lambda r: r.url.endswith('/reservations')) as rejected:
            page.get_by_role('button', name='Preserve or reconcile originals').click()
        if rejected.value.status != 422:
            raise RuntimeError('F3_CORRUPT_FINAL_NOT_REJECTED')
        expect(page.get_by_text('No completed intake receipt was received.', exact=False)).to_be_visible()
        print('F3_BROWSER_CORRUPT_FINAL_PREFLIGHT_REJECTED', flush=True)
        page.get_by_label(labels[-1], exact=True).set_input_files({'name': bundle[-1].filename, 'mimeType': bundle[-1].media_type, 'buffer': bundle[-1].content})

        def own_reservation(route) -> None:
            response = route.fetch(timeout=180000)
            if response.status != 200:
                raise RuntimeError('F3_RESERVATION_FAILED')
            rows = response.json()['sources']
            if len(rows) != 4:
                raise RuntimeError('F3_RESERVATION_NOT_FOUR')
            registered[:] = rows
            for row, source in zip(rows, bundle, strict=True):
                if row['sha256'] != hashlib.sha256(source.content).hexdigest():
                    raise RuntimeError('F3_RESERVATION_HASH_DIFFERS')
                path = '/'.join((org, case, row['document_id'], row['version_id'], row['sha256']))
                record(key, run, 'storage_file', path)
            route.fulfill(response=response)
        page.route('**/intake/matters/*/reservations', own_reservation)
        count = 0
        def lose_first_ack(route) -> None:
            nonlocal count
            count += 1
            if count == 1:
                response = route.fetch(timeout=180000)
                if response.status != 200:
                    raise RuntimeError('F3_REAL_TRANSFER_FAILED')
                route.abort('failed')  # Actual server writes committed; browser gets no acknowledgement.
            else:
                route.continue_()
        page.route('**/intake/matters/*/sources', lose_first_ack)
        page.get_by_role('button', name='Preserve or reconcile originals').click()
        expect(page.get_by_text('No completed intake receipt was received.', exact=False)).to_be_visible(timeout=180000)
        original_ids = [r['version_id'] for r in registered]
        page.get_by_role('button', name='Preserve or reconcile originals').click()
        expect(page.get_by_text('All originals passed fresh authorized hash readback.', exact=False)).to_be_visible(timeout=180000)
        if [r['version_id'] for r in registered] != original_ids:
            raise RuntimeError('F3_RETRY_DUPLICATED_ORIGINALS')
        print('F3_REAL_UPLOAD_LOST_ACK_EXACT_READBACK_REPLAY_PASSED', flush=True)
        _server_stop(proc)
        proc = _server_start()
        page.reload()
        acceptance.login(page)
        expect(page.get_by_text('All originals passed fresh authorized hash readback.', exact=False)).to_be_visible(timeout=180000)
        page.get_by_role('link', name='Review inventory and page mappings').click()
        expect(page.get_by_role('heading', name='Confirm inventory')).to_be_visible()
        expect(page.get_by_label('Preserved exhibit').first).to_be_visible(timeout=120000)
        page.get_by_label('Preserved exhibit').first.select_option(registered[2]['version_id'])
        page.get_by_role('checkbox').check()
        page.get_by_role('button', name='Save inventory confirmation').click()
        expect(page.get_by_text('Inventory confirmation saved and freshly read back.', exact=False)).to_be_visible(timeout=120000)
        page.reload()
        acceptance.login(page)
        expect(page.get_by_role('button', name='Run explicit check')).to_be_enabled(timeout=120000)
        print('F3_BROWSER_COLD_PROCESS_SIGNIN_INVENTORY_RECEIPT_REOPEN_PASSED', flush=True)
        for role in ('ungranted', 'foreign'):
            context = acceptance.browser.new_context()
            denied = context.new_page()
            try:
                denied.goto(ORIGIN + f'/workspace/matters/{case}/sources')
                with denied.expect_response(lambda r: r.url.endswith('/intake/matters/' + case)) as response:
                    acceptance.login(denied, role)
                if response.value.status not in (403, 404):
                    raise RuntimeError('F3_UNGRANTED_INTAKE_NOT_DENIED')
                expect(denied.get_by_role('button', name='Sign in', exact=True)).to_be_visible()
            finally:
                context.close()
        if acceptance.external or page.evaluate('() => localStorage.length + sessionStorage.length'):
            raise RuntimeError('F3_BROWSER_EGRESS_OR_PERSISTENCE')
        owner = next(r['resource_id'].split(':', 1)[1] for r in rows(key, run)
                     if r['resource_type'] == 'auth_user' and r['resource_id'].startswith('owner:') and '@' not in r['resource_id'])
        admin_rpc(key, 'revoke', {'p_run': run, 'p_owner': owner, 'p_case': case})
        page.get_by_role('link', name='Back to sources').click()
        expect(page.get_by_role('button', name='Sign in', exact=True)).to_be_visible(timeout=120000)
        expect(page.get_by_role('heading', name='Preserve the source bundle')).to_have_count(0)
        print('F3_GENUINE_BROWSER_CREATE_INTAKE_CONFIRM_COLD_RESUME_DENIAL_REVOCATION_PASSED', flush=True)
    finally:
        acceptance.close()
        _server_stop(proc)
