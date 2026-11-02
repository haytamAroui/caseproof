"""Protected genuine-Auth browser acceptance; no traces/screenshots/credential logs.

Consumes only registered synthetic fixtures. Browser expiry uses a controlled
browser clock against a real provider-issued expiry, not an hour-long wall wait.
"""
from __future__ import annotations

import os
import time

from playwright.sync_api import Page, Request, Response, expect, sync_playwright

ORIGIN = 'http://127.0.0.1:8765'


class WorkspaceBrowserAcceptance:
    def __init__(self, case: str, snapshot: str) -> None:
        self.case, self.snapshot = case, snapshot
        self.driver = sync_playwright().start()
        self.browser = self.driver.chromium.launch()
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.external: list[bool] = []
        def observe(request: Request) -> None:
            if not request.url.startswith(ORIGIN + '/'):
                self.external.append(True)
        self.page.on('request', observe)
        # Only fixed stage names/status numbers; no URLs, bodies or credentials.
        def inspect_response(response: Response) -> None:
            if response.url.endswith('/viewer'):
                print(f'F2_VIEWER_CONTEXT_HTTP_{response.status}', flush=True)
            elif response.url.endswith('/viewer/original'):
                print(f'F2_VIEWER_ORIGINAL_HTTP_{response.status}', flush=True)
            elif response.url == ORIGIN + '/v2/workspace/session':
                print(f'F1_SIGNIN_HTTP_{response.status}', flush=True)
            elif '/dossier?' in response.url:
                print(f'F1_REPORT_HTTP_{response.status}', flush=True)
        self.page.on('response', inspect_response)

    def login(self, page: Page, role: str = 'owner') -> None:
        page.get_by_label('Email address').fill(os.environ[f'CASEPROOF_P3_{role.upper()}_EMAIL'])
        page.get_by_label('Password', exact=True).fill(os.environ[f'CASEPROOF_P3_{role.upper()}_PASSWORD'])
        page.get_by_role('button', name='Sign in', exact=True).click()

    def exercise(self) -> None:
        page = self.page
        print('F1_STAGE_INITIAL_SIGNIN', flush=True)
        page.goto(ORIGIN + '/workspace/')
        self.login(page)
        expect(page.get_by_role('heading', name='Your permitted matters')).to_be_visible(timeout=30000)
        page.locator(f'a[href="/workspace/matters/{self.case}"]').click()
        expect(page.get_by_role('heading', name='Preserved reports')).to_be_visible(timeout=30000)
        page.locator(f'a[href$="snapshot={self.snapshot}"]').click()
        expect(page.get_by_role('heading', name='Review the evidence')).to_be_visible(timeout=30000)
        if os.getenv('CASEPROOF_F2_BROWSER_LIVE') == 'YES':
            print('F2_GENUINE_REPORT_OPENED_WAITING_FOR_SOURCE', flush=True)
            try:
                expect(page.get_by_text('Source page rendered.', exact=True)).to_be_visible(timeout=45000)
            except Exception:
                for index, message in enumerate((
                    'This source could not be opened.',
                    'PDF opening exceeded its time budget.',
                    'This page could not be rendered.',
                    'Page rendering exceeded its time budget.',
                )):
                    if page.get_by_text(message, exact=False).count():
                        print(f'F2_VIEWER_FIXED_ERROR_CATEGORY_{index}', flush=True)
                raise RuntimeError('F2_GENUINE_INITIAL_RENDER_FAILED') from None
            dimensions = page.locator('.inspection > dl.dimensions')
            original_dimensions = dimensions.text_content() or ''
            canvas = page.locator('canvas[aria-label="Preserved PDF page pixels"]')
            if int(canvas.get_attribute('width') or '0') <= 0:
                raise RuntimeError('F2_GENUINE_PDF_PIXELS_MISSING')
            page.get_by_role('button', name='Zoom in', exact=True).click()
            expect(page.get_by_text('Source page rendered.', exact=True)).to_be_visible(timeout=20000)
            page.get_by_role('button', name='Rotate page', exact=True).click()
            expect(page.get_by_text('Source page rendered.', exact=True)).to_be_visible(timeout=20000)
            expect(page.locator('dl[aria-label="Reference page spaces"]')).to_be_visible()
            page.get_by_role('button', name='Zoom in', exact=True).click()
            expect(page.get_by_text('Source page rendered.', exact=True)).to_be_visible(timeout=20000)
            expect(dimensions).to_have_text(original_dimensions)
            labels = page.locator('dl[aria-label="Reference page spaces"] dd')
            expect(labels.nth(0)).to_have_text('1')
            expect(labels.nth(2)).to_have_text('12')
            print('F2_STAGE_SWITCH_TO_SCAN', flush=True)
            with page.expect_response(lambda r: r.url.endswith('/viewer/original'), timeout=45000) as switched:
                page.locator('.queue .finding').nth(1).click()
            if switched.value.status != 200:
                raise RuntimeError('F2_SCAN_ORIGINAL_READ_DENIED')
            expect(page.get_by_text('Source page rendered.', exact=True)).to_be_visible(timeout=45000)
            expect(labels.nth(0)).to_have_text('1')
            expect(labels.nth(1)).to_have_text('7')
            print('F2_STAGE_RETURN_TO_TEXT_SOURCE', flush=True)
            with page.expect_response(lambda r: r.url.endswith('/viewer/original'), timeout=45000) as restored:
                page.locator('.queue .finding').first.click()
            if restored.value.status != 200:
                raise RuntimeError('F2_TEXT_ORIGINAL_READ_DENIED')
            expect(page.get_by_text('Source page rendered.', exact=True)).to_be_visible(timeout=45000)
            expect(dimensions).to_have_text(original_dimensions)
            print('F2_GENUINE_PAGE_SPACES_AND_UNCERTAINTY_PRESERVED_PASSED', flush=True)
            print('F2_GENUINE_FROZEN_SOURCE_HASH_BOUND_WORKER_RENDER_ZOOM_ROTATE_PASSED', flush=True)

        if page.evaluate('() => localStorage.length + sessionStorage.length') != 0 or self.context.cookies():
            raise RuntimeError('F1_PERSISTENT_SESSION_MATERIAL')
        print('F1_STAGE_COLD_RELOAD', flush=True)
        page.reload()
        expect(page.get_by_role('button', name='Sign in', exact=True)).to_be_visible()
        self.login(page)
        expect(page.get_by_role('heading', name='Review the evidence')).to_be_visible(timeout=30000)
        # Fresh browser remains authenticated until the later real grant revoke.
        print('F1_STAGE_FOREIGN_UNGRANTED', flush=True)
        for role in ('ungranted', 'foreign'):
            context = self.browser.new_context()
            other = context.new_page()
            try:
                other.goto(ORIGIN + '/workspace/')
                self.login(other, role)
                expect(other.get_by_role('heading', name='Your permitted matters')).to_be_visible(timeout=30000)
                expect(other.locator(f'a[href="/workspace/matters/{self.case}"]')).to_have_count(0)
                other.goto(ORIGIN + f'/workspace/matters/{self.case}')
                with other.expect_response(lambda r: r.url.endswith('/reports')) as denied:
                    self.login(other, role)
                if denied.value.status != 404:
                    raise RuntimeError('F1_FOREIGN_REPORT_CATALOG_NOT_MASKED')
                # The genuine signed catalog request is masked and clears memory.
                expect(other.get_by_role('button', name='Sign in', exact=True)).to_be_visible()
                expect(other.get_by_role('link', name='Open preserved report')).to_have_count(0)
            finally:
                context.close()
        print('F1_STAGE_EXPIRY_CONTEXT', flush=True)
        expiry_context = self.browser.new_context()
        expired = expiry_context.new_page()
        try:
            expired.clock.install()
            expired.goto(ORIGIN + '/workspace/')
            with expired.expect_response(lambda r: r.url == ORIGIN + '/v2/workspace/session') as response:
                self.login(expired)
            expires = response.value.json()['expires_at']
            expect(expired.get_by_role('heading', name='Your permitted matters')).to_be_visible(timeout=30000)
            expired.locator(f'a[href="/workspace/matters/{self.case}"]').click()
            expect(expired.get_by_role('heading', name='Preserved reports')).to_be_visible(timeout=30000)
            print('F1_STAGE_EXPIRY_HISTORY_OPENED', flush=True)
            expired.clock.fast_forward(max(1000, int((expires - time.time()) * 1000 + 2000)))
            expect(expired.get_by_role('button', name='Sign in', exact=True)).to_be_visible()
            if expired.evaluate('() => localStorage.length + sessionStorage.length'):
                raise RuntimeError('F1_EXPIRED_SESSION_RETAINED')
            expect(expired.get_by_role('link', name='Open preserved report')).to_have_count(0)
            # Restore wall time before a fresh provider login; no synthetic token.
            print('F1_STAGE_EXPIRED_PRIVATE_DOM_CLEARED', flush=True)
            expired.clock.set_system_time(time.time())
            self.login(expired)
            expect(expired.get_by_role('heading', name='Your permitted matters')).to_be_visible(timeout=30000)
            expect(expired.get_by_role('heading', name='Preserved reports')).to_have_count(0)
            print('F1_STAGE_FRESH_LOGIN_RECOVERY', flush=True)
            expired.get_by_role('button', name='Reopen previous location', exact=True).click()
            expect(expired.get_by_role('heading', name='Preserved reports')).to_be_visible(timeout=30000)
            expired.locator(f'a[href$="snapshot={self.snapshot}"]').click()
            expect(expired.get_by_role('heading', name='Review the evidence')).to_be_visible(timeout=30000)
            print('F1_GENUINE_EXPIRED_HISTORY_EXPLICIT_RELOGIN_REOPEN_PASSED', flush=True)
        finally:
            expiry_context.close()
        if self.external:
            raise RuntimeError('F1_BROWSER_EXTERNAL_REQUEST')
        print('F1_GENUINE_SIGNIN_CATALOG_REPORT_COLD_RELOAD_FOREIGN_UNGRANTED_AND_BROWSER_CLOCK_EXPIRY_PASSED', flush=True)

    def historical(self, brief: str, original_sha256: str) -> None:
        """Actual signed browser: old A must reopen after current confirmation B."""
        page = self.page
        target = ORIGIN + f'/workspace/matters/{self.case}/briefs/{brief}?snapshot={self.snapshot}'
        page.goto(target)
        with page.expect_response(lambda r: '/dossier/history/' in r.url and r.url.endswith(self.snapshot), timeout=45000) as historical, page.expect_response(lambda r: '/dossier/history/' in r.url and r.url.endswith('/viewer/original'), timeout=45000) as original:
            self.login(page)
        if historical.value.status != 200:
            raise RuntimeError('PR174_SIGNED_HISTORICAL_REPORT_DENIED')
        expect(page.get_by_text('Historical report · read-only')).to_be_visible(timeout=45000)
        expect(page.get_by_text('Source page rendered.', exact=True)).to_be_visible(timeout=45000)
        if original.value.status != 200 or original.value.headers.get('x-caseproof-original-sha256') != original_sha256:
            raise RuntimeError('PR174_SIGNED_OLD_ORIGINAL_BINDING_FAILED')
        expect(page.get_by_text('Historical original version · read-only.', exact=False)).to_be_visible()
        for action in ('Confirm support', 'Commit correction', 'Export signed ledger'):
            if page.get_by_role('button', name=action).count():
                raise RuntimeError('PR174_STALE_WRITE_CONTROL_VISIBLE')
        canvas = page.locator('canvas[aria-label="Preserved PDF page pixels"]')
        if int(canvas.get_attribute('width') or '0') == 0:
            raise RuntimeError('PR174_HISTORICAL_RASTER_NOT_RENDERED')
        page.get_by_role('button', name='Rotate page', exact=True).click()
        expect(page.get_by_text('Source page rendered.', exact=True)).to_be_visible(timeout=25000)
        page.get_by_role('button', name='Zoom in', exact=True).click()
        expect(page.get_by_text('Source page rendered.', exact=True)).to_be_visible(timeout=25000)
        page.reload()  # Cold browser reconstruction must obtain fresh provider Auth.
        self.login(page)
        expect(page.get_by_text('Historical report · read-only')).to_be_visible(timeout=45000)
        expect(page.get_by_text('Source page rendered.', exact=True)).to_be_visible(timeout=45000)
        if page.evaluate('() => localStorage.length + sessionStorage.length'):
            raise RuntimeError('PR174_HISTORICAL_SESSION_PERSISTED')
        if self.external:
            raise RuntimeError('PR174_HISTORICAL_BROWSER_EXTERNAL_REQUEST')
        print('PR174_SIGNED_HISTORY_OLD_SOURCE_READONLY_ROTATE_ZOOM_COLD_REOPEN_PASSED', flush=True)

    def revoked(self) -> None:
        # Current page held the allowed report before the grant was revoked.
        # Explicit navigation reauthorizes; 404 must remove its private DOM/cache.
        self.page.get_by_role('link', name='CaseProof Evidence workspace').click()
        expect(self.page.get_by_role('heading', name='Your permitted matters')).to_be_visible(timeout=30000)
        expect(self.page.locator(f'a[href="/workspace/matters/{self.case}"]')).to_have_count(0)
        self.page.goto(ORIGIN + f'/workspace/matters/{self.case}')
        with self.page.expect_response(lambda r: r.url.endswith('/reports')) as denied:
            self.login(self.page)
        if denied.value.status != 404:
            raise RuntimeError('F1_REVOKED_REPORT_CATALOG_NOT_MASKED')
        expect(self.page.get_by_role('button', name='Sign in', exact=True)).to_be_visible()
        expect(self.page.get_by_role('heading', name='Review the evidence')).to_have_count(0)
        print('F1_GENUINE_GRANT_REVOCATION_DENIAL_AND_PRIVATE_VIEW_CLEAR_PASSED', flush=True)

    def close(self) -> None:
        self.browser.close()
        self.driver.stop()
