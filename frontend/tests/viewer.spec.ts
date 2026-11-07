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
    const NativeWorker = window.Worker;
    window.f2ActiveWorkers = 0;
    class TrackedWorker extends NativeWorker {
      private ended = false;
      constructor(...args: ConstructorParameters<typeof Worker>) {
        super(...args);
        window.f2ActiveWorkers++;
      }
      override terminate() {
        if (!this.ended) {
          this.ended = true;
          window.f2ActiveWorkers--;
        }
        super.terminate();
      }
    }
    window.Worker = TrackedWorker;
  });
  await page.route('**/dossier?*', (route) => route.fulfill({ json: report }));
  await page.route('**/viewer', (route) =>
    route.fulfill({
      json: view(route.request().url().includes('/r2/') ? 'r2' : 'r1'),
    }),
  );
  await page.route('**/viewer/regions', (route) =>
    route.fulfill({
      json: {
        schema: 'caseproof-raster-overlays-v1',
        snapshot_hash: snapshot,
        original_sha256: fixture.sha256,
        source_version_id: 'source',
        regions: [],
        unassessed_region_count: 2,
        interpretation: 'navigation_only_never_a_verdict',
      },
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
  const scroll = page.getByRole('region', { name: 'Scrollable source page' });
  await scroll.focus();
  const beforeScroll = await scroll.evaluate((node) => node.scrollTop);
  await page.keyboard.press('ArrowDown');
  await expect
    .poll(() => scroll.evaluate((node) => node.scrollTop))
    .toBeGreaterThan(beforeScroll);
  await page.getByLabel('Find text on this page').fill('Repeated source text');
  await expect(
    page.getByText('2 derived text locations in this page.', { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByText('region(s) in this report have unassessed provenance.', {
      exact: false,
    }),
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
  await expect.poll(() => page.evaluate(() => window.f2ActiveWorkers)).toBe(0);
  expect(external).toEqual([]);
});
test('fractional device pixel ratio renders and disposes the real worker', async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, 'devicePixelRatio', { value: 0.8 });
  });
  await page.goto(
    `/workspace/matters/${matter}/briefs/${brief}?snapshot=${snapshot}`,
  );
  await page.getByRole('button', { name: 'Connect session' }).click();
  await expect(
    page.getByText('Source page rendered.', { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole('img', { name: 'Preserved PDF page pixels' }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'End session', exact: true }).click();
  await expect.poll(() => page.evaluate(() => window.f2ActiveWorkers)).toBe(0);
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

declare global {
  interface Window {
    f2ActiveWorkers: number;
  }
}

test('printed p.4 targets PDF p.6, preserves uncertainty at 200% and returns from exploration', async ({
  page,
}) => {
  const large = manifest.fixtures.find((f) => f.name === 'large200')!;
  await page.route('**/dossier?*', (route) =>
    route.fulfill({
      json: {
        ...report,
        findings: [
          {
            ...report.findings[0],
            fidelity: 'representation_conflict',
            pdf_page: 6,
            page_spaces: {
              pdf: { state: 'mapped', value: 6 },
              printed: { state: 'mapped', value: '4' },
              bundle: { state: 'unmapped', value: null },
            },
          },
        ],
      },
    }),
  );
  await page.route('**/viewer', (route) =>
    route.fulfill({
      json: {
        ...view(),
        pdf_page: 6,
        original_sha256: large.sha256,
        byte_length: large.bytes,
      },
    }),
  );
  await page.route('**/viewer/original', async (route) =>
    route.fulfill({
      body: await readFile(
        'tests/viewer-comparison/generated/fixtures/large200.pdf',
      ),
      contentType: 'application/pdf',
      headers: {
        'X-CaseProof-Snapshot': snapshot,
        'X-CaseProof-Original-SHA256': large.sha256,
      },
    }),
  );
  await page.route('**/viewer/regions', (route) =>
    route.fulfill({
      json: {
        schema: 'caseproof-raster-overlays-v1',
        snapshot_hash: snapshot,
        original_sha256: large.sha256,
        source_version_id: 'source',
        regions: [],
        unassessed_region_count: 2,
        interpretation: 'navigation_only_never_a_verdict',
      },
    }),
  );
  await page.goto(
    `/workspace/matters/${matter}/briefs/${brief}?snapshot=${snapshot}`,
  );
  await page.getByRole('button', { name: 'Connect session' }).click();
  await expect(
    page.getByText('Source page rendered.', { exact: true }),
  ).toBeVisible();
  const labels = page.locator('dl[aria-label="Reference page spaces"]');
  await expect(labels).toContainText(/Reference PDF page\s*6/);
  await expect(labels).toContainText(/Printed page\s*4/);
  await expect(labels).toContainText(/Bundle page\s*Unmapped/);
  await expect(
    page.getByText('PDF page 6 of 200', { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText('The source representations conflict.', { exact: false }),
  ).toBeVisible();
  await page
    .getByText('Extracted text — derived, not an OCR or fidelity assessment', {
      exact: true,
    })
    .click();
  await expect(page.locator('.source-viewer pre').first()).toContainText(
    'Synthetic physical page 6',
  );
  for (let i = 0; i < 4; i++) {
    await page.getByRole('button', { name: 'Zoom in', exact: true }).click();
    await expect(
      page.getByText('Source page rendered.', { exact: true }),
    ).toBeVisible();
  }
  await expect(page.getByText('Zoom 200%', { exact: true })).toBeVisible();
  await page
    .getByRole('button', { name: 'Next source page', exact: true })
    .click();
  await expect(
    page.getByText('Source page rendered.', { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText('Browsing another PDF page.', { exact: false }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Return to reference page' }).focus();
  await page.keyboard.press('Enter');
  await expect(
    page.getByText('Source page rendered.', { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText('PDF page 6 of 200', { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText('The source representations conflict.', { exact: false }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test('explicit reopen reauthorizes bytes and clears failed inspection state', async ({
  page,
}) => {
  let corrupt = true,
    contexts = 0,
    originals = 0;
  await page.route('**/viewer', (route) => {
    contexts++;
    return route.fulfill({ json: view() });
  });
  await page.route('**/viewer/original', async (route) => {
    originals++;
    return route.fulfill({
      body: corrupt
        ? '%PDF-tampered'
        : await readFile(
            'tests/viewer-comparison/generated/fixtures/mixed.pdf',
          ),
      contentType: 'application/pdf',
      headers: {
        'X-CaseProof-Snapshot': snapshot,
        'X-CaseProof-Original-SHA256': fixture.sha256,
      },
    });
  });
  await page.goto(
    `/workspace/matters/${matter}/briefs/${brief}?snapshot=${snapshot}`,
  );
  await page.getByRole('button', { name: 'Connect session' }).click();
  await expect(
    page.getByText('This source could not be opened.', { exact: false }),
  ).toBeVisible();
  await expect.poll(() => page.evaluate(() => window.f2ActiveWorkers)).toBe(0);
  corrupt = false;
  await page
    .getByRole('button', { name: 'Reopen source', exact: true })
    .click();
  await expect(
    page.getByText('Source page rendered.', { exact: true }),
  ).toBeVisible();
  expect(contexts).toBe(2);
  expect(originals).toBe(2);
  await expect(
    page.getByText('This source could not be opened.', { exact: false }),
  ).toHaveCount(0);
  await expect.poll(() => page.evaluate(() => window.f2ActiveWorkers)).toBe(1);
  await page.getByRole('button', { name: 'End session', exact: true }).click();
  await expect.poll(() => page.evaluate(() => window.f2ActiveWorkers)).toBe(0);
});

test('scan has pixels and explicit text/OCR uncertainty; denied switch clears its worker', async ({
  page,
}) => {
  const scan = manifest.fixtures.find((f) => f.name === 'scan')!;
  await page.route('**/viewer', (route) =>
    route.request().url().includes('/r2/')
      ? route.fulfill({ status: 403 })
      : route.fulfill({
          json: {
            ...view(),
            original_sha256: scan.sha256,
            byte_length: scan.bytes,
          },
        }),
  );
  await page.route('**/viewer/original', async (route) =>
    route.fulfill({
      body: await readFile(
        'tests/viewer-comparison/generated/fixtures/scan.pdf',
      ),
      contentType: 'application/pdf',
      headers: {
        'X-CaseProof-Snapshot': snapshot,
        'X-CaseProof-Original-SHA256': scan.sha256,
      },
    }),
  );
  await page.route('**/viewer/regions', (route) =>
    route.fulfill({
      json: {
        schema: 'caseproof-raster-overlays-v1',
        snapshot_hash: snapshot,
        original_sha256: scan.sha256,
        source_version_id: 'source',
        regions: [],
        unassessed_region_count: 2,
        interpretation: 'navigation_only_never_a_verdict',
      },
    }),
  );
  await page.goto(
    `/workspace/matters/${matter}/briefs/${brief}?snapshot=${snapshot}`,
  );
  await page.getByRole('button', { name: 'Connect session' }).click();
  await expect(
    page.getByText('Source page rendered.', { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText('OCR is unreliable for this reference.', { exact: false }),
  ).toBeVisible();
  await page
    .getByText('Extracted text — derived, not an OCR or fidelity assessment', {
      exact: true,
    })
    .click();
  await expect(
    page.getByText('No selectable text was extracted.', { exact: false }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Stuk 2' }).click();
  await expect(
    page.getByRole('button', { name: 'Sign in', exact: true }),
  ).toBeVisible();
  await expect(page.locator('canvas')).toHaveCount(0);
  await expect.poll(() => page.evaluate(() => window.f2ActiveWorkers)).toBe(0);
});

test('late old-source bytes cannot replace the newly selected reference', async ({
  page,
}) => {
  let release!: () => void;
  let delivered!: () => void;
  const finished = new Promise<void>((resolve) => {
    delivered = resolve;
  });
  await page.route('**/references/r1/viewer/original', async (route) => {
    await new Promise<void>((resolve) => {
      release = resolve;
    });
    await route.fulfill({
      body: await readFile(
        'tests/viewer-comparison/generated/fixtures/mixed.pdf',
      ),
      contentType: 'application/pdf',
      headers: {
        'X-CaseProof-Snapshot': snapshot,
        'X-CaseProof-Original-SHA256': fixture.sha256,
      },
    });
    delivered();
  });
  await page.goto(
    `/workspace/matters/${matter}/briefs/${brief}?snapshot=${snapshot}`,
  );
  await page.getByRole('button', { name: 'Connect session' }).click();
  await expect.poll(() => typeof release).toBe('function');
  await page.getByRole('button', { name: 'Stuk 2' }).click();
  await expect(
    page.getByText('Source page rendered.', { exact: true }),
  ).toBeVisible();
  release();
  await finished;
  await expect(
    page.getByText(
      'Page 1 is an exploration starting point, not a mapped reference.',
      { exact: false },
    ),
  ).toBeVisible();
  await expect(
    page.getByText('OCR is unreliable for this reference.', { exact: false }),
  ).toHaveCount(0);
  await expect.poll(() => page.evaluate(() => window.f2ActiveWorkers)).toBe(1);
  await page.getByRole('button', { name: 'End session', exact: true }).click();
  await expect.poll(() => page.evaluate(() => window.f2ActiveWorkers)).toBe(0);
});

test('a stale snapshot opens its preserved PDF in explicitly historical read-only mode', async ({
  page,
}) => {
  await page.route('**/dossier?*', (route) => route.fulfill({ status: 409 }));
  await page.route(`**/dossier/history/${snapshot}`, (route) =>
    route.fulfill({
      json: {
        mode: 'historical_read_only',
        currentness: 'not_asserted',
        source_availability: 'not_assessed',
        report,
      },
    }),
  );
  await page.goto(
    `/workspace/matters/${matter}/briefs/${brief}?snapshot=${snapshot}`,
  );
  await page.getByRole('button', { name: 'Connect session' }).click();
  await expect(page.getByText('Historical report · read-only')).toBeVisible();
  await expect(
    page.getByText('Historical original version · read-only.', {
      exact: false,
    }),
  ).toBeVisible();
  await expect(
    page.getByText('Source page rendered.', { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: /confirm support/i }),
  ).toHaveCount(0);
  await expect(
    page.getByRole('button', { name: /export signed/i }),
  ).toHaveCount(0);
});

test('source-bound raster outlines align with pixels on mixed-size nonzero CropBoxes', async ({
  page,
}) => {
  const cropped = manifest.fixtures.find((item) => item.name === 'mixedcrop')!;
  const crops = [
    [100, 150, 500, 700],
    [50, 100, 750, 550],
  ];
  const regions = [
    { bbox: [40, 460, 160, 500], image_size: [400, 550] },
    { bbox: [90, 310, 210, 350], image_size: [700, 450] },
  ];
  await page.route('**/dossier?*', (route) =>
    route.fulfill({
      json: {
        ...report,
        findings: report.findings.map((item) => ({
          ...item,
          page_mapping: 'mapped',
        })),
      },
    }),
  );
  await page.route('**/viewer', (route) => {
    const second = route.request().url().includes('/r2/');
    return route.fulfill({
      json: {
        ...view(second ? 'r2' : 'r1'),
        original_sha256: cropped.sha256,
        byte_length: cropped.bytes,
        page_mapping: 'mapped',
        pdf_page: second ? 2 : 1,
      },
    });
  });
  await page.route('**/viewer/regions', (route) => {
    const index = route.request().url().includes('/r2/') ? 1 : 0;
    return route.fulfill({
      json: {
        schema: 'caseproof-raster-overlays-v1',
        snapshot_hash: snapshot,
        original_sha256: cropped.sha256,
        source_version_id: 'source',
        interpretation: 'navigation_only_never_a_verdict',
        unassessed_region_count: 0,
        regions: [
          {
            region_id: 'c'.repeat(64),
            original_sha256: cropped.sha256,
            page_number: index + 1,
            ...regions[index],
            crop_box: crops[index],
            rotation: 0,
            user_unit: 1,
            cropbox_rasterized: true,
          },
        ],
      },
    });
  });
  await page.route('**/viewer/original', async (route) =>
    route.fulfill({
      body: await readFile(
        'tests/viewer-comparison/generated/fixtures/mixedcrop.pdf',
      ),
      contentType: 'application/pdf',
      headers: {
        'X-CaseProof-Snapshot': snapshot,
        'X-CaseProof-Original-SHA256': cropped.sha256,
      },
    }),
  );
  await page.goto(
    `/workspace/matters/${matter}/briefs/${brief}?snapshot=${snapshot}`,
  );
  await page.getByRole('button', { name: 'Connect session' }).click();
  for (let index = 0; index < 2; index++) {
    if (index) await page.getByRole('button', { name: /^Stuk 2/ }).click();
    await expect(
      page.getByText(`PDF page ${index + 1} of 2`, { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText('1 source-bound raster outline(s) aligned on this page.', {
        exact: true,
      }),
    ).toBeVisible();
    const box = regions[index]!;
    const pixels = await page.locator('.viewer-page').evaluate((node, data) => {
      const canvases = node.querySelectorAll('canvas');
      const original = canvases[0] as HTMLCanvasElement;
      const overlay = canvases[1] as HTMLCanvasElement;
      const ctx = original.getContext('2d')!;
      const over = overlay.getContext('2d')!;
      const px = (x: number, width: number, total: number) =>
        Math.round((x / total) * width);
      const x1 = px(data.bbox[0]!, original.width, data.image_size[0]!);
      const x2 = px(data.bbox[2]!, original.width, data.image_size[0]!);
      const y1 = px(data.bbox[1]!, original.height, data.image_size[1]!);
      const y2 = px(data.bbox[3]!, original.height, data.image_size[1]!);
      const interior = ctx.getImageData(
        Math.floor((x1 + x2) / 2),
        Math.floor((y1 + y2) / 2),
        1,
        1,
      ).data;
      const nearby = over.getImageData(
        Math.max(0, x1 - 3),
        Math.max(0, y1 - 3),
        7,
        7,
      ).data;
      return {
        dark: interior[0]! < 30 && interior[1]! < 30 && interior[2]! < 30,
        outline: Array.from(nearby).some(
          (value, at) => at % 4 === 3 && value > 0,
        ),
      };
    }, box);
    expect(pixels).toEqual({ dark: true, outline: true });
  }
});

test('OCR word positions are opt-in, source bound and exposed as accessible text', async ({
  page,
}) => {
  await page.route('**/viewer/regions', (route) =>
    route.fulfill({
      json: {
        schema: 'caseproof-raster-overlays-v1',
        snapshot_hash: snapshot,
        original_sha256: fixture.sha256,
        source_version_id: 'source',
        interpretation: 'navigation_only_never_a_verdict',
        unassessed_region_count: 0,
        regions: [
          {
            region_id: 'c'.repeat(64),
            original_sha256: fixture.sha256,
            page_number: 1,
            bbox: [140, 560, 260, 600],
            image_size: [600, 800],
            crop_box: [0, 0, 600, 800],
            rotation: 0,
            user_unit: 1,
            cropbox_rasterized: true,
            ocr_word: { text: '<synthetic>', bbox: [145, 565, 255, 595] },
          },
        ],
      },
    }),
  );
  await page.goto(
    `/workspace/matters/${matter}/briefs/${brief}?snapshot=${snapshot}`,
  );
  await page.getByRole('button', { name: 'Connect session' }).click();
  await expect(
    page.getByText('Source page rendered.', { exact: true }),
  ).toBeVisible();
  const originalMode = page.getByRole('button', { name: 'Original pixels' });
  await expect(originalMode).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: 'Show OCR word positions' }).click();
  await expect(originalMode).toHaveAttribute('aria-pressed', 'false');
  await expect(
    page.getByRole('img', { name: 'Preserved PDF page pixels' }),
  ).toBeVisible();
  await expect(
    page.getByRole('list', { name: 'OCR words on this page' }),
  ).toContainText('<synthetic>');
  await expect(
    page.getByText('Derived OCR words and numbered positions', {
      exact: false,
    }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Hide navigation boxes' }).click();
  const overlayHasWord = await page
    .locator('.viewer-overlay')
    .evaluate((node) => {
      const canvas = node as HTMLCanvasElement;
      const x = Math.round((145 / 600) * canvas.width);
      const y = Math.round((565 / 800) * canvas.height);
      const pixels = canvas
        .getContext('2d')!
        .getImageData(x - 3, y - 3, 7, 7).data;
      return Array.from(pixels).some(
        (value, index) => index % 4 === 3 && value > 0,
      );
    });
  expect(overlayHasWord).toBe(true);
  await originalMode.click();
  await expect(originalMode).toHaveAttribute('aria-pressed', 'true');
  await expect(
    page.getByRole('list', { name: 'OCR words on this page' }),
  ).toHaveCount(0);
});

test('OCR word positions abstain when the PDF CropBox does not match provenance', async ({
  page,
}) => {
  await page.route('**/viewer/regions', (route) =>
    route.fulfill({
      json: {
        schema: 'caseproof-raster-overlays-v1',
        snapshot_hash: snapshot,
        original_sha256: fixture.sha256,
        source_version_id: 'source',
        interpretation: 'navigation_only_never_a_verdict',
        unassessed_region_count: 0,
        regions: [
          {
            region_id: 'd'.repeat(64),
            original_sha256: fixture.sha256,
            page_number: 1,
            bbox: [140, 560, 260, 600],
            image_size: [600, 800],
            crop_box: [1, 0, 601, 800],
            rotation: 0,
            user_unit: 1,
            cropbox_rasterized: true,
            ocr_word: { text: 'synthetic', bbox: [145, 565, 255, 595] },
          },
        ],
      },
    }),
  );
  await page.goto(
    `/workspace/matters/${matter}/briefs/${brief}?snapshot=${snapshot}`,
  );
  await page.getByRole('button', { name: 'Connect session' }).click();
  await expect(
    page.getByText('Source page rendered.', { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Show OCR word positions' }),
  ).toHaveCount(0);
  await expect(
    page.getByText('Some OCR positions cannot be aligned', { exact: false }),
  ).toBeVisible();
});

test('Storyteller cockpit exposes workflow, keyboard-resizable panes and mobile stacking', async ({
  page,
}) => {
  await page.goto(
    `/workspace/matters/${matter}/briefs/${brief}?snapshot=${snapshot}`,
  );
  await page.getByRole('button', { name: 'Connect session' }).click();
  await expect(page.getByRole('navigation', { name: 'Matter workflow' })).toBeVisible();
  await expect(page.getByText('3–4 · Verify and review')).toHaveAttribute('aria-current', 'step');
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  const width = page.getByRole('slider', { name: 'Draft panel width percentage' });
  await expect(width).toHaveValue('50');
  await width.focus();
  await page.keyboard.press('ArrowRight');
  await expect(width).toHaveValue('55');
  await expect(page.locator('.cockpit-inspection')).toHaveCSS('--draft-panel-width', '55%');
  await page.getByRole('button', { name: 'Equal panels' }).click();
  await expect(width).toHaveValue('50');
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(width).toBeHidden();
  await expect(page.locator('.cockpit-inspection')).toHaveCSS('grid-template-columns', /.+/);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('Storyteller reading cockpit honors reduced motion and remains accessible in dark mode', async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: 'reduce', colorScheme: 'dark' });
  await page.goto(
    `/workspace/matters/${matter}/briefs/${brief}?snapshot=${snapshot}`,
  );
  await page.getByRole('button', { name: 'Connect session' }).click();
  const layout = page.locator('.review-layout');
  await expect(layout).toHaveCSS('animation-name', 'none');
  await expect(page.locator('.cockpit-inspection')).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: 'test-results/storyteller-dark-desktop.png',
    fullPage: true,
  });
});

test('Storyteller focus modes preserve evidence state and keyboard accessibility', async ({
  page,
}) => {
  await page.goto(
    `/workspace/matters/${matter}/briefs/${brief}?snapshot=${snapshot}`,
  );
  await page.getByRole('button', { name: 'Connect session' }).click();
  const source = page.locator('.cockpit-evidence');
  await expect(source).toBeVisible();
  await page.getByRole('button', { name: 'Draft focus' }).click();
  await expect(page.getByRole('button', { name: 'Draft focus' })).toHaveAttribute('aria-pressed', 'true');
  await expect(source).toBeHidden();
  await page.getByRole('button', { name: 'Source focus' }).click();
  await expect(source).toBeVisible();
  await expect(page.locator('.cockpit-draft')).toBeHidden();
  await page.getByRole('button', { name: 'Split view' }).click();
  await expect(page.locator('.cockpit-draft')).toBeVisible();
  await expect(source).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
