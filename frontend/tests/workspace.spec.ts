import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
const matter = '11111111-1111-4111-8111-111111111111',
  brief = '22222222-2222-4222-8222-222222222222',
  hash = 'a'.repeat(64);
const report = {
  schema: 'caseproof-dossier-v1',
  case_id: matter,
  brief_id: brief,
  snapshot_hash: hash,
  coverage: { reference_recall_measured: false, fully_checked: false },
  findings: [
    {
      reference_id: 'r1',
      literal: 'Stuk 1 <img src=x>',
      identity: 'resolved',
      page_mapping: 'mapped',
      fidelity: 'representation_conflict',
      support: 'not_assessed',
    },
    {
      reference_id: 'r2',
      literal: 'Exhibit A',
      identity: 'not_assessed',
      page_mapping: 'unmapped',
      fidelity: 'not_assessed',
      support: 'not_assessed',
    },
  ],
};
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.caseproofSession = {
      getBearer: async () => 'synthetic-browser-fixture',
    };
  });
});
test('Storyteller stage navigation, accessible panel splitters and stable review preferences', async ({
  page,
}) => {
  await page.route('**/v2/**', (route) => route.fulfill({ json: report }));
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.goto(
    `/workspace/matters/${matter}/briefs/${brief}?snapshot=${hash}`,
  );
  await page.getByRole('button', { name: 'Connect session' }).click();
  const primary = page.getByRole('navigation', { name: 'Primary workspace' });
  await expect(primary.getByRole('link', { name: 'Matter' })).toHaveAttribute(
    'href',
    /\/workspace\/?$/,
  );
  await expect(
    primary.getByRole('link', { name: 'Verification' }),
  ).toHaveAttribute('href', /\/briefs\/.*snapshot=/);
  await expect(primary.getByRole('link', { name: 'Export' })).toHaveAttribute(
    'href',
    /\/exports\?brief=.*snapshot=/,
  );
  const journey = page.getByRole('navigation', { name: 'Matter workflow' });
  await expect(journey.locator('li')).toHaveCount(7);
  await expect(
    journey.getByRole('link', { name: /04 Evidence review/ }),
  ).toHaveAttribute('aria-current', 'step');
  const queue = page.getByRole('separator', { name: 'Resize findings queue' });
  const draft = page.getByRole('separator', {
    name: 'Resize draft and source panels',
  });
  await expect(queue).toHaveAttribute('aria-valuenow', '300');
  await queue.focus();
  await page.keyboard.press('ArrowRight');
  await expect(queue).toHaveAttribute('aria-valuenow', '310');
  await draft.focus();
  await page.keyboard.press('ArrowRight');
  await expect(draft).toHaveAttribute('aria-valuenow', '390');
  await page.keyboard.press('ArrowLeft');
  await expect(draft).toHaveAttribute('aria-valuenow', '400');
  await page.keyboard.press('ArrowRight');
  await expect(draft).toHaveAttribute('aria-valuenow', '390');
  await page.getByRole('button', { name: 'Exhibit A' }).click();
  await expect(
    page.getByRole('separator', { name: 'Resize draft and source panels' }),
  ).toHaveAttribute('aria-valuenow', '390');
  await page.getByRole('button', { name: 'Source focus' }).click();
  await expect(page.locator('.cockpit-draft')).toBeHidden();
  await expect(page.locator('.cockpit-evidence')).toBeVisible();
  await page.getByRole('button', { name: 'Split view' }).click();
  await expect(draft).toHaveAttribute('aria-valuenow', '390');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const transition = await page
    .getByRole('button', { name: 'Split view' })
    .evaluate((node) => getComputedStyle(node).transitionDuration);
  expect(transition).toBe('0s');
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(queue).toBeHidden();
  await expect(draft).toBeHidden();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test('frozen report, keyboard, accessibility, narrow layout and session removal', async ({
  page,
}) => {
  const external: string[] = [];
  page.on('request', (r) => {
    if (new URL(r.url()).origin !== 'http://127.0.0.1:4173')
      external.push(r.url());
  });
  await page.route('**/v2/**', (route) => route.fulfill({ json: report }));
  const response = await page.goto(
    `/workspace/matters/${matter}/briefs/${brief}?snapshot=${hash}`,
  );
  expect(response?.headers()['content-security-policy']).toContain(
    "object-src 'none'",
  );
  await page.getByRole('button', { name: 'Connect session' }).click();
  await expect(
    page.getByRole('heading', { name: 'Review the evidence' }),
  ).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Stuk 1 <img src=x>' }),
  ).toBeVisible();
  expect(await page.locator('img').count()).toBe(0);
  const second = page.getByRole('button', { name: 'Exhibit A' });
  await second.focus();
  await page.keyboard.press('Enter');
  await expect(second).toHaveAttribute('aria-current', 'true');
  await expect(page.getByRole('heading', { name: 'Exhibit A' })).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: 'test-results/workspace-desktop.png',
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: 'test-results/workspace-narrow.png',
    fullPage: true,
  });
  await page.getByRole('button', { name: 'End session' }).click();
  await expect(page).toHaveURL('http://127.0.0.1:4173/workspace');
  await expect(
    page.getByRole('heading', { name: 'Connect your workspace session' }),
  ).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Exhibit A' })).toHaveCount(0);
  expect(external).toEqual([]);
});
test('denied access clears private view; no automatic retry', async ({
  page,
}) => {
  let calls = 0;
  await page.route('**/v2/**', (route) => {
    calls++;
    return route.fulfill({ status: 403 });
  });
  await page.goto(
    `/workspace/matters/${matter}/briefs/${brief}?snapshot=${hash}`,
  );
  await page.getByRole('button', { name: 'Connect session' }).click();
  await expect(
    page.getByRole('heading', { name: 'Connect your workspace session' }),
  ).toBeVisible();
  await expect.poll(() => calls).toBe(1);
});
test('schema mismatch and missing provider remain actionable', async ({
  page,
}) => {
  await page.route('**/v2/**', (route) =>
    route.fulfill({
      json: {
        ...report,
        findings: [{ ...report.findings[0], identity: 'verified' }],
      },
    }),
  );
  await page.goto(
    `/workspace/matters/${matter}/briefs/${brief}?snapshot=${hash}`,
  );
  await page.getByRole('button', { name: 'Connect session' }).click();
  await expect(page.getByRole('alert')).toContainText('report format changed');
});

test('empty results, provider absence and form validation are explicit', async ({
  page,
}) => {
  await page.goto('/workspace/reports/open');
  await page.evaluate(() => {
    delete window.caseproofSession;
  });
  await page.getByRole('button', { name: 'Connect session' }).click();
  await expect(page.getByRole('status')).toContainText('No session provider');
  await page.evaluate(() => {
    window.caseproofSession = { getBearer: async () => 'synthetic' };
  });
  await page.getByRole('button', { name: 'Connect session' }).click();
  await page.getByRole('button', { name: 'Open report' }).click();
  await expect(page.getByLabel('Matter ID')).toBeFocused();
  await expect(page.getByLabel('Matter ID')).toHaveAttribute(
    'aria-invalid',
    'true',
  );
  await page.route('**/v2/**', (route) =>
    route.fulfill({ json: { ...report, findings: [] } }),
  );
  await page.getByLabel('Matter ID').fill(matter);
  await page.getByLabel('Brief version ID').fill(brief);
  await page.getByLabel('Snapshot SHA-256').fill(hash);
  await page.getByRole('button', { name: 'Open report' }).click();
  await expect(
    page.getByText('No explicit references were detected.', { exact: false }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test('large reference queues are paged and source text stays inert', async ({
  page,
}) => {
  const findings = Array.from({ length: 120 }, (_, i) => ({
    ...report.findings[0],
    reference_id: `r${i}`,
    literal: `Stuk ${i + 1}`,
  }));
  await page.route('**/v2/**', (route) =>
    route.fulfill({ json: { ...report, findings } }),
  );
  await page.goto(
    `/workspace/matters/${matter}/briefs/${brief}?snapshot=${hash}`,
  );
  await page.getByRole('button', { name: 'Connect session' }).click();
  await expect(page.locator('.finding')).toHaveCount(50);
  await page.getByRole('button', { name: 'Next references' }).click();
  await expect(
    page.getByRole('heading', { name: 'Stuk 51', exact: true }),
  ).toBeVisible();
  await expect(page.locator('.finding')).toHaveCount(50);
});
