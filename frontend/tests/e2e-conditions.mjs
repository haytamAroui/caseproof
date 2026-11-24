/* global window */
// FAKE-BACKED browser test (loopback only): save a condition, read it back, remove the last one, reload.
// Real: built React app, route/matching/contract code. FAKE: auth, storage, DB, conditions store, previews.
// Run from repo root (no network):
//   (cd frontend && npm run build) &&
//   unshare -rn bash -c 'ip link set lo up; (PYTHONPATH=. uv run --locked python scripts/e2e_fake_signed_server.py \
//     <brief.docx> <corpus_dir> 8765 &) ; sleep 7; cd frontend && node tests/e2e-conditions.mjs; pkill -f e2e_fake_signed_server'
import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';

const m = '11111111-1111-4111-8111-111111111111';
const b = '22222222-2222-4222-8222-222222222222';
const out = process.env.E2E_SCREENSHOT_DIR ?? '/tmp';
const br = await chromium.launch({
  executablePath: process.env.CHROME ?? '/usr/bin/google-chrome',
  args: ['--no-sandbox'],
});
const page = await br.newPage({ viewport: { width: 1400, height: 1000 } });
await page.addInitScript(() => {
  window.caseproofSession = {
    getBearer: async () => 'synthetic-browser-fixture',
  };
});
const requests = [];
page.on('console', (m) => {
  if (process.env.E2E_DEBUG) console.log('console:', m.text());
});
page.on('pageerror', (e) => {
  if (process.env.E2E_DEBUG) console.log('pageerror:', e.message);
});
page.on('response', (r) => {
  if (process.env.E2E_DEBUG)
    console.log('resp', r.status(), r.url().slice(-60));
});
page.on('request', (r) => requests.push(r.url()));
const open = async () => {
  await page.goto(
    `http://127.0.0.1:8765/workspace/matters/${m}/briefs/${b}/legal`,
  );
  await page.getByRole('button', { name: 'Connect session' }).click();
  await page
    .getByRole('heading', { name: 'Conditions defined by the lawyer' })
    .waitFor();
};
await open();
await page.getByText('Revision 0').waitFor();
const form = page.getByRole('form', { name: 'Add a condition' });
await form.getByLabel(/Identifier/).fill('paiement');
await form.getByLabel('Label').fill('Paiement reçu');
await form.getByLabel(/Words in the brief/).fill('Sur le fond');
await form.getByLabel(/Words to find/).fill('reçu, ontvangen');
await form.getByRole('button', { name: 'Save condition' }).click();
await page
  .getByText('Saved as revision 1 and read back from the store.')
  .waitFor({ timeout: 10000 });
await page.getByLabel('Condition anchors').waitFor({ timeout: 10000 });
await page.screenshot({
  path: `${out}/e2e-conditions-saved.png`,
  fullPage: true,
});
// Exact-page reopening in the app: the original PDF is fetched by digest and one physical page is rendered.
await page
  .getByText(/Pièce 3/)
  .first()
  .waitFor();
await page
  .getByRole('button', { name: /Open original PDF page 2 \(Pièce 2\)/ })
  .click();
const pageCanvas = page.getByLabel('Original PDF page 2 of Pièce 2');
await pageCanvas.waitFor({ timeout: 15000 });
await page.waitForFunction(
  () => {
    const c = document.querySelector('canvas[aria-label^="Original PDF page"]');
    if (!(c instanceof HTMLCanvasElement) || c.width === 0) return false;
    const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
    for (let i = 0; i < d.length; i += 4)
      if (d[i + 3] > 0 && d[i] < 128) return true;
    return false;
  },
  null,
  { timeout: 15000 },
);
await page.getByText(/verified before display/).waitFor();
await pageCanvas.screenshot({
  path: `${out}/e2e-conditions-original-page.png`,
});
await page.screenshot({
  path: `${out}/e2e-conditions-original-page-full.png`,
  fullPage: true,
});

const downloadPromise = page.waitForEvent('download');
await page
  .getByRole('button', { name: /Download offline review pack/ })
  .click();
const download = await downloadPromise;
await download.saveAs(`${out}/e2e-conditions-pack-configured.zip`);

await page.getByRole('button', { name: 'Remove' }).click();
await page
  .getByText('Saved as revision 2 and read back from the store.')
  .waitFor({ timeout: 10000 });
assert.equal(await page.getByRole('button', { name: 'Remove' }).count(), 0);
await page.getByText(/Anchors: 0;/).waitFor({ timeout: 10000 });
assert.equal(
  await page.getByLabel('Condition anchors').locator('li').count(),
  0,
);
await page.screenshot({
  path: `${out}/e2e-conditions-cleared.png`,
  fullPage: true,
});

const cleared = page.waitForEvent('download');
await page
  .getByRole('button', { name: /Download offline review pack/ })
  .click();
await (await cleared).saveAs(`${out}/e2e-conditions-pack-cleared.zip`);

await open();
await page.getByText(/Revision 2, spec/).waitFor({ timeout: 10000 });
assert.equal(await page.getByRole('button', { name: 'Remove' }).count(), 0);
const external = requests.filter((u) => !u.includes('127.0.0.1'));
assert.equal(external.length, 0);
console.log(
  'ok: saved rev 1, removed last condition (rev 2), reload shows rev 2, external requests 0',
);
await br.close();
