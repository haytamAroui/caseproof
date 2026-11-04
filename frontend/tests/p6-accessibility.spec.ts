import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const matter = '11111111-1111-4111-8111-111111111111';
const brief = '22222222-2222-4222-8222-222222222222';
const snapshot = 'a'.repeat(64);
const examples = [
  'Stuk 1 — De verzoekende partij betwist de verwijzing naar de fysieke PDF-bladzijde en vraagt een menselijke controle van het origineel.',
  'Pièce 2 — La citation mentionne plusieurs pages imprimées et doit rester non évaluée en présence de divergences visuelles.',
  'Exhibit A — This English reference is unsupported; a human must review the source and no verified identity may be inferred.',
];
const report = {
  schema: 'caseproof-dossier-v1', case_id: matter, brief_id: brief,
  snapshot_hash: snapshot,
  coverage: { references_detected: 3, references_not_assessed: 2, fully_checked: false },
  findings: examples.map((literal, index) => ({
    reference_id: 'ref-' + index, literal,
    identity: index === 2 ? 'not_assessed' : 'resolved',
    page_mapping: 'unmapped', fidelity: 'not_assessed', support: 'not_assessed',
  })),
};
test('P6 NL/FR/EN, keyboard, reflow, reduced motion, forced colors and axe', async ({ page }) => {
  const external: string[] = [];
  page.on('request', (request) => {
    if (new URL(request.url()).origin !== 'http://127.0.0.1:4173')
      external.push(request.url());
  });
  await page.addInitScript(() => {
    window.caseproofSession = { getBearer: async () => 'synthetic-a11y-only' };
  });
  await page.route('**/v2/**', (route) => route.fulfill({ json: report }));
  await page.goto('/workspace/matters/' + matter + '/briefs/' + brief + '?snapshot=' + snapshot);
  await page.getByRole('button', { name: 'Connect session' }).click();
  await expect(page.getByRole('heading', { name: 'Review the evidence' })).toBeVisible();
  for (const literal of examples)
    await expect(page.getByRole('button', { name: literal })).toBeVisible();

  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze();
  expect(results.violations.map((v) => ({ id: v.id, nodes: v.nodes.length }))).toEqual([]);

  await page.setViewportSize({ width: 320, height: 700 });
  await page.emulateMedia({ reducedMotion: 'reduce', forcedColors: 'active' });
  await expect(page.getByRole('heading', { name: 'Review the evidence' })).toBeVisible();
  const english = page.getByRole('button', { name: examples[2]! });
  await english.focus();
  await expect(english).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(english).toHaveAttribute('aria-current', 'true');
  await expect(page.getByRole('heading', { name: examples[2]! })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.emulateMedia({ reducedMotion: 'reduce', forcedColors: 'none' });
  await page.evaluate(() => { document.documentElement.style.zoom = '2'; });
  await expect(page.getByRole('heading', { name: 'Review the evidence' })).toBeVisible();
  expect(external).toEqual([]);
});
