import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
const matter = '11111111-1111-4111-8111-111111111111';
const hash = 'a'.repeat(64);
const report = {
  schema: 'caseproof-dossier-v1',
  case_id: matter,
  brief_id: matter,
  snapshot_hash: hash,
  findings: [],
  coverage: {},
};
test('password sign-in, server report navigation, cold reload and no persistence', async ({
  page,
}) => {
  let logins = 0;
  await page.route('**/v2/workspace/session', (route) => {
    logins++;
    expect(route.request().postDataJSON()).toEqual({
      email: 'synthetic@example.com',
      password: 'synthetic-password',
    });
    return route.fulfill({
      json: {
        access_token: 'synthetic-signed-token',
        expires_at: Math.floor(Date.now() / 1000) + 3600,
      },
    });
  });
  await page.route('**/v2/workspace/session/end', (route) =>
    route.fulfill({ status: 204 }),
  );
  await page.route('**/v2/workspace/matters', (route) =>
    route.fulfill({
      json: {
        schema: 'caseproof-workspace-matters-v1',
        matters: [{ case_id: matter, case_revision: 1, state: 'open' }],
      },
    }),
  );
  await page.route('**/v2/workspace/matters/*/reports', (route) =>
    route.fulfill({
      json: {
        schema: 'caseproof-workspace-reports-v1',
        case_id: matter,
        reports: [
          {
            brief_id: matter,
            snapshot_hash: hash,
            created_at: '2026-11-01T12:00:00Z',
          },
        ],
        next_cursor: null,
      },
    }),
  );
  await page.route('**/dossier?*', (route) => route.fulfill({ json: report }));
  await page.goto('/workspace/');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByLabel('Email address')).toBeFocused();
  await page.getByLabel('Email address').fill('synthetic@example.com');
  await page.getByLabel('Password', { exact: true }).fill('synthetic-password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await page.locator('.matter-list a').first().click();
  await expect(
    page.getByRole('heading', { name: 'Preserved reports' }),
  ).toBeVisible();
  await page.getByRole('link', { name: /Open preserved report/ }).click();
  await expect(
    page.getByRole('heading', { name: 'Review the evidence' }),
  ).toBeVisible();
  expect(logins).toBe(1);
  expect(
    await page.evaluate(() => ({
      local: localStorage.length,
      session: sessionStorage.length,
    })),
  ).toEqual({ local: 0, session: 0 });
  expect(await page.context().cookies()).toEqual([]);
  await page.reload();
  await expect(
    page.getByRole('button', { name: 'Sign in', exact: true }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
test('bad credentials retain email, clear password and allow explicit retry', async ({
  page,
}) => {
  let calls = 0;
  await page.route('**/v2/workspace/session', (route) => {
    calls++;
    return route.fulfill({ status: 401 });
  });
  await page.goto('/workspace/');
  await page.getByLabel('Email address').fill('synthetic@example.com');
  await page.getByLabel('Password', { exact: true }).fill('wrong');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Sign-in was rejected');
  await expect(page.getByLabel('Email address')).toHaveValue(
    'synthetic@example.com',
  );
  await expect(page.getByLabel('Password', { exact: true })).toHaveValue('');
  expect(calls).toBe(1);
});
