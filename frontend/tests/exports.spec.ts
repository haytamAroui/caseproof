import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const caseId = '11111111-1111-4111-8111-111111111111';
const briefId = '22222222-2222-4222-8222-222222222222';
const snapshot = 'a'.repeat(64);
const digest =
  '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824';
const workspace =
  '/workspace/matters/' +
  caseId +
  '/exports?brief=' +
  briefId +
  '&snapshot=' +
  snapshot;
const preview = {
  schema: 'caseproof-release-preview-v1',
  case_id: caseId,
  brief_id: briefId,
  snapshot_hash: snapshot,
  finding_count: 2,
  review_count: 1,
  release_ready: true,
  can_release: true,
  currentness: 'current',
  release_policy: {
    version: 1,
    scope: 'partial',
    can_release: true,
    total_findings: 2,
    required_findings: 2,
    reviewed_findings: 1,
    unreviewed_findings: 1,
    review_complete: false,
    reviewed_reference_ids: ['ref-one'],
    unreviewed_reference_ids: ['ref-two'],
    references_truncated: false,
    reason_codes: ['UNREVIEWED_FINDINGS'],
  },
  formats: ['json', 'markdown', 'docx'],
  coverage: {
    unprocessed_regions: 1,
    text_coverage_complete: false,
    reference_recall_measured: false,
  },
  limitations: [
    'Partial OCR remains unassessed.',
    'Human decision is not legal certification.',
  ],
};
function record(releaseId: string, frozen = snapshot) {
  return {
    state: 'released',
    release_id: releaseId,
    brief_id: briefId,
    snapshot_hash: frozen,
    manifest: {
      schema: 'caseproof-reviewed-release-v1',
      case_id: caseId,
      brief_id: briefId,
      snapshot_hash: frozen,
      release_id: releaseId,
      bundle_signature: 'b'.repeat(64),
      review_count: 1,
      finding_count: 2,
      release_policy: preview.release_policy,
      coverage: preview.coverage,
      sources: [
        { role: 'draft', version_id: briefId, sha256: 'c'.repeat(64) },
        {
          role: 'exhibit',
          version_id: '33333333-3333-4333-8333-333333333333',
          sha256: 'd'.repeat(64),
        },
      ],
      source_links: [
        {
          role: 'draft',
          version_id: briefId,
          sha256: 'c'.repeat(64),
          original_path:
            '/v2/matters/' +
            caseId +
            '/briefs/' +
            briefId +
            '/dossier/history/' +
            frozen +
            '/sources/' +
            briefId +
            '/original',
        },
        {
          role: 'exhibit',
          version_id: '33333333-3333-4333-8333-333333333333',
          sha256: 'd'.repeat(64),
          original_path:
            '/v2/matters/' +
            caseId +
            '/briefs/' +
            briefId +
            '/dossier/history/' +
            frozen +
            '/sources/33333333-3333-4333-8333-333333333333/original',
        },
      ],
      reference_links: [
        {
          reference_id: 'ref-one',
          source_version_id: '33333333-3333-4333-8333-333333333333',
          original_sha256: 'd'.repeat(64),
          pdf_page: 6,
          page_space: 'physical_pdf_page',
          viewer_path:
            '/matters/' +
            caseId +
            '/briefs/' +
            briefId +
            '?snapshot=' +
            frozen +
            '&finding=ref-one',
        },
      ],
      limitations: preview.limitations,
      manifest_sha256: 'e'.repeat(64),
      server_receipt: 'f'.repeat(64),
      artifacts: {
        json: {
          sha256: digest,
          byte_length: 5,
          media_type: 'application/json',
        },
        markdown: {
          sha256: digest,
          byte_length: 5,
          media_type: 'text/markdown; charset=utf-8',
        },
        docx: {
          sha256: digest,
          byte_length: 5,
          media_type:
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        },
      },
    },
  };
}
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.caseproofSession = { getBearer: async () => 'synthetic-browser-f6' };
  });
});
async function open(page: import('@playwright/test').Page) {
  await page.goto(workspace);
  await page.getByRole('button', { name: 'Connect session' }).click();
  await expect(
    page.getByRole('heading', { name: 'Reviewed exports and history' }),
  ).toBeVisible();
}
test('F6 preview, release, hash-verified download and cold reopen of history', async ({
  page,
}) => {
  const saved: ReturnType<typeof record>[] = [];
  let releasePosts = 0;
  await page.route('**/dossier/releases/preview?*', (route) =>
    route.fulfill({ json: preview }),
  );
  await page.route('**/dossier/releases', (route) => {
    if (route.request().method() === 'GET')
      return route.fulfill({ json: { releases: saved } });
    releasePosts++;
    const command = route.request().postDataJSON() as {
      release_id: string;
      snapshot_hash: string;
      acknowledge_partial: boolean;
    };
    expect(command.snapshot_hash).toBe(snapshot);
    expect(command.acknowledge_partial).toBe(true);
    const next = record(command.release_id);
    saved.push(next);
    return route.fulfill({ json: next });
  });
  await page.route('**/dossier/releases/*/artifacts/json', (route) =>
    route.fulfill({
      body: 'hello',
      contentType: 'application/json',
      headers: {
        'X-CaseProof-Snapshot': snapshot,
        'X-CaseProof-Export-SHA256': digest,
        'X-CaseProof-Export-Size': '5',
      },
    }),
  );
  await open(page);
  await expect(page.getByText('Partial OCR remains unassessed.')).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Create frozen reviewed release' }),
  ).toBeDisabled();
  await page
    .getByRole('checkbox', {
      name: /I understand this is a partial reviewed release/,
    })
    .check();
  await page
    .getByRole('button', { name: 'Create frozen reviewed release' })
    .click();
  await expect(
    page.getByRole('heading', { name: 'Selected frozen release' }),
  ).toBeVisible();
  await expect(
    page.getByRole('link', { name: 'Inspect preserved reference ref-one' }),
  ).toHaveAttribute(
    'href',
    '/workspace/matters/' +
      caseId +
      '/briefs/' +
      briefId +
      '?snapshot=' +
      snapshot +
      '&finding=ref-one',
  );
  await page.getByLabel('Output format').selectOption('json');
  const started = page.waitForEvent('download');
  await page
    .getByRole('button', { name: 'Verify SHA-256 and download JSON' })
    .click();
  const downloaded = await started;
  expect(downloaded.suggestedFilename()).toMatch(
    /^caseproof-reviewed-[0-9a-f-]{36}\.json$/,
  );
  await expect(
    page.getByText(/Verified bytes offered to your browser/),
  ).toBeVisible();
  expect(releasePosts).toBe(1);
  expect(
    await page.evaluate(() => localStorage.length + sessionStorage.length),
  ).toBe(0);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.reload();
  await page.getByRole('button', { name: 'Connect session' }).click();
  await expect(
    page.getByRole('button', { name: /Select release/ }),
  ).toBeVisible();
  await page.getByRole('button', { name: /Select release/ }).click();
  await expect(
    page.getByRole('heading', { name: 'Selected frozen release' }),
  ).toBeVisible();
  expect(releasePosts).toBe(1);
});

test('F6 lost POST acknowledgment reconciles without repeating the write', async ({
  page,
}) => {
  let committed: ReturnType<typeof record> | null = null;
  let posts = 0;
  await page.route('**/dossier/releases/preview?*', (route) =>
    route.fulfill({ json: preview }),
  );
  await page.route('**/dossier/releases', (route) => {
    if (route.request().method() === 'GET')
      return route.fulfill({
        json: { releases: committed ? [committed] : [] },
      });
    posts++;
    const command = route.request().postDataJSON() as { release_id: string };
    committed = record(command.release_id);
    return route.abort('failed');
  });
  await page.route(/\/dossier\/releases\/[0-9a-f-]{36}$/, (route) => {
    if (!committed) return route.fulfill({ json: { state: 'absent' } });
    return route.fulfill({ json: committed });
  });
  await open(page);
  await page
    .getByRole('checkbox', {
      name: /I understand this is a partial reviewed release/,
    })
    .check();
  await page
    .getByRole('button', { name: 'Create frozen reviewed release' })
    .click();
  await expect(page.getByText(/Release outcome unknown/)).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Create frozen reviewed release' }),
  ).toBeDisabled();
  await page
    .getByRole('button', { name: 'Reconcile previous release' })
    .click();
  await expect(
    page.getByText(/previously submitted release was found/),
  ).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Selected frozen release' }),
  ).toBeVisible();
  expect(posts).toBe(1);
});

test('F6 stale preview denies new release; a valid reader does not lose session for an export denial', async ({
  page,
}) => {
  let previewCalls = 0;
  await page.route('**/dossier/releases/preview?*', (route) => {
    previewCalls++;
    return route.fulfill({ status: 403, body: '{}' });
  });
  await page.route('**/dossier/releases', (route) =>
    route.fulfill({ status: 403, body: '{}' }),
  );
  await open(page);
  await expect(page.getByText(/Release preview unavailable/)).toBeVisible();
  await expect(page.getByText(/Release history is unavailable/)).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Create frozen reviewed release' }),
  ).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'End session' })).toBeVisible();
  expect(previewCalls).toBe(1);
});

test('F6 corrupted artifact is never offered as a download', async ({
  page,
}) => {
  const release = record('44444444-4444-4444-8444-444444444444');
  await page.route('**/dossier/releases/preview?*', (route) =>
    route.fulfill({ json: preview }),
  );
  await page.route('**/dossier/releases', (route) =>
    route.fulfill({ json: { releases: [release] } }),
  );
  await page.route('**/dossier/releases/*/artifacts/json', (route) =>
    route.fulfill({
      body: 'wrong',
      contentType: 'application/json',
      headers: {
        'X-CaseProof-Snapshot': snapshot,
        'X-CaseProof-Export-SHA256': digest,
        'X-CaseProof-Export-Size': '5',
      },
    }),
  );
  await open(page);
  await page.getByRole('button', { name: /Select release/ }).click();
  await page.getByLabel('Output format').selectOption('json');
  await page
    .getByRole('button', { name: 'Verify SHA-256 and download JSON' })
    .click();
  await expect(
    page.getByText(/Download failed integrity, access or transfer validation/),
  ).toBeVisible();
  await expect(page.getByText(/Verified bytes offered/)).toHaveCount(0);
});
