import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';

const caseId = '11111111-1111-4111-8111-111111111111';
const brief = '22222222-2222-4222-8222-222222222222';
const snapshot = 'a'.repeat(64);
const manifest = JSON.parse(
  await readFile(
    'tests/viewer-comparison/generated/fixtures/manifest.json',
    'utf8',
  ),
) as { fixtures: { name: string; sha256: string; bytes: number }[] };
const source = manifest.fixtures.find((r) => r.name === 'mixed')!;
const originalPdf = await readFile(
  'tests/viewer-comparison/generated/fixtures/mixed.pdf',
);
const finding = {
  reference_id: 'ref-one',
  literal: 'Stuk 1',
  identity: 'resolved',
  page_mapping: 'mapped',
  fidelity: 'ocr_unreliable',
  support: 'not_assessed',
  visual_assessment: { regions: [{ region_id: 'c'.repeat(64) }] },
};
const report = {
  schema: 'caseproof-dossier-v1',
  case_id: caseId,
  brief_id: brief,
  snapshot_hash: snapshot,
  coverage: { fully_checked: false, unprocessed_regions: 1 },
  findings: [finding],
};
const scope = `/workspace/matters/${caseId}/briefs/${brief}?snapshot=${snapshot}`;
const ledger = {
  schema: 'caseproof-review-ledger-v1',
  case_id: caseId,
  brief_id: brief,
  snapshot_hash: snapshot,
  decisions: [] as Array<{
    reference_id: string;
    request_id: string;
    reviewer_id: string;
    decision:
      'CONFIRMED_SUPPORTED' | 'CONFIRMED_QUALIFIED' | 'CONFIRMED_CONTRADICTED';
    rationale: string;
    reviewed_region_ids: string[];
    timestamp: string;
  }>,
};
test.beforeEach(async ({ page }) => {
  ledger.decisions = [];
  await page.addInitScript(() => {
    window.caseproofSession = {
      getBearer: async () => 'synthetic-review-owner',
    };
  });
  await page.route('**/dossier?*', (route) => route.fulfill({ json: report }));
  await page.route('**/draft-context', (route) =>
    route.fulfill({
      json: {
        schema: 'caseproof-draft-excerpt-v1',
        case_id: caseId,
        brief_id: brief,
        snapshot_hash: snapshot,
        reference_id: 'ref-one',
        original_sha256: 'b'.repeat(64),
        available: true,
        region: 'word/document.xml',
        excerpt: 'Before Stuk 1 after',
        selection_start: 7,
        selection_end: 13,
        reason: null,
      },
    }),
  );
  await page.route('**/reviews?*', (route) => route.fulfill({ json: ledger }));
  await page.route('**/viewer', (route) =>
    route.fulfill({
      json: {
        schema: 'caseproof-viewer-v1',
        case_id: caseId,
        brief_id: brief,
        snapshot_hash: snapshot,
        reference_id: 'ref-one',
        version_id: 'source',
        original_sha256: source.sha256,
        byte_length: source.bytes,
        page_mapping: 'mapped',
        pdf_page: 1,
        legacy_region_count: 0,
        geometry_policy: 'derived_pdf_text_only_legacy_raster_not_projected',
      },
    }),
  );
  await page.route('**/viewer/regions', (route) =>
    route.fulfill({
      json: {
        schema: 'caseproof-raster-overlays-v1',
        snapshot_hash: snapshot,
        original_sha256: source.sha256,
        source_version_id: 'source',
        regions: [],
        unassessed_region_count: 1,
        interpretation: 'navigation_only_never_a_verdict',
      },
    }),
  );
  await page.route('**/viewer/original', (route) =>
    route.fulfill({
      body: originalPdf,
      contentType: 'application/pdf',
      headers: {
        'X-CaseProof-Snapshot': snapshot,
        'X-CaseProof-Original-SHA256': source.sha256,
      },
    }),
  );
});
test('review requires rendered original and explicit region inspection; lost acknowledgement reconciles exact durable record', async ({
  page,
}) => {
  let posts = 0;
  await page.route('**/dossier/reviews', (route) => {
    posts += 1;
    const data = route.request().postDataJSON() as {
      reference_id: string;
      request_id: string;
      rationale: string;
      decision: 'CONFIRMED_QUALIFIED';
      reviewed_region_ids: string[];
    };
    ledger.decisions.push({
      reference_id: data.reference_id,
      request_id: data.request_id,
      decision: data.decision,
      rationale: data.rationale,
      reviewed_region_ids: data.reviewed_region_ids,
      reviewer_id: 'reviewer',
      timestamp: '2026-11-02T17:00:00Z',
    });
    return route.abort('failed');
  });
  await page.goto(scope);
  await page.getByRole('button', { name: 'Connect session' }).click();
  const review = page.getByRole('region', { name: 'Human review' });
  const save = review.getByRole('button', { name: 'Save human decision' });
  await expect(save).toBeDisabled();
  await expect(
    page.getByText('Source page rendered.', { exact: true }),
  ).toBeVisible();
  await expect(page.getByText('Before', { exact: false })).toBeVisible();
  await expect(save).toBeDisabled();
  await review.getByRole('checkbox', { name: /Region 1/ }).check();
  await review
    .getByLabel('Rationale (required, visible to authorized reviewers)')
    .fill('Viewed preserved pixels');
  await expect(save).toBeEnabled();
  await save.click();
  await expect(
    review.getByText('The write outcome is unknown.', { exact: false }),
  ).toBeVisible();
  await review
    .getByRole('button', { name: 'Reconcile durable receipt' })
    .click();
  await expect(
    review.getByText('The exact decision is persisted', { exact: false }),
  ).toBeVisible();
  expect(posts).toBe(1);
  await page.reload();
  await page.getByRole('button', { name: 'Connect session' }).click();
  await expect(
    page.getByRole('list', { name: 'Saved review history' }),
  ).toContainText('Viewed preserved pixels');
});
test('historical read-only snapshot never renders reviewer save controls', async ({
  page,
}) => {
  await page.route('**/dossier?*', (route) =>
    route.fulfill({ status: 409, body: '{}' }),
  );
  await page.route(`**/history/${snapshot}`, (route) =>
    route.fulfill({
      json: {
        mode: 'historical_read_only',
        currentness: 'not_asserted',
        source_availability: 'not_assessed',
        report,
      },
    }),
  );
  await page.route(
    `**/history/${snapshot}/references/ref-one/viewer`,
    (route) =>
      route.fulfill({
        json: {
          schema: 'caseproof-viewer-v1',
          case_id: caseId,
          brief_id: brief,
          snapshot_hash: snapshot,
          reference_id: 'ref-one',
          version_id: 'source',
          original_sha256: source.sha256,
          byte_length: source.bytes,
          page_mapping: 'mapped',
          pdf_page: 1,
          legacy_region_count: 0,
          geometry_policy: 'derived_pdf_text_only_legacy_raster_not_projected',
        },
      }),
  );
  await page.goto(scope);
  await page.getByRole('button', { name: 'Connect session' }).click();
  await expect(
    page.getByText('Historical report · read-only', { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Save human decision' }),
  ).toHaveCount(0);
});

test('correction preview, lost commit acknowledgement, durable reconciliation and independent report comparison', async ({
  page,
}) => {
  const nextBrief = '33333333-3333-4333-8333-333333333333';
  let commits = 0;
  let operation = '';
  await page.route('**/correction-operations', (route) =>
    route.fulfill({
      json: { operations: [], current_draft_version_id: brief },
    }),
  );
  await page.route('**/correction-anchor', (route) =>
    route.fulfill({
      json: {
        snapshot_hash: snapshot,
        brief_version_id: brief,
        reference_id: finding.reference_id,
        original_sha256: 'b'.repeat(64),
        paragraph_index: 0,
        before: finding.literal,
      },
    }),
  );
  await page.route('**/corrections/review-receipt?*', (route) =>
    route.fulfill({
      json: {
        schema: 'caseproof-correction-review-receipt-v1',
        brief_version_id: brief,
        snapshot_hash: snapshot,
        reference_id: finding.reference_id,
        reviewer_id: '44444444-4444-4444-8444-444444444444',
        review_request_id: '55555555-5555-4555-8555-555555555555',
      },
    }),
  );
  await page.route('**/corrections/preview', (route) =>
    route.fulfill({
      json: {
        ...route.request().postDataJSON(),
        schema: 'caseproof-docx-correction-preview-v1',
        committed: false,
        requires_recheck: true,
        brief_version_id: brief,
        derivative_sha256: 'd'.repeat(64),
        derivative_byte_length: 2000,
      },
    }),
  );
  await page.route('**/corrections/commit', (route) => {
    commits++;
    operation = route.request().postDataJSON().request_id;
    return route.abort('failed');
  });
  await page.route('**/corrections/status', (route) => {
    expect(route.request().postDataJSON().request_id).toBe(operation);
    return route.fulfill({
      json: {
        state: 'active',
        committed: true,
        requires_recheck: true,
        version_id: nextBrief,
      },
    });
  });
  await page.route('**/dossier/recheck', (route) => {
    expect(route.request().url()).toContain(`/briefs/${nextBrief}/`);
    return route.fulfill({
      json: { ...report, brief_id: nextBrief, snapshot_hash: 'e'.repeat(64) },
    });
  });
  await page.route('**/dossier/history/*', (route) =>
    route.fulfill({ json: { mode: 'historical_read_only', report } }),
  );
  await page.goto(scope);
  await page.getByRole('button', { name: 'Connect session' }).click();
  const correction = page.getByRole('region', {
    name: 'Correction preview and recheck',
    exact: true,
  });
  await correction.getByLabel('Replacement text').fill('Stuk 2');
  await correction
    .getByRole('button', { name: 'Validate exact preview' })
    .click();
  await expect(
    correction.getByText('Proposed change (not committed)', { exact: true }),
  ).toBeVisible();
  await correction
    .getByRole('button', { name: 'Explicitly commit and activate new draft' })
    .click();
  await correction
    .getByRole('button', { name: 'Reconcile identical operation' })
    .click();
  await correction
    .getByRole('button', { name: 'Recheck activated draft', exact: true })
    .click();
  await expect(
    correction.getByRole('heading', { name: 'Previous report', exact: true }),
  ).toBeVisible();
  await expect(
    correction.getByRole('heading', { name: 'Rechecked report', exact: true }),
  ).toBeVisible();
  expect(commits).toBe(1);
});

test('correction commit is blocked without a durable actor-scoped review receipt', async ({
  page,
}) => {
  let commits = 0;
  await page.route('**/correction-operations', (route) =>
    route.fulfill({
      json: { operations: [], current_draft_version_id: brief },
    }),
  );
  await page.route('**/correction-anchor', (route) =>
    route.fulfill({
      json: {
        snapshot_hash: snapshot,
        brief_version_id: brief,
        reference_id: finding.reference_id,
        original_sha256: 'b'.repeat(64),
        paragraph_index: 0,
        before: finding.literal,
      },
    }),
  );
  await page.route('**/corrections/review-receipt?*', (route) =>
    route.fulfill({
      status: 409,
      json: { detail: 'persisted actor review required' },
    }),
  );
  await page.route('**/corrections/preview', (route) =>
    route.fulfill({
      json: {
        ...route.request().postDataJSON(),
        schema: 'caseproof-docx-correction-preview-v1',
        committed: false,
        requires_recheck: true,
        brief_version_id: brief,
        derivative_sha256: 'd'.repeat(64),
        derivative_byte_length: 2000,
      },
    }),
  );
  await page.route('**/corrections/commit', (route) => {
    commits++;
    return route.abort('failed');
  });
  await page.goto(scope);
  await page.getByRole('button', { name: 'Connect session' }).click();
  const correction = page.getByRole('region', {
    name: 'Correction preview and recheck',
    exact: true,
  });
  await correction.getByLabel('Replacement text').fill('Stuk 2');
  await correction
    .getByRole('button', { name: 'Validate exact preview' })
    .click();
  await expect(
    correction.getByText('Proposed change (not committed)', { exact: true }),
  ).toBeVisible();
  await expect(
    correction.getByRole('button', {
      name: 'Explicitly commit and activate new draft',
    }),
  ).toBeDisabled();
  expect(commits).toBe(0);
});
