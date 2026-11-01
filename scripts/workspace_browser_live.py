"""Protected genuine-Auth browser acceptance; no traces/screenshots/credential logs.

Consumes only registered synthetic fixtures. Browser expiry uses a controlled
browser clock against a real provider-issued expiry, not an hour-long wall wait.
"""
from __future__ import annotations

import os
import time

from playwright.sync_api import Page, Request, expect, sync_playwright

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

    def login(self, page: Page, role: str = 'owner') -> None:
        page.get_by_label('Email address').fill(os.environ[f'CASEPROOF_P3_{role.upper()}_EMAIL'])
        page.get_by_label('Password', exact=True).fill(os.environ[f'CASEPROOF_P3_{role.upper()}_PASSWORD'])
        page.get_by_role('button', name='Sign in', exact=True).click()

    def exercise(self) -> None:
        page = self.page
        page.goto(ORIGIN + '/workspace/')
        self.login(page)
        expect(page.get_by_role('heading', name='Your permitted matters')).to_be_visible()
        page.locator(f'a[href="/workspace/matters/{self.case}"]').click()
        expect(page.get_by_role('heading', name='Preserved reports')).to_be_visible()
        page.locator(f'a[href$="snapshot={self.snapshot}"]').click()
        expect(page.get_by_role('heading', name='Review the evidence')).to_be_visible()
        if page.evaluate('() => localStorage.length + sessionStorage.length') != 0 or self.context.cookies():
            raise RuntimeError('F1_PERSISTENT_SESSION_MATERIAL')
        page.reload()
        expect(page.get_by_role('button', name='Sign in', exact=True)).to_be_visible()
        self.login(page)
        expect(page.get_by_role('heading', name='Review the evidence')).to_be_visible()
        # Fresh browser remains authenticated until the later real grant revoke.
        for role in ('ungranted', 'foreign'):
            context = self.browser.new_context()
            other = context.new_page()
            try:
                other.goto(ORIGIN + '/workspace/')
                self.login(other, role)
                expect(other.get_by_role('heading', name='Your permitted matters')).to_be_visible()
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
        expiry_context = self.browser.new_context()
        expired = expiry_context.new_page()
        try:
            expired.clock.install()
            expired.goto(ORIGIN + '/workspace/')
            with expired.expect_response(lambda r: r.url == ORIGIN + '/v2/workspace/session') as response:
                self.login(expired)
            expires = response.value.json()['expires_at']
            expect(expired.get_by_role('heading', name='Your permitted matters')).to_be_visible()
            expired.clock.fast_forward(max(1000, int((expires - time.time()) * 1000 + 2000)))
            expect(expired.get_by_role('button', name='Sign in', exact=True)).to_be_visible()
            if expired.evaluate('() => localStorage.length + sessionStorage.length'):
                raise RuntimeError('F1_EXPIRED_SESSION_RETAINED')
        finally:
            expiry_context.close()
        if self.external:
            raise RuntimeError('F1_BROWSER_EXTERNAL_REQUEST')
        print('F1_GENUINE_SIGNIN_CATALOG_REPORT_COLD_RELOAD_FOREIGN_UNGRANTED_AND_BROWSER_CLOCK_EXPIRY_PASSED', flush=True)

    def revoked(self) -> None:
        # Current page held the allowed report before the grant was revoked.
        # Explicit navigation reauthorizes; 404 must remove its private DOM/cache.
        self.page.get_by_role('link', name='CaseProof Evidence workspace').click()
        expect(self.page.get_by_role('heading', name='Your permitted matters')).to_be_visible()
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
