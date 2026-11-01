import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFile } from 'node:fs/promises';
const matter = '11111111-1111-4111-8111-111111111111',
  brief = '22222222-2222-4222-8222-222222222222',
  snapshot = 'a'.repeat(64);
const manifest = JSON.parse(
  await readFile(
    'tests/viewer-comparison/generated/fixtures/manifest.json',
    'utf8',
  ),
) as { fixtures: { name: string; bytes: number; sha256: string }[] };
const fixture = manifest.fixtures.find((f) => f.name === 'mixed')!;
const report = {
  schema: 'caseproof-dossier-v1',
  case_id: matter,
  brief_id: brief,
  snapshot_hash: snapshot,
  coverage: { fully_checked: false },
  findings: [
    {
      reference_id: 'r1',
      literal: 'Stuk 1',
      identity: 'resolved',
      page_mapping: 'mapped',
      fidelity: 'ocr_unreliable',
      support: 'not_assessed',
    },
    {
      reference_id: 'r2',
      literal: 'Stuk 2',
      identity: 'resolved',
      page_mapping: 'unmapped',
      fidelity: 'not_assessed',
      support: 'not_assessed',
    },
  ],
};
const view = (reference = 'r1') => ({
  schema: 'caseproof-viewer-v1',
  case_id: matter,
  brief_id: brief,
  snapshot_hash: snapshot,
  reference_id: reference,
  version_id: 'source',
  original_sha256: fixture.sha256,
  byte_length: fixture.bytes,
  page_mapping: reference === 'r1' ? 'mapped' : 'unmapped',
  pdf_page: reference === 'r1' ? 1 : null,
  legacy_region_count: 2,
  geometry_policy: 'derived_pdf_text_only_legacy_raster_not_projected',
});
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.caseproofSession = {
      getBearer: async () => 'synthetic-viewer-token',
    };
  });
  await page.route('**/dossier?*', (route) => route.fulfill({ json: report }));
  await page.route('**/viewer', (route) =>
    route.fulfill({
      json: view(route.request().url().includes('/r2/') ? 'r2' : 'r1'),
    }),
  );
  await page.route('**/viewer/original', async (route) =>
    route.fulfill({
      body: await readFile(
        'tests/viewer-comparison/generated/fixtures/mixed.pdf',
      ),
      contentType: 'application/pdf',
      headers: {
        'X-CaseProof-Snapshot': snapshot,
        'X-CaseProof-Original-SHA256': fixture.sha256,
      },
    }),
  );
});
test('real worker pixels, repeated search, zoom/rotate/resize, page navigation and signout cleanup', async ({
  page,
}) => {
  const external: string[] = [];
  page.on('request', (r) => {
    if (new URL(r.url()).origin !== 'http://127.0.0.1:4173')
      external.push(r.url());
  });
  await page.goto(
    `/workspace/matters/${matter}/briefs/${brief}?snapshot=${snapshot}`,
  );
  await page.getByRole('button', { name: 'Connect session' }).click();
  await expect(
    page.getByText('Source page rendered.', { exact: true }),
  ).toBeVisible();
  await page.getByLabel('Find text on this page').fill('Repeated source text');
  await expect(
    page.getByText('2 derived text locations in this page.', { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByText(
      '2 frozen raster regions lack complete PDF page-box geometry.',
      { exact: false },
    ),
  ).toBeVisible();
  const canvas = page.locator('canvas[aria-label="Preserved PDF page pixels"]');
  const oldWidth = await canvas.evaluate(
    (c) => c.getBoundingClientRect().width,
  );
  await page.getByRole('button', { name: 'Zoom in', exact: true }).click();
  await expect(
    page.getByText('Source page rendered.', { exact: true }),
  ).toBeVisible();
  expect(
    await canvas.evaluate((c) => c.getBoundingClientRect().width),
  ).toBeGreaterThan(oldWidth * 1.2);
  await page.getByRole('button', { name: 'Rotate page', exact: true }).click();
  await expect(
    page.getByText('Source page rendered.', { exact: true }),
  ).toBeVisible();
  await page
    .getByRole('button', { name: 'Next source page', exact: true })
    .click();
  await expect(
    page.getByText('PDF page 2 of 2', { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText('Source page rendered.', { exact: true }),
  ).toBeVisible();
  await page
    .getByRole('button', { name: 'Previous source page', exact: true })
    .click();
  await expect(
    page.getByText('Source page rendered.', { exact: true }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: 'test-results/viewer-desktop.png',
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByText('Source page rendered.', { exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole('button', { name: 'Stuk 2' }).click();
  await expect(
    page.getByText(
      'Page 1 is an exploration starting point, not a mapped reference.',
      { exact: false },
    ),
  ).toBeVisible();
  await expect(
    page.getByText('Source page rendered.', { exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'End session', exact: true }).click();
  await expect(page.locator('canvas')).toHaveCount(0);
  expect(external).toEqual([]);
});
test('wrong hash fails closed before PDF parsing', async ({ page }) => {
  await page.route('**/viewer/original', (route) =>
    route.fulfill({
      body: '%PDF-1.7 tampered',
      contentType: 'application/pdf',
      headers: {
        'X-CaseProof-Snapshot': snapshot,
        'X-CaseProof-Original-SHA256': fixture.sha256,
      },
    }),
  );
  await page.goto(
    `/workspace/matters/${matter}/briefs/${brief}?snapshot=${snapshot}`,
  );
  await page.getByRole('button', { name: 'Connect session' }).click();
  await expect(
    page.getByText('This source could not be opened.', { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Next source page' }),
  ).toHaveCount(0);
});
