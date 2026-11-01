import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
const row = {
  case_id: '11111111-1111-4111-8111-111111111111',
  case_revision: 4,
  state: 'open <img src=x>',
};
const catalog = (matters: unknown[]) => ({
  schema: 'caseproof-workspace-matters-v1',
  matters,
});
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.caseproofSession = {
      getBearer: async () => 'synthetic-catalog-fixture',
    };
  });
});
test('server-returned matter selection, paging, keyboard and narrow layout', async ({
  page,
}) => {
  const rows = Array.from({ length: 25 }, (_, i) => ({
    ...row,
    case_id: `${String(i + 1).padStart(8, '0')}-1111-4111-8111-111111111111`,
  }));
  await page.route('**/v2/workspace/matters', (route) =>
    route.fulfill({ json: catalog(rows) }),
  );
  await page.goto('/workspace/');
  await page.getByRole('button', { name: 'Connect session' }).click();
  await expect(page.locator('.matter-list li')).toHaveCount(20);
  await expect(page.locator('img')).toHaveCount(0);
  await page.getByRole('button', { name: 'Next matters' }).click();
  await expect(page.locator('.matter-list li')).toHaveCount(5);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: 'test-results/matters-narrow.png',
    fullPage: true,
  });
  await page.locator('.matter-list a').first().focus();
  await page.keyboard.press('Enter');
  await expect(page.getByLabel('Matter ID')).toHaveValue(rows[20]!.case_id);
  await expect(page.getByLabel('Matter ID')).toHaveAttribute('readonly', '');
  await page.getByRole('link', { name: 'Back to permitted matters' }).click();
  await page.getByRole('button', { name: 'End session' }).click();
  await expect(page.locator('.matter-list li')).toHaveCount(0);
});
test('empty, failed refresh, recovery and revocation clear', async ({
  page,
}) => {
  let status = 200;
  let rows: unknown[] = [];
  await page.route('**/v2/workspace/matters', (route) =>
    route.fulfill({ status, json: catalog(rows) }),
  );
  await page.goto('/workspace/');
  await page.getByRole('button', { name: 'Connect session' }).click();
  await expect(
    page.getByText('No permitted matters were returned.', { exact: false }),
  ).toBeVisible();
  rows = [row];
  await page
    .getByRole('button', { name: 'Refresh matters', exact: true })
    .click();
  await expect(page.locator('.matter-list li')).toHaveCount(1);
  status = 503;
  await page
    .getByRole('button', { name: 'Refresh matters', exact: true })
    .click();
  await expect(page.getByRole('alert')).toContainText('catalog is unavailable');
  await expect(page.locator('.matter-list li')).toHaveCount(0);
  status = 200;
  await page
    .getByRole('button', { name: 'Refresh matters', exact: true })
    .click();
  await expect(page.locator('.matter-list li')).toHaveCount(1);
  status = 403;
  await page
    .getByRole('button', { name: 'Refresh matters', exact: true })
    .click();
  await expect(
    page.getByRole('heading', { name: 'Connect your workspace session' }),
  ).toBeVisible();
  await expect(page.locator('.matter-list li')).toHaveCount(0);
});
test('malformed catalog fails closed without retry', async ({ page }) => {
  let calls = 0;
  await page.route('**/v2/workspace/matters', (route) => {
    calls++;
    return route.fulfill({ json: catalog([row, row]) });
  });
  await page.goto('/workspace/');
  await page.getByRole('button', { name: 'Connect session' }).click();
  await expect(page.getByRole('alert')).toContainText('catalog is unavailable');
  expect(calls).toBe(1);
});
