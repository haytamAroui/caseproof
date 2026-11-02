import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
const caseId = '11111111-1111-4111-8111-111111111111',
  org = '22222222-2222-4222-8222-222222222222';
const ids = [3, 4, 5, 6].map(
  (n) => `${n.toString().repeat(8)}-1111-4111-8111-111111111111`,
);
const docx =
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
const sources = ['draft.docx', 'inventory.txt', 'text.pdf', 'scan.pdf'].map(
  (filename, i) => ({
    filename,
    role: i === 0 ? 'draft' : i === 1 ? 'inventory' : 'exhibit',
    document_id: ids[i],
    version_id: ids[i],
    sha256: 'a'.repeat(64),
    byte_length: 12,
    media_type: i === 0 ? docx : i === 1 ? 'text/plain' : 'application/pdf',
    page_count: i >= 2 ? 1 : null,
    processing: i === 3 ? 'partial' : 'preserved',
  }),
);
function intake(complete = true) {
  return {
    schema: 'caseproof-workspace-intake-v1',
    case_id: caseId,
    brief_id: complete ? ids[0] : null,
    bundle_signature: complete ? 'b'.repeat(64) : null,
    sources: complete ? sources : [],
    entries: complete
      ? [{ label: 'stuk', number: '1', source_version_id: null, pages: [] }]
      : [],
    confirmation_id: null,
    inventory_complete: false,
    readback_complete: complete,
  };
}
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.caseproofSession = { getBearer: async () => 'synthetic-intake' };
  });
  await page.route('**/v2/workspace/matters', (route) =>
    route.fulfill({
      json: { schema: 'caseproof-workspace-matters-v1', matters: [] },
    }),
  );
  await page.route('**/intake/organizations', (route) =>
    route.fulfill({
      json: {
        schema: 'caseproof-workspace-create-orgs-v1',
        organizations: [{ org_id: org, name: 'Synthetic organization' }],
      },
    }),
  );
});
async function connect(page: import('@playwright/test').Page, path: string) {
  await page.goto(path);
  await page.getByRole('button', { name: 'Connect session' }).click();
}
test('create through returned organization, unknown upload recovery, inventory and readback', async ({
  page,
}) => {
  let uploaded = false,
    writes = 0,
    saved: Record<string, unknown> | null = null;
  await page.route('**/intake/matters', async (route) => {
    const data = route.request().postDataJSON() as { request_id: string };
    await route.fulfill({
      json: {
        schema: 'caseproof-workspace-created-v1',
        case_id: caseId,
        request_id: data.request_id,
      },
    });
  });
  await page.route(`**/intake/matters/${caseId}`, (route) =>
    route.fulfill({
      json: saved
        ? {
            ...intake(),
            entries: (
              saved.entries as {
                label: string;
                number: string;
                source_version_id: string | null;
                pages: {
                  space: string;
                  label: string;
                  pdf_page: number;
                  rationale: string;
                }[];
              }[]
            ).map((e) => ({
              label: e.label,
              number: e.number,
              source_version_id: e.source_version_id,
              pages: e.pages.map((p) => ({
                space: p.space,
                label: p.label,
                pdf_page: p.pdf_page,
                rationale: p.rationale,
              })),
            })),
            confirmation_id: saved.request_id,
            inventory_complete: true,
          }
        : intake(uploaded),
    }),
  );
  await page.route(`**/intake/matters/${caseId}/reservations`, (route) =>
    route.fulfill({ json: intake(false) }),
  );
  await page.route(`**/intake/matters/${caseId}/sources`, async (route) => {
    writes++;
    if (writes === 1) {
      await route.abort('failed');
      return;
    }
    uploaded = true;
    await route.fulfill({ json: intake() });
  });
  await page.route('**/dossier/confirmation', async (route) => {
    saved = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      json: { request_id: saved.request_id, reviewer_id: org },
    });
  });
  await connect(page, '/workspace/matters/new');
  await expect(
    page.getByRole('heading', { name: 'Create a private matter' }),
  ).toBeVisible();
  await page.getByLabel('Organization', { exact: true }).selectOption(org);
  await page.getByLabel('Matter title').fill('Synthetic matter');
  await page
    .getByRole('button', { name: 'Create matter', exact: true })
    .click();
  await expect(
    page.getByRole('heading', { name: 'Preserve the source bundle' }),
  ).toBeVisible();
  for (const [i, label] of [
    'DOCX draft',
    'UTF-8 inventory',
    'First PDF exhibit',
    'Second PDF exhibit or scan',
  ].entries())
    await page.getByLabel(label, { exact: true }).setInputFiles({
      name: sources[i]!.filename,
      mimeType: sources[i]!.media_type,
      buffer: Buffer.from('synthetic original'),
    });
  await page
    .getByRole('button', { name: 'Preserve or reconcile originals' })
    .click();
  await expect(
    page.getByText('No completed intake receipt was received.', {
      exact: false,
    }),
  ).toBeVisible();
  expect(writes).toBe(1);
  await page
    .getByRole('button', { name: 'Preserve or reconcile originals' })
    .click();
  await expect(
    page.getByText('All originals passed fresh authorized hash readback.', {
      exact: false,
    }),
  ).toBeVisible();
  await page
    .getByRole('link', { name: 'Review inventory and page mappings' })
    .click();
  await page.getByLabel('Preserved exhibit').selectOption(ids[2]!);
  await page
    .getByRole('button', { name: 'Add alternative source binding' })
    .first()
    .click();
  await expect(page.getByLabel('Preserved exhibit')).toHaveCount(2);
  await page
    .getByRole('button', {
      name: 'Remove alternative binding for stuk 1',
      exact: true,
    })
    .last()
    .click();
  await expect(page.getByLabel('Preserved exhibit')).toHaveCount(1);
  await page.getByLabel('Page label', { exact: true }).fill('12');
  await page.getByLabel('Physical PDF page', { exact: true }).fill('1');
  await page
    .getByLabel('Mapping rationale')
    .fill('Inspected synthetic page label');
  await page.getByRole('button', { name: 'Add inspected mapping' }).click();
  await page.getByRole('link', { name: 'Back to sources' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('button', { name: 'Stay here' }).click();
  await expect(page.getByRole('dialog')).not.toBeVisible();
  await page.getByRole('checkbox').check();
  await page
    .getByRole('button', { name: 'Save inventory confirmation' })
    .click();
  await expect(
    page.getByText('Inventory confirmation saved and freshly read back.', {
      exact: false,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Run explicit check' }),
  ).toBeEnabled();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: 'test-results/f3-inventory-desktop.png',
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole('button', { name: 'End session', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Confirm inventory' }),
  ).toHaveCount(0);
});
test('denied intake clears private forms and stale confirmation never shows saved', async ({
  page,
}) => {
  await page.route(`**/intake/matters/${caseId}`, (route) =>
    route.fulfill({ json: intake() }),
  );
  await page.route('**/dossier/confirmation', (route) =>
    route.fulfill({ status: 409, json: { error: 'stale' } }),
  );
  await connect(page, `/workspace/matters/${caseId}/inventory`);
  await page
    .getByRole('button', { name: 'Save inventory confirmation' })
    .click();
  await expect(
    page.getByText(
      'Confirmation was rejected, stale or has an unknown outcome.',
      { exact: false },
    ),
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Run explicit check' }),
  ).toBeDisabled();
  await page.route(`**/intake/matters/${caseId}`, (route) =>
    route.fulfill({ status: 404, json: { error: 'masked' } }),
  );
  await page
    .getByRole('button', { name: 'Refresh inventory', exact: true })
    .click();
  await expect(
    page.getByRole('button', { name: 'Sign in', exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel('Preserved exhibit')).toHaveCount(0);
});

test('definite validation rejection permits correction with a new operation', async ({
  page,
}) => {
  let saved: {
    request_id: string;
    entries: unknown[];
    inventory_complete: boolean;
  } | null = null;
  let attempts = 0;
  await page.route(`**/intake/matters/${caseId}`, (route) =>
    route.fulfill({
      json: saved
        ? {
            ...intake(),
            confirmation_id: saved.request_id,
            entries: saved.entries,
            inventory_complete: saved.inventory_complete,
          }
        : intake(),
    }),
  );
  await page.route('**/dossier/confirmation', async (route) => {
    attempts++;
    if (attempts === 1)
      await route.fulfill({ status: 422, json: { error: 'invalid_request' } });
    else {
      saved = route.request().postDataJSON() as typeof saved;
      await route.fulfill({ json: { request_id: saved?.request_id } });
    }
  });
  await connect(page, `/workspace/matters/${caseId}/inventory`);
  await page
    .getByRole('button', { name: 'Save inventory confirmation' })
    .click();
  await expect(
    page.getByText('The confirmation failed validation.', { exact: false }),
  ).toBeVisible();
  await page.getByLabel('Preserved exhibit').selectOption(ids[2]!);
  await page
    .getByRole('button', { name: 'Add alternative source binding' })
    .first()
    .click();
  await expect(page.getByLabel('Preserved exhibit')).toHaveCount(2);
  await page
    .getByRole('button', {
      name: 'Remove alternative binding for stuk 1',
      exact: true,
    })
    .last()
    .click();
  await expect(page.getByLabel('Preserved exhibit')).toHaveCount(1);
  await page
    .getByRole('button', { name: 'Save inventory confirmation' })
    .click();
  await expect(
    page.getByText('Inventory confirmation saved and freshly read back.', {
      exact: false,
    }),
  ).toBeVisible();
  expect(attempts).toBe(2);
});

test('registered originals show independent unknown and signed verified readbacks before recovery', async ({ page }) => {
  const partial = {
    ...intake(false),
    bundle_signature: 'b'.repeat(64),
    sources: sources.map((source, index) => ({
      ...source,
      readback: index === 0 ? 'verified' : index === 2 ? 'integrity_mismatch' : 'unknown',
      processing: 'unavailable',
    })),
  };
  await page.route(`**/intake/matters/${caseId}`, (route) =>
    route.fulfill({ json: partial }),
  );
  await connect(page, `/workspace/matters/${caseId}/sources`);
  await expect(page.getByRole('region', { name: 'Registered original status' })).toBeVisible();
  await expect(page.getByText('readback verified', { exact: false })).toHaveCount(1);
  await expect(page.getByText('readback unknown', { exact: false })).toHaveCount(2);
  await expect(page.getByText('readback integrity_mismatch', { exact: false })).toHaveCount(1);
  await expect(page.getByRole('link', { name: 'Review inventory and page mappings' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Preserve or reconcile originals' })).toBeVisible();
});

test('Roman printed page and detector miss remain review-needed after durable confirmation', async ({ page }) => {
  let saved: Record<string, unknown> | null = null;
  await page.route(`**/intake/matters/${caseId}`, (route) =>
    route.fulfill({
      json: saved ? { ...intake(), sources: sources.map((s) => ({
        ...s, page_count: s.role === 'exhibit' ? 6 : null
      })), entries: saved.entries, exceptions: saved.exceptions,
        inventory_complete: false, confirmation_id: saved.request_id }
        : { ...intake(), sources: sources.map((s) => ({
          ...s, page_count: s.role === 'exhibit' ? 6 : null
        })) },
    }),
  );
  await page.route('**/dossier/confirmation', async (route) => {
    saved = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({ json: { request_id: saved.request_id } });
  });
  await connect(page, `/workspace/matters/${caseId}/inventory`);
  await page.getByLabel('Preserved exhibit').selectOption(ids[2]!);
  await page.getByLabel('Page label', { exact: true }).fill('IC');
  await page.getByLabel('Physical PDF page').fill('6');
  await page.getByLabel('Mapping rationale').fill('Inspected real printed label');
  await page.getByRole('button', { name: 'Add inspected mapping' }).click();
  await expect(page.getByText('Use a unique literal numeric or canonical Roman label', { exact: false })).toBeVisible();
  await page.getByLabel('Page label', { exact: true }).fill('iv');
  await page.getByRole('button', { name: 'Add inspected mapping' }).click();
  await expect(page.getByText('printed iv → PDF 6:', { exact: false })).toBeVisible();
  await page.getByLabel('Exact inventory excerpt').fill('Annex 9');
  await page.getByLabel('Reason for human review').fill('Detector missed a literal source reference');
  await page.getByRole('button', { name: 'Add review-needed exception' }).click();
  await expect(page.getByRole('checkbox')).toBeDisabled();
  await page.getByRole('button', { name: 'Save inventory confirmation' }).click();
  await expect(page.getByText('Inventory confirmation saved and freshly read back.', { exact: false })).toBeVisible();
  expect(saved?.inventory_complete).toBe(false);
  expect((saved?.exceptions as { review_state: string }[])[0]?.review_state).toBe('review_needed');
  expect((saved?.entries as { pages: { label: string; pdf_page: number }[] }[])[0]?.pages[0]).toMatchObject({
    label: 'iv', pdf_page: 6,
  });
});
