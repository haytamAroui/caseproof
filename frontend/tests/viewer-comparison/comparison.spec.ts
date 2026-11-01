import { test, expect } from '@playwright/test';
import { readFile, writeFile } from 'node:fs/promises';
import { cpus } from 'node:os';
interface Fixture {
  name: string;
  pages: number;
  expectedBox: number[];
  expectedByRotation: Record<string, number[]>;
  scan: boolean;
  rotation: number;
  cropBox: number[];
  mediaBox: number[];
  server: {
    page: number;
    elapsed_ms: number;
    png: string;
    size: number[];
    sha256: string;
  }[];
}
const corpus = JSON.parse(
  await readFile(
    'tests/viewer-comparison/generated/fixtures/manifest.json',
    'utf8',
  ),
) as { fixtures: Fixture[] };
test('same-fixture server-image versus pinned PDF.js: geometry, budgets and cleanup', async ({
  page,
  browser,
}, testInfo) => {
  const external: string[] = [];
  page.on('request', (r) => {
    if (new URL(r.url()).origin !== 'http://127.0.0.1:4175')
      external.push(new URL(r.url()).origin);
  });
  await page.goto('/workspace/tests/viewer-comparison/harness.html');
  const evidence: {
    fixture: string;
    pdfjs: { page: number; renderMs: number; width: number; height: number }[];
    server: Fixture['server'];
    openMs: number;
    maxCssGeometryError: number;
  }[] = [];
  for (const fixture of corpus.fixtures.filter((f) => f.pages <= 200)) {
    let maxCssGeometryError = 0;
    const opened = await page.evaluate(
      (name) => window.f2Harness.open(name),
      fixture.name,
    );
    expect(opened.pages).toBe(fixture.pages);
    expect(opened.openMs).toBeLessThan(5000);
    const pdfjs: (typeof evidence)[number]['pdfjs'] = [];
    for (const physical of fixture.pages === 200
      ? [1, 200, 100, 1]
      : fixture.name === 'mixed'
        ? [1, 2]
        : [1]) {
      const rendered = await page.evaluate(
        (p) => window.f2Harness.render(p),
        physical,
      );
      expect(rendered.renderMs).toBeLessThan(5000);
      pdfjs.push({
        page: physical,
        renderMs: rendered.renderMs,
        width: rendered.width,
        height: rendered.height,
      });
      if (physical === 1) {
        // Probe independently specified PDF fiducial interior and exterior, not a renderer-reported box.
        const probe = await page.evaluate(
          (box) => window.f2Harness.probe(box),
          fixture.expectedBox,
        );
        for (let i = 0; i < 4; i++)
          expect(
            (maxCssGeometryError = Math.max(
              maxCssGeometryError,
              Math.abs(probe.bounds[i]! - fixture.expectedBox[i]!) *
                probe.cssScale,
            )),
          ).toBeLessThanOrEqual(2);
        const server = fixture.server.find((s) => s.page === 1);
        expect(server, 'Missing real server candidate evidence').toBeTruthy();
        expect(server!.elapsed_ms).toBeLessThan(15000);
        expect(probe.size).toEqual(server!.size);
        const serverProbe = await page.evaluate(
          ({ file, box }) => window.f2Harness.serverProbe(file, box),
          { file: server!.png, box: fixture.expectedBox },
        );
        for (let i = 0; i < 4; i++)
          expect(
            (maxCssGeometryError = Math.max(
              maxCssGeometryError,
              Math.abs(serverProbe.bounds[i]! - fixture.expectedBox[i]!) *
                serverProbe.cssScale,
            )),
          ).toBeLessThanOrEqual(2);
      }
      if (fixture.name === 'hostile')
        expect(
          await page.evaluate(() => window.f2Harness.redPixels()),
        ).toBeGreaterThan(20);
      if (fixture.scan) expect(rendered.text.trim()).toBe('');
      if (fixture.name === 'mixed' && physical === 2)
        expect(rendered.userUnit).toBe(1.25);
      if (fixture.name === 'mixed' && physical === 2) {
        expect([rendered.width, rendered.height]).toEqual([2000, 1500]);
        // Record server UserUnit behavior without silently forcing it to agree.
        expect(fixture.server.find((s) => s.page === 2)).toBeTruthy();
      }
      if (fixture.name === 'clean')
        expect(
          rendered.textBoxes.filter((item) =>
            item.text.includes('Repeated source text'),
          ).length,
        ).toBe(2);
    }
    if (fixture.name === 'crop' || fixture.name === 'rotate90') {
      for (const angle of [90, 180, 270]) {
        const r = await page.evaluate(
          (a) => window.f2Harness.render(1, 1, a, 2),
          angle,
        );
        expect(r.rotation).toBe((fixture.rotation + angle) % 360);
        const expected = fixture.expectedByRotation[String(r.rotation)]!;
        const pixels = await page.evaluate(
          (box) => window.f2Harness.probe(box),
          expected,
        );
        for (let i = 0; i < 4; i++)
          expect(
            (maxCssGeometryError = Math.max(
              maxCssGeometryError,
              Math.abs(pixels.bounds[i]! - expected[i]!) * pixels.cssScale,
            )),
          ).toBeLessThanOrEqual(2);

        expect(r.renderMs).toBeLessThan(5000);
      }
    }
    evidence.push({
      fixture: fixture.name,
      pdfjs,
      server: fixture.server,
      openMs: opened.openMs,
      maxCssGeometryError,
    });
    const closed = await page.evaluate(() => window.f2Harness.close());
    expect(closed.pages).toBe(0);
    expect(closed.disposalFailed).toBe(false);
  }
  for (const name of ['corrupt', 'overflow201'])
    await expect(
      page.evaluate((n) => window.f2Harness.open(n), name),
    ).rejects.toThrow();
  await page.evaluate(() => window.f2Harness.close());
  expect(await page.evaluate(() => '__caseproofPdfExecuted' in window)).toBe(
    false,
  );
  expect(external).toEqual([]);
  const cdp = await browser.newBrowserCDPSession();
  const processes = (await cdp.send('SystemInfo.getProcessInfo')) as {
    processInfo: { id: number; type: string }[];
  };
  let rss = 0;
  for (const process of processes.processInfo) {
    const status = await readFile(`/proc/${process.id}/status`, 'utf8').catch(
      () => null,
    );
    if (status)
      rss += Number(status.match(/^VmRSS:\s+(\d+)/m)?.[1] ?? 0) * 1024;
  }
  expect(
    rss,
    'Actual Chromium RSS measurement must be available',
  ).toBeGreaterThan(0);
  expect(rss, 'Aggregate controlled Chromium process RSS budget').toBeLessThan(
    1024 * 1024 * 1024,
  );
  const report = {
    schema: 'caseproof-f2-viewer-comparison-v1',
    browser: browser.version(),
    cpu: cpus()[0]?.model,
    runner: process.env.RUNNER_OS ?? 'local',
    rssBytes: rss,
    budgets: {
      openMs: 5000,
      pageMs: 5000,
      serverMs: 15000,
      chromiumRss: 1073741824,
      coordinateToleranceCssPx: 2,
    },
    evidence,
  };
  console.log('F2_COMPARISON_JSON:' + JSON.stringify(report));
  await writeFile(
    testInfo.outputPath('comparison.json'),
    JSON.stringify(report, null, 2),
  );
  await testInfo.attach('comparison', {
    body: JSON.stringify(report, null, 2),
    contentType: 'application/json',
  });
});
