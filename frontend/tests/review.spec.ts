import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';

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
        locator_identity: {
          exact_text: finding.literal,
          prefix: '',
          suffix: '',
          occurrence_index: 0,
          content_hash: 'c'.repeat(64),
          paragraph_id: null,
          source_version_id: brief,
        },
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
      json: {
        ...report,
        brief_id: nextBrief,
        snapshot_hash: 'e'.repeat(64),
        findings: [
          {
            ...finding,
            identity_reason: 'SOURCE_CONFIRMED',
            visual_assessment: {
              ...finding.visual_assessment,
              reason: 'source_scan_ocr_unavailable',
            },
          },
        ],
      },
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
  const counts = correction.getByRole('region', {
    name: 'Comparison of check counts',
  });
  await expect(
    counts.getByRole('row', { name: 'OCR unreliable 1 1' }),
  ).toBeVisible();
  await expect(
    counts.getByText('They do not match references', { exact: false }),
  ).toBeVisible();
  await expect(
    correction.getByText('Visual assessment: source_scan_ocr_unavailable'),
  ).toBeVisible();
  await expect(
    correction.getByRole('button', { name: 'Open ref-one in previous report' }),
  ).toBeVisible();
  await expect(
    correction.getByRole('button', {
      name: 'Open ref-one in rechecked report',
    }),
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
        locator_identity: {
          exact_text: finding.literal,
          prefix: '',
          suffix: '',
          occurrence_index: 0,
          content_hash: 'c'.repeat(64),
          paragraph_id: null,
          source_version_id: brief,
        },
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

test('inspection and unsaved review never carry into another snapshot with the same reference', async ({
  page,
}) => {
  const nextSnapshot = 'f'.repeat(64);
  await page.route('**/dossier?*', (route) => {
    const requested = new URL(route.request().url()).searchParams.get(
      'snapshot_hash',
    );
    return route.fulfill({ json: { ...report, snapshot_hash: requested } });
  });
  await page.route('**/reviews?*', (route) => {
    const requested = new URL(route.request().url()).searchParams.get(
      'snapshot_hash',
    );
    return route.fulfill({
      json: { ...ledger, snapshot_hash: requested, decisions: [] },
    });
  });
  await page.route('**/viewer', (route) =>
    route.request().url().includes(nextSnapshot)
      ? route.fulfill({ status: 503, json: { error: 'unavailable' } })
      : route.fallback(),
  );
  await page.goto(scope);
  await page.getByRole('button', { name: 'Connect session' }).click();
  await expect(
    page.getByText('Source page rendered.', { exact: true }),
  ).toBeVisible();
  const review = page.getByRole('region', { name: 'Human review' });
  await review.getByRole('checkbox', { name: /Region 1/ }).check();
  const rationale = review.getByLabel(
    'Rationale (required, visible to authorized reviewers)',
  );
  await rationale.fill('Prior snapshot only');
  await expect(
    review.getByRole('button', { name: 'Save human decision' }),
  ).toBeEnabled();
  await page.evaluate((url) => {
    history.pushState({}, '', url);
    window.dispatchEvent(new PopStateEvent('popstate'));
  }, `/workspace/matters/${caseId}/briefs/${brief}?snapshot=${nextSnapshot}`);
  await expect(page.getByText(nextSnapshot, { exact: true })).toBeVisible();
  await expect(rationale).toHaveValue('');
  await expect(
    review.getByRole('button', { name: 'Save human decision' }),
  ).toBeDisabled();
  await expect(
    review.getByText('Open and inspect the preserved original', {
      exact: false,
    }),
  ).toBeVisible();
});

test('draft excerpt highlights the exact reference after an astral Unicode character', async ({
  page,
}) => {
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
        excerpt: '😀 Before Stuk 1 after',
        selection_start: 9,
        selection_end: 15,
        reason: null,
      },
    }),
  );
  await page.goto(scope);
  await page.getByRole('button', { name: 'Connect session' }).click();
  const context = page.getByRole('region', {
    name: 'Read-only draft reference',
  });
  await expect(context.locator('mark')).toHaveText('Stuk 1');
  await expect(context.getByText('😀 Before', { exact: false })).toBeVisible();
});

test('draft excerpt refuses a server selection that does not match the finding', async ({
  page,
}) => {
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
        excerpt: 'Before Stuk 2 after',
        selection_start: 7,
        selection_end: 13,
        reason: null,
      },
    }),
  );
  await page.goto(scope);
  await page.getByRole('button', { name: 'Connect session' }).click();
  const context = page.getByRole('region', {
    name: 'Read-only draft reference',
  });
  await expect(
    context.getByText('Draft context unavailable', { exact: false }),
  ).toBeVisible();
  await expect(context.locator('mark')).toHaveCount(0);
  await expect(
    page.getByRole('region', { name: 'Correction preview and recheck' }),
  ).toHaveCount(0);
});

test('coverage details distinguish regions and only navigate to an existing exact region', async ({
  page,
}) => {
  await page.route('**/dossier?*', (route) =>
    route.fulfill({
      json: {
        ...report,
        findings: [
          {
            ...finding,
            region: 'word/document.xml',
            version_id: 'source',
            source_sha256: 'a'.repeat(64),
            pdf_page: 1,
          },
        ],
        coverage: {
          ...report.coverage,
          source_pages_total: 2,
          source_pages: [
            {
              version_id: 'source',
              original_sha256: 'a'.repeat(64),
              pdf_page: 1,
              method: 'FAILED',
              reason: 'ocr_unavailable',
            },
            {
              version_id: 'source',
              original_sha256: 'b'.repeat(64),
              pdf_page: 1,
              method: 'NOT_PROCESSED',
              reason: 'outside_assessed_reference_scope',
            },
          ],
          docx_regions: {
            coverage_unknown: false,
            regions: [
              {
                part: 'word/document.xml',
                kind: 'MAIN_BODY',
                status: 'SCANNED',
                reason: 'TEXT_SCANNED_RECALL_UNMEASURED',
              },
              {
                part: 'word/document.xml#structured',
                kind: 'STRUCTURED_CONTENT',
                status: 'UNSUPPORTED_REGION',
                reason: 'UNSUPPORTED_STRUCTURED_CONTENT',
              },
            ],
          },
        },
      },
    }),
  );
  await page.goto(scope);
  await page.getByRole('button', { name: 'Connect session' }).click();
  const coverage = page.getByRole('region', {
    name: 'Verification and processing coverage',
  });
  await coverage.getByText('DOCX region coverage', { exact: true }).click();
  await expect(
    coverage.locator('p').filter({ hasText: 'UNSUPPORTED_STRUCTURED_CONTENT' }),
  ).toBeVisible();
  await expect(
    coverage.getByRole('button', {
      name: 'Open detected reference in this region',
    }),
  ).toHaveCount(1);
  await expect(
    coverage.getByText('No detected reference is available', { exact: false }),
  ).toBeVisible();
  await coverage.getByText('Source-page processing', { exact: true }).click();
  await expect(
    coverage.locator('p').filter({ hasText: 'ocr_unavailable' }),
  ).toBeVisible();
  await expect(
    coverage.getByRole('button', {
      name: 'Open reference on this source page',
    }),
  ).toHaveCount(1);
  await expect(
    coverage.getByText('No mapped reference is available', { exact: false }),
  ).toBeVisible();
});

test('J and K move focus and selection across reference pages', async ({
  page,
}) => {
  const findings = Array.from({ length: 51 }, (_, index) => ({
    ...finding,
    reference_id: `ref-${index + 1}`,
    literal: `Stuk ${index + 1}`,
  }));
  await page.route('**/dossier?*', (route) =>
    route.fulfill({ json: { ...report, findings } }),
  );
  await page.goto(scope);
  await page.getByRole('button', { name: 'Connect session' }).click();
  const queue = page.getByRole('region', { name: 'References' });
  const last = queue.getByRole('button', { name: /^Stuk 50/ });
  await last.focus();
  await page.keyboard.press('j');
  const next = queue.getByRole('button', { name: /^Stuk 51/ });
  await expect(next).toBeFocused();
  await expect(next).toHaveAttribute('aria-current', 'true');
  await page.keyboard.press('k');
  await expect(queue.getByRole('button', { name: /^Stuk 50/ })).toBeFocused();
  await page.keyboard.press('Space');
  await expect(page.getByRole('region', { name: 'Stuk 50' })).toBeFocused();
  await expect(queue.getByRole('button', { name: /^Stuk 50/ })).toHaveAttribute(
    'aria-current',
    'true',
  );
});

test('coverage navigation reveals a filtered reference on its queue page', async ({
  page,
}) => {
  const findings = Array.from({ length: 51 }, (_, index) => ({
    ...finding,
    reference_id: `ref-${index + 1}`,
    literal: `Stuk ${index + 1}`,
    region: index === 50 ? 'word/header1.xml' : 'word/document.xml',
  }));
  await page.route('**/dossier?*', (route) =>
    route.fulfill({
      json: {
        ...report,
        findings,
        coverage: {
          docx_regions: {
            coverage_unknown: false,
            regions: [
              {
                part: 'word/header1.xml',
                kind: 'HEADER',
                status: 'SCANNED',
                reason: 'SCANNED',
              },
            ],
          },
        },
      },
    }),
  );
  await page.goto(scope);
  await page.getByRole('button', { name: 'Connect session' }).click();
  await page
    .getByLabel('Search reference text (this session only)')
    .fill('Stuk 1');
  const coverage = page.getByRole('region', {
    name: 'Verification and processing coverage',
  });
  await coverage.getByText('DOCX region coverage', { exact: true }).click();
  await coverage
    .getByRole('button', { name: 'Open detected reference in this region' })
    .click();
  const queue = page.getByRole('region', { name: 'References' });
  await expect(queue.getByRole('button', { name: /^Stuk 51/ })).toHaveAttribute(
    'aria-current',
    'true',
  );
  await expect(
    page.getByLabel('Search reference text (this session only)'),
  ).toHaveValue('');
  await expect(queue.getByRole('button', { name: 'Show all' })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await page
    .getByLabel('Search reference text (this session only)')
    .fill('not present');
  await expect(
    queue.getByText('The selected reference is outside this queue', {
      exact: false,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Stuk 51', exact: true }),
  ).toBeVisible();
});

test('quotation and derived source text are separate and never rendered as markup', async ({
  page,
}) => {
  await page.route('**/dossier?*', (route) =>
    route.fulfill({
      json: {
        ...report,
        findings: [
          {
            ...finding,
            quoted_text: '<img src=x>',
            source_text_context: 'Scanned text: <img src=x>',
            source_text_context_partial: true,
            translation_review_required: true,
          },
        ],
      },
    }),
  );
  await page.goto(scope);
  await page.getByRole('button', { name: 'Connect session' }).click();
  const context = page.getByRole('region', {
    name: 'Quotation and derived source text',
  });
  await expect(context.getByText('<img src=x>', { exact: true })).toBeVisible();
  await expect(context.getByText('Scanned text: <img src=x>')).toBeVisible();
  await expect(
    context.getByText('Translation requires human review', { exact: false }),
  ).toBeVisible();
  await expect(context.locator('img')).toHaveCount(0);
  await context
    .getByRole('button', { name: 'Highlight exact text occurrences' })
    .click();
  await expect(
    context.getByText('1 exact occurrences', { exact: false }),
  ).toBeVisible();
  await expect(context.locator('mark')).toHaveText('<img src=x>');
  await expect(context.locator('img')).toHaveCount(0);
});

test('attention filter retains qualified and contradicted human support', async ({
  page,
}) => {
  const base = { ...finding, fidelity: 'exact_match' };
  await page.route('**/dossier?*', (route) =>
    route.fulfill({
      json: {
        ...report,
        findings: [
          {
            ...base,
            reference_id: 'supported',
            literal: 'Supported',
            support: 'supported',
          },
          {
            ...base,
            reference_id: 'qualified',
            literal: 'Qualified',
            support: 'qualified',
          },
          {
            ...base,
            reference_id: 'contradicted',
            literal: 'Contradicted',
            support: 'contradicted',
          },
        ],
      },
    }),
  );
  await page.goto(scope);
  await page.getByRole('button', { name: 'Connect session' }).click();
  const queue = page.getByRole('region', { name: 'References' });
  await expect(queue.getByRole('button', { name: /^Qualified/ })).toBeVisible();
  await expect(
    queue.getByRole('button', { name: /^Contradicted/ }),
  ).toBeVisible();
  await expect(queue.getByRole('button', { name: /^Supported/ })).toHaveCount(
    0,
  );
  await expect(
    queue.getByText('2 need attention out of 3', { exact: false }),
  ).toBeVisible();
});

test('next saved decision follows the active filtered queue', async ({
  page,
}) => {
  const findings = [
    finding,
    {
      ...finding,
      reference_id: 'ref-clear',
      literal: 'Stuk clear',
      fidelity: 'exact_match',
      support: 'supported',
    },
    { ...finding, reference_id: 'ref-next', literal: 'Stuk next' },
  ];
  await page.route('**/dossier/reviews', (route) => {
    const command = route.request().postDataJSON() as {
      reference_id: string;
      request_id: string;
      decision: 'CONFIRMED_QUALIFIED';
      rationale: string;
      reviewed_region_ids: string[];
    };
    ledger.decisions.push({
      reference_id: command.reference_id,
      request_id: command.request_id,
      decision: command.decision,
      rationale: command.rationale,
      reviewed_region_ids: command.reviewed_region_ids,
      reviewer_id: 'reviewer',
      timestamp: '2026-11-02T17:00:00Z',
    });
    return route.abort('failed');
  });
  await page.route('**/dossier?*', (route) =>
    route.fulfill({ json: { ...report, findings } }),
  );
  await page.goto(scope);
  await page.getByRole('button', { name: 'Connect session' }).click();
  const review = page.getByRole('region', { name: 'Human review' });
  await review.getByRole('checkbox', { name: /Region 1/ }).check();
  await review
    .getByLabel('Rationale (required, visible to authorized reviewers)')
    .fill('Viewed preserved pixels');
  await review.getByRole('button', { name: 'Save human decision' }).click();
  await review
    .getByRole('button', { name: 'Reconcile durable receipt' })
    .click();
  await expect(
    review.getByRole('button', { name: 'Save & Next finding' }),
  ).toBeVisible();
  await page
    .getByLabel('Search reference text (this session only)')
    .fill('Stuk 1');
  await expect(
    review.getByRole('button', { name: 'Save & Next finding' }),
  ).toHaveCount(0);
  await page.getByLabel('Search reference text (this session only)').clear();
  await page.getByRole('button', { name: 'Save & Next finding' }).click();
  await expect(
    page.getByRole('heading', { name: 'Stuk next', exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByRole('region', { name: 'References' })
      .getByRole('button', { name: /^Stuk next/ }),
  ).toHaveAttribute('aria-current', 'true');
});

test('unmatched coverage page opens the snapshot-bound original and clears on sign-out', async ({
  page,
}) => {
  await page.route('**/dossier?*', (route) =>
    route.fulfill({
      json: {
        ...report,
        sources: [
          {
            version_id: 'source',
            sha256: source.sha256,
            media_type: 'application/pdf',
            byte_length: source.bytes,
          },
        ],
        coverage: {
          source_pages_total: 1,
          source_pages: [
            {
              version_id: 'source',
              original_sha256: source.sha256,
              pdf_page: 2,
              method: 'FAILED',
              reason: 'ocr_unavailable',
            },
          ],
        },
      },
    }),
  );
  await page.route('**/dossier/sources/source/original?*', (route) =>
    route.fulfill({
      body: originalPdf,
      contentType: 'application/octet-stream',
      headers: {
        'X-CaseProof-Snapshot': snapshot,
        'X-CaseProof-Original-SHA256': source.sha256,
      },
    }),
  );
  await page.goto(scope);
  await page.getByRole('button', { name: 'Connect session' }).click();
  const coverage = page.getByRole('region', {
    name: 'Verification and processing coverage',
  });
  await coverage.getByText('Source-page processing', { exact: true }).click();
  await expect(
    coverage.getByText('No mapped reference is available', { exact: false }),
  ).toBeVisible();
  await coverage
    .getByRole('button', { name: 'Open preserved PDF page 2' })
    .click();
  const original = coverage.getByRole('region', {
    name: 'Coverage original source',
  });
  await expect(
    original.getByText('Original PDF page 2 rendered.', { exact: false }),
  ).toBeVisible();
  await expect(
    original.getByRole('img', { name: 'Preserved original PDF page 2' }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'End session' }).click();
  await expect(
    page.getByRole('region', { name: 'Coverage original source' }),
  ).toHaveCount(0);
});

test('unanchored DOCX region offers only a snapshot-bound preserved original', async ({
  page,
}) => {
  const original = Buffer.from('synthetic preserved draft');
  const sha = createHash('sha256').update(original).digest('hex');
  await page.route('**/dossier?*', (route) =>
    route.fulfill({
      json: {
        ...report,
        sources: [
          {
            role: 'draft',
            version_id: brief,
            sha256: sha,
            byte_length: original.length,
            media_type:
              'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          },
        ],
        coverage: {
          docx_regions: {
            coverage_unknown: false,
            regions: [
              {
                part: 'word/header1.xml',
                kind: 'HEADER',
                status: 'UNPROCESSED_REGION',
                reason: 'NOT_SCANNED',
              },
            ],
          },
        },
      },
    }),
  );
  await page.route(`**/dossier/sources/${brief}/original?*`, (route) =>
    route.fulfill({
      body: original,
      contentType: 'application/octet-stream',
      headers: {
        'X-CaseProof-Snapshot': snapshot,
        'X-CaseProof-Original-SHA256': sha,
      },
    }),
  );
  await page.goto(scope);
  await page.getByRole('button', { name: 'Connect session' }).click();
  const coverage = page.getByRole('region', {
    name: 'Verification and processing coverage',
  });
  await coverage.getByText('DOCX region coverage', { exact: true }).click();
  await expect(
    coverage.getByText('No detected reference is available', { exact: false }),
  ).toBeVisible();
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    coverage
      .getByRole('button', { name: 'Download preserved original DOCX' })
      .click(),
  ]);
  expect(download.suggestedFilename()).toBe(
    'caseproof-preserved-original.docx',
  );
  expect(await download.failure()).toBeNull();
});
