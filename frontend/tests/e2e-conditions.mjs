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

await open();
await page.getByText(/Revision 2, spec/).waitFor({ timeout: 10000 });
assert.equal(await page.getByRole('button', { name: 'Remove' }).count(), 0);
const external = requests.filter((u) => !u.includes('127.0.0.1'));
assert.equal(external.length, 0);
console.log(
  'ok: saved rev 1, removed last condition (rev 2), reload shows rev 2, external requests 0',
);
await br.close();
