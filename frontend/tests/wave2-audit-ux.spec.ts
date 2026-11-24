import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const matter = '11111111-1111-4111-8111-111111111111';
const brief = '22222222-2222-4222-8222-222222222222';
const snapshot = 'a'.repeat(64);

const report = {
  schema: 'caseproof-dossier-v1',
  case_id: matter,
  brief_id: brief,
  snapshot_hash: snapshot,
  coverage: {
    references_detected: 2,
    references_not_assessed: 1,
    fully_checked: false,
  },
  findings: [
    {
      reference_id: 'ref-status-cue',
      literal: 'Pièce 3 — Avenant signé le 14 mars 2026',
      identity: 'resolved',
      page_mapping: 'mapped',
      fidelity: 'exact_match',
      support: 'not_assessed',
      quoted_text: "L'avenant a été signé le 14 mars 2026",
      source_text_context:
        "Projet d'avenant envoyé pour signature le 14 mars 2026 — non paraphé.",
      source_text_context_partial: false,
    },
    {
      reference_id: 'ref-unconfirmed',
      literal: 'Pièce 1 — Contrat de bail commercial',
      identity: 'not_assessed',
      reason: 'INVENTORY_UNCONFIRMED',
      page_mapping: 'unmapped',
      fidelity: 'not_assessed',
      support: 'not_assessed',
    },
  ],
};

test('FE-01/02/03: lexical appraisal card, inline unconfirmed inventory drawer, omission shortcut, and axe', async ({
  page,
}) => {
  await page.addInitScript(() => {
    window.caseproofSession = { getBearer: async () => 'synthetic-wave2-ux' };
  });
  await page.route('**/v2/**', (route) => route.fulfill({ json: report }));
  await page.goto(
    `/workspace/matters/${matter}/briefs/${brief}?snapshot=${snapshot}&finding=ref-status-cue`,
  );
  await page.getByRole('button', { name: 'Connect session' }).click();

  // FE-01: targeted lexical appraisal card inside ReportScreen
  await expect(page.getByText('Lexical appraisal flag')).toBeVisible();
  await expect(
    page.getByText('Flagged for lawyer appraisal — not semantically verified.'),
  ).toBeVisible();

  // FE-02: inline progressive unconfirmed inventory drawer
  await page.getByRole('button', { name: 'Inspect mappings inline' }).click();
  await expect(
    page.getByRole('heading', {
      name: 'Unconfirmed exhibit mappings (progressive preview)',
    }),
  ).toBeVisible();
  await expect(
    page.getByText('Pièce 1 — Contrat de bail commercial').first(),
  ).toBeVisible();

  // FE-03: Conditions & legal link + omission quick-report drawer
  await expect(
    page.getByRole('link', { name: 'Conditions & legal articles' }),
  ).toHaveAttribute(
    'href',
    `/workspace/matters/${matter}/briefs/${brief}/legal`,
  );
  await page.getByRole('button', { name: 'Report missed passage' }).click();
  await expect(
    page.getByRole('heading', {
      name: 'Log an omission note (quick shortcut)',
    }),
  ).toBeVisible();

  const axe = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
    .analyze();
  expect(axe.violations).toEqual([]);
});

test('FE-07: rapid double-click on Sign in sends only one session POST', async ({
  page,
}) => {
  let logins = 0;
  await page.route('**/v2/workspace/session', async (route) => {
    logins += 1;
    await new Promise((resolve) => setTimeout(resolve, 250));
    await route.fulfill({
      json: {
        access_token: 'synthetic-signed-token',
        expires_at: Math.floor(Date.now() / 1000) + 3600,
      },
    });
  });
  await page.route('**/v2/workspace/matters', (route) =>
    route.fulfill({
      json: { schema: 'caseproof-workspace-matters-v1', matters: [] },
    }),
  );
  await page.goto('/workspace/');
  await page.getByLabel('Email address').fill('synthetic@example.com');
  await page.getByLabel('Password', { exact: true }).fill('synthetic-password');
  const submit = page.getByRole('button', { name: 'Sign in', exact: true });
  await submit.dblclick();
  await expect(page.getByText('Permitted matters').first()).toBeVisible();
  expect(logins).toBe(1);
});
